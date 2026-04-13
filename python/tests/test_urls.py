from yt_knowledge_ingest.paths import resolve_slug
from yt_knowledge_ingest.urls import normalize_youtube_url, read_urls_from_text, youtube_video_id


def test_normalize_watch():
    u = normalize_youtube_url("https://www.youtube.com/watch?v=abc123_Xy")
    assert u == "https://www.youtube.com/watch?v=abc123_Xy"


def test_normalize_short():
    u = normalize_youtube_url("https://youtu.be/abc123_Xy")
    assert u == "https://www.youtube.com/watch?v=abc123_Xy"


def test_normalize_watch_path():
    u = normalize_youtube_url("https://www.youtube.com/watch/dQw4w9WgXcQ")
    assert u == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_normalize_live():
    u = normalize_youtube_url("https://www.youtube.com/live/dQw4w9WgXcQ")
    assert u == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_read_urls_dedup_and_comments():
    text = """
https://www.youtube.com/watch?v=a
https://youtu.be/a
# https://www.youtube.com/watch?v=b
not-a-url
https://www.youtube.com/watch?v=c
"""
    urls = read_urls_from_text(text)
    assert urls == [
        "https://www.youtube.com/watch?v=a",
        "https://www.youtube.com/watch?v=c",
    ]


def test_video_id():
    u = "https://www.youtube.com/watch?v=Z123"
    assert youtube_video_id(u) == "Z123"


def test_resolve_slug_with_map():
    u = "https://www.youtube.com/watch?v=abc"
    m = {u: "Hello / World"}
    s = resolve_slug(u, m)
    assert s == "Hello-World-abc"
