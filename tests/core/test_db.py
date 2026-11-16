import os
import subprocess
import sys

import pytest

from koc import db


def test_schema_tables_and_upserts_are_idempotent(tmp_path):
    conn = db.connect(tmp_path / "core.db")
    db.init_db(conn)
    expected = {
        "runs", "tasks", "creators", "videos", "metrics", "scores", "analyses",
        "recommendations", "api_calls", "llm_calls", "http_cache", "llm_cache", "run_results", "faithfulness",
    }
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert names == expected
    db.upsert_creator(conn, "c1", "alice", {"followers": 12000})
    db.upsert_creator(conn, "c1", "alice", {"followers": 13000, "creator_contact_email": "private"})
    assert conn.execute("SELECT COUNT(*) FROM creators").fetchone()[0] == 1
    assert conn.execute("SELECT data_json FROM creators").fetchone()[0] == '{"followers":13000}'


def test_existing_task_table_migrates_to_blocked_status(tmp_path):
    conn = db.connect(tmp_path / "legacy.db")
    conn.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, stage TEXT NOT NULL, key TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed')), retries INTEGER NOT NULL DEFAULT 0, error TEXT, updated_at TEXT NOT NULL)")
    conn.execute("INSERT INTO tasks VALUES ('r:S3:c1','r','S3','c1','pending',0,NULL,'now')")
    db.init_db(conn)

    assert tuple(conn.execute("SELECT task_id,status FROM tasks").fetchone()) == ("r:S3:c1", "pending")
    db.block_task(conn, "r:S3:c1", "Hạn mức LLM đã bị vượt.")
    assert tuple(conn.execute("SELECT status,error FROM tasks").fetchone()) == ("blocked", "Hạn mức LLM đã bị vượt.")
    conn.execute("UPDATE tasks SET status='skipped' WHERE task_id='r:S3:c1'")
    assert conn.execute("SELECT status FROM tasks").fetchone()[0] == "skipped"


def test_task_result_write_rolls_back_and_resume_resets_running(tmp_path):
    conn = db.connect(tmp_path / "core.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    task_id = db.add_task(conn, run_id, "S1", "c1")
    db.mark_task_running(conn, task_id)
    with pytest.raises(RuntimeError):
        db.complete_task(conn, task_id, lambda c: (_ for _ in ()).throw(RuntimeError("crash")))
    assert db.get_task(conn, task_id)["status"] == "running"
    assert conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 0
    db.reset_running(conn, run_id)
    assert db.get_task(conn, task_id)["status"] == "pending"


def test_init_db_makes_existing_scores_nullable(tmp_path):
    conn = db.connect(tmp_path / "legacy-scores.db")
    conn.execute("CREATE TABLE scores (run_id TEXT NOT NULL, creator_id TEXT NOT NULL, stage TEXT NOT NULL, score REAL NOT NULL, breakdown_json TEXT NOT NULL, PRIMARY KEY(run_id,creator_id,stage))")
    conn.execute("INSERT INTO scores VALUES ('r1','c1','S1',50,'{}')")
    conn.commit()

    db.init_db(conn)
    conn.execute("INSERT INTO scores VALUES ('r1','c2','S3',NULL,'{}')")

    assert conn.execute("SELECT score FROM scores WHERE creator_id='c1'").fetchone()[0] == 50
    assert conn.execute("SELECT score FROM scores WHERE creator_id='c2'").fetchone()[0] is None


def test_process_crash_leaves_work_resumable(tmp_path):
    path = tmp_path / "crash.db"
    code = """
from koc import db
c=db.connect(%r); db.init_db(c); r=db.create_run(c,{})
t=db.add_task(c,r,'S1','c1'); db.mark_task_running(c,t)
os._exit(23)
""" % str(path)
    crashed = subprocess.run([sys.executable, "-c", "import os\n" + code], env={**os.environ, "PYTHONPATH": "src"})
    assert crashed.returncode == 23
    conn = db.connect(path)
    db.reset_running(conn)
    assert conn.execute("SELECT status FROM tasks").fetchone()[0] == "pending"


def test_paid_response_is_cached_before_process_crash(tmp_path):
    path = tmp_path / "paid.db"
    code = """
from koc import db
from koc.kalodata import KalodataClient
c=db.connect(%r); db.init_db(c)
client=KalodataClient(c,run_id='r1',api_key='x',transport=lambda *a:{'data':[{'id':'paid'}]})
client.creator_rank(page_size=100)
os._exit(24)
""" % str(path)
    child = subprocess.run([sys.executable, "-c", "import os\n" + code], env={**os.environ, "PYTHONPATH": "src"})
    assert child.returncode == 24
    conn = db.connect(path)
    db.init_db(conn)
    client = __import__("koc.kalodata", fromlist=["KalodataClient"]).KalodataClient(
        conn, run_id="r1", api_key="x", transport=lambda *_: (_ for _ in ()).throw(AssertionError("duplicate paid call")))
    assert client.creator_rank(page_size=100) == {"data": [{"id": "paid"}]}
    assert conn.execute("SELECT SUM(credits) FROM api_calls").fetchone()[0] == pytest.approx(.1)
