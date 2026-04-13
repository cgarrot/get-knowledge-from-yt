from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .urls import youtube_video_id


def safe_path_segment(name: str, max_len: int = 80) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.strip()
    n = re.sub(r"[^\w\s.-]+", "", n, flags=re.ASCII)
    n = re.sub(r"\s+", "-", n).strip("-._")
    n = n[:max_len] or "playlist"
    return n


def default_slug_for_url(url: str, video_id: str | None) -> str:
    if video_id:
        return f"video-{video_id}"
    import hashlib

    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"video-{h}"


def resolve_slug(url: str, title_by_url: dict[str, str] | None) -> str:
    vid = youtube_video_id(url)
    title = None
    if title_by_url:
        title = title_by_url.get(url)
    if title:
        base = safe_path_segment(title, max_len=100)
        if vid:
            return f"{base}-{vid}"
        return base
    return default_slug_for_url(url, vid)


def playlist_dir_for_source(source_path: Path | None, label: str) -> str:
    if source_path is not None:
        return safe_path_segment(source_path.stem)
    parts = [p for p in label.replace("\\", "/").split("/") if p.strip()]
    if not parts:
        return "playlist"
    return "/".join(safe_path_segment(p) for p in parts)
