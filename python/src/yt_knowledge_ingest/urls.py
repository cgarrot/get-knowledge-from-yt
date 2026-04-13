from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_YT_HOST = re.compile(r"(^|\.)youtube\.com$|^youtu\.be$", re.I)


def normalize_youtube_url(raw: str) -> str | None:
    u = raw.strip()
    if not u or u.startswith("#"):
        return None
    parsed = urlparse(u)
    if not parsed.scheme:
        u2 = "https://" + u
        parsed = urlparse(u2)
    host = parsed.netloc.lower()
    if not _YT_HOST.search(host):
        return None
    if host.endswith("youtu.be"):
        vid = parsed.path.lstrip("/").split("/")[0]
        if not vid:
            return None
        return f"https://www.youtube.com/watch?v={vid}"
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return f"https://www.youtube.com/watch?v={qs['v'][0]}"
    m = re.match(r"^/shorts/([^/?#]+)", parsed.path)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.match(r"^/embed/([^/?#]+)", parsed.path)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.match(r"^/watch/([^/?#]+)", parsed.path)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.match(r"^/live/([^/?#]+)", parsed.path)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return None


def youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]
    if parsed.netloc.lower().endswith("youtu.be"):
        return parsed.path.lstrip("/").split("/")[0] or None
    return None


def read_urls_from_text(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        n = normalize_youtube_url(line)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
