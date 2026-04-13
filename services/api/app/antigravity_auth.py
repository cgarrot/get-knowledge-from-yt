"""Browser OAuth for Antigravity: store refresh token for cloudcode-pa.

Aligned with opencode-antigravity-auth: PKCE (code_challenge / code_verifier), same scopes,
optional redirect http://localhost:51121/oauth-callback via loopback server.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urlencode, parse_qs, urlparse

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from yt_knowledge_ingest.antigravity import (
    _oauth_config,
    clear_antigravity_session_cleared,
    mark_antigravity_session_cleared,
)

from .config import ANTIGRAVITY_OAUTH_REDIRECT_URI, DATA_DIR, FRONTEND_BASE
from .db import get_conn, kv_delete, kv_get, kv_set
from .worker import reset_antigravity_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/antigravity", tags=["auth"])

STATE_TTL_SEC = 600
_OAUTH_STATE_PREFIX = "antigravity_oauth_state:"

# Same scope list as opencode-antigravity-auth/src/constants.ts (no "openid").
_ANTIGRAVITY_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/cclog",
        "https://www.googleapis.com/auth/experimentsandconfigs",
    ]
)

# Registered redirect for the public Antigravity OAuth client (opencode-antigravity-auth).
OPENCODE_ANTIGRAVITY_REDIRECT_URI = "http://localhost:51121/oauth-callback"


def _pkce_verifier() -> str:
    # 43–128 chars URL-safe (RFC 7636)
    return secrets.token_urlsafe(32)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _oauth_state_key(state: str) -> str:
    return f"{_OAUTH_STATE_PREFIX}{state}"


def _purge_stale_oauth_states() -> None:
    now = time.time()
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT key, value FROM app_kv WHERE key LIKE ?",
            (f"{_OAUTH_STATE_PREFIX}%",),
        )
        stale: list[str] = []
        for row in cur.fetchall():
            key = str(row[0])
            raw = str(row[1])
            created: float | None = None
            try:
                data = json.loads(raw)
                created = float(data["created"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                try:
                    created = float(raw)
                except ValueError:
                    stale.append(key)
                    continue
            if created is None or now - created > STATE_TTL_SEC:
                stale.append(key)
        for key in stale:
            conn.execute("DELETE FROM app_kv WHERE key = ?", (key,))
        conn.commit()


def _store_oauth_state(state: str, verifier: str) -> None:
    payload = json.dumps({"created": time.time(), "verifier": verifier})
    kv_set(_oauth_state_key(state), payload)


def _consume_oauth_state(state: str) -> Optional[str]:
    """Return PKCE verifier if state was valid (and remove it)."""
    key = _oauth_state_key(state)
    raw = kv_get(key)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        created = float(data["created"])
        verifier = data["verifier"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        kv_delete(key)
        return None
    if time.time() - created > STATE_TTL_SEC or not isinstance(verifier, str):
        kv_delete(key)
        return None
    kv_delete(key)
    return verifier


def _should_start_loopback_server() -> bool:
    # Only the OpenCode-registered URI uses a separate port (never the API port).
    return (
        ANTIGRAVITY_OAUTH_REDIRECT_URI.rstrip("/")
        == OPENCODE_ANTIGRAVITY_REDIRECT_URI.rstrip("/")
    )


def start_antigravity_oauth_loopback_server() -> None:
    """Listen on localhost:51121 for /oauth-callback when using OpenCode-compatible redirect_uri."""
    logger.info("Antigravity OAuth redirect_uri=%s", ANTIGRAVITY_OAUTH_REDIRECT_URI)
    if not _should_start_loopback_server():
        logger.info(
            "Antigravity OAuth loopback off (custom redirect_uri). "
            "Google Cloud must allow exactly: %s — or unset GKFY_ANTIGRAVITY_OAUTH_REDIRECT_URI "
            "for default %s",
            ANTIGRAVITY_OAUTH_REDIRECT_URI,
            OPENCODE_ANTIGRAVITY_REDIRECT_URI,
        )
        return

    parsed = urlparse(ANTIGRAVITY_OAUTH_REDIRECT_URI)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        logger.warning(
            "GKFY_ANTIGRAVITY_OAUTH_LOOPBACK only supports localhost; got %s",
            ANTIGRAVITY_OAUTH_REDIRECT_URI,
        )
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    bind = (os.environ.get("GKFY_ANTIGRAVITY_OAUTH_LOOPBACK_BIND") or "127.0.0.1").strip()

    def handle_request(
        code: Optional[str], state: Optional[str], error: Optional[str]
    ) -> str:
        return _oauth_callback_location(code, state, error)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            req_path = urlparse(self.path).path
            if req_path != path:
                self.send_error(404, "Not Found")
                return
            qs = parse_qs(urlparse(self.path).query)
            code = qs.get("code", [None])[0]
            state = qs.get("state", [None])[0]
            err = qs.get("error", [None])[0]
            loc = handle_request(code, state, err)
            self.send_response(302)
            self.send_header("Location", loc)
            self.end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            logger.info("Antigravity OAuth loopback: %s", fmt % args)

    def serve() -> None:
        try:
            httpd = HTTPServer((bind, port), _Handler)
        except OSError as exc:
            logger.error(
                "Antigravity OAuth loopback could not bind %s:%s (%s). "
                "Stop OpenCode or free the port, or use FastAPI redirect instead.",
                bind,
                port,
                exc,
            )
            return
        logger.info(
            "Antigravity OAuth loopback server on http://%s:%s%s (OpenCode-compatible)",
            bind,
            port,
            path,
        )
        httpd.serve_forever()

    threading.Thread(target=serve, name="ag-oauth-loopback", daemon=True).start()


@router.get("/status")
def antigravity_status() -> Dict[str, Union[bool, str, None]]:
    from yt_knowledge_ingest.antigravity import antigravity_connection_status

    connected, email = antigravity_connection_status()
    return {"connected": connected, "email": email if connected else None}


@router.post("/logout")
def antigravity_logout() -> Dict[str, Union[bool, str, None]]:
    """Remove the refresh token saved by the web OAuth flow (data/antigravity_refresh_token.txt)."""
    from yt_knowledge_ingest.antigravity import antigravity_connection_status

    path = DATA_DIR / "antigravity_refresh_token.txt"
    if path.is_file():
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("Could not remove Antigravity token file: %s", exc)
            raise HTTPException(
                status_code=500, detail="Impossible de supprimer le fichier token"
            ) from exc
    os.environ.pop("ANTIGRAVITY_REFRESH_TOKEN", None)
    mark_antigravity_session_cleared()
    reset_antigravity_client()
    connected, email = antigravity_connection_status()
    logger.info("Antigravity web token removed; connected=%s", connected)
    return {
        "ok": True,
        "connected": connected,
        "email": email if connected else None,
    }


@router.get("/opencode-accounts")
def antigravity_opencode_accounts() -> Dict[str, List[Dict[str, Any]]]:
    """List OpenCode Antigravity account slots (no tokens) for picking an import target."""
    from yt_knowledge_ingest.antigravity import list_opencode_antigravity_accounts_preview

    return {"accounts": list_opencode_antigravity_accounts_preview()}


@router.post("/import-opencode")
def antigravity_import_opencode(
    account_index: Optional[int] = Query(
        None,
        description="OpenCode accounts[] index; omit to use active gemini slot (activeIndexByFamily.gemini).",
    ),
) -> Dict[str, Union[bool, str, None]]:
    """Copy refresh token from ~/.config/opencode/antigravity-accounts.json into app data (same host as API)."""
    from yt_knowledge_ingest.antigravity import (
        antigravity_connection_status,
        clear_antigravity_session_cleared,
        read_opencode_antigravity_refresh_token,
        read_opencode_antigravity_refresh_token_at_index,
    )

    if account_index is not None:
        token = read_opencode_antigravity_refresh_token_at_index(account_index)
        if not token:
            raise HTTPException(
                status_code=400,
                detail=f"Compte OpenCode index {account_index} introuvable, désactivé ou sans refresh token.",
            )
    else:
        token = read_opencode_antigravity_refresh_token()
        if not token:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Aucun jeton OpenCode : connecte-toi une fois avec Antigravity dans OpenCode, "
                    "ou vérifie ~/.config/opencode/antigravity-accounts.json sur la machine qui héberge l’API."
                ),
            )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "antigravity_refresh_token.txt"
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    os.environ.pop("ANTIGRAVITY_REFRESH_TOKEN", None)
    clear_antigravity_session_cleared()
    reset_antigravity_client()
    connected, email = antigravity_connection_status()
    logger.info("Antigravity refresh token imported from OpenCode accounts file")
    return {
        "ok": True,
        "connected": connected,
        "email": email if connected else None,
    }


@router.get("/login")
def antigravity_login() -> RedirectResponse:
    _purge_stale_oauth_states()
    try:
        client_id, _, _ = _oauth_config()
    except RuntimeError as exc:
        logger.warning("Antigravity OAuth login: %s", exc)
        return RedirectResponse(
            f"{FRONTEND_BASE}/?antigravity_error=oauth_not_configured",
            status_code=302,
        )
    state = secrets.token_urlsafe(32)
    verifier = _pkce_verifier()
    challenge = _pkce_challenge(verifier)
    _store_oauth_state(state, verifier)
    redirect_uri = ANTIGRAVITY_OAUTH_REDIRECT_URI
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _ANTIGRAVITY_SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    logger.info(
        "Antigravity OAuth: redirect to Google (302), redirect_uri=%s",
        redirect_uri,
    )
    return RedirectResponse(url, status_code=302)


def _oauth_callback_location(
    code: Optional[str],
    state: Optional[str],
    error: Optional[str],
) -> str:
    if error:
        logger.warning("Antigravity OAuth error from provider: %s", error)
        return f"{FRONTEND_BASE}/?antigravity_error={quote(error, safe='')}"
    if not code or not state:
        return f"{FRONTEND_BASE}/?antigravity_error=missing_code_or_state"

    verifier = _consume_oauth_state(state)
    if not verifier:
        logger.warning("Antigravity OAuth callback: invalid or expired state")
        return f"{FRONTEND_BASE}/?antigravity_error=invalid_state"

    try:
        client_id, client_secret, _ = _oauth_config()
    except RuntimeError as exc:
        logger.warning("Antigravity OAuth callback: %s", exc)
        return f"{FRONTEND_BASE}/?antigravity_error=oauth_not_configured"
    redirect_uri = ANTIGRAVITY_OAUTH_REDIRECT_URI
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    if not resp.ok:
        logger.error(
            "Antigravity token exchange failed: %s %s",
            resp.status_code,
            resp.text[:500],
        )
        return f"{FRONTEND_BASE}/?antigravity_error=token_exchange"

    data = resp.json()
    refresh = data.get("refresh_token")
    if not refresh:
        logger.error("Antigravity token response had no refresh_token: %s", data.keys())
        return f"{FRONTEND_BASE}/?antigravity_error=no_refresh_token"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "antigravity_refresh_token.txt"
    path.write_text(str(refresh).strip() + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    # Env wins over file in _get_refresh_token(); drop stale env so the new login applies.
    os.environ.pop("ANTIGRAVITY_REFRESH_TOKEN", None)
    reset_antigravity_client()
    clear_antigravity_session_cleared()
    logger.info("Antigravity refresh token saved via web OAuth")
    return f"{FRONTEND_BASE}/?antigravity_connected=1"


@router.get("/callback")
def antigravity_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> RedirectResponse:
    loc = _oauth_callback_location(code, state, error)
    return RedirectResponse(loc, status_code=302)
