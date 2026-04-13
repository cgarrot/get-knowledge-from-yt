from yt_knowledge_ingest.prompts import (
    DEFAULT_USER_TURN,
    split_prompt_markdown,
)


def test_split_prompt_markdown_plain_uses_default_user_turn():
    system, user_turn = split_prompt_markdown("Hello system body")
    assert user_turn == DEFAULT_USER_TURN
    assert system == "Hello system body"


def test_split_prompt_markdown_with_header():
    raw = '<!-- user_turn: "Do the thing." -->\n\nSystem part here'
    system, user_turn = split_prompt_markdown(raw)
    assert user_turn == "Do the thing."
    assert system == "System part here"


def test_split_prompt_markdown_strips_outer_whitespace():
    raw = '\n  <!-- user_turn: "x" -->\n\n  body  \n'
    system, user_turn = split_prompt_markdown(raw)
    assert user_turn == "x"
    assert system == "body"
