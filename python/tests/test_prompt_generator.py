from __future__ import annotations

from yt_knowledge_ingest.prompt_generator import (
    _MAX_REFERENCE_VIDEOS,
    _PROMPT_ENGINEER_SYSTEM,
    _normalize_generated_prompt_markdown,
    generate_prompt_markdown,
    normalize_reference_video_urls,
    strip_markdown_fences,
)
from yt_knowledge_ingest.prompts import USER_TURN_TEMPLATE


def test_strip_markdown_fences_plain_unchanged():
    s = '<!-- user_turn: "x" -->\n\nHello'
    assert strip_markdown_fences(s) == s


def test_strip_markdown_fences_with_wrapper():
    inner = '<!-- user_turn: "go" -->\n\nBody here'
    wrapped = f"```markdown\n{inner}\n```"
    assert strip_markdown_fences(wrapped) == inner


def test_strip_markdown_fences_language_tag_only():
    assert strip_markdown_fences("```\nline\n```") == "line"


def test_normalize_generated_prompt_markdown_injects_default_user_turn():
    out = _normalize_generated_prompt_markdown("System body")
    assert out == f'<!-- user_turn: "{USER_TURN_TEMPLATE}" -->\n\nSystem body'


def test_normalize_generated_prompt_markdown_sanitizes_user_turn():
    out = _normalize_generated_prompt_markdown(
        '<!-- user_turn: "Do "the" thing now" -->\n\nSystem body'
    )
    assert out == '<!-- user_turn: "Do \'the\' thing now" -->\n\nSystem body'


def test_normalize_generated_prompt_markdown_drops_malformed_header():
    out = _normalize_generated_prompt_markdown(
        "<!-- user_turn: missing quote -->\n\nSystem body"
    )
    assert out == f'<!-- user_turn: "{USER_TURN_TEMPLATE}" -->\n\nSystem body'


def test_normalize_generated_prompt_markdown_rejects_empty_body():
    try:
        _normalize_generated_prompt_markdown(
            '<!-- user_turn: "Do the thing" -->\n\n'
        )
    except ValueError as e:
        assert "empty" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")


def test_prompt_engineer_system_pushes_information_dense_outputs():
    text = _PROMPT_ENGINEER_SYSTEM.lower()
    assert "detail density & coverage" in text
    assert "concise only in the tl;dr" in text
    assert "records multiple concrete examples" in text


def test_generate_prompt_markdown_validates_empty_video_type():
    try:
        generate_prompt_markdown(
            client=object(),
            provider="gemini",
            model="gemini-2.5-flash",
            video_type="   ",
        )
    except ValueError as e:
        assert "non-empty" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")


def test_normalize_reference_video_urls_dedupes():
    u1 = "https://www.youtube.com/watch?v=abc"
    assert normalize_reference_video_urls([u1, u1, "https://youtu.be/abc"]) == [
        u1
    ]


def test_normalize_reference_video_urls_rejects_invalid():
    try:
        normalize_reference_video_urls(["https://example.com/video"])
    except ValueError as e:
        assert "valid YouTube" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_normalize_reference_video_urls_max():
    many = [f"https://www.youtube.com/watch?v={i}" for i in range(_MAX_REFERENCE_VIDEOS + 1)]
    try:
        normalize_reference_video_urls(many)
    except ValueError as e:
        assert "at most" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")


def test_generate_prompt_markdown_validates_video_type_length():
    try:
        generate_prompt_markdown(
            client=object(),
            provider="gemini",
            model="gemini-2.5-flash",
            video_type="x" * 3000,
        )
    except ValueError as e:
        assert "exceeds" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")
