"""Model IDs exposed to the UI: Gemini API vs Antigravity (cloudcode-pa) differ.

Gemini API: https://ai.google.dev/gemini-api/docs/models

Antigravity (Unified Gateway, ``/v1internal:generateContent``): model IDs are
**not** the same as the public Gemini API. Verified catalog (Dec 2025) and
tier rules: https://github.com/NoeFabris/opencode-antigravity-auth/blob/main/docs/ANTIGRAVITY_API_SPEC.md

Gemini 3.x **Pro** routes typically require a ``-high`` / ``-low`` suffix; a
bare ``gemini-3.1-pro`` often returns 404 (see e.g. OpenClaw issue discussions).
"""

from __future__ import annotations

# --- Google AI (Gemini API) — multimodal video URL + key ---
GEMINI_API_MODEL_IDS: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-pro-preview",
)

DEFAULT_GEMINI_API_MODEL: str = "gemini-2.5-flash"

# --- Antigravity / cloudcode-pa (OAuth refresh token) ---
ANTIGRAVITY_MODEL_IDS: tuple[str, ...] = (
    # Gemini (gateway; multimodal / YouTube URL — prefer these for this app)
    "gemini-3-pro-high",
    "gemini-3-pro-low",
    "gemini-3.1-pro-high",
    "gemini-3.1-pro-low",
    "gemini-3-flash",
    # Also routed by the same Antigravity endpoint (video support may differ)
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gpt-oss-120b-medium",
)

# Default: first entry verified in ANTIGRAVITY_API_SPEC for Gemini Pro tier.
DEFAULT_ANTIGRAVITY_MODEL: str = "gemini-3-pro-high"


def models_for_provider(provider: str) -> tuple[str, ...]:
    if provider == "antigravity":
        return ANTIGRAVITY_MODEL_IDS
    return GEMINI_API_MODEL_IDS


def default_model_for_provider(provider: str) -> str:
    if provider == "antigravity":
        return DEFAULT_ANTIGRAVITY_MODEL
    return DEFAULT_GEMINI_API_MODEL
