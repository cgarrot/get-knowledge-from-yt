from __future__ import annotations

from yt_knowledge_ingest.auto_ingest_prompt import (
    allocate_prompt_name,
    build_video_type_from_reference_urls,
    slugify_prompt_base,
    unique_prompt_name,
)
from yt_knowledge_ingest.youtube_titles import YoutubeOembedInfo


def test_slugify_prompt_base_ascii_and_prefix():
    assert slugify_prompt_base("Hello World!") == "auto-hello-world"


def test_slugify_prompt_base_empty_core():
    assert slugify_prompt_base("!!!") == "auto-prompt-gen"


def test_unique_prompt_name_collision():
    existing = {"auto-foo", "auto-foo-2", "auto-foo-3"}
    assert unique_prompt_name("auto-foo", existing) == "auto-foo-4"


def test_allocate_prompt_name_respects_existing():
    names = {"auto-hello", "auto-hello-2"}
    vt = "Hello"
    assert allocate_prompt_name(vt, names) == "auto-hello-3"


def test_build_video_type_with_oembed_metadata():
    u1 = "https://www.youtube.com/watch?v=abc"
    u2 = "https://www.youtube.com/watch?v=def"
    infos = {
        u1: YoutubeOembedInfo(title="Talk One", author_name="Channel A"),
        u2: YoutubeOembedInfo(title="Talk Two", author_name="Channel B"),
    }
    text = build_video_type_from_reference_urls([u1, u2], oembed_infos=infos)
    assert "Talk One" in text
    assert "Channel A" in text
    assert u1 in text


def test_build_video_type_fallback_when_no_metadata():
    u1 = "https://www.youtube.com/watch?v=xyz"
    text = build_video_type_from_reference_urls([u1], oembed_infos={})
    assert "metadata unavailable" in text.lower()
    assert u1 in text
