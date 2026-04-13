"""LLM-assisted generation of ingest prompt templates (.md for load_prompt)."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from google import genai
from google.genai import types

from .gemini_client import _thinking_config
from .prompts import USER_TURN_TEMPLATE
from .urls import normalize_youtube_url

logger = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = ("gemini", "antigravity")

_MAX_RETRIES = 2
_RETRY_BASE_DELAY_S = 3

# ---------------------------------------------------------------------------
# Meta-prompt: system instruction for the prompt-engineer LLM
# ---------------------------------------------------------------------------
_PROMPT_ENGINEER_SYSTEM = """\
You are a staff-level prompt engineer designing reusable prompt templates
for a multimodal YouTube -> knowledge-wiki pipeline.

Your task: return ONE markdown document that will be saved as a prompt
template file. Return only the file body. No preamble. No explanation.
No outer code fences.

## FORMAT

The generated file is consumed as follows:
- First line REQUIRED: exactly one HTML comment in this form:
  `<!-- user_turn: "..." -->`
- The quoted user_turn must be:
  - a single line
  - short, imperative, and domain-appropriate
  - reusable across similar videos of the same type
  - safe for a simple parser: no internal double quotes, no line breaks
  - English unless the user's context clearly requires another language
- Everything after that first line is the SYSTEM instruction for the
  downstream model.

## PRIMARY GOAL

Design the downstream system instruction to maximize durable, verifiable
knowledge capture while minimizing hallucination, overclaiming, empty
summaries, and stylistic fluff.

The downstream prompt must be strong enough to produce the final wiki
document directly, not notes about how to write one.

## ADAPT TO THE REQUESTED VIDEO TYPE

The generated prompt must adapt to the user's requested video type.
Do NOT default to "software tutorial", "engineering walkthrough", or
"how-to" unless the request clearly calls for that genre.

Tune the downstream prompt's vocabulary, section names, and extraction focus
to the actual source, for example:
- tutorials / walkthroughs: procedures, ordered steps, tool usage, trade-offs
- talks / lectures: claims, frameworks, arguments, evidence, counterpoints
- interviews / podcasts: viewpoints, decision criteria, anecdotes with signal
- essays / explainers: thesis, supporting examples, mechanisms, open questions
- retrospectives / case studies: timeline, decisions, outcomes, lessons learned

If the source is primarily descriptive, analytical, historical, or
reflective, do not force "implementation rules" or "pitfalls" sections
unless the video actually supports them. Prefer the closest
evidence-grounded equivalent.

## EVIDENCE POLICY

Design the downstream system instruction so that the downstream model:
- treats the video as multimodal evidence: speech, on-screen text, UI,
  slides, code, demos, charts, edits, comparisons, and emphasis/timing when
  useful
- extracts concrete details when present: names, numbers, dates, labels,
  file/API names, ordered steps, before/after contrasts, and exact quotes
  only when clearly spoken or shown
- distinguishes between directly observed facts, reasonable
  evidence-grounded inferences, and uncertainty, ambiguity, or missing
  evidence
- marks inferred and uncertain claims explicitly, preferably with lightweight
  inline labels such as `[Inference]` or `[Uncertain]` when ambiguity matters
- omits rather than invents anything not clearly supported
- filters filler, sponsor talk, repetition, jokes, and off-topic banter
  unless they carry real information
- explains mechanisms, causality, or intent only when the evidence supports
  them; no mind-reading or speculative attribution
- uses domain-appropriate vocabulary with a neutral, reference-document tone
- remains reusable for future videos of the same type instead of overfitting
  to a single creator, franchise, or episode unless explicitly requested

## OUTPUT STRUCTURE

Require the downstream output to be structured wiki markdown with a
consistent, audit-friendly heading hierarchy.

The generated prompt should require these core sections or close
equivalents:
- Title / category
- TL;DR
- Key ideas, findings, or thesis
- Evidence, examples, or case material
- Uncertainty / evidence gaps

The generated prompt may require these optional sections only when relevant
to the video type and supported by evidence:
- Why it works / mechanisms / causal links
- Process / ordered steps / workflow
- Actionable rules / heuristics / recommendations
- Pitfalls / anti-patterns / failure modes
- Timeline / chronology / decision history
- Open questions / unresolved tensions

Make it explicit that headings should fit the genre. The downstream model
must not include empty sections or headings that promise content the source
does not supply.

## QUALITY

Hard requirements for the generated SYSTEM instruction:
- Prefer accuracy, evidence traceability, and durable reference value
  over eloquence.
- Integrate multimodal evidence when available, but do not mention
  modalities that are absent.
- Do not fabricate visuals, quotes, charts, code, metrics, or timelines.
- Avoid boilerplate openings and conclusions.
- Keep the prompt compact, specific, and reusable for future videos of the
  same type.
- Make it obvious that the downstream model must produce the final wiki
  document directly.
- Make the downstream model favor omission and explicit uncertainty over
  confident invention.

## REFERENCE SKELETON

Below is a concise structural reference. Use it as a pattern, not as domain
content to imitate.

<!-- user_turn: "Extract durable knowledge from this video" -->

You are an expert analyst producing a durable wiki-style reference document
from a [video type] video.

Use the video as multimodal evidence. Extract concrete details when present.
Separate direct observations from evidence-grounded inferences, and mark
uncertainty explicitly. Do not invent missing details.

Output the final wiki document directly in this structure:

# [Descriptive Title]
**Category:** [Domain / video type]

## TL;DR
3-4 sentences on the main idea, outcome, or value.

## Key Ideas / Findings
Explain the core concepts, arguments, decisions, or takeaways.

## Evidence & Examples
List the strongest concrete evidence from the video. Include exact names,
numbers, labels, steps, or quotes only when clearly visible or stated.

## [Optional genre-specific section]
Include only if the source supports it: mechanisms, implementation rules,
pitfalls, chronology, trade-offs, or open questions.

## Uncertainty & Evidence Gaps
State what remains unclear, implied, disputed, or unsupported by the video.

## OUTPUT RULES

- Return ONLY the markdown file content.
- Do NOT wrap the answer in markdown code fences.
- The first line MUST be the user_turn HTML comment.

## REFERENCE VIDEOS (when provided)

When one or more YouTube videos are supplied as multimodal input alongside this request, use them to calibrate the downstream template: actual genre,
pacing, typical visuals (slides, talking head, demo, B-roll), and what kinds
of evidence appear. Extract reusable extraction rules for that *kind* of
source—do not bake in one-off trivia, proper nouns, or spoilers that would
not transfer to other videos of the same type unless the user asked for that.
Still keep the template reusable for future ingest jobs of the same genre."""

_VIDEO_TYPE_MAX_LEN = 2000
_EXTRA_NOTES_MAX_LEN = 4000
_MAX_REFERENCE_VIDEOS = 8
_USER_TURN_MAX_LEN = 240
_USER_TURN_LINE_RE = re.compile(r'^<!--\s*user_turn:\s*"(.*)"\s*-->$')


def normalize_reference_video_urls(urls: list[str] | None) -> list[str]:
    """Validate, normalize, dedupe YouTube URLs; max :data:`_MAX_REFERENCE_VIDEOS`."""
    if not urls:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        s = (raw or "").strip()
        if not s:
            continue
        n = normalize_youtube_url(s)
        if not n:
            raise ValueError(f"Not a valid YouTube URL: {s!r}")
        if n not in seen:
            seen.add(n)
            out.append(n)
    if len(out) > _MAX_REFERENCE_VIDEOS:
        raise ValueError(
            f"At most {_MAX_REFERENCE_VIDEOS} reference videos allowed "
            f"(got {len(out)})"
        )
    return out


def strip_markdown_fences(text: str) -> str:
    """Remove a single outer ``` / ```markdown wrapper if the model added one."""
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    lines = raw.split("\n")
    if not lines:
        return raw
    lines = lines[1:]
    while lines and lines[-1].strip() == "":
        lines.pop()
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _sanitize_user_turn(user_turn: str) -> str:
    """Normalize the generated user_turn so the loader regex can parse it safely."""
    cleaned = " ".join(user_turn.replace("\r", "\n").split())
    cleaned = cleaned.replace('"', "'").strip()
    if not cleaned:
        cleaned = USER_TURN_TEMPLATE
    if len(cleaned) > _USER_TURN_MAX_LEN:
        truncated = cleaned[:_USER_TURN_MAX_LEN].rsplit(" ", 1)[0].strip()
        cleaned = truncated or cleaned[:_USER_TURN_MAX_LEN].strip()
    return cleaned or USER_TURN_TEMPLATE


def _normalize_generated_prompt_markdown(text: str) -> str:
    """Ensure the generated prompt has a safe user_turn header and non-empty body."""
    raw = strip_markdown_fences(text).strip()
    if not raw:
        raise ValueError("Generated prompt markdown is empty")

    lines = raw.splitlines()
    first_line = lines[0].strip() if lines else ""
    user_turn = USER_TURN_TEMPLATE
    body_lines = lines

    match = _USER_TURN_LINE_RE.match(first_line)
    if match:
        user_turn = _sanitize_user_turn(match.group(1))
        body_lines = lines[1:]
    elif first_line.startswith("<!--") and "user_turn" in first_line.lower():
        body_lines = lines[1:]

    body = "\n".join(body_lines).strip()
    if not body:
        raise ValueError("Generated prompt markdown is empty")

    return f'<!-- user_turn: "{user_turn}" -->\n\n{body}'


def _build_user_message(
    *,
    video_type: str,
    extra_notes: str,
    video_urls: list[str],
    all_videos_multimodal: bool,
) -> str:
    parts = [
        f"Video type (free-form, from the user): {video_type.strip()}",
    ]
    if video_urls:
        if all_videos_multimodal:
            parts.append(
                "Reference YouTube videos are attached as multimodal input "
                "(same order as below). Use them to calibrate the template."
            )
            for i, u in enumerate(video_urls, start=1):
                parts.append(f"{i}. {u}")
        elif len(video_urls) == 1:
            parts.append(
                "One reference video is attached as multimodal input (URL below)."
            )
            parts.append(f"- {video_urls[0]}")
        else:
            parts.append(
                "The FIRST reference video below is attached as multimodal input. "
                "The others are listed for context only (not attached separately)."
            )
            for i, u in enumerate(video_urls, start=1):
                parts.append(f"{i}. {u}")
    if extra_notes.strip():
        parts.append("Additional notes from the user:")
        parts.append(extra_notes.strip())
    parts.append(
        "Produce the prompt template markdown now, following all rules in your instructions."
    )
    return "\n\n".join(parts)


def _generate_gemini(
    *,
    client: genai.Client,
    model: str,
    thinking_level: str,
    user_text: str,
    video_urls: list[str],
) -> str:
    cfg = types.GenerateContentConfig(
        system_instruction=_PROMPT_ENGINEER_SYSTEM,
        thinking_config=_thinking_config(thinking_level),
    )
    parts: list[types.Part] = []
    for url in video_urls:
        parts.append(
            types.Part(
                file_data=types.FileData(
                    file_uri=url,
                    mime_type="video/*",
                )
            )
        )
    parts.append(types.Part(text=user_text))
    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=parts,
            )
        ],
        config=cfg,
    )
    t = getattr(resp, "text", None) or ""
    return str(t)


def _generate_antigravity(
    *,
    client: Any,
    model: str,
    thinking_level: str,
    user_text: str,
    file_uri: str | None,
) -> str:
    from .antigravity import AntigravityClient

    if not isinstance(client, AntigravityClient):
        raise TypeError(
            f"Expected AntigravityClient, got {type(client).__name__}"
        )
    return client.generate(
        model=model,
        system_instruction=_PROMPT_ENGINEER_SYSTEM,
        user_text=user_text,
        file_uri=file_uri,
        thinking_level=thinking_level,
    )


def _call_llm(
    *,
    client: object,
    provider: str,
    model: str,
    thinking_level: str,
    user_text: str,
    video_urls: list[str],
) -> str:
    """Dispatch to the right provider and return raw LLM output."""
    primary = video_urls[0] if video_urls else None
    if provider == "antigravity":
        return _generate_antigravity(
            client=client,
            model=model,
            thinking_level=thinking_level,
            user_text=user_text,
            file_uri=primary,
        )
    if provider == "gemini":
        if not isinstance(client, genai.Client):
            raise TypeError(
                f"Expected genai.Client for provider 'gemini', "
                f"got {type(client).__name__}"
            )
        return _generate_gemini(
            client=client,
            model=model,
            thinking_level=thinking_level,
            user_text=user_text,
            video_urls=video_urls,
        )
    raise ValueError(
        f"Unknown provider {provider!r}. "
        f"Supported: {', '.join(_SUPPORTED_PROVIDERS)}"
    )


def generate_prompt_markdown(
    *,
    client: object,
    provider: str,
    model: str,
    video_type: str,
    thinking_level: str = "medium",
    extra_notes: str = "",
    video_urls: list[str] | None = None,
    max_retries: int = _MAX_RETRIES,
) -> str:
    """Call the configured LLM and return cleaned markdown for a prompt file.

    Retries up to *max_retries* times on transient failures (empty output,
    normalization errors, or API exceptions) with exponential back-off.
    """
    vt = video_type.strip()
    if not vt:
        raise ValueError("video_type must be non-empty")
    if len(vt) > _VIDEO_TYPE_MAX_LEN:
        raise ValueError(f"video_type exceeds {_VIDEO_TYPE_MAX_LEN} characters")
    notes = (extra_notes or "").strip()
    if len(notes) > _EXTRA_NOTES_MAX_LEN:
        raise ValueError(f"extra_notes exceeds {_EXTRA_NOTES_MAX_LEN} characters")

    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown provider {provider!r}. "
            f"Supported: {', '.join(_SUPPORTED_PROVIDERS)}"
        )

    ref_urls = normalize_reference_video_urls(video_urls)
    all_mm = bool(ref_urls) and provider == "gemini"
    user_text = _build_user_message(
        video_type=vt,
        extra_notes=notes,
        video_urls=ref_urls,
        all_videos_multimodal=all_mm,
    )
    logger.info(
        "Generating prompt template: provider=%s model=%s video_type=%r "
        "reference_videos=%d",
        provider,
        model,
        vt,
        len(ref_urls),
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 2):  # attempt 1 .. max_retries+1
        try:
            raw = _call_llm(
                client=client,
                provider=provider,
                model=model,
                thinking_level=thinking_level,
                user_text=user_text,
                video_urls=ref_urls,
            )
            logger.debug(
                "LLM returned %d chars (attempt %d)", len(raw), attempt
            )
            result = _normalize_generated_prompt_markdown(raw)
            logger.info(
                "Prompt template generated successfully on attempt %d", attempt
            )
            return result
        except (TypeError, ValueError):
            raise
        except Exception as exc:
            last_error = exc
            if attempt <= max_retries:
                delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %d/%d failed (%s: %s), retrying in %ds",
                    attempt,
                    max_retries + 1,
                    type(exc).__name__,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "All %d attempts exhausted. Last error: %s",
                    max_retries + 1,
                    exc,
                )

    raise RuntimeError(
        f"Prompt generation failed after {max_retries + 1} attempts"
    ) from last_error
