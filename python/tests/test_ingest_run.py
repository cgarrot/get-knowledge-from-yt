from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from yt_knowledge_ingest.ingest import PlaylistSpec, RunMetrics, run


def test_run_respects_concurrency_and_aggregates(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls: list[str] = []

    def fake_process_video_job(**kwargs):
        url = kwargs["url"]
        calls.append(url)
        return True, False, f"OK {url}", f"# {url}\n"

    mock_client = MagicMock()
    from yt_knowledge_ingest import ingest as ingest_mod

    monkeypatch.setattr(ingest_mod, "process_video_job", fake_process_video_job)
    specs = [
        PlaylistSpec(
            label="a.txt",
            source_path=tmp_path / "a.txt",
            urls=[
                "https://www.youtube.com/watch?v=aaaaaaaaaaa",
                "https://www.youtube.com/watch?v=bbbbbbbbbbb",
            ],
        ),
    ]
    (tmp_path / "a.txt").write_text("\n".join(specs[0].urls), encoding="utf-8")
    metrics = run(
        specs,
        out_dir=tmp_path / "out",
        concurrency=2,
        force=False,
        model="gemini-test",
        title_map=None,
        client=mock_client,
    )
    assert isinstance(metrics, RunMetrics)
    assert metrics.attempted == 2
    assert metrics.succeeded == 2
    assert metrics.failed == 0
    assert set(calls) == set(specs[0].urls)
