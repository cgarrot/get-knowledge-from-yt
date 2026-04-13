from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .gemini_client import DEFAULT_MODEL, THINKING_LEVELS
from .ingest import RunMetrics, load_playlist_from_stdin, load_playlists_from_files, run
from .prompts import load_prompt
from .title_map import load_title_map

PROVIDERS = ("gemini", "antigravity")


def _concurrency_type(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("concurrency must be a positive integer")
    return n


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="yt-knowledge-ingest",
        description=(
            "Ingest YouTube URLs grouped by playlist files (or stdin) into "
            "Gemini-generated markdown wiki pages."
        ),
    )
    p.add_argument(
        "playlists",
        nargs="*",
        type=Path,
        help="Files containing one YouTube URL per line (each file = one logical playlist).",
    )
    p.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        required=True,
        help="Root output directory",
    )
    p.add_argument(
        "--concurrency",
        type=_concurrency_type,
        default=2,
        help="Parallel workers (default: 2, min 1)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even when an OK markdown already exists",
    )
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model id (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--title-map",
        type=Path,
        default=None,
        help="Optional TSV (title<TAB>url) or CSV with columns title,url",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    p.add_argument(
        "--thinking-level",
        default="minimal",
        choices=THINKING_LEVELS,
        help="Gemini thinking level (default: minimal)",
    )
    p.add_argument(
        "--prompt",
        default="default",
        help="Prompt name to load from prompt directory (default: default). "
        "Looks for <name>.md in the prompt directory.",
    )
    p.add_argument(
        "--prompt-dir",
        type=Path,
        default=None,
        help="Custom prompt directory (default: built-in prompts/)",
    )
    p.add_argument(
        "--provider",
        default="gemini",
        choices=PROVIDERS,
        help=(
            "AI provider: gemini (GEMINI_API_KEY) or antigravity "
            "(ANTIGRAVITY_* OAuth client env vars, see README) (default: gemini)"
        ),
    )
    p.add_argument(
        "--auto-title",
        action="store_true",
        help="Auto-fetch YouTube video titles via oEmbed for human-readable filenames",
    )
    return p


def _exit_code(metrics: RunMetrics, had_work: bool) -> int:
    """Exit 0 if any ingest succeeded or all URLs were skipped; 3 if no work or total failure."""
    if not had_work:
        return 3
    if metrics.succeeded > 0:
        return 0
    if metrics.attempted > 0 and metrics.skipped == metrics.attempted:
        return 0
    return 3


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(message)s",
    )
    title_by_url = load_title_map(args.title_map) if args.title_map else None

    system_instruction, user_turn = load_prompt(args.prompt, args.prompt_dir)

    if args.playlists:
        specs = load_playlists_from_files(args.playlists)
    else:
        specs = [load_playlist_from_stdin()]

    total_urls = sum(len(s.urls) for s in specs)
    if total_urls == 0:
        logging.error("No valid YouTube URLs found in input.")
        sys.exit(3)

    if args.auto_title and not title_by_url:
        from .youtube_titles import fetch_titles

        all_urls = [u for s in specs for u in s.urls]
        logging.info("Fetching titles for %d videos...", len(all_urls))
        title_by_url = fetch_titles(all_urls)
        logging.info("Got %d titles.", len(title_by_url))
    elif args.auto_title and title_by_url:
        from .youtube_titles import fetch_titles

        known = set(title_by_url.keys())
        missing = [u for s in specs for u in s.urls if u not in known]
        if missing:
            logging.info("Fetching titles for %d additional videos...", len(missing))
            extra = fetch_titles(missing)
            title_by_url.update(extra)
            logging.info("Got %d extra titles.", len(extra))

    try:
        metrics = run(
            specs,
            out_dir=args.output_dir,
            concurrency=args.concurrency,
            force=args.force,
            model=args.model,
            title_map=title_by_url,
            thinking_level=args.thinking_level,
            provider=args.provider,
            system_instruction=system_instruction,
            user_turn=user_turn,
        )
    except RuntimeError as exc:
        if "GEMINI_API_KEY" in str(exc) or "ANTIGRAVITY" in str(exc):
            logging.error("%s", exc)
            sys.exit(2)
        logging.exception("Configuration error")
        sys.exit(2)

    logging.info(
        "Done: attempted=%s succeeded=%s skipped=%s failed=%s",
        metrics.attempted,
        metrics.succeeded,
        metrics.skipped,
        metrics.failed,
    )
    code = _exit_code(metrics, had_work=total_urls > 0)
    sys.exit(code)


if __name__ == "__main__":
    main()
