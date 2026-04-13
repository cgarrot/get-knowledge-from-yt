from __future__ import annotations

import json
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from dotenv import load_dotenv

from yt_knowledge_ingest.collection_classifier import classify_collection_folder
from yt_knowledge_ingest.gemini_client import DEFAULT_MODEL, make_client
from yt_knowledge_ingest.ingest import process_video_job
from yt_knowledge_ingest.paths import playlist_dir_for_source, resolve_slug
from yt_knowledge_ingest.prompts import load_prompt, split_prompt_markdown

from .config import (
    DEFAULT_WORKER_CONCURRENCY,
    OUTPUT_DIR,
    REPO_EXPORT_DIR,
    USER_PROMPTS_DIR,
    WRITE_OUTPUT_FILES,
)
from .db import (
    get_job,
    kv_get,
    list_classifier_folder_hints,
    list_pending_job_ids,
    update_job,
    user_prompt_get,
)
from .repo_export import mirror_markdown

load_dotenv()
logger = logging.getLogger(__name__)

_tls = threading.local()
_ag_lock = threading.Lock()
_ag_client: Optional[object] = None


def _thread_gemini_client():
    c = getattr(_tls, "gemini_client", None)
    if c is None:
        c = make_client()
        _tls.gemini_client = c
    return c


def _shared_antigravity_client() -> object:
    global _ag_client
    with _ag_lock:
        if _ag_client is None:
            from yt_knowledge_ingest.antigravity import make_antigravity_client

            _ag_client = make_antigravity_client()
        return _ag_client


def reset_antigravity_client() -> None:
    """Drop cached Antigravity client (e.g. after saving a new refresh token)."""
    global _ag_client
    with _ag_lock:
        _ag_client = None


def load_prompt_for_name(name: str) -> tuple[str, str]:
    raw = user_prompt_get(name)
    if raw is not None:
        return split_prompt_markdown(raw)
    user_path = USER_PROMPTS_DIR / f"{name}.md"
    if user_path.is_file():
        return load_prompt(name, USER_PROMPTS_DIR)
    return load_prompt(name, None)


def _maybe_mirror_repo(rel: str, analysis_text: Optional[str]) -> None:
    if not analysis_text or REPO_EXPORT_DIR is None:
        return
    try:
        mirror_markdown(REPO_EXPORT_DIR, rel, analysis_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Repo mirror failed for %s: %s", rel, exc)


def _classifier_kv_settings() -> tuple[str, str]:
    raw = kv_get("collection_classifier_settings")
    if not raw:
        return "minimal", ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "minimal", ""
    tl = data.get("thinking_level") or "minimal"
    instr = data.get("instructions") or ""
    return str(tl), str(instr)


def _resolve_client(provider: str):
    if provider == "antigravity":
        return _shared_antigravity_client()
    return _thread_gemini_client()


def resolve_provider_client(provider: str):
    """Return a Gemini API or Antigravity client for the given provider (shared with jobs)."""
    return _resolve_client(provider)


def process_one_job(job_id: str) -> None:
    row = get_job(job_id)
    if row is None or row.status != "pending":
        return

    update_job(job_id, status="processing", log_message="started")

    try:
        system_instruction, user_turn = load_prompt_for_name(row.prompt_name)
    except FileNotFoundError as exc:
        update_job(
            job_id,
            status="error",
            error_message=str(exc),
            log_message="prompt not found",
        )
        return

    title_map = None
    if row.auto_title:
        from yt_knowledge_ingest.youtube_titles import fetch_titles

        title_map = fetch_titles([row.url])

    playlist_label = row.playlist_label
    if row.playlist_auto:
        c_provider = row.classifier_provider or row.provider
        c_model = row.classifier_model or row.model
        c_thinking, c_extra = _classifier_kv_settings()
        c_client = _resolve_client(c_provider)
        resolved, cmsg = classify_collection_folder(
            url=row.url,
            out_root=OUTPUT_DIR,
            client=c_client,
            model=c_model,
            thinking_level=c_thinking,
            provider=c_provider,
            extra_instructions=c_extra,
            fallback_label=row.playlist_label or "default",
            existing_folder_hints=list_classifier_folder_hints(),
        )
        playlist_label = resolved
        update_job(job_id, playlist_label=playlist_label, log_message=f"collection {cmsg}")

    playlist_folder = playlist_dir_for_source(None, playlist_label)
    client = _resolve_client(row.provider)

    try:
        ok, skipped, msg, md_full = process_video_job(
            client=client,
            model=row.model or DEFAULT_MODEL,
            out_root=OUTPUT_DIR,
            playlist_folder=playlist_folder,
            playlist_human=playlist_label,
            url=row.url,
            title_map=title_map,
            force=row.force_ingest,
            thinking_level=row.thinking_level,
            provider=row.provider,
            system_instruction=system_instruction,
            user_turn=user_turn,
            write_to_disk=WRITE_OUTPUT_FILES,
        )
    except BaseException as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        update_job(
            job_id,
            status="error",
            error_message=f"{type(exc).__name__}: {exc}",
            log_message=str(exc),
        )
        return

    slug = resolve_slug(row.url, title_map)
    rel = f"{playlist_folder}/{slug}.md"
    out_full = OUTPUT_DIR / playlist_folder / f"{slug}.md"
    analysis_text: Optional[str] = md_full
    if analysis_text is None and WRITE_OUTPUT_FILES and out_full.is_file():
        try:
            analysis_text = out_full.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read analysis file %s: %s", out_full, exc)

    if skipped:
        update_job(
            job_id,
            status="skipped",
            output_rel_path=rel,
            log_message=msg,
            analysis_markdown=analysis_text,
        )
        _maybe_mirror_repo(rel, analysis_text)
    elif ok:
        update_job(
            job_id,
            status="ok",
            output_rel_path=rel,
            log_message=msg,
            analysis_markdown=analysis_text,
        )
        _maybe_mirror_repo(rel, analysis_text)
    else:
        update_job(
            job_id,
            status="error",
            output_rel_path=rel,
            log_message=msg,
            analysis_markdown=analysis_text,
        )
        _maybe_mirror_repo(rel, analysis_text)


class JobWorkerPool:
    def __init__(self, max_workers: Optional[int] = None):
        self._max_workers = max_workers or DEFAULT_WORKER_CONCURRENCY
        self._job_queue: queue.Queue[str] = queue.Queue()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._dispatcher: Optional[threading.Thread] = None
        self._started = threading.Event()

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def start(self) -> None:
        if self._dispatcher and self._dispatcher.is_alive():
            return
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        def dispatch() -> None:
            assert self._executor is not None
            while True:
                jid = self._job_queue.get()
                self._executor.submit(self._run_job, jid)

        self._dispatcher = threading.Thread(target=dispatch, daemon=True)
        self._dispatcher.start()
        for jid in list_pending_job_ids():
            self._job_queue.put(jid)
        self._started.set()

    @staticmethod
    def _run_job(job_id: str) -> None:
        process_one_job(job_id)

    def enqueue(self, job_id: str) -> None:
        self._started.wait(timeout=5.0)
        self._job_queue.put(job_id)


pool = JobWorkerPool()
