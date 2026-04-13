from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import DATA_DIR, DB_PATH, OUTPUT_DIR, USER_PROMPTS_DIR

_db_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate_jobs(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(jobs)")
    cols = {str(row[1]) for row in cur.fetchall()}
    if "playlist_auto" not in cols:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN playlist_auto INTEGER NOT NULL DEFAULT 0"
        )
    if "classifier_provider" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN classifier_provider TEXT")
    if "classifier_model" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN classifier_model TEXT")
    if "analysis_markdown" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN analysis_markdown TEXT")
    if "job_kind" not in cols:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN job_kind TEXT NOT NULL DEFAULT 'video'"
        )
    if "payload_json" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN payload_json TEXT")


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    USER_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    with _db_lock, sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              url TEXT NOT NULL,
              playlist_label TEXT NOT NULL DEFAULT 'default',
              status TEXT NOT NULL,
              model TEXT NOT NULL,
              thinking_level TEXT NOT NULL,
              provider TEXT NOT NULL,
              force_ingest INTEGER NOT NULL DEFAULT 0,
              prompt_name TEXT NOT NULL,
              auto_title INTEGER NOT NULL DEFAULT 0,
              output_rel_path TEXT,
              error_message TEXT,
              log_message TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prompts_catalog (
              name TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_kv (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_prompts (
              name TEXT PRIMARY KEY,
              content TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        now = _utc_now()
        conn.execute(
            """
            INSERT OR IGNORE INTO app_kv (key, value, updated_at)
            VALUES ('schema_version', '2', ?)
            """,
            (now,),
        )
        _migrate_jobs(conn)
        conn.commit()
    migrate_user_prompts_from_filesystem(USER_PROMPTS_DIR)


def migrate_user_prompts_from_filesystem(user_dir: Path) -> None:
    """Import legacy ``data/prompts/*.md`` into SQLite when the name is not yet in DB."""
    if not user_dir.is_dir():
        return
    with get_conn() as conn:
        for p in user_dir.glob("*.md"):
            name = p.stem
            cur = conn.execute(
                "SELECT 1 FROM user_prompts WHERE name = ?", (name,)
            )
            if cur.fetchone() is not None:
                continue
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                continue
            now = _utc_now()
            conn.execute(
                """
                INSERT INTO user_prompts (name, content, updated_at)
                VALUES (?, ?, ?)
                """,
                (name, content, now),
            )
        conn.commit()


def user_prompt_get(name: str) -> Optional[str]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT content FROM user_prompts WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        return str(row["content"]) if row else None


def user_prompt_upsert(name: str, content: str) -> None:
    now = _utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_prompts (name, content, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET content = excluded.content,
              updated_at = excluded.updated_at
            """,
            (name, content, now),
        )
        conn.commit()


def user_prompt_delete(name: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM user_prompts WHERE name = ?", (name,))
        conn.commit()
        return cur.rowcount > 0


def iter_user_prompt_names() -> list[str]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT name FROM user_prompts ORDER BY name COLLATE NOCASE"
        )
        return [str(r[0]) for r in cur.fetchall()]


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=60.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


@dataclass
class JobRow:
    id: str
    url: str
    playlist_label: str
    status: str
    model: str
    thinking_level: str
    provider: str
    force_ingest: bool
    prompt_name: str
    auto_title: bool
    playlist_auto: bool
    classifier_provider: Optional[str]
    classifier_model: Optional[str]
    analysis_markdown: Optional[str]
    output_rel_path: Optional[str]
    error_message: Optional[str]
    log_message: Optional[str]
    job_kind: str
    payload_json: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobRow:
        keys = row.keys()
        return cls(
            id=row["id"],
            url=row["url"],
            playlist_label=row["playlist_label"],
            status=row["status"],
            model=row["model"],
            thinking_level=row["thinking_level"],
            provider=row["provider"],
            force_ingest=bool(row["force_ingest"]),
            prompt_name=row["prompt_name"],
            auto_title=bool(row["auto_title"]),
            playlist_auto=bool(row["playlist_auto"]) if "playlist_auto" in keys else False,
            classifier_provider=(
                row["classifier_provider"]
                if "classifier_provider" in keys
                else None
            ),
            classifier_model=(
                row["classifier_model"] if "classifier_model" in keys else None
            ),
            analysis_markdown=(
                row["analysis_markdown"] if "analysis_markdown" in keys else None
            ),
            output_rel_path=row["output_rel_path"],
            error_message=row["error_message"],
            log_message=row["log_message"],
            job_kind=(
                str(row["job_kind"]) if "job_kind" in keys else "video"
            ),
            payload_json=(
                str(row["payload_json"])
                if "payload_json" in keys and row["payload_json"] is not None
                else None
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self, *, include_analysis: bool = False) -> dict[str, Any]:
        """include_analysis: full markdown (can be large); omit in list/stream endpoints."""
        d: dict[str, Any] = {
            "id": self.id,
            "url": self.url,
            "playlist_label": self.playlist_label,
            "status": self.status,
            "model": self.model,
            "thinking_level": self.thinking_level,
            "provider": self.provider,
            "force": self.force_ingest,
            "prompt_name": self.prompt_name,
            "auto_title": self.auto_title,
            "playlist_auto": self.playlist_auto,
            "classifier_provider": self.classifier_provider,
            "classifier_model": self.classifier_model,
            "output_rel_path": self.output_rel_path,
            "error_message": self.error_message,
            "log_message": self.log_message,
            "job_kind": self.job_kind,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.payload_json:
            try:
                d["payload"] = json.loads(self.payload_json)
            except json.JSONDecodeError:
                d["payload"] = None
        else:
            d["payload"] = None
        if include_analysis:
            d["analysis_markdown"] = self.analysis_markdown
        return d


def insert_job(
    *,
    url: str,
    playlist_label: str,
    model: str,
    thinking_level: str,
    provider: str,
    force: bool,
    prompt_name: str,
    auto_title: bool,
    playlist_auto: bool = False,
    classifier_provider: Optional[str] = None,
    classifier_model: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    now = _utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, url, playlist_label, status, model, thinking_level, provider,
              force_ingest, prompt_name, auto_title, playlist_auto,
              classifier_provider, classifier_model, job_kind, payload_json,
              output_rel_path, error_message, log_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'video', NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                url,
                playlist_label,
                "pending",
                model,
                thinking_level,
                provider,
                1 if force else 0,
                prompt_name,
                1 if auto_title else 0,
                1 if playlist_auto else 0,
                classifier_provider,
                classifier_model,
                now,
                now,
            ),
        )
        conn.commit()
    try:
        from . import realtime

        realtime.emit_job_created(job_id)
    except Exception:  # noqa: BLE001
        pass
    return job_id


PROMPT_GENERATE_JOB_URL = "gkfy:prompt-generate"
PROMPT_GENERATE_JOB_PROMPT_NAME = "_prompt_generate_"


def insert_prompt_generate_job(
    *,
    model: str,
    thinking_level: str,
    provider: str,
    payload: dict[str, Any],
) -> str:
    """Queue LLM prompt-template generation (same worker pool as video jobs)."""
    job_id = str(uuid.uuid4())
    now = _utc_now()
    payload_s = json.dumps(payload, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, url, playlist_label, status, model, thinking_level, provider,
              force_ingest, prompt_name, auto_title, playlist_auto,
              classifier_provider, classifier_model, job_kind, payload_json,
              output_rel_path, error_message, log_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 0, 0, NULL, NULL, 'prompt_generate', ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                PROMPT_GENERATE_JOB_URL,
                "prompts",
                "pending",
                model,
                thinking_level,
                provider,
                PROMPT_GENERATE_JOB_PROMPT_NAME,
                payload_s,
                now,
                now,
            ),
        )
        conn.commit()
    try:
        from . import realtime

        realtime.emit_job_created(job_id)
    except Exception:  # noqa: BLE001
        pass
    return job_id


def cancel_pending_job(job_id: str) -> bool:
    """Mark a job as cancelled if it is still pending. Returns True if a row was updated."""
    now = _utc_now()
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
            SET status = 'cancelled',
                log_message = 'cancelled (removed from queue)',
                updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, job_id),
        )
        conn.commit()
        ok = cur.rowcount > 0
    if ok:
        try:
            from . import realtime

            realtime.emit_job_cancelled(job_id)
        except Exception:  # noqa: BLE001
            pass
    return ok


def update_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    playlist_label: Optional[str] = None,
    output_rel_path: Optional[str] = None,
    error_message: Optional[str] = None,
    log_message: Optional[str] = None,
    analysis_markdown: Optional[str] = None,
) -> None:
    fields: list[str] = []
    values: list[Any] = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if playlist_label is not None:
        fields.append("playlist_label = ?")
        values.append(playlist_label)
    if output_rel_path is not None:
        fields.append("output_rel_path = ?")
        values.append(output_rel_path)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if log_message is not None:
        fields.append("log_message = ?")
        values.append(log_message)
    if analysis_markdown is not None:
        fields.append("analysis_markdown = ?")
        values.append(analysis_markdown)
    if not fields:
        return
    artifact_touched = output_rel_path is not None or analysis_markdown is not None
    fields.append("updated_at = ?")
    values.append(_utc_now())
    values.append(job_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    try:
        from . import realtime

        realtime.emit_job_updated(job_id, artifact_touched=artifact_touched)
    except Exception:  # noqa: BLE001
        pass


def get_job(job_id: str) -> Optional[JobRow]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        return JobRow.from_row(row) if row else None


def get_latest_job_by_output_rel(output_rel_path: str) -> Optional[JobRow]:
    """Most recently updated job for this output path (e.g. ``playlist/slug.md``)."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM jobs
            WHERE output_rel_path = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (output_rel_path,),
        )
        row = cur.fetchone()
        return JobRow.from_row(row) if row else None


def list_jobs(
    *,
    limit: int = 200,
    status: Optional[str] = None,
) -> list[JobRow]:
    q = "SELECT * FROM jobs"
    args: list[Any] = []
    if status:
        q += " WHERE status = ?"
        args.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with get_conn() as conn:
        cur = conn.execute(q, args)
        return [JobRow.from_row(r) for r in cur.fetchall()]


def list_jobs_dashboard_view(
    *,
    recent_limit: int = 40,
    pending_limit: int = 500,
) -> list[JobRow]:
    """Pending jobs (queue) plus recent activity; pending first FIFO, then newest non-pending."""
    pending_rows = list_jobs(limit=pending_limit, status="pending")
    pending_sorted = sorted(pending_rows, key=lambda r: r.created_at)
    seen = {r.id for r in pending_sorted}
    recent_rows = list_jobs(limit=recent_limit)
    tail = [r for r in recent_rows if r.id not in seen]
    return list(pending_sorted) + tail


def list_pending_job_ids() -> list[str]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id FROM jobs WHERE status = 'pending' ORDER BY created_at ASC"
        )
        return [r[0] for r in cur.fetchall()]


def job_counts() -> dict[str, int]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT status, COUNT(*) FROM jobs GROUP BY status"
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def sync_prompts_catalog(builtin_dir: Path, user_dir: Path) -> None:
    """Rebuild prompts_catalog from built-in package dir + user prompts (DB + legacy files)."""
    from yt_knowledge_ingest.prompts import builtin_prompt_names_for_catalog

    catalog: dict[str, str] = {}
    for stem in builtin_prompt_names_for_catalog():
        catalog[stem] = "builtin"
    if builtin_dir.is_dir():
        for p in builtin_dir.glob("*.md"):
            catalog[p.stem] = "builtin"
    user_names = set(iter_user_prompt_names())
    if user_dir.is_dir():
        for p in user_dir.glob("*.md"):
            user_names.add(p.stem)
    for stem in user_names:
        catalog[stem] = "user"
    now = _utc_now()
    with get_conn() as conn:
        conn.execute("DELETE FROM prompts_catalog")
        for name, source in sorted(catalog.items(), key=lambda x: x[0].lower()):
            conn.execute(
                "INSERT INTO prompts_catalog (name, source, updated_at) VALUES (?, ?, ?)",
                (name, source, now),
            )
        conn.commit()


def fetch_prompts_catalog() -> list[tuple[str, str]]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT name, source FROM prompts_catalog ORDER BY name COLLATE NOCASE"
        )
        return [(str(r[0]), str(r[1])) for r in cur.fetchall()]


def _latest_analysis_rels_ordered() -> list[str]:
    """Distinct output paths, newest job first (one entry per path)."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT output_rel_path, updated_at FROM jobs
            WHERE output_rel_path IS NOT NULL AND analysis_markdown IS NOT NULL
            ORDER BY updated_at DESC
            """
        )
        seen: set[str] = set()
        out: list[str] = []
        for row in cur:
            rel = str(row["output_rel_path"])
            if rel in seen:
                continue
            seen.add(rel)
            out.append(rel)
        return out


def list_classifier_folder_hints(limit: int = 200) -> list[str]:
    """Parent directory paths (posix) under output, from stored analyses."""
    folders: set[str] = set()
    for rel in _latest_analysis_rels_ordered():
        parent = Path(rel).parent.as_posix()
        if parent not in (".", ""):
            folders.add(parent)
    return sorted(folders)[:limit]


def artifact_tree_from_db() -> dict[str, list[str]]:
    """Map parent dir key ('' = root) -> markdown basenames."""
    by_dir: dict[str, list[str]] = {}
    for rel in _latest_analysis_rels_ordered():
        p = Path(rel)
        parent = p.parent.as_posix()
        key = "" if parent == "." else parent
        by_dir.setdefault(key, []).append(p.name)
    for k in by_dir:
        by_dir[k] = sorted(set(by_dir[k]))
    return by_dir


def get_analysis_markdown_by_rel(rel: str) -> Optional[str]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT analysis_markdown FROM jobs
            WHERE output_rel_path = ? AND analysis_markdown IS NOT NULL
            ORDER BY updated_at DESC LIMIT 1
            """,
            (rel,),
        )
        row = cur.fetchone()
        return str(row["analysis_markdown"]) if row else None


def iter_zip_analysis_rows(
    playlist_prefix: Optional[str] = None,
) -> Iterator[tuple[str, str]]:
    """Yield (output_rel_path, markdown) for ZIP export."""
    raw_pl = (playlist_prefix or "").strip()
    pl = raw_pl.strip("/")
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT output_rel_path, analysis_markdown, updated_at FROM jobs
            WHERE output_rel_path IS NOT NULL AND analysis_markdown IS NOT NULL
            ORDER BY updated_at DESC
            """
        )
        seen: set[str] = set()
        for row in cur:
            rel = str(row["output_rel_path"])
            if rel in seen:
                continue
            seen.add(rel)
            parent = Path(rel).parent.as_posix()
            if playlist_prefix is not None and playlist_prefix != "":
                if raw_pl == ".":
                    if parent != ".":
                        continue
                elif pl:
                    if not (rel.startswith(pl + "/") or parent == pl):
                        continue
            yield rel, str(row["analysis_markdown"])


def kv_get(key: str) -> Optional[str]:
    with get_conn() as conn:
        cur = conn.execute("SELECT value FROM app_kv WHERE key = ?", (key,))
        row = cur.fetchone()
        return str(row[0]) if row else None


def kv_set(key: str, value: str) -> None:
    now = _utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        conn.commit()


def kv_delete(key: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM app_kv WHERE key = ?", (key,))
        conn.commit()
