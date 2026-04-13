from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from yt_knowledge_ingest import gemini_client
from yt_knowledge_ingest.gemini_client import iter_stream_video, make_client
from yt_knowledge_ingest.prompts import DEFAULT_BUILTIN_SYSTEM_INSTRUCTION, USER_TURN_TEMPLATE


def test_make_client_requires_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        make_client()


def test_make_client_uses_env_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    c = make_client()
    assert c is not None


def test_iter_stream_video_calls_stream_with_file_data_and_system_instruction():
    class _Chunk:
        __slots__ = ("text",)

        def __init__(self, text):
            self.text = text

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [
        _Chunk("Hello "),
        _Chunk(None),
        _Chunk("wiki"),
    ]

    out = "".join(
        iter_stream_video(
            "https://www.youtube.com/watch?v=abc123",
            model="gemini-test",
            client=mock_client,
        )
    )
    assert out == "Hello wiki"

    mock_client.models.generate_content_stream.assert_called_once()
    kwargs = mock_client.models.generate_content_stream.call_args.kwargs
    assert kwargs["model"] == "gemini-test"
    cfg = kwargs["config"]
    assert cfg.system_instruction == DEFAULT_BUILTIN_SYSTEM_INSTRUCTION
    assert cfg.thinking_config is not None
    contents = kwargs["contents"]
    assert len(contents) == 1
    parts = contents[0].parts
    assert len(parts) == 2
    assert parts[0].file_data.file_uri == "https://www.youtube.com/watch?v=abc123"
    assert parts[0].file_data.mime_type == "video/*"
    assert parts[1].text == USER_TURN_TEMPLATE


def test_thinking_config_fallback_uses_budget_zero_for_minimal():
    tc = gemini_client._thinking_config("minimal")
    assert tc.include_thoughts is False
    assert tc.thinking_budget == 0
