from pathlib import Path

import pytest

from yt_knowledge_ingest.collection_classifier import (
    list_existing_folder_paths,
    parse_folder_from_llm_text,
)


def test_parse_folder_key():
    assert parse_folder_from_llm_text('{"folder": "ml/transformers"}') == "ml/transformers"


def test_parse_parent_child():
    assert (
        parse_folder_from_llm_text('{"parent": "cooking", "child": "pasta"}')
        == "cooking/pasta"
    )


def test_parse_fenced_json():
    text = """Here is the result:
```json
{"folder": "dev/rust"}
```
"""
    assert parse_folder_from_llm_text(text) == "dev/rust"


def test_parse_trailing_junk():
    assert (
        parse_folder_from_llm_text('prefix {"folder": "a/b"} suffix') == "a/b"
    )


def test_parse_invalid():
    assert parse_folder_from_llm_text("no json here") is None


def test_list_existing_folder_paths(tmp_path: Path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "x.md").write_text("# x", encoding="utf-8")
    (tmp_path / "root.md").write_text("# r", encoding="utf-8")
    paths = list_existing_folder_paths(tmp_path)
    assert paths == ["a/b"]
