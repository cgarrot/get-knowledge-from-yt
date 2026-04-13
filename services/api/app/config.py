from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("GKFY_DATA_DIR", str(REPO_ROOT / "data"))).resolve()
OUTPUT_DIR = (DATA_DIR / "output").resolve()
DB_PATH = (DATA_DIR / "app.db").resolve()
USER_PROMPTS_DIR = (DATA_DIR / "prompts").resolve()

DEFAULT_WORKER_CONCURRENCY = int(os.environ.get("GKFY_WORKER_CONCURRENCY", "2"))

# When true, also write markdown under DATA_DIR/output (legacy / export). Default: DB only.
_WRITE_FLAG = (os.environ.get("GKFY_WRITE_OUTPUT_FILES") or "").strip().lower()
WRITE_OUTPUT_FILES = _WRITE_FLAG in ("1", "true", "yes", "on")

# Optional mirror under REPO_ROOT (e.g. ``knowledge-export``) for Git-friendly copies.
_REPO_EXPORT_RAW = (os.environ.get("GKFY_REPO_EXPORT_DIR") or "").strip()
REPO_EXPORT_DIR: Optional[Path] = None
REPO_EXPORT_PATH_STR = ""
if _REPO_EXPORT_RAW:
    try:
        _cand = (REPO_ROOT / _REPO_EXPORT_RAW).resolve()
        _cand.relative_to(REPO_ROOT.resolve())
        REPO_EXPORT_DIR = _cand
        REPO_EXPORT_PATH_STR = str(_cand)
    except ValueError:
        REPO_EXPORT_DIR = None
        REPO_EXPORT_PATH_STR = ""

# Logged at API startup when the env var is set but rejected.
REPO_EXPORT_INVALID_RAW = (
    _REPO_EXPORT_RAW if _REPO_EXPORT_RAW and REPO_EXPORT_DIR is None else ""
)

# OAuth redirect must match an "Authorized redirect URI" in Google Cloud Console.
PUBLIC_API_BASE = os.environ.get("GKFY_PUBLIC_API_URL", "http://127.0.0.1:8000").rstrip(
    "/"
)
FRONTEND_BASE = os.environ.get("GKFY_FRONTEND_URL", "http://localhost:3030").rstrip("/")

# Antigravity OAuth redirect_uri must match an authorized URI for the client.
# Default: same as opencode-antigravity-auth (pre-registered on the public Antigravity OAuth client).
# Override with GKFY_ANTIGRAVITY_OAUTH_REDIRECT_URI if you added another URI in Google Cloud
# (e.g. http://127.0.0.1:8000/auth/antigravity/callback).
_ANTIGRAVITY_REDIRECT_ENV = (os.environ.get("GKFY_ANTIGRAVITY_OAUTH_REDIRECT_URI") or "").strip()
if _ANTIGRAVITY_REDIRECT_ENV:
    ANTIGRAVITY_OAUTH_REDIRECT_URI = _ANTIGRAVITY_REDIRECT_ENV
else:
    ANTIGRAVITY_OAUTH_REDIRECT_URI = "http://localhost:51121/oauth-callback"
