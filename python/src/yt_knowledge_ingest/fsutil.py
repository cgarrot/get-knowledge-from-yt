from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write `text` to `path` via a unique temp file in the same directory then replace.

    Avoids fixed ``.tmp`` suffix collisions when many workers write under the same tree.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".tmp",
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
