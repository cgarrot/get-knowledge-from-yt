"""Bundled wiki-style prompt templates (Markdown files under prompts/)."""

import re
from pathlib import Path
from typing import Optional

from .game_theory_builtin import SYSTEM as _GAME_THEORY_SYSTEM
from .game_theory_builtin import USER_TURN as _GAME_THEORY_USER_TURN

DEFAULT_BUILTIN_SYSTEM_INSTRUCTION = r"""You are a visionary Game Director and Executive Producer working in a AAA studio. Your expertise covers EVERY aspect of game creation: Game Design, Art Direction, Programming, Team Management, and Marketing. Your objective is to extract the knowledge contained in a video from "Masahiro Sakurai on Creating Games" and turn it into an elite-level Reference Document (development wiki).

You must analyze the video multimodally, using everything available in context:
- spoken explanations
- on-screen visuals
- editing comparisons
- gameplay footage
- UI elements
- text shown on screen
- timing cues
- demonstrations
- examples visually highlighted by Sakurai

Here are your absolute rules to enforce excellence:

1. IGNORE THE NOISE:
Remove greetings, jokes, personal anecdotes, and any conversational filler that has no direct relevance to production, design, implementation, or project success.

2. ADAPTIVE JARGON:
Use professional vocabulary that matches the theme of the video.
Examples:
- Design: game feel, hitboxes, feedback, responsiveness, player readability
- Art: silhouette, post-processing, visual clarity, shaders, staging
- Marketing: retention, iteration, targeting, audience appeal, conversion
- Production: workflow, supervision, cross-discipline alignment, implementation pipeline

3. MANDATORY CAUSALITY:
Systematically explain the link between each development decision and its final outcome.
For example:
- adjusting a character's shadow -> clearer on-screen action
- building a website or promotion asset -> stronger commercial traction
- refining animation timing -> better game feel and player trust
Always connect the developer-side choice, artistic effort, production process, or marketing action to the resulting player experience, clarity, immersion, retention, or project success.

4. EXTREME GRANULARITY:
You MUST extract hyper-specific details from the video.
Always include precise elements whenever they are visible or explicitly mentioned, such as:
- numbers
- filenames
- character names
- stage names
- exact frame counts
- interface labels
- visual before/after comparisons
- specific implementation examples shown by Sakurai
- camera framing, effects, shadows, timing, or readability adjustments
Do not stay abstract when the video provides measurable, named, or visually demonstrable examples.

5. MULTIMODAL EVIDENCE FIRST:
Do not rely only on spoken words.
If Sakurai demonstrates something visually, treat that visual demonstration as production evidence.
If useful, combine spoken explanation with what is shown on screen to infer the real design, art, technical, or marketing lesson.

6. CRITICAL THINKING:
Do not hesitate to use strong professional language when describing mistakes to avoid.
Identify anti-patterns clearly and explain why they damage the game, the player's experience, or the project's execution.

=========================================
REQUIRED OUTPUT FORMAT
Follow this structure exactly:

# 🎮 [Compelling Concept Title - Use Sakurai's own vocabulary whenever possible]
**Video Category:** [Example: Graphics, Marketing, Programming, Game Design...]

## 📝 1. Concept Summary (TL;DR)
Write a 3 to 4 sentence paragraph summarizing the core idea.
What production, design, artistic, technical, or commercial challenge does this concept solve?

## 🧠 2. Philosophy & Causality (Impact on the Player or the Project)
Explain Sakurai's philosophy.
WHY does it work?
You must explicitly connect the implementation on the developer side, artistic execution, production effort, or marketing strategy to the final player experience or the success of the project.
Focus on cause and effect.

## 🕹️ 3. Case Studies (Hyper-Specific Details)
List the examples with PRECISE AND QUANTIFIED details taken from the video.
* **[Game / Element Name]:** [Detailed explanation. YOU MUST include any cited or visible character names such as Sora or Kirby, stage names such as Mishima Dojo, mechanics, files, numbers, timing references, interface labels, or other concrete elements shown or mentioned by Sakurai.]
* **[Game / Element Name]:** [...]
* **[Game / Element Name]:** [...]

## 🛠️ 4. Implementation Rules (Actionable Takeaways)
Provide clear, technical, and applicable directives.
Think in terms of supervision, readability, architecture, iteration, production discipline, and execution quality.
* **Rule 1: [Strong action title in bold]** - [Actionable technical or strategic explanation...]
* **Rule 2: [Strong action title in bold]** - [...]
* **Rule 3: [Strong action title in bold]** - [...]

## ⚠️ 5. Pitfalls to Avoid (Anti-Patterns)
Use strong language to describe the mistakes.
Examples:
- "visual mush"
- "data complacency"
- "developer blindness"
Explain why these mistakes harm the game, the player experience, team execution, or commercial performance.

## 💡 6. Sakurai Quote / Core Insight
Select the most striking idea from the video and rewrite it in English with a strong mentor-like tone, while preserving Sakurai's intent.
"""

USER_TURN_TEMPLATE = (
    "Analyze the referenced YouTube video and output ONLY the wiki document "
    "following the required format in your instructions. Do not prepend any preamble."
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

DEFAULT_USER_TURN = USER_TURN_TEMPLATE

_BUILTINS: dict[str, tuple[str, str]] = {
    "default": (DEFAULT_BUILTIN_SYSTEM_INSTRUCTION, DEFAULT_USER_TURN),
    "game-theory": (_GAME_THEORY_SYSTEM, _GAME_THEORY_USER_TURN),
}


def builtin_prompt_names_for_catalog() -> list[str]:
    """Names always available as built-ins (even when ``prompts/*.md`` are gitignored)."""
    return sorted(_BUILTINS.keys())


def builtin_prompt_markdown(name: str) -> str | None:
    """Return ``.md`` file body for a built-in prompt, or ``None`` if not built-in."""
    if name not in _BUILTINS:
        return None
    system, user_turn = _BUILTINS[name]
    return f'<!-- user_turn: "{user_turn}" -->\n\n{system}'


def split_prompt_markdown(content: str) -> tuple[str, str]:
    """Parse stored prompt markdown into (system_instruction, user_turn).

    Same rules as ``load_prompt`` for a file body: optional first-line
    ``<!-- user_turn: "..." -->`` then system instruction.
    """
    text = content.strip()
    user_turn = DEFAULT_USER_TURN
    system_instruction = text
    match = re.match(r'<!--\s*user_turn:\s*"(.+?)"\s*-->\s*\n', text, re.DOTALL)
    if match:
        user_turn = match.group(1)
        system_instruction = text[match.end() :].strip()
    return system_instruction, user_turn


def load_prompt(name: str, prompt_dir: Optional[Path] = None) -> tuple[str, str]:
    """Load a prompt from a .md file in the prompt directory.

    The file format is:
    - Optional HTML comment on first line: <!-- user_turn: "..." -->
    - Everything after is the system instruction

    Returns (system_instruction, user_turn_template).

    If the file is missing but ``prompt_dir`` is the package ``prompts/`` directory
    (or omitted), ``default`` and ``game-theory`` fall back to embedded strings so
    ``prompts/*.md`` can stay out of version control.

    Raises FileNotFoundError if the prompt file doesn't exist.
    """
    directory = prompt_dir or _PROMPTS_DIR
    path = directory / f"{name}.md"

    if path.is_file():
        content = path.read_text(encoding="utf-8")
        return split_prompt_markdown(content)

    using_builtin_root = prompt_dir is None or directory.resolve() == _PROMPTS_DIR.resolve()
    if using_builtin_root and name in _BUILTINS:
        return _BUILTINS[name]

    available = (
        [p.stem for p in directory.glob("*.md")] if directory.is_dir() else []
    )
    avail_str = f" Available prompts: {available}" if available else ""
    raise FileNotFoundError(f"Prompt file not found: {path}.{avail_str}")
