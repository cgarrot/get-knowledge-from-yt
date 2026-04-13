"""LLM-based relative path for markdown output (parent/subfolder)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Union

from google import genai
from google.genai import types

from .gemini_client import _thinking_config
from .paths import playlist_dir_for_source, safe_path_segment
from .youtube_titles import fetch_oembed_infos

logger = logging.getLogger(__name__)

_CLASSIFIER_SYSTEM_FULL = """You classify YouTube videos into a relative folder path for a knowledge library.
Reply with a single JSON object and no other text. Use only ASCII letters, digits, hyphens and slashes in path segments.
Prefer 1–2 path segments: a broad topic, optionally a subtopic (e.g. "ml/transformers" or "cooking/pasta").
If existing folders are listed, prefer reusing one when it clearly fits; otherwise propose a sensible new path."""

_CLASSIFIER_SYSTEM_SUB = """You pick subfolders under a fixed channel directory for a knowledge library.
The first path segment is already chosen from the YouTube channel name so all videos from the same channel stay together.
Reply with a single JSON object and no other text. Use only ASCII letters, digits, hyphens and slashes.
Return {"folder": "subpath"} where subpath is 0–2 segments only (e.g. "tutorials" or "season-2/episodes") — do NOT repeat the channel name.
If existing folders are listed, prefer reusing a matching subpath when it clearly fits."""

_JSON_DECODER = json.JSONDecoder()


def list_existing_folder_paths(out_root: Path, *, limit: int = 200) -> list[str]:
    """Directory paths (posix, relative to out_root) that contain at least one .md file."""
    if not out_root.is_dir():
        return []
    found: set[str] = set()
    for f in out_root.rglob("*.md"):
        try:
            rel = f.relative_to(out_root.resolve())
        except ValueError:
            continue
        parent = rel.parent
        s = parent.as_posix()
        if s and s != ".":
            found.add(s)
    return sorted(found)[:limit]


def parse_folder_from_llm_text(text: str) -> str | None:
    """Parse JSON with \"folder\" string or \"parent\"+\"child\" from model output."""
    raw = text.strip()
    if "```" in raw:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
    start = raw.find("{")
    if start < 0:
        return None
    try:
        obj, _end = _JSON_DECODER.raw_decode(raw[start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    folder = obj.get("folder")
    if isinstance(folder, str) and folder.strip():
        return folder.strip()
    parent = obj.get("parent")
    child = obj.get("child")
    if isinstance(parent, str) and isinstance(child, str):
        p, c = parent.strip(), child.strip()
        if p and c:
            return f"{p}/{c}"
        if p:
            return p
        if c:
            return c
    return None


def _build_user_prompt(
    *,
    url: str,
    title: str,
    author_name: str,
    channel_prefix: str,
    existing: list[str],
    extra_instructions: str,
) -> str:
    lines = [
        f"Video URL: {url}",
        f"Title: {title or '(unknown)'}",
    ]
    if author_name:
        lines.append(f"YouTube channel: {author_name}")
    if channel_prefix:
        lines.append(
            f"Fixed first-level folder (already applied): {channel_prefix} "
            "(all videos from this channel share it)."
        )
    if existing:
        lines.append("Existing collection folders (relative paths):")
        lines.extend(f"  - {p}" for p in existing)
    else:
        lines.append("No existing folders yet; propose a sensible path.")
    if extra_instructions.strip():
        lines.append("Additional instructions from the user:")
        lines.append(extra_instructions.strip())
    if channel_prefix:
        lines.append(
            'Respond with JSON only, e.g. {"folder": "topic/subtopic"} '
            "with subpath only under the fixed channel folder."
        )
    else:
        lines.append('Respond with JSON only, e.g. {"folder": "topic/subtopic"}')
    return "\n".join(lines)


def _classify_gemini(
    *,
    client: genai.Client,
    model: str,
    thinking_level: str,
    user_text: str,
    system_instruction: str,
) -> str:
    cfg = types.GenerateContentConfig(
        system_instruction=system_instruction,
        thinking_config=_thinking_config(thinking_level),
    )
    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=user_text)],
            )
        ],
        config=cfg,
    )
    t = getattr(resp, "text", None) or ""
    return str(t)


def _classify_antigravity(
    *,
    client: Any,
    model: str,
    thinking_level: str,
    user_text: str,
    system_instruction: str,
) -> str:
    from .antigravity import AntigravityClient

    assert isinstance(client, AntigravityClient)
    return client.generate(
        model=model,
        system_instruction=system_instruction,
        user_text=user_text,
        file_uri=None,
        thinking_level=thinking_level,
    )


def classify_collection_folder(
    *,
    url: str,
    out_root: Path,
    client: Union[genai.Client, object],
    model: str,
    thinking_level: str = "minimal",
    provider: str = "gemini",
    extra_instructions: str = "",
    fallback_label: str = "default",
    existing_folder_hints: list[str] | None = None,
) -> tuple[str, str]:
    """Return (playlist_label segments joined for DB, log message)."""
    infos = fetch_oembed_infos([url])
    info = infos.get(url)
    title = info.title if info else ""
    author_name = info.author_name if info else ""
    channel_prefix = safe_path_segment(author_name) if author_name else ""
    use_channel_anchor = bool(channel_prefix)
    system = _CLASSIFIER_SYSTEM_SUB if use_channel_anchor else _CLASSIFIER_SYSTEM_FULL
    disk_existing = list_existing_folder_paths(out_root)
    if existing_folder_hints is not None:
        existing = sorted(set(existing_folder_hints) | set(disk_existing))[:200]
    else:
        existing = disk_existing
    user_text = _build_user_prompt(
        url=url,
        title=title,
        author_name=author_name,
        channel_prefix=channel_prefix,
        existing=existing,
        extra_instructions=extra_instructions,
    )
    raw = ""
    try:
        if provider == "antigravity":
            raw = _classify_antigravity(
                client=client,
                model=model,
                thinking_level=thinking_level,
                user_text=user_text,
                system_instruction=system,
            )
        else:
            assert isinstance(client, genai.Client)
            raw = _classify_gemini(
                client=client,
                model=model,
                thinking_level=thinking_level,
                user_text=user_text,
                system_instruction=system,
            )
        parsed = parse_folder_from_llm_text(raw)
        if not parsed:
            logger.warning("Classifier returned no parseable folder: %s", raw[:500])
            return fallback_label, f"classifier_parse_fallback raw={raw[:200]!r}"
        if use_channel_anchor:
            sub = playlist_dir_for_source(None, parsed)
            if not sub or sub == "playlist":
                combined = channel_prefix
            else:
                combined = f"{channel_prefix}/{sub}"
            normalized = playlist_dir_for_source(None, combined)
        else:
            normalized = playlist_dir_for_source(None, parsed)
        if not normalized or normalized == "playlist":
            return fallback_label, f"classifier_empty_fallback normalized_from={parsed!r}"
        note = f"classified as {normalized}"
        if use_channel_anchor:
            note += f" (channel {author_name!r})"
        return normalized, note
    except Exception as exc:  # noqa: BLE001
        logger.exception("Classifier failed: %s", exc)
        return fallback_label, f"classifier_error {type(exc).__name__}: {exc}"

