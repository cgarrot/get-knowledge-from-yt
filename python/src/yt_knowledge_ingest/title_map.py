from __future__ import annotations

import csv
from pathlib import Path

from .urls import normalize_youtube_url


def load_title_map(path: Path) -> dict[str, str]:
    """Map canonical YouTube URL -> title."""
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    lines = text.splitlines()
    if lines and "\t" in lines[0]:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            title, raw_url = parts[0].strip(), parts[1].strip()
            u = normalize_youtube_url(raw_url)
            if u and title:
                out[u] = title
        return out
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return out
    fn = [f.lower().strip() for f in reader.fieldnames]
    try:
        i_title = fn.index("title")
        i_url = fn.index("url")
    except ValueError:
        return out
    orig_fields = reader.fieldnames
    for row in reader:
        title = (row.get(orig_fields[i_title]) or "").strip()
        raw = (row.get(orig_fields[i_url]) or "").strip()
        u = normalize_youtube_url(raw)
        if u and title:
            out[u] = title
    return out
