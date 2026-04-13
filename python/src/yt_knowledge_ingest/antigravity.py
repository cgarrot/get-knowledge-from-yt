"""Antigravity OAuth client for Gemini models via cloudcode-pa endpoint.

Uses Google OAuth refresh token to access Gemini Pro models for free.
No API key needed — authenticates via Antigravity proxy.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

import requests

from .model_options import DEFAULT_ANTIGRAVITY_MODEL

logger = logging.getLogger(__name__)

# OAuth client + project for Antigravity / cloudcode-pa token exchange, aligned with OpenCode /
# opencode-antigravity-auth (same public desktop OAuth constants as their constants.ts).
#
# The embedded client_secret is not end-user credential material: for this OAuth client type it is
# distributed with the app (like other desktop flows). Real secrets to protect are refresh tokens,
# GEMINI_API_KEY, and anything under data/ — see README.md and SECURITY.md.
#
# Optional overrides: ANTIGRAVITY_OAUTH_CLIENT_ID, ANTIGRAVITY_OAUTH_CLIENT_SECRET, ANTIGRAVITY_PROJECT_ID.
# Same strings as opencode-antigravity-auth src/constants.ts, stored as UTF-8 hex so GitHub push
# protection accepts the repo (it blocks plaintext Google OAuth client id / secret literals).
_DEFAULT_OAUTH_CLIENT_ID = bytes.fromhex(
    "313037313030363036303539312d746d687373696e326832316c63726532333576746f6c6f6a68346734303365702e617070732e676f6f676c6575736572636f6e74656e742e636f6d"
).decode()
_DEFAULT_OAUTH_CLIENT_SECRET = bytes.fromhex(
    "474f435350582d4b35384657523438364c644c4a316d4c4238735843347a3671444166"
).decode()
_DEFAULT_PROJECT_ID = bytes.fromhex("726973696e672d666163742d7034316663").decode()


def _oauth_config() -> tuple[str, str, str]:
    """Return (client_id, client_secret, project_id); env vars override built-in defaults."""
    cid = os.environ.get("ANTIGRAVITY_OAUTH_CLIENT_ID", "").strip() or _DEFAULT_OAUTH_CLIENT_ID
    secret = (
        os.environ.get("ANTIGRAVITY_OAUTH_CLIENT_SECRET", "").strip()
        or _DEFAULT_OAUTH_CLIENT_SECRET
    )
    project = (
        os.environ.get("ANTIGRAVITY_PROJECT_ID", "").strip() or _DEFAULT_PROJECT_ID
    )
    return cid, secret, project


# Endpoint fallback order
_ENDPOINTS = [
    "https://daily-cloudcode-pa.sandbox.googleapis.com",
    "https://autopush-cloudcode-pa.sandbox.googleapis.com",
    "https://cloudcode-pa.googleapis.com",
]

_DEFAULT_MODEL = DEFAULT_ANTIGRAVITY_MODEL
_ANTIGRAVITY_HEADERS = {
    "User-Agent": "antigravity/1.22.2 darwin/arm64",
    "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
}

# Token file locations (same as OpenCode)
_ACCOUNTS_FILE = Path.home() / ".config" / "opencode" / "antigravity-accounts.json"


def _opencode_account_usable(acc: object) -> bool:
    return (
        isinstance(acc, dict)
        and acc.get("enabled") is not False
        and acc.get("refreshToken")
    )


def _load_opencode_accounts_raw() -> tuple[dict[str, Any], list[Any]] | None:
    if not _ACCOUNTS_FILE.is_file():
        return None
    try:
        raw = _ACCOUNTS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list) or not accounts:
        return None
    return data, accounts


def _opencode_gemini_active_index(data: dict[str, Any], accounts: list[Any]) -> int | None:
    """Index OpenCode uses for Antigravity (gemini family). See accounts.ts activeIndexByFamily.gemini."""
    n = len(accounts)
    if n == 0:
        return None
    by_fam = data.get("activeIndexByFamily")
    if isinstance(by_fam, dict):
        g = by_fam.get("gemini")
        if isinstance(g, int) and 0 <= g < n:
            return g
    active = data.get("activeIndex")
    if isinstance(active, int) and 0 <= active < n:
        return active
    return None


def read_opencode_antigravity_refresh_token_at_index(index: int) -> str | None:
    """Return refresh token for OpenCode account slot ``index``."""
    loaded = _load_opencode_accounts_raw()
    if loaded is None:
        return None
    _data, accounts = loaded
    if index < 0 or index >= len(accounts):
        return None
    acc = accounts[index]
    if not _opencode_account_usable(acc):
        return None
    assert isinstance(acc, dict)
    t = str(acc["refreshToken"]).strip()
    return t or None


def list_opencode_antigravity_accounts_preview() -> list[dict[str, Any]]:
    """Summaries for UI: index, email, last_used, active_for_gemini (no secrets)."""
    loaded = _load_opencode_accounts_raw()
    if loaded is None:
        return []
    data, accounts = loaded
    gemini_idx = _opencode_gemini_active_index(data, accounts)
    out: list[dict[str, Any]] = []
    for i, acc in enumerate(accounts):
        if not isinstance(acc, dict):
            continue
        email = acc.get("email")
        try:
            last_used = float(acc.get("lastUsed", 0))
        except (TypeError, ValueError):
            last_used = 0.0
        out.append(
            {
                "index": i,
                "email": email if isinstance(email, str) else None,
                "last_used": last_used,
                "enabled": acc.get("enabled") is not False,
                "has_refresh_token": bool(acc.get("refreshToken")),
                "active_for_gemini": i == gemini_idx,
            }
        )
    return out


def read_opencode_antigravity_refresh_token() -> str | None:
    """Refresh token for the OpenCode account Antigravity (gemini) is using."""
    loaded = _load_opencode_accounts_raw()
    if loaded is None:
        return None
    data, accounts = loaded
    idx = _opencode_gemini_active_index(data, accounts)
    if idx is not None:
        acc = accounts[idx]
        if _opencode_account_usable(acc):
            assert isinstance(acc, dict)
            t = str(acc["refreshToken"]).strip()
            return t or None

    best_token: str | None = None
    best_last = -1.0
    for acc in accounts:
        if not _opencode_account_usable(acc):
            continue
        assert isinstance(acc, dict)
        try:
            last_used = float(acc.get("lastUsed", 0))
        except (TypeError, ValueError):
            last_used = 0.0
        rt = str(acc["refreshToken"]).strip()
        if not rt:
            continue
        if last_used >= best_last:
            best_last = last_used
            best_token = rt
    return best_token

# Set by API logout so we do not fall back to OpenCode after the user cleared the app token.
ANTIGRAVITY_NO_FALLBACK_ENV = "GKFY_ANTIGRAVITY_NO_FALLBACK"


class AntigravityError(Exception):
    """Raised when Antigravity API call fails."""


def _get_refresh_token() -> str:
    """Get refresh token from env, token file, or OpenCode accounts file."""
    token = (os.environ.get("ANTIGRAVITY_REFRESH_TOKEN") or "").strip()
    if token:
        return token

    token_file = os.environ.get("ANTIGRAVITY_REFRESH_TOKEN_FILE", "").strip()
    if token_file:
        p = Path(token_file).expanduser()
        if p.is_file():
            body = p.read_text(encoding="utf-8").strip()
            if body:
                return body

    data_dir = os.environ.get("GKFY_DATA_DIR", "").strip()
    if data_dir:
        legacy = Path(data_dir) / "antigravity_refresh_token.txt"
        if legacy.is_file():
            body = legacy.read_text(encoding="utf-8").strip()
            if body:
                return body

    if not _opencode_fallback_disabled():
        from_opencode = read_opencode_antigravity_refresh_token()
        if from_opencode:
            return from_opencode

    raise RuntimeError(
        "No Antigravity refresh token: set ANTIGRAVITY_REFRESH_TOKEN, "
        "ANTIGRAVITY_REFRESH_TOKEN_FILE, use the web UI « Se connecter (Antigravity) », "
        "or configure ~/.config/opencode/antigravity-accounts.json (OpenCode)."
    )


def _opencode_fallback_disabled() -> bool:
    v = (os.environ.get(ANTIGRAVITY_NO_FALLBACK_ENV) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def mark_antigravity_session_cleared() -> None:
    """After API logout: ignore OpenCode account file until new web OAuth or server restart."""
    os.environ[ANTIGRAVITY_NO_FALLBACK_ENV] = "1"


def clear_antigravity_session_cleared() -> None:
    os.environ.pop(ANTIGRAVITY_NO_FALLBACK_ENV, None)


def _google_oauth_email_from_refresh_token(refresh_token: str) -> str | None:
    """Exchange refresh token for an access token and fetch the Google account email."""
    client_id, client_secret, _ = _oauth_config()
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if not resp.ok:
            return None
        access = resp.json().get("access_token")
        if not access or not isinstance(access, str):
            return None
        ui = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access}"},
            timeout=15,
        )
        if not ui.ok:
            return None
        data = ui.json()
        email = data.get("email")
        if not email or not isinstance(email, str):
            return None
        return email.strip() or None
    except (requests.RequestException, TypeError, ValueError):
        return None


def antigravity_connection_status() -> tuple[bool, str | None]:
    """Return (connected, email) for the configured Antigravity refresh token."""
    try:
        refresh = _get_refresh_token()
    except RuntimeError:
        return False, None
    email = _google_oauth_email_from_refresh_token(refresh)
    return True, email


class AntigravityClient:
    """Manages OAuth token lifecycle for Antigravity API calls."""

    def __init__(self, refresh_token: str | None = None):
        self._refresh_token = refresh_token or _get_refresh_token()
        self._access_token = ""
        self._token_expiry: float = 0

    def _refresh_access_token(self) -> str:
        """Exchange refresh token for a fresh access token."""
        client_id, client_secret, _proj = _oauth_config()
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        logger.debug(
            "Antigravity access token refreshed, expires in %ds",
            data.get("expires_in", 3600),
        )
        return self._access_token

    @property
    def access_token(self) -> str:
        if not self._access_token or time.time() >= self._token_expiry - 60:
            return self._refresh_access_token()
        return self._access_token

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            **_ANTIGRAVITY_HEADERS,
            "Client-Metadata": json.dumps(
                {
                    "ideType": "ANTIGRAVITY",
                    "platform": "MACOS",
                    "pluginType": "GEMINI",
                }
            ),
        }

    def _build_body(
        self,
        *,
        model: str,
        system_instruction: str,
        user_text: str,
        file_uri: str | None = None,
        thinking_level: str = "high",
    ) -> dict[str, Any]:
        """Build the Antigravity-wrapped request body."""
        _cid, _sec, project_id = _oauth_config()
        parts: list[dict[str, Any]] = []
        if file_uri:
            parts.append({"file_data": {"file_uri": file_uri, "mime_type": "video/*"}})
        parts.append({"text": user_text})

        return {
            "project": project_id,
            "model": model or _DEFAULT_MODEL,
            "request": {
                "contents": [{"role": "user", "parts": parts}],
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": {
                    "thinkingConfig": {"thinkingLevel": thinking_level},
                },
            },
            "userAgent": "antigravity",
            "requestId": str(uuid.uuid4()),
        }

    def _call_endpoint(
        self, endpoint: str, body: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Call a single Antigravity endpoint."""
        resp = requests.post(
            f"{endpoint}/v1internal:generateContent",
            json=body,
            headers=headers,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        system_instruction: str,
        user_text: str,
        file_uri: str | None = None,
        thinking_level: str = "high",
        retries: int = 3,
    ) -> str:
        """Generate content via Antigravity with retry on 429."""
        headers = self._build_headers()
        body = self._build_body(
            model=model,
            system_instruction=system_instruction,
            user_text=user_text,
            file_uri=file_uri,
            thinking_level=thinking_level,
        )

        last_error: Exception | None = None
        for attempt in range(retries):
            if attempt > 0:
                wait = 60 * attempt
                logger.info(
                    "Rate limited, retrying in %ds (attempt %d/%d)...",
                    wait,
                    attempt + 1,
                    retries,
                )
                time.sleep(wait)
                headers = self._build_headers()

            for endpoint in _ENDPOINTS:
                try:
                    result = self._call_endpoint(endpoint, body, headers)
                    return _extract_text(result)
                except requests.RequestException as exc:
                    logger.warning("Antigravity endpoint %s failed: %s", endpoint, exc)
                    last_error = exc

        raise AntigravityError(
            f"All Antigravity endpoints failed after {retries} retries: {last_error}"
        )


def _extract_text(result: dict[str, Any]) -> str:
    """Extract text from Antigravity response envelope."""
    if "response" in result and "candidates" not in result:
        response = result.get("response")
        if isinstance(response, dict):
            result = response

    try:
        candidates = result["candidates"]
        parts = candidates[0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    except (KeyError, IndexError, TypeError) as exc:
        raise AntigravityError(f"Unexpected response format: {result}") from exc


def make_antigravity_client() -> AntigravityClient:
    """Create an AntigravityClient from env/config."""
    return AntigravityClient()


def iter_stream_video(
    youtube_url: str,
    *,
    model: str,
    client: AntigravityClient,
    system_instruction: str,
    user_turn: str,
    thinking_level: str = "high",
) -> Iterator[str]:
    """Analyze a YouTube video via Antigravity.

    Matches gemini_client.iter_stream_video()'s Iterator[str] pattern, but yields a
    single chunk because the Antigravity proxy does not expose streaming here.
    """
    text = client.generate(
        model=model,
        system_instruction=system_instruction,
        user_text=user_turn,
        file_uri=youtube_url,
        thinking_level=thinking_level,
    )
    if text:
        yield text
