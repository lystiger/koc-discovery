from datetime import datetime, timezone

from kalodata_intake import db, mapping


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_upsert_creator_writes_one_evidence_row_per_field(conn, creator):
    db.upsert_creator(conn, creator)
    rows = conn.execute(
        "SELECT field, raw_field, source, status FROM source_evidence WHERE entity_type='creator' AND entity_id='c1'"
    ).fetchall()
    assert len(rows) == 11
    followers = next(r for r in rows if r["field"] == "followers")
    assert followers["source"] == "https://example.test/c/1"
    assert followers["status"] == "observed"


def test_duplicate_upsert_keeps_one_row_and_updates(conn, creator, video):
    db.upsert_creator(conn, creator)
    db.upsert_creator(conn, creator.model_copy(update={"username": creator.username.model_copy(update={"value": "bob"})}))
    db.upsert_video(conn, video)
    db.upsert_video(conn, video)
    assert _count(conn, "creators") == 1
    assert _count(conn, "videos") == 1
    assert "bob" in conn.execute("SELECT data FROM creators").fetchone()["data"]


def test_add_task_is_idempotent(conn):
    run = db.start_run(conn, {})
    first = db.add_task(conn, run, "creator", "c1")
    second = db.add_task(conn, run, "creator", "c1")
    assert first == second
    assert len(db.next_pending_tasks(conn, run)) == 1


def test_checkpoint_rolls_back_when_write_fails(conn, creator):
    run = db.start_run(conn, {})
    task = db.add_task(conn, run, "creator", "c1")
    db.mark_task(conn, task, "running")

    def write(c):
        db.upsert_creator(c, creator)
        raise RuntimeError("boom")

    try:
        db.complete_task_with(conn, task, write)
    except RuntimeError:
        pass
    assert _count(conn, "creators") == 0
    assert conn.execute("SELECT status FROM extraction_tasks WHERE task_id=?", (task,)).fetchone()[0] == "running"


def test_interrupted_run_recovers_on_resume(conn, creator):
    run = db.start_run(conn, {})
    task = db.add_task(conn, run, "creator", "c1")
    db.mark_task(conn, task, "running")  # simulated crash here
    assert db.latest_run(conn)["run_id"] == run
    db.reset_running(conn, run)
    pending = db.next_pending_tasks(conn, run)
    assert [t["task_id"] for t in pending] == [task]
    db.complete_task_with(conn, task, lambda c: db.upsert_creator(c, creator))
    assert conn.execute("SELECT status FROM extraction_tasks WHERE task_id=?", (task,)).fetchone()[0] == "done"
    assert _count(conn, "creators") == 1


def test_field_sources_override_reaches_source_evidence(conn, creator_fields):
    sales = mapping.KALODATA_CREATOR_FIELDS["sales_volume_30d"]
    creator_fields[sales] = "134.76k"
    creator_fields["_field_sources"] = {sales: "https://example.test/rank"}
    now = datetime(2026, 11, 14, 11, 37, 58, tzinfo=timezone.utc)
    db.upsert_creator(conn, mapping.normalize_creator(creator_fields, "https://example.test/c/1", "30d", now))
    row = conn.execute(
        "SELECT source, collected_at FROM source_evidence WHERE entity_type='creator' AND field='sales_volume_30d'"
    ).fetchone()
    assert row["source"] == "https://example.test/rank"
    assert row["collected_at"] == now.isoformat()
