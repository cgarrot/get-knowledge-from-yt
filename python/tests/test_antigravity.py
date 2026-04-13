from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from yt_knowledge_ingest.antigravity import (
    AntigravityClient,
    AntigravityError,
    _extract_text,
    iter_stream_video,
)


def test_extract_text_simple():
    result = {
        "response": {"candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]}
    }
    assert _extract_text(result) == "Hello world"


def test_extract_text_unwrapped():
    result = {
        "candidates": [
            {"content": {"parts": [{"text": "Direct"}, {"text": " result"}]}}
        ]
    }
    assert _extract_text(result) == "Direct result"


def test_extract_text_bad_format():
    with pytest.raises(AntigravityError, match="Unexpected response"):
        _extract_text({"candidates": []})


@patch("yt_knowledge_ingest.antigravity._get_refresh_token", return_value="fake-token")
def test_client_refresh_token(_mock):
    client = AntigravityClient()
    assert client._refresh_token == "fake-token"


def test_iter_stream_video_yields_text():
    mock_client = MagicMock(spec=AntigravityClient)
    mock_client.generate.return_value = "Analysis result"
    chunks = list(
        iter_stream_video(
            "https://youtube.com/watch?v=test",
            model="gemini-3.1-pro-high",
            client=mock_client,
            system_instruction="sys",
            user_turn="user",
        )
    )
    assert chunks == ["Analysis result"]


def test_iter_stream_video_empty_yields_nothing():
    mock_client = MagicMock(spec=AntigravityClient)
    mock_client.generate.return_value = ""
    chunks = list(
        iter_stream_video(
            "https://youtube.com/watch?v=test",
            model="gemini-3.1-pro-high",
            client=mock_client,
            system_instruction="sys",
            user_turn="user",
        )
    )
    assert chunks == []
