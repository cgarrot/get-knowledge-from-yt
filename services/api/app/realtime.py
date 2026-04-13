"""In-process WebSocket broadcast for live UI updates (REST remains source of truth)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from .db import JobRow, get_job, job_counts, list_jobs_dashboard_view

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None
_connections: Set[WebSocket] = set()

_TERMINAL_STATUSES = frozenset({"ok", "error", "skipped", "cancelled"})


def bind_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def _job_payload(row: JobRow) -> dict[str, Any]:
    include_analysis = row.status in _TERMINAL_STATUSES
    return row.to_dict(include_analysis=include_analysis)


def build_snapshot_payload() -> dict[str, Any]:
    return {
        "counts": job_counts(),
        "recent": [j.to_dict() for j in list_jobs_dashboard_view(recent_limit=40)],
    }


async def _broadcast_raw(message: str) -> None:
    dead: list[WebSocket] = []
    for ws in list(_connections):
        try:
            await ws.send_text(message)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        _connections.discard(ws)


def schedule_broadcast(message: dict[str, Any]) -> None:
    """Thread-safe: schedule JSON broadcast on the API event loop."""
    global _loop
    if _loop is None:
        return
    raw = json.dumps(message, ensure_ascii=False)

    async def _run() -> None:
        await _broadcast_raw(raw)

    try:
        fut = asyncio.run_coroutine_threadsafe(_run(), _loop)

        def _log_err(f: asyncio.Future[None]) -> None:
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001
                logger.debug("WebSocket broadcast failed: %s", exc)

        fut.add_done_callback(_log_err)
    except RuntimeError as exc:
        logger.debug("Could not schedule WebSocket broadcast: %s", exc)


def emit_snapshot() -> None:
    schedule_broadcast({"type": "snapshot", "data": build_snapshot_payload()})


def emit_job_created(job_id: str) -> None:
    row = get_job(job_id)
    if row is None:
        return
    schedule_broadcast(
        {
            "type": "job_created",
            "data": {"job": _job_payload(row)},
        }
    )


def emit_job_updated(job_id: str, *, artifact_touched: bool = False) -> None:
    row = get_job(job_id)
    if row is None:
        return
    schedule_broadcast(
        {
            "type": "job_updated",
            "data": {"job": _job_payload(row)},
        }
    )
    if artifact_touched and row.output_rel_path:
        schedule_broadcast(
            {
                "type": "artifact_updated",
                "data": {"rel": row.output_rel_path},
            }
        )


def emit_job_cancelled(job_id: str) -> None:
    row = get_job(job_id)
    if row is None:
        return
    schedule_broadcast(
        {
            "type": "job_cancelled",
            "data": {"job": _job_payload(row)},
        }
    )


def emit_prompt_saved(name: str, source: str) -> None:
    schedule_broadcast(
        {
            "type": "prompt_saved",
            "data": {"name": name, "source": source},
        }
    )


def emit_prompt_deleted(name: str) -> None:
    schedule_broadcast(
        {
            "type": "prompt_deleted",
            "data": {"name": name},
        }
    )


async def handle_websocket(ws: WebSocket) -> None:
    await ws.accept()
    global _loop
    if _loop is None:
        bind_event_loop(asyncio.get_running_loop())
    _connections.add(ws)
    try:
        await ws.send_text(
            json.dumps(
                {"type": "snapshot", "data": build_snapshot_payload()},
                ensure_ascii=False,
            )
        )
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=25.0)
            except asyncio.TimeoutError:
                await ws.send_text(
                    json.dumps({"type": "heartbeat", "data": {}}, ensure_ascii=False)
                )
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)
