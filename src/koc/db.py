import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, params_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage TEXT NOT NULL, key TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed','blocked','skipped')), retries INTEGER NOT NULL DEFAULT 0, error TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS creators (creator_id TEXT PRIMARY KEY, handle TEXT, data_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS videos (video_id TEXT PRIMARY KEY, creator_id TEXT NOT NULL, data_json TEXT NOT NULL, mp4_path TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metrics (creator_id TEXT NOT NULL, name TEXT NOT NULL, value TEXT, source TEXT, period TEXT, collected_at TEXT NOT NULL, PRIMARY KEY(creator_id,name,period));
CREATE TABLE IF NOT EXISTS scores (run_id TEXT NOT NULL, creator_id TEXT NOT NULL, stage TEXT NOT NULL, score REAL, breakdown_json TEXT NOT NULL, PRIMARY KEY(run_id,creator_id,stage));
CREATE TABLE IF NOT EXISTS analyses (video_id TEXT NOT NULL, prompt_version TEXT NOT NULL, model TEXT NOT NULL, analysis_json TEXT NOT NULL, PRIMARY KEY(video_id,prompt_version,model));
CREATE TABLE IF NOT EXISTS recommendations (run_id TEXT NOT NULL, creator_id TEXT NOT NULL, rank INTEGER NOT NULL, est_cost_vnd INTEGER NOT NULL, rec_json TEXT NOT NULL, PRIMARY KEY(run_id,creator_id));
CREATE TABLE IF NOT EXISTS api_calls (id INTEGER PRIMARY KEY, run_id TEXT, endpoint TEXT NOT NULL, request_hash TEXT NOT NULL, status TEXT NOT NULL, credits REAL NOT NULL, latency_ms INTEGER NOT NULL, cache_hit INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS llm_calls (id INTEGER PRIMARY KEY, run_id TEXT, kind TEXT NOT NULL, request_hash TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, latency_ms INTEGER NOT NULL, cost_usd REAL NOT NULL, cache_hit INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS http_cache (request_hash TEXT PRIMARY KEY, endpoint TEXT NOT NULL, response_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS llm_cache (request_hash TEXT PRIMARY KEY, output_json TEXT NOT NULL, usage_json TEXT NOT NULL, created_at TEXT NOT NULL, call_id INTEGER);
CREATE TABLE IF NOT EXISTS run_results (run_id TEXT NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, call_id INTEGER, model TEXT, prompt_version TEXT, provenance TEXT, PRIMARY KEY(run_id,kind,subject));
CREATE TABLE IF NOT EXISTS faithfulness (run_id TEXT NOT NULL, creator_id TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, request_hash TEXT NOT NULL, score REAL NOT NULL, verdicts_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(run_id,creator_id,model,prompt_version));
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | Path = "data/koc.db") -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    if "call_id" not in {row[1] for row in conn.execute("PRAGMA table_info(llm_cache)")}:
        with transaction(conn):
            conn.execute("ALTER TABLE llm_cache ADD COLUMN call_id INTEGER")  # id of the llm_calls row that produced the entry
    if "provenance" not in {row[1] for row in conn.execute("PRAGMA table_info(run_results)")}:
        with transaction(conn):
            conn.execute("ALTER TABLE run_results ADD COLUMN provenance TEXT")  # confirmed | reused | unknown (NULL: written before this column)
    with transaction(conn):
        # Legacy cache rows: take the producer from this run's own recorded reference when the call's hash proves it.
        conn.execute("UPDATE llm_cache SET call_id=(SELECT rr.call_id FROM run_results rr JOIN llm_calls l ON l.id=rr.call_id "
                     "WHERE l.request_hash=llm_cache.request_hash AND l.cache_hit=0 AND rr.call_id IS NOT NULL LIMIT 1) "
                     "WHERE call_id IS NULL AND EXISTS (SELECT 1 FROM run_results rr JOIN llm_calls l ON l.id=rr.call_id "
                     "WHERE l.request_hash=llm_cache.request_hash AND l.cache_hit=0 AND rr.call_id IS NOT NULL)")
    definition = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='scores'").fetchone()[0]
    if "score REAL NOT NULL" in definition:
        with transaction(conn):
            conn.execute("CREATE TABLE scores_new (run_id TEXT NOT NULL, creator_id TEXT NOT NULL, stage TEXT NOT NULL, score REAL, breakdown_json TEXT NOT NULL, PRIMARY KEY(run_id,creator_id,stage))")
            conn.execute("INSERT INTO scores_new SELECT * FROM scores")
            conn.execute("DROP TABLE scores")
            conn.execute("ALTER TABLE scores_new RENAME TO scores")
    definition = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'").fetchone()[0]
    if "'blocked'" not in definition or "'skipped'" not in definition:
        with transaction(conn):
            conn.execute("CREATE TABLE tasks_new (task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage TEXT NOT NULL, key TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed','blocked','skipped')), retries INTEGER NOT NULL DEFAULT 0, error TEXT, updated_at TEXT NOT NULL)")
            conn.execute("INSERT INTO tasks_new SELECT * FROM tasks")
            conn.execute("DROP TABLE tasks")
            conn.execute("ALTER TABLE tasks_new RENAME TO tasks")


@contextmanager
def transaction(conn: sqlite3.Connection):
    if conn.in_transaction:
        yield conn
    else:
        with conn:
            yield conn


def create_run(conn: sqlite3.Connection, params: dict) -> str:
    run_id = uuid.uuid4().hex
    with transaction(conn):
        conn.execute("INSERT INTO runs VALUES (?,?,NULL,'running',?)", (run_id, now(), json.dumps(params, sort_keys=True)))
    return run_id


def add_task(conn: sqlite3.Connection, run_id: str, stage: str, key: str) -> str:
    task_id = f"{run_id}:{stage}:{key}"
    with transaction(conn):
        conn.execute("INSERT INTO tasks VALUES (?,?,?,?,'pending',0,NULL,?) ON CONFLICT(task_id) DO NOTHING", (task_id, run_id, stage, key, now()))
    return task_id


def mark_task_running(conn: sqlite3.Connection, task_id: str) -> None:
    with transaction(conn):
        conn.execute("UPDATE tasks SET status='running',updated_at=? WHERE task_id=?", (now(), task_id))


def complete_task(conn: sqlite3.Connection, task_id: str, write_result) -> None:
    conn.execute("BEGIN")
    try:
        write_result(conn)
        conn.execute("UPDATE tasks SET status='done',error=NULL,updated_at=? WHERE task_id=?", (now(), task_id))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def fail_task(conn: sqlite3.Connection, task_id: str, error: str) -> None:
    with transaction(conn):
        conn.execute("UPDATE tasks SET status='failed',error=?,retries=retries+1,updated_at=? WHERE task_id=?", (error, now(), task_id))


def block_task(conn: sqlite3.Connection, task_id: str, reason: str) -> None:
    with transaction(conn):
        conn.execute("UPDATE tasks SET status='blocked',error=?,updated_at=? WHERE task_id=?", (reason, now(), task_id))


def get_task(conn: sqlite3.Connection, task_id: str):
    return conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()


def reset_running(conn: sqlite3.Connection, run_id: str | None = None) -> None:
    sql = "UPDATE tasks SET status='pending',updated_at=? WHERE status='running'"
    args = [now()]
    if run_id:
        sql += " AND run_id=?"
        args.append(run_id)
    with transaction(conn):
        conn.execute(sql, args)


def pending_tasks(conn: sqlite3.Connection, run_id: str):
    return conn.execute("SELECT * FROM tasks WHERE run_id=? AND status='pending' ORDER BY rowid", (run_id,)).fetchall()


def upsert_creator(conn: sqlite3.Connection, creator_id: str, handle: str | None, data: dict) -> None:
    clean = strip_contacts(data)
    with transaction(conn):
        conn.execute("INSERT INTO creators VALUES (?,?,?,?) ON CONFLICT(creator_id) DO UPDATE SET handle=excluded.handle,data_json=excluded.data_json,updated_at=excluded.updated_at", (creator_id, handle, json.dumps(clean, sort_keys=True, separators=(",", ":")), now()))


def upsert_video(conn: sqlite3.Connection, video_id: str, creator_id: str, data: dict, mp4_path: str | None = None) -> None:
    with transaction(conn):
        conn.execute("INSERT INTO videos VALUES (?,?,?,?,?) ON CONFLICT(video_id) DO UPDATE SET creator_id=excluded.creator_id,data_json=excluded.data_json,mp4_path=excluded.mp4_path,updated_at=excluded.updated_at", (video_id, creator_id, json.dumps(data, sort_keys=True, separators=(",", ":")), mp4_path, now()))


def upsert_metric(conn: sqlite3.Connection, creator_id: str, name: str, value, source: str, period: str = "last30Day") -> None:
    with transaction(conn):
        conn.execute("INSERT INTO metrics VALUES (?,?,?,?,?,?) ON CONFLICT(creator_id,name,period) DO UPDATE SET value=excluded.value,source=excluded.source,collected_at=excluded.collected_at", (creator_id, name, json.dumps(value), source, period, now()))


def upsert_score(conn: sqlite3.Connection, run_id: str, creator_id: str, stage: str, score: float, breakdown: dict) -> None:
    with transaction(conn):
        conn.execute("INSERT INTO scores VALUES (?,?,?,?,?) ON CONFLICT(run_id,creator_id,stage) DO UPDATE SET score=excluded.score,breakdown_json=excluded.breakdown_json", (run_id, creator_id, stage, score, json.dumps(breakdown, sort_keys=True)))


def run_latest(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()


def finish_run(conn: sqlite3.Connection, run_id: str, status: str = "done") -> None:
    with transaction(conn):
        conn.execute("UPDATE runs SET status=?,finished_at=? WHERE run_id=?", (status, now(), run_id))


TTL_ENDPOINTS = {"creator/rank", "creator/detail", "video/rank"}


def http_cache_get(conn: sqlite3.Connection, request_hash: str, ttl_days: float | None = None):
    """Cached response, or None. With ttl_days, rank/detail/video-rank rows older than that count as missing."""
    row = conn.execute("SELECT response_json,endpoint,created_at FROM http_cache WHERE request_hash=?", (request_hash,)).fetchone()
    if not row:
        return None
    if ttl_days is not None and row[1] in TTL_ENDPOINTS:
        if datetime.fromisoformat(now()) - datetime.fromisoformat(row[2]) > timedelta(days=ttl_days):
            return None
    return json.loads(row[0])


def http_cache_put(conn: sqlite3.Connection, request_hash: str, endpoint: str, response: dict) -> None:
    with transaction(conn):
        conn.execute("INSERT INTO http_cache VALUES (?,?,?,?) ON CONFLICT(request_hash) DO UPDATE SET response_json=excluded.response_json,created_at=excluded.created_at", (request_hash, endpoint, json.dumps(response, sort_keys=True), now()))


def add_api_call(conn: sqlite3.Connection, run_id: str | None, endpoint: str, request_hash: str, status: str, credits: float, latency_ms: int, cache_hit: bool) -> None:
    with transaction(conn):
        conn.execute("INSERT INTO api_calls(run_id,endpoint,request_hash,status,credits,latency_ms,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?)", (run_id, endpoint, request_hash, status, credits, latency_ms, int(cache_hit), now()))


def finalize_api_call(conn: sqlite3.Connection, call_id: int, status: str, latency_ms: int, *, billed: bool) -> None:
    with transaction(conn):
        conn.execute("UPDATE api_calls SET status=?,credits=CASE WHEN ? THEN credits ELSE 0 END,latency_ms=? WHERE id=?", (status, int(billed), latency_ms, call_id))


def credits_used(conn: sqlite3.Connection) -> float:
    return conn.execute("SELECT COALESCE(SUM(credits),0) FROM api_calls").fetchone()[0]


def add_llm_call(conn, run_id, kind, request_hash, usage, cache_hit):
    with transaction(conn):
        cursor = conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, kind, request_hash, usage.model, usage.prompt_version, usage.input_tokens, usage.output_tokens,
                      usage.latency_ms, usage.cost_usd, int(cache_hit), now()))
    return cursor.lastrowid


def record_run_result(conn, run_id, kind, subject, call_id, usage, provenance=None):
    """Remember which result a run selected and which llm_calls row produced it (None: produced outside this run).

    Call inside the transaction that commits the result so failed tasks leave no selection behind.
    """
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO run_results(run_id,kind,subject,call_id,model,prompt_version,provenance) VALUES (?,?,?,?,?,?,?)",
                     (run_id, kind, subject, call_id, usage.model, usage.prompt_version, provenance or ("confirmed" if call_id else "reused")))


def run_analyses(conn, run_id, creator_id, mock=None):
    """Analyses behind the run's S3 score for a creator: [(video_id, prompt_version, model, analysis_json)].

    Videos come from the S3 breakdown (else the creator's videos). Per video: the run_results pick, else the
    current S3 prompt (or its _repair, configured model preferred), else the newest row of any version (historical
    runs). Without breakdown video ids, videos that only have the newest-row fallback are dropped when others match.
    """
    from .config import load_config
    if mock is None:
        row = conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        mock = bool(json.loads(row[0]).get("mock")) if row else False
    row = conn.execute("SELECT breakdown_json FROM scores WHERE run_id=? AND creator_id=? AND stage='S3'", (run_id, creator_id)).fetchone()
    ids = (json.loads(row[0]) if row else {}).get("video_ids")
    listed = ids is not None
    if not listed:
        ids = [r[0] for r in conn.execute("SELECT video_id FROM videos WHERE creator_id=? ORDER BY rowid", (creator_id,))]
    has_results = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_results'").fetchone())
    model = load_config()["llm_caps"].get("model", "gemini-3.8-flash")
    prompt = "content_v1" if mock else "content_v3"
    columns = "video_id,prompt_version,model,analysis_json"
    out = []
    for vid in ids:
        pick = conn.execute("SELECT prompt_version,model FROM run_results WHERE run_id=? AND kind='content' AND subject=?", (run_id, vid)).fetchone() if has_results else None
        found, tier = None, 1
        if pick:
            found = conn.execute(f"SELECT {columns} FROM analyses WHERE video_id=? AND prompt_version=? AND model=?", (vid, pick[0], pick[1])).fetchone()
        if not found:
            tier = 2
            found = conn.execute(f"SELECT {columns} FROM analyses WHERE video_id=? AND prompt_version IN (?,?) "
                                 "ORDER BY (model=? OR model LIKE ?) DESC, rowid DESC", (vid, prompt, prompt + "_repair", model, "%/" + model)).fetchone()
        if not found:
            tier = 3
            found = conn.execute(f"SELECT {columns} FROM analyses WHERE video_id=? ORDER BY rowid DESC", (vid,)).fetchone()
        if found:
            out.append((tuple(found), tier))
    if not listed and any(tier < 3 for _, tier in out):
        out = [item for item in out if item[1] < 3]
    return [row for row, _ in out]


def update_llm_request_hash(conn, run_id, kind, request_hash, after_id=0):
    with transaction(conn):
        conn.execute("UPDATE llm_calls SET request_hash=? WHERE run_id IS ? AND kind=? AND request_hash='' AND id>?",
                     (request_hash, run_id, kind, after_id))


def strip_contacts(value):
    if isinstance(value, dict):
        return {k: strip_contacts(v) for k, v in value.items() if not k.lower().startswith("creator_contact_")}
    if isinstance(value, list):
        return [strip_contacts(v) for v in value]
    return value


def cache_key(endpoint: str, body: dict) -> str:
    canonical = json.dumps({"endpoint": endpoint, "body": body}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
