from yt_knowledge_ingest.frontmatter import build_markdown, is_ok_skip_existing


def test_is_ok_skip_existing_true():
    md = build_markdown(
        source_url="https://example.com",
        playlist="p",
        slug="s",
        status="ok",
        error="",
        body="# body",
    )
    assert is_ok_skip_existing(md) is True


def test_is_ok_skip_existing_error_not_skip():
    md = build_markdown(
        source_url="https://example.com",
        playlist="p",
        slug="s",
        status="error",
        error="quota",
        body="_fail_",
    )
    assert is_ok_skip_existing(md) is False


def test_is_ok_no_frontmatter():
    assert is_ok_skip_existing("# plain\n") is False
