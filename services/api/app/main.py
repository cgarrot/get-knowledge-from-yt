from __future__ import annotations

import asyncio
import json
import logging
import os
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, List, Literal, Optional, Union

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from yt_knowledge_ingest.auto_ingest_prompt import (
    allocate_prompt_name,
    build_video_type_from_reference_urls,
)
from yt_knowledge_ingest.gemini_client import DEFAULT_MODEL, THINKING_LEVELS, make_client_or_none
from yt_knowledge_ingest.prompt_generator import generate_prompt_markdown
from yt_knowledge_ingest.model_options import (
    ANTIGRAVITY_MODEL_IDS,
    DEFAULT_ANTIGRAVITY_MODEL,
    DEFAULT_GEMINI_API_MODEL,
    GEMINI_API_MODEL_IDS,
    default_model_for_provider,
    models_for_provider,
)
from yt_knowledge_ingest.urls import read_urls_from_text

from . import antigravity_auth
from .config import (
    DB_PATH,
    DATA_DIR,
    OUTPUT_DIR,
    REPO_EXPORT_DIR,
    REPO_EXPORT_INVALID_RAW,
    REPO_EXPORT_PATH_STR,
    REPO_ROOT,
    USER_PROMPTS_DIR,
    WRITE_OUTPUT_FILES,
)
from .db import (
    artifact_tree_from_db,
    fetch_prompts_catalog,
    get_analysis_markdown_by_rel,
    cancel_pending_job,
    requeue_failed_job,
    get_job,
    get_latest_job_by_output_rel,
    init_db,
    insert_job,
    insert_prompt_generate_job,
    iter_zip_analysis_rows,
    job_counts,
    kv_get,
    kv_set,
    list_jobs,
    list_jobs_dashboard_view,
    sync_prompts_catalog,
    user_prompt_delete,
    user_prompt_get,
    user_prompt_upsert,
)
from .repo_export import mirror_markdown
from . import realtime
from .worker import pool, resolve_provider_client

COLLECTION_CLASSIFIER_SETTINGS_KEY = "collection_classifier_settings"

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BUILTIN_PROMPTS_DIR = (
    REPO_ROOT / "python" / "src" / "yt_knowledge_ingest" / "prompts"
)

app = FastAPI(title="get-knowledge-from-yt API", version="0.1.0")
app.include_router(antigravity_auth.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3030",
        "http://127.0.0.1:3030",
    ],
    # Dev: any port on localhost / 127.0.0.1 / ::1 (POST logout was blocked when origin not listed).
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup_realtime_loop() -> None:
    realtime.bind_event_loop(asyncio.get_running_loop())


@app.on_event("startup")
def _startup() -> None:
    if "GKFY_DATA_DIR" not in os.environ:
        os.environ["GKFY_DATA_DIR"] = str(DATA_DIR)
    os.environ["ANTIGRAVITY_REFRESH_TOKEN_FILE"] = str(
        DATA_DIR / "antigravity_refresh_token.txt"
    )
    init_db()
    sync_prompts_catalog(BUILTIN_PROMPTS_DIR, USER_PROMPTS_DIR)
    if REPO_EXPORT_INVALID_RAW:
        logger.warning(
            "GKFY_REPO_EXPORT_DIR ignored (must stay under repo root): %s",
            REPO_EXPORT_INVALID_RAW,
        )
    antigravity_auth.start_antigravity_oauth_loopback_server()
    pool.start()
    logger.info(
        "Worker pool started (concurrency=%s, write_output_files=%s)",
        pool.max_workers,
        WRITE_OUTPUT_FILES,
    )


class CollectionClassifierSettingsBody(BaseModel):
    default_provider: Literal["gemini", "antigravity"] = "gemini"
    default_model: str = ""
    thinking_level: Literal["minimal", "low", "medium", "high"] = "minimal"
    instructions: str = ""


def _load_collection_classifier_kv() -> dict[str, Any]:
    raw = kv_get(COLLECTION_CLASSIFIER_SETTINGS_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


@app.get("/settings/collection-classifier")
def get_collection_classifier_settings() -> dict[str, Any]:
    data = _load_collection_classifier_kv()
    prov = data.get("default_provider", "gemini")
    if prov not in ("gemini", "antigravity"):
        prov = "gemini"
    model = (data.get("default_model") or "").strip()
    allowed = set(models_for_provider(prov))
    if not model or model not in allowed:
        model = default_model_for_provider(prov)
    tl = data.get("thinking_level", "minimal")
    if tl not in THINKING_LEVELS:
        tl = "minimal"
    instructions = data.get("instructions") or ""
    return {
        "default_provider": prov,
        "default_model": model,
        "thinking_level": tl,
        "instructions": str(instructions),
    }


@app.put("/settings/collection-classifier")
def put_collection_classifier_settings(
    body: CollectionClassifierSettingsBody,
) -> dict[str, Any]:
    allowed = set(models_for_provider(body.default_provider))
    model = body.default_model
    if not model or model not in allowed:
        model = default_model_for_provider(body.default_provider)
    tl = body.thinking_level
    if tl not in THINKING_LEVELS:
        tl = "minimal"
    payload = {
        "default_provider": body.default_provider,
        "default_model": model,
        "thinking_level": tl,
        "instructions": body.instructions or "",
    }
    kv_set(COLLECTION_CLASSIFIER_SETTINGS_KEY, json.dumps(payload, ensure_ascii=False))
    return payload


@app.get("/options/models")
def options_models() -> dict[str, Any]:
    """Model IDs per provider (Gemini API vs Antigravity proxy differ)."""
    return {
        "gemini": {
            "default": DEFAULT_GEMINI_API_MODEL,
            "models": list(GEMINI_API_MODEL_IDS),
        },
        "antigravity": {
            "default": DEFAULT_ANTIGRAVITY_MODEL,
            "models": list(ANTIGRAVITY_MODEL_IDS),
        },
    }


def _safe_output_rel(rel: str) -> Path:
    if ".." in rel or rel.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    base = OUTPUT_DIR.resolve()
    full = (base / rel).resolve()
    try:
        full.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path outside output") from exc
    return full


def _merge_disk_into_tree(by_dir: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {k: list(v) for k, v in by_dir.items()}
    if not WRITE_OUTPUT_FILES or not OUTPUT_DIR.is_dir():
        return merged
    base = OUTPUT_DIR.resolve()
    for f in base.rglob("*.md"):
        if not f.is_file():
            continue
        rel = f.relative_to(base)
        parent = rel.parent.as_posix()
        key = "" if parent == "." else parent
        merged.setdefault(key, []).append(rel.name)
    for k in merged:
        merged[k] = sorted(set(merged[k]))
    return merged


def _tree_to_playlists(by_dir: dict[str, list[str]]) -> list[dict[str, Any]]:
    playlists: list[dict[str, Any]] = []
    for name in sorted(by_dir.keys(), key=lambda s: (s != "", s.lower())):
        playlists.append(
            {
                "name": name if name else ".",
                "files": by_dir[name],
            }
        )
    return playlists


class EnqueueRequest(BaseModel):
    urls: Union[str, List[str]] = Field(
        ...,
        description="YouTube URLs as list or newline-separated text",
    )
    playlist_label: str = "default"
    playlist_auto: bool = False
    classifier_provider: Optional[Literal["gemini", "antigravity"]] = None
    classifier_model: Optional[str] = None
    model: str = DEFAULT_MODEL
    thinking_level: Literal["minimal", "low", "medium", "high"] = "minimal"
    provider: Literal["gemini", "antigravity"] = "gemini"
    force: bool = False
    prompt: str = "default"
    auto_title: bool = False
    auto_generate_prompt: bool = False
    prompt_reference_count: int = Field(
        3,
        ge=1,
        le=3,
        description="First N URLs used as multimodal references for template generation",
    )
    prompt_gen_thinking_level: Literal["minimal", "low", "medium", "high"] = "medium"


class EnqueueResponse(BaseModel):
    job_ids: list[str]
    urls: list[str]
    generated_prompt_name: Optional[str] = None


@app.post("/jobs", response_model=EnqueueResponse)
def create_jobs(body: EnqueueRequest) -> EnqueueResponse:
    if isinstance(body.urls, list):
        text = "\n".join(body.urls)
    else:
        text = body.urls
    urls = read_urls_from_text(text)
    if not urls:
        raise HTTPException(status_code=400, detail="No valid YouTube URLs")
    if body.thinking_level not in THINKING_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid thinking_level")

    allowed_models = set(models_for_provider(body.provider))
    resolved_model = (
        body.model
        if body.model in allowed_models
        else default_model_for_provider(body.provider)
    )
    if resolved_model != body.model:
        logger.info(
            "Adjusted model for provider=%s: %r -> %r",
            body.provider,
            body.model,
            resolved_model,
        )

    cp_override: Optional[str] = None
    cm_override: Optional[str] = None
    if body.playlist_auto:
        prov_c = body.classifier_provider or body.provider
        allowed_c = set(models_for_provider(prov_c))
        cm_raw = body.classifier_model
        if cm_raw and cm_raw in allowed_c:
            cm_override = cm_raw
        elif cm_raw:
            cm_adj = default_model_for_provider(prov_c)
            logger.info(
                "Adjusted classifier model for provider=%s: %r -> %r",
                prov_c,
                cm_raw,
                cm_adj,
            )
            cm_override = cm_adj
        if body.classifier_provider is not None:
            cp_override = body.classifier_provider

    generated_prompt_name: Optional[str] = None
    prompt_for_jobs = body.prompt
    if body.auto_generate_prompt:
        k = max(1, min(body.prompt_reference_count, len(urls)))
        ref_urls = urls[:k]
        video_type = build_video_type_from_reference_urls(ref_urls)
        if body.provider == "gemini" and make_client_or_none() is None:
            raise HTTPException(
                status_code=503,
                detail="GEMINI_API_KEY is not set",
            )
        try:
            client = resolve_provider_client(body.provider)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        tl_gen = body.prompt_gen_thinking_level
        if tl_gen not in THINKING_LEVELS:
            tl_gen = "medium"
        try:
            prompt_markdown = generate_prompt_markdown(
                client=client,
                provider=body.provider,
                model=resolved_model,
                video_type=video_type,
                thinking_level=tl_gen,
                extra_notes="",
                video_urls=ref_urls,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc

        sync_prompts_catalog(BUILTIN_PROMPTS_DIR, USER_PROMPTS_DIR)
        existing = {n for n, _ in fetch_prompts_catalog()}
        new_prompt_name = allocate_prompt_name(video_type, existing)
        user_prompt_upsert(new_prompt_name, prompt_markdown)
        sync_prompts_catalog(BUILTIN_PROMPTS_DIR, USER_PROMPTS_DIR)
        realtime.emit_prompt_saved(new_prompt_name, "user")
        if REPO_EXPORT_DIR is not None:
            try:
                mirror_markdown(
                    REPO_EXPORT_DIR,
                    f"prompts/{new_prompt_name}.md",
                    prompt_markdown,
                )
            except Exception as exc:
                logger.warning(
                    "Repo mirror failed for prompt %s: %s",
                    new_prompt_name,
                    exc,
                )
        prompt_for_jobs = new_prompt_name
        generated_prompt_name = new_prompt_name

    job_ids: list[str] = []
    for url in urls:
        jid = insert_job(
            url=url,
            playlist_label=body.playlist_label,
            model=resolved_model,
            thinking_level=body.thinking_level,
            provider=body.provider,
            force=body.force,
            prompt_name=prompt_for_jobs,
            auto_title=body.auto_title,
            playlist_auto=body.playlist_auto,
            classifier_provider=cp_override if body.playlist_auto else None,
            classifier_model=cm_override if body.playlist_auto else None,
        )
        job_ids.append(jid)
        pool.enqueue(jid)
    return EnqueueResponse(
        job_ids=job_ids,
        urls=urls,
        generated_prompt_name=generated_prompt_name,
    )


@app.get("/jobs")
def get_jobs(
    limit: int = Query(200, ge=1, le=1000),
    status: Optional[str] = None,
    dashboard: bool = Query(
        False,
        description="If true, return queued pending jobs plus the most recent others (limit = recent slice).",
    ),
) -> dict[str, Any]:
    if dashboard:
        rows = list_jobs_dashboard_view(recent_limit=min(limit, 100))
    else:
        rows = list_jobs(limit=limit, status=status)
    return {"jobs": [r.to_dict() for r in rows]}


@app.get("/jobs/summary")
def jobs_summary() -> dict[str, Any]:
    counts = job_counts()
    return {"counts": counts}


@app.get("/jobs/by-output")
def get_job_by_output(rel: str = Query(..., min_length=1)) -> dict[str, Any]:
    """Resolve the latest job metadata for an analysis path (under ``data/output``)."""
    _safe_output_rel(rel)
    row = get_latest_job_by_output_rel(rel)
    if row is None:
        raise HTTPException(
            status_code=404, detail="No job found for this output path"
        )
    return row.to_dict()


@app.get("/jobs/{job_id}")
def get_job_detail(job_id: str) -> dict[str, Any]:
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row.to_dict(include_analysis=True)


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    """Remove a pending job from the queue (in-memory worker will no-op when it runs)."""
    if cancel_pending_job(job_id):
        row = get_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return row.to_dict()
    row = get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    raise HTTPException(
        status_code=409,
        detail=f"Job cannot be cancelled (status: {row.status})",
    )


@app.post("/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict[str, Any]:
    """Put a failed (*error*) job back in the worker queue with the same parameters."""
    if requeue_failed_job(job_id):
        pool.enqueue(job_id)
        row = get_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return row.to_dict()
    row = get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    raise HTTPException(
        status_code=409,
        detail=f"Job cannot be retried (status: {row.status})",
    )


@app.get("/jobs/stream")
async def jobs_stream() -> StreamingResponse:
    async def gen():
        while True:
            payload = {
                "counts": job_counts(),
                "recent": [
                    j.to_dict() for j in list_jobs_dashboard_view(recent_limit=30)
                ],
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.websocket("/ws")
async def websocket_live(ws: WebSocket) -> None:
    await realtime.handle_websocket(ws)


@app.get("/prompts")
def prompts_list() -> dict[str, Any]:
    sync_prompts_catalog(BUILTIN_PROMPTS_DIR, USER_PROMPTS_DIR)
    rows = fetch_prompts_catalog()
    return {
        "prompts": [{"name": n, "source": s} for n, s in rows],
    }


class PromptGenerateBody(BaseModel):
    provider: Literal["gemini", "antigravity"] = "gemini"
    model: str = ""
    video_type: str = Field(..., min_length=1, max_length=2000)
    thinking_level: Literal["minimal", "low", "medium", "high"] = "medium"
    extra_notes: str = Field("", max_length=4000)
    video_urls: List[str] = Field(
        default_factory=list,
        description="Optional YouTube URLs (one multimodal signal per provider rules)",
    )
    enqueue: bool = Field(
        False,
        description="If true, run via the same worker queue as video jobs.",
    )
    save_to_name: Optional[str] = Field(
        None,
        max_length=200,
        description="If set, persist under this user prompt name when the job completes.",
    )

    @field_validator("video_urls")
    @classmethod
    def _cap_video_urls(cls, v: List[str]) -> List[str]:
        if len(v) > 8:
            raise ValueError("At most 8 entries in video_urls")
        return v

    @field_validator("save_to_name")
    @classmethod
    def _safe_save_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        s = str(v).strip()
        if "/" in s or ".." in s or not s:
            raise ValueError("Invalid save_to_name")
        return s


@app.post("/prompts/generate")
def prompts_generate(body: PromptGenerateBody) -> dict[str, Any]:
    """Generate a prompt template (.md) via LLM from a video type description."""
    allowed = set(models_for_provider(body.provider))
    model = (body.model or "").strip()
    if not model or model not in allowed:
        model = default_model_for_provider(body.provider)
    tl = body.thinking_level
    if tl not in THINKING_LEVELS:
        tl = "medium"

    if body.provider == "gemini" and make_client_or_none() is None:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set",
        )

    try:
        resolve_provider_client(body.provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if body.enqueue:
        payload = {
            "video_type": body.video_type,
            "extra_notes": body.extra_notes,
            "video_urls": body.video_urls,
            "save_to_name": body.save_to_name,
        }
        jid = insert_prompt_generate_job(
            model=model,
            thinking_level=tl,
            provider=body.provider,
            payload=payload,
        )
        pool.enqueue(jid)
        return {"job_id": jid, "queued": True}

    try:
        client = resolve_provider_client(body.provider)
        content = generate_prompt_markdown(
            client=client,
            provider=body.provider,
            model=model,
            video_type=body.video_type,
            thinking_level=tl,
            extra_notes=body.extra_notes,
            video_urls=body.video_urls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    return {"content": content, "queued": False}


@app.get("/prompts/{name}")
def prompt_get(name: str) -> dict[str, str]:
    if "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid name")
    db_body = user_prompt_get(name)
    if db_body is not None:
        return {"name": name, "source": "user", "content": db_body}
    user = USER_PROMPTS_DIR / f"{name}.md"
    if user.is_file():
        return {"name": name, "source": "user", "content": user.read_text(encoding="utf-8")}
    builtin = BUILTIN_PROMPTS_DIR / f"{name}.md"
    if builtin.is_file():
        return {
            "name": name,
            "source": "builtin",
            "content": builtin.read_text(encoding="utf-8"),
        }
    from yt_knowledge_ingest.prompts import builtin_prompt_markdown

    embedded = builtin_prompt_markdown(name)
    if embedded is not None:
        return {"name": name, "source": "builtin", "content": embedded}
    raise HTTPException(status_code=404, detail="Prompt not found")


class PromptPut(BaseModel):
    content: str


@app.put("/prompts/{name}")
def prompt_put(name: str, body: PromptPut) -> dict[str, str]:
    if "/" in name or ".." in name or not name.strip():
        raise HTTPException(status_code=400, detail="Invalid name")
    user_prompt_upsert(name, body.content)
    sync_prompts_catalog(BUILTIN_PROMPTS_DIR, USER_PROMPTS_DIR)
    if REPO_EXPORT_DIR is not None:
        try:
            mirror_markdown(REPO_EXPORT_DIR, f"prompts/{name}.md", body.content)
        except Exception as exc:
            logger.warning("Repo mirror failed for prompt %s: %s", name, exc)
    realtime.emit_prompt_saved(name, "user")
    return {"name": name, "source": "user", "content": body.content}


@app.delete("/prompts/{name}")
def prompt_delete(name: str) -> dict[str, bool]:
    if "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid name")
    removed_db = user_prompt_delete(name)
    path = USER_PROMPTS_DIR / f"{name}.md"
    had_file = path.is_file()
    if not removed_db and not had_file:
        raise HTTPException(status_code=404, detail="User prompt not found")
    if had_file:
        path.unlink()
    sync_prompts_catalog(BUILTIN_PROMPTS_DIR, USER_PROMPTS_DIR)
    realtime.emit_prompt_deleted(name)
    return {"deleted": True}


@app.get("/artifacts/tree")
def artifacts_tree() -> dict[str, Any]:
    by_dir = _merge_disk_into_tree(artifact_tree_from_db())
    return {"playlists": _tree_to_playlists(by_dir)}


@app.get("/artifacts/raw")
def artifact_raw(rel: str = Query(..., description="Relative path under output")):
    path = _safe_output_rel(rel)
    if WRITE_OUTPUT_FILES and path.is_file():
        return FileResponse(
            path,
            media_type="text/markdown; charset=utf-8",
            filename=path.name,
        )
    body = get_analysis_markdown_by_rel(rel)
    if body is None:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(
        content=body.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"',
        },
    )


@app.get("/artifacts/content")
def artifact_content(rel: str = Query(...)) -> dict[str, str]:
    path = _safe_output_rel(rel)
    if WRITE_OUTPUT_FILES and path.is_file():
        return {"path": rel, "content": path.read_text(encoding="utf-8")}
    body = get_analysis_markdown_by_rel(rel)
    if body is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": rel, "content": body}


@app.get("/artifacts/zip")
def artifact_zip(playlist: Optional[str] = Query(None)) -> Response:
    buf = BytesIO()
    written: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, body in iter_zip_analysis_rows(playlist):
            zf.writestr(rel, body)
            written.add(rel)
        if WRITE_OUTPUT_FILES and OUTPUT_DIR.is_dir():
            base = OUTPUT_DIR.resolve()
            if playlist:
                sub = (base / playlist).resolve()
                try:
                    sub.relative_to(base)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail="Invalid playlist") from exc
                if sub.is_dir():
                    for f in sub.rglob("*.md"):
                        arc = str(f.relative_to(base))
                        if arc not in written:
                            zf.write(f, arc)
            else:
                for f in base.rglob("*.md"):
                    arc = str(f.relative_to(base))
                    if arc not in written:
                        zf.write(f, arc)
    buf.seek(0)
    name = f"{playlist or 'all'}-wiki.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "database": str(DB_PATH),
        "write_output_files": str(WRITE_OUTPUT_FILES),
        "repo_export_dir": REPO_EXPORT_PATH_STR,
    }
