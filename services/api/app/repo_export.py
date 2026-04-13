from __future__ import annotations

from pathlib import Path

from yt_knowledge_ingest.fsutil import atomic_write_text


def validate_rel_posix(rel: str) -> None:
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        raise ValueError("Invalid relative path")
    p = Path(rel)
    if p.is_absolute():
        raise ValueError("Invalid relative path")


def mirror_markdown(export_root: Path, rel_posix: str, body: str) -> None:
    """Write ``body`` under ``export_root / rel_posix`` (atomic)."""
    validate_rel_posix(rel_posix)
    base = export_root.resolve()
    target = (base / rel_posix).resolve()
    target.relative_to(base)
    atomic_write_text(target, body)
