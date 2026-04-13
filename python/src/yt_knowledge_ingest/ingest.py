from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from google import genai
from google.genai import errors as genai_errors

from .frontmatter import build_markdown, is_ok_skip_existing
from .fsutil import atomic_write_text
from .gemini_client import (
    DEFAULT_MODEL,
    iter_stream_video,
    make_client,
    make_client_or_none,
)
from .paths import playlist_dir_for_source, resolve_slug
from .prompts import DEFAULT_BUILTIN_SYSTEM_INSTRUCTION, USER_TURN_TEMPLATE
from .urls import read_urls_from_text

logger = logging.getLogger(__name__)

_tls = threading.local()


def _thread_client() -> genai.Client:
    c = getattr(_tls, "client", None)
    if c is None:
        c = make_client()
        _tls.client = c
    return c


@dataclass
class PlaylistSpec:
    label: str
    source_path: Path | None
    urls: list[str]


@dataclass
class RunMetrics:
    attempted: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0


def load_playlists_from_files(paths: list[Path]) -> list[PlaylistSpec]:
    specs: list[PlaylistSpec] = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        urls = read_urls_from_text(text)
        specs.append(
            PlaylistSpec(label=p.name, source_path=p, urls=urls),
        )
    return specs


def load_playlist_from_stdin() -> PlaylistSpec:
    import sys

    text = sys.stdin.read()
    urls = read_urls_from_text(text)
    return PlaylistSpec(label="stdin", source_path=None, urls=urls)


def _classify_error(exc: BaseException) -> str:
    if isinstance(exc, genai_errors.ClientError):
        return f"client_error: {exc}"
    if isinstance(exc, genai_errors.ServerError):
        return f"server_error: {exc}"
    return f"{type(exc).__name__}: {exc}"


def process_video_job(
    *,
    client: Union[genai.Client, object],
    model: str,
    out_root: Path,
    playlist_folder: str,
    playlist_human: str,
    url: str,
    title_map: dict[str, str] | None,
    force: bool,
    thinking_level: str = "minimal",
    provider: str = "gemini",
    system_instruction: str = DEFAULT_BUILTIN_SYSTEM_INSTRUCTION,
    user_turn: str = USER_TURN_TEMPLATE,
    write_to_disk: bool = False,
) -> tuple[bool, bool, str, str | None]:
    """Returns (succeeded, skipped, message, full_markdown_or_none).

    When ``write_to_disk`` is False (API default), no file is written; callers
    persist ``full_markdown`` themselves. CLI passes ``write_to_disk=True``.
    """
    slug = resolve_slug(url, title_map)
    dir_path = out_root / playlist_folder
    out_path = dir_path / f"{slug}.md"

    if write_to_disk and out_path.is_file() and not force:
        existing = out_path.read_text(encoding="utf-8")
        if is_ok_skip_existing(existing):
            return False, True, f"SKIP ok existing {out_path}", existing

    body_parts: list[str] = []
    try:
        if provider == "antigravity":
            from .antigravity import AntigravityClient, iter_stream_video as ag_iter

            assert isinstance(client, AntigravityClient)
            stream = ag_iter(
                url,
                model=model,
                client=client,
                thinking_level=thinking_level,
                system_instruction=system_instruction,
                user_turn=user_turn,
            )
        else:
            assert isinstance(client, genai.Client)
            stream = iter_stream_video(
                url,
                model=model,
                client=client,
                thinking_level=thinking_level,
                system_instruction=system_instruction,
                user_turn=user_turn,
            )

        for piece in stream:
            body_parts.append(piece)
        body = "".join(body_parts).strip()
        if not body:
            raise RuntimeError("empty model output")
        md = build_markdown(
            source_url=url,
            playlist=playlist_human,
            slug=slug,
            status="ok",
            error="",
            body=body,
        )
        if write_to_disk:
            atomic_write_text(out_path, md)
        return True, False, f"OK {out_path}", md
    except BaseException as exc:  # noqa: BLE001 — surface any API/stack failure
        err = _classify_error(exc)
        logger.exception("Failed for %s", url)
        fail_md = build_markdown(
            source_url=url,
            playlist=playlist_human,
            slug=slug,
            status="error",
            error=err,
            body=f"_Generation failed: {err}_\n",
        )
        if write_to_disk:
            atomic_write_text(out_path, fail_md)
        return False, False, f"FAIL {out_path}: {err}", fail_md


def run(
    playlists: list[PlaylistSpec],
    *,
    out_dir: Path,
    concurrency: int,
    force: bool,
    model: str,
    title_map: dict[str, str] | None,
    thinking_level: str = "minimal",
    client: Union[genai.Client, object, None] = None,
    provider: str = "gemini",
    system_instruction: str = DEFAULT_BUILTIN_SYSTEM_INSTRUCTION,
    user_turn: str = USER_TURN_TEMPLATE,
) -> RunMetrics:
    """Run ingest jobs with bounded thread parallelism.

    If ``client`` is omitted, each worker thread constructs its own client via
    :func:`make_client` (gemini provider) or :func:`make_antigravity_client`
    (antigravity provider).
    """
    metrics = RunMetrics()
    jobs: list[tuple[str, str, str]] = []
    for spec in playlists:
        folder = playlist_dir_for_source(spec.source_path, spec.label)
        human = spec.source_path.stem if spec.source_path else spec.label
        for url in spec.urls:
            jobs.append((folder, human, url))

    if not jobs:
        return metrics

    # Resolve the client once for the antigravity provider (shares token state)
    resolved_client: Union[genai.Client, object, None] = client
    if resolved_client is None and provider == "antigravity":
        from .antigravity import make_antigravity_client

        resolved_client = make_antigravity_client()

    def _task(args: tuple[str, str, str]) -> tuple[bool, bool, str]:
        folder, human, url = args
        if resolved_client is not None:
            worker_client = resolved_client
        elif provider == "gemini":
            worker_client = _thread_client()
        else:
            from .antigravity import make_antigravity_client

            worker_client = make_antigravity_client()
        return process_video_job(
            client=worker_client,
            model=model or DEFAULT_MODEL,
            out_root=out_dir,
            playlist_folder=folder,
            playlist_human=human,
            url=url,
            title_map=title_map,
            force=force,
            thinking_level=thinking_level,
            provider=provider,
            system_instruction=system_instruction,
            user_turn=user_turn,
            write_to_disk=True,
        )

    metrics.attempted = len(jobs)
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = [ex.submit(_task, (folder, human, url)) for folder, human, url in jobs]
        for fut in as_completed(futs):
            ok, skipped, msg, _md = fut.result()
            logger.info("%s", msg)
            if skipped:
                metrics.skipped += 1
            elif ok:
                metrics.succeeded += 1
            else:
                metrics.failed += 1
    return metrics
