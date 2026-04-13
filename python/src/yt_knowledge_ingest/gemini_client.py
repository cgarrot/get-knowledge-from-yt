from __future__ import annotations

import os
from typing import Iterator

from google import genai
from google.genai import types

from .model_options import DEFAULT_GEMINI_API_MODEL
from .prompts import DEFAULT_BUILTIN_SYSTEM_INSTRUCTION, USER_TURN_TEMPLATE

DEFAULT_MODEL = DEFAULT_GEMINI_API_MODEL

THINKING_LEVELS = ("minimal", "low", "medium", "high")


def make_client() -> genai.Client:
    """`google.genai.Client` using `GEMINI_API_KEY` (required)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key)


def make_client_or_none() -> genai.Client | None:
    """Return a ``genai.Client`` if ``GEMINI_API_KEY`` is set, else ``None``."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return genai.Client(api_key=key)


def _thinking_config(level: str) -> types.ThinkingConfig:
    """Build ThinkingConfig: `thinking_level` when the SDK exposes it, else token budget."""
    level = level.lower()
    fields = getattr(types.ThinkingConfig, "model_fields", {})
    if "thinking_level" in fields:
        # e.g. ThinkingConfig(thinking_level="MINIMAL")
        return types.ThinkingConfig(thinking_level=level.upper())  # type: ignore[call-arg]
    # google-genai 1.47.x: only include_thoughts / thinking_budget (0 = disabled)
    budget_map = {"minimal": 0, "low": 8192, "medium": 16384, "high": 24576}
    return types.ThinkingConfig(
        include_thoughts=False,
        thinking_budget=budget_map.get(level, 0),
    )


def iter_stream_video(
    youtube_url: str,
    *,
    model: str,
    client: genai.Client,
    thinking_level: str = "minimal",
    system_instruction: str = DEFAULT_BUILTIN_SYSTEM_INSTRUCTION,
    user_turn: str = USER_TURN_TEMPLATE,
) -> Iterator[str]:
    """Stream `generate_content_stream`; yield each chunk's text for caller aggregation."""
    parts = [
        types.Part(
            file_data=types.FileData(
                file_uri=youtube_url,
                mime_type="video/*",
            )
        ),
        types.Part(text=user_turn),
    ]
    cfg = types.GenerateContentConfig(
        system_instruction=system_instruction,
        thinking_config=_thinking_config(thinking_level),
    )
    for resp in client.models.generate_content_stream(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=cfg,
    ):
        t = getattr(resp, "text", None)
        if t:
            yield t
