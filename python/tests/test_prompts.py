from __future__ import annotations

from pathlib import Path

import pytest

from yt_knowledge_ingest.prompts import load_prompt


def test_load_default_prompt():
    system, user = load_prompt("default")
    assert "Game Director" in system
    assert "wiki document" in user


def test_load_game_theory_prompt():
    system, user = load_prompt("game-theory")
    assert "Geopolitical Strategist" in system
    assert "Strategic Reference Document" in user


def test_load_prompt_not_found():
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        load_prompt("nonexistent")


def test_load_prompt_custom_dir(tmp_path: Path):
    prompt_file = tmp_path / "custom.md"
    prompt_file.write_text(
        '<!-- user_turn: "Do the thing" -->\n\nCustom system instruction.',
        encoding="utf-8",
    )
    system, user = load_prompt("custom", prompt_dir=tmp_path)
    assert system == "Custom system instruction."
    assert user == "Do the thing"


def test_load_prompt_no_user_turn_comment(tmp_path: Path):
    prompt_file = tmp_path / "bare.md"
    prompt_file.write_text("Just the instruction body.", encoding="utf-8")
    system, user = load_prompt("bare", prompt_dir=tmp_path)
    assert system == "Just the instruction body."
    assert "wiki document" in user
