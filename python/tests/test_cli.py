from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_knowledge_ingest.cli import _exit_code, main
from yt_knowledge_ingest.ingest import RunMetrics


def test_exit_code_all_ok() -> None:
    m = RunMetrics(attempted=2, succeeded=2, skipped=0, failed=0)
    assert _exit_code(m, had_work=True) == 0


def test_exit_code_partial_failure() -> None:
    m = RunMetrics(attempted=2, succeeded=1, skipped=0, failed=1)
    assert _exit_code(m, had_work=True) == 0


def test_exit_code_all_skipped() -> None:
    m = RunMetrics(attempted=2, succeeded=0, skipped=2, failed=0)
    assert _exit_code(m, had_work=True) == 0


def test_exit_code_all_failed_no_success() -> None:
    m = RunMetrics(attempted=2, succeeded=0, skipped=0, failed=2)
    assert _exit_code(m, had_work=True) == 3


def test_exit_code_skipped_and_failed_no_success() -> None:
    m = RunMetrics(attempted=2, succeeded=0, skipped=1, failed=1)
    assert _exit_code(m, had_work=True) == 3


def test_exit_code_no_work() -> None:
    m = RunMetrics()
    assert _exit_code(m, had_work=False) == 3


def test_main_no_urls_exits_3(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    empty = tmp_path / "empty.txt"
    empty.write_text("not a url\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--output-dir", str(tmp_path / "out"), str(empty)])
    assert exc.value.code == 3


def test_main_concurrency_invalid() -> None:
    with pytest.raises(SystemExit):
        main(["--output-dir", "/tmp", "--concurrency", "0", __file__])


@patch("yt_knowledge_ingest.cli.run")
def test_main_job_failure_exits_3(mock_run: MagicMock, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    urls = tmp_path / "urls.txt"
    urls.write_text("https://www.youtube.com/watch?v=dQw4w9WgXcQ\n", encoding="utf-8")
    mock_run.return_value = RunMetrics(attempted=1, succeeded=0, skipped=0, failed=1)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    with pytest.raises(SystemExit) as exc:
        main(["--output-dir", str(tmp_path / "out"), str(urls)])
    assert exc.value.code == 3
