"""Helpers for ingest-time automatic prompt generation (batch references + naming)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from .youtube_titles import YoutubeOembedInfo, fetch_oembed_infos

_VIDEO_TYPE_MAX_LEN = 2000


def slugify_prompt_base(video_type: str) -> str:
    """Match web `slugifyPromptBase`: ASCII slug, max 48 chars + ``auto-`` prefix."""
    raw = video_type.strip().lower()
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(c for c in raw if unicodedata.category(c) != "Mn")
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"^-+|-+$", "", raw)
    raw = raw[:48]
    core = raw or "prompt-gen"
    return f"auto-{core}"


def unique_prompt_name(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def allocate_prompt_name(video_type: str, existing_names: set[str]) -> str:
    base = slugify_prompt_base(video_type)
    return unique_prompt_name(base, existing_names)


def build_video_type_from_reference_urls(
    ref_urls: list[str],
    *,
    oembed_infos: dict[str, YoutubeOembedInfo] | None = None,
) -> str:
    """Build a free-form *video_type* string for :func:`generate_prompt_markdown`.

    When oEmbed metadata is missing for all references, use a timestamped fallback
    so the derived slug stays unique.
    """
    if not ref_urls:
        raise ValueError("ref_urls must be non-empty")

    infos = oembed_infos if oembed_infos is not None else fetch_oembed_infos(ref_urls)

    def _has_meta(u: str) -> bool:
        inf = infos.get(u)
        return bool(inf and (inf.title or inf.author_name))

    lines: list[str] = []
    for url in ref_urls:
        inf = infos.get(url)
        if inf and (inf.title or inf.author_name):
            parts: list[str] = []
            if inf.title:
                parts.append(f'"{inf.title}"')
            if inf.author_name:
                parts.append(f"channel: {inf.author_name}")
            lines.append(f"- {url} — {'; '.join(parts)}")
        else:
            lines.append(f"- {url}")

    if not any(_has_meta(u) for u in ref_urls):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        listed = "\n".join(f"- {u}" for u in ref_urls)
        text = (
            "YouTube videos batch for durable wiki-style knowledge extraction. "
            f"Reference URLs (metadata unavailable at ingest time, {ts}).\n"
            f"{listed}\n"
            "Calibrate the reusable template from the attached reference videos."
        )
    else:
        text = (
            "Batch of similar YouTube videos; infer genre, pacing, and evidence "
            "patterns from these references and design one reusable ingest template.\n"
            "References:\n" + "\n".join(lines)
        )

    text = text.strip()
    if len(text) > _VIDEO_TYPE_MAX_LEN:
        text = text[: _VIDEO_TYPE_MAX_LEN].rsplit("\n", 1)[0].strip() or text[:_VIDEO_TYPE_MAX_LEN]
    return text
