from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from yt_knowledge_ingest.fsutil import atomic_write_text


def test_atomic_write_text_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "out.md"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_concurrent_atomic_writes_distinct_paths(tmp_path: Path) -> None:
    def write_one(i: int) -> Path:
        p = tmp_path / f"f{i}.md"
        atomic_write_text(p, f"content-{i}")
        return p

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(write_one, i) for i in range(32)]
        paths = [f.result() for f in as_completed(futures)]
    by_index = {int(p.stem[1:]): p.read_text(encoding="utf-8") for p in paths}
    for i in range(32):
        assert by_index[i] == f"content-{i}"
