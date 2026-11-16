import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .schemas import Creator, Video, field_values

SCHEMA = """
CREATE TABLE IF NOT EXISTS creators (
    creator_id TEXT PRIMARY KEY, data JSON NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY, creator_id TEXT NOT NULL, data JSON NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS extraction_runs (
    run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
    status TEXT NOT NULL, params JSON);
CREATE TABLE IF NOT EXISTS extraction_tasks (
    task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','done','failed')),
    retries INTEGER NOT NULL DEFAULT 0, error TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
    field TEXT NOT NULL, raw_field TEXT, source TEXT, collected_at TEXT NOT NULL,
    period TEXT, status TEXT NOT NULL, UNIQUE(entity_type, entity_id, field));
CREATE TABLE IF NOT EXISTS media_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL, provider TEXT, model TEXT,
    prompt_version TEXT, preprocess JSON, input_tokens INTEGER, output_tokens INTEGER,
    latency_ms INTEGER, est_cost REAL, actual_cost REAL, validation_status TEXT NOT NULL,
    output JSON, created_at TEXT NOT NULL);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _tx(conn: sqlite3.Connection):
    """Commit on exit, unless the caller already opened the transaction."""
    if conn.in_transaction:
        yield conn
    else:
        with conn:
            yield conn


def _write_evidence(conn: sqlite3.Connection, entity_type: str, entity_id: str, model: BaseModel) -> None:
    for field, fv in field_values(model).items():
        conn.execute(
            """INSERT INTO source_evidence (entity_type, entity_id, field, raw_field, source,
                   collected_at, period, status) VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(entity_type, entity_id, field) DO UPDATE SET
                   raw_field=excluded.raw_field, source=excluded.source,
                   collected_at=excluded.collected_at, period=excluded.period,
                   status=excluded.status""",
            (entity_type, entity_id, field, fv.raw_field, fv.source,
             fv.collected_at.isoformat(), fv.period, fv.status),
        )


def upsert_creator(conn: sqlite3.Connection, creator: Creator) -> None:
    with _tx(conn):
        conn.execute(
            """INSERT INTO creators (creator_id, data, updated_at) VALUES (?,?,?)
               ON CONFLICT(creator_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at""",
            (creator.creator_id, creator.model_dump_json(), _now()),
        )
        _write_evidence(conn, "creator", creator.creator_id, creator)


def upsert_video(conn: sqlite3.Connection, video: Video) -> None:
    with _tx(conn):
        conn.execute(
            """INSERT INTO videos (video_id, creator_id, data, updated_at) VALUES (?,?,?,?)
               ON CONFLICT(video_id) DO UPDATE SET creator_id=excluded.creator_id,
                   data=excluded.data, updated_at=excluded.updated_at""",
            (video.video_id, video.creator_id, video.model_dump_json(), _now()),
        )
        _write_evidence(conn, "video", video.video_id, video)


def start_run(conn: sqlite3.Connection, params: dict) -> str:
    run_id = uuid.uuid4().hex
    with _tx(conn):
        conn.execute(
            "INSERT INTO extraction_runs (run_id, started_at, status, params) VALUES (?,?,?,?)",
            (run_id, _now(), "running", json.dumps(params)),
        )
    return run_id


def finish_run(conn: sqlite3.Connection, run_id: str) -> None:
    with _tx(conn):
        conn.execute(
            "UPDATE extraction_runs SET status='finished', finished_at=? WHERE run_id=?",
            (_now(), run_id),
        )


def add_task(conn: sqlite3.Connection, run_id: str, kind: str, key: str) -> str:
    task_id = f"{run_id}:{kind}:{key}"
    with _tx(conn):
        conn.execute(
            """INSERT INTO extraction_tasks (task_id, run_id, kind, key, status, retries, updated_at)
               VALUES (?,?,?,?,'pending',0,?) ON CONFLICT(task_id) DO NOTHING""",
            (task_id, run_id, kind, key, _now()),
        )
    return task_id


def next_pending_tasks(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM extraction_tasks WHERE run_id=? AND status='pending' ORDER BY rowid",
        (run_id,),
    ).fetchall()


def mark_task(conn: sqlite3.Connection, task_id: str, status: str, error: str | None = None) -> None:
    with _tx(conn):
        conn.execute(
            """UPDATE extraction_tasks SET status=?, error=?,
                   retries = retries + CASE WHEN ?='failed' THEN 1 ELSE 0 END, updated_at=?
               WHERE task_id=?""",
            (status, error, status, _now(), task_id),
        )


def complete_task_with(conn: sqlite3.Connection, task_id: str, write_fn) -> None:
    """Run write_fn and mark the task done in one transaction. Rolls back on error."""
    conn.execute("BEGIN")
    try:
        write_fn(conn)
        mark_task(conn, task_id, "done")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def reset_running(conn: sqlite3.Connection, run_id: str) -> None:
    with _tx(conn):
        conn.execute(
            "UPDATE extraction_tasks SET status='pending', updated_at=? WHERE run_id=? AND status='running'",
            (_now(), run_id),
        )


def latest_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM extraction_runs ORDER BY rowid DESC LIMIT 1").fetchone()


MEDIA_COLUMNS = [
    "video_id", "provider", "model", "prompt_version", "preprocess", "input_tokens",
    "output_tokens", "latency_ms", "est_cost", "actual_cost", "validation_status",
    "output", "created_at",
]


def insert_media_test(conn: sqlite3.Connection, row: dict) -> None:
    placeholders = ",".join("?" * len(MEDIA_COLUMNS))
    with _tx(conn):
        conn.execute(
            f"INSERT INTO media_tests ({','.join(MEDIA_COLUMNS)}) VALUES ({placeholders})",
            [row.get(c) for c in MEDIA_COLUMNS],
        )
