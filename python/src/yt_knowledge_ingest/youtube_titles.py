from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

import requests

from .urls import youtube_video_id

logger = logging.getLogger(__name__)

_OEMBED_URL = "https://www.youtube.com/oembed"


@dataclass(frozen=True)
class YoutubeOembedInfo:
    title: str
    author_name: str


def fetch_oembed_infos(urls: list[str], timeout: int = 10) -> Dict[str, YoutubeOembedInfo]:
    """YouTube oEmbed: title + channel name (author_name), no API key."""
    out: Dict[str, YoutubeOembedInfo] = {}
    for url in urls:
        vid = youtube_video_id(url)
        if not vid:
            continue
        try:
            resp = requests.get(
                _OEMBED_URL,
                params={"url": url, "format": "json"},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            title = (data.get("title") or "").strip()
            author = (data.get("author_name") or "").strip()
            if title or author:
                out[url] = YoutubeOembedInfo(title=title, author_name=author)
                logger.debug("oEmbed for %s: title=%r author=%r", vid, title, author)
        except Exception:
            logger.warning("Could not fetch oEmbed for %s", url)
    return out


def fetch_titles(urls: list[str], timeout: int = 10) -> Dict[str, str]:
    """Map URL -> title (only entries with a non-empty title)."""
    return {
        u: inf.title
        for u, inf in fetch_oembed_infos(urls, timeout).items()
        if inf.title
    }
