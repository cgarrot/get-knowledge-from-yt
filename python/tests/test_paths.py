from pathlib import Path

from yt_knowledge_ingest.paths import (
    playlist_dir_for_source,
    resolve_slug,
    safe_path_segment,
)


def test_safe_path_segment_ascii_and_length():
    assert safe_path_segment("  Hello / World!!  ") == "Hello-World"
    assert safe_path_segment("", max_len=10) == "playlist"
    long = "a" * 100
    assert len(safe_path_segment(long, max_len=20)) == 20


def test_playlist_dir_from_file_stem():
    p = Path("my-playlist.txt")
    assert playlist_dir_for_source(p, "ignored") == "my-playlist"


def test_playlist_dir_stdin_label():
    assert playlist_dir_for_source(None, "stdin") == "stdin"


def test_playlist_dir_nested_label():
    assert playlist_dir_for_source(None, "Tech / ML basics!!") == "Tech/ML-basics"


def test_playlist_dir_nested_empty_parts_ignored():
    assert playlist_dir_for_source(None, "a//b/ ") == "a/b"


def test_resolve_slug_default_video_id():
    u = "https://www.youtube.com/watch?v=AbC123dEfGh"
    assert resolve_slug(u, None) == "video-AbC123dEfGh"


def test_resolve_slug_title_map():
    u = "https://www.youtube.com/watch?v=xx1"
    m = {u: "Design / Feel"}
    assert resolve_slug(u, m) == "Design-Feel-xx1"
