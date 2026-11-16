"""Regression tests for the round-5 review finding R5-F1 (REVIEW_live_fixes_r5.md)."""
import koc.pipeline as pipeline
from koc import db
from koc.benchmark import aggregate
from tests.core.test_audience_placeholder import _seed


def _paid_run(tmp_path):
    conn = db.connect(tmp_path / "r5.db")
    db.init_db(conn)
    run_id = _seed(conn, [(70.0 + i, 20.0, 30.0) for i in range(5)])
    with db.transaction(conn):
        pipeline._s4(conn, run_id, mock=True)(conn)
    assert aggregate(conn, run_id)["stages_success"]["S4"]["calls"] == 5
    return conn, run_id


def _retry_reselect(conn, run_id):
    """What an explicit retry does to S4 (invalidate, then re-select from the cache)."""
    with db.transaction(conn):
        conn.execute("DELETE FROM recommendations WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM run_results WHERE run_id=? AND kind='reasons'", (run_id,))
    with db.transaction(conn):
        pipeline._s4(conn, run_id, mock=True)(conn)


def test_r5_f1_upgraded_run_keeps_known_producers_through_retry(tmp_path):
    """Cache rows written before llm_cache.call_id existed get their producer from this run's own references."""
    conn, run_id = _paid_run(tmp_path)
    conn.execute("UPDATE llm_cache SET call_id=NULL")  # state of a database upgraded from the previous schema
    conn.commit()
    db.init_db(conn)  # migration backfills only producers this run recorded
    assert conn.execute("SELECT COUNT(*) FROM llm_cache WHERE call_id IS NOT NULL").fetchone()[0] == 5
    _retry_reselect(conn, run_id)
    result = aggregate(conn, run_id)
    assert result["stages_success"]["S4"]["calls"] == 5 and result["success_estimated"] is False
    assert result["totals_total"]["calls"] == 5  # retry made no new paid call


def test_r5_f1_unknown_provenance_is_estimated_never_exact_zero(tmp_path):
    """A legacy cache row with no known producer is 'unknown': the stage stays estimated, not exact zero."""
    conn, run_id = _paid_run(tmp_path)
    conn.execute("UPDATE llm_cache SET call_id=NULL")
    conn.execute("DELETE FROM run_results")  # nothing recorded that could prove the producer
    conn.commit()
    _retry_reselect(conn, run_id)
    assert {r[0] for r in conn.execute("SELECT provenance FROM run_results")} == {"unknown"}
    result = aggregate(conn, run_id)
    assert result["success_estimated_stages"] == ["S4"]
    assert result["stages_success"]["S4"]["calls"] == 5  # heuristic estimate, not an exact 0


def test_r5_f1_cache_reuse_from_another_run_is_reused_not_unknown(tmp_path):
    conn, run_id = _paid_run(tmp_path)
    other = db.create_run(conn, {"limit": 5, "mock": False})
    for creator in ("c0", "c1", "c2", "c3", "c4"):
        conn.execute("INSERT INTO scores SELECT ?,creator_id,stage,score,breakdown_json FROM scores WHERE run_id=? AND creator_id=?", (other, run_id, creator))
    conn.commit()
    with db.transaction(conn):
        pipeline._s4(conn, other, mock=True)(conn)
    assert {r[0] for r in conn.execute("SELECT provenance FROM run_results WHERE run_id=?", (other,))} == {"reused"}
    result = aggregate(conn, other)
    assert result["stages_success"]["S4"]["calls"] == 0 and result["success_estimated"] is False


def test_r6_f1_unknown_result_does_not_let_heuristic_claim_known_failed_call(tmp_path):
    """Per-result attribution: a reused result keeps exact 0 even when another result in the stage is unknown."""
    from koc.budget_guard import llm_cache_key
    from koc.pipeline import _commit_selected
    from tests.core.test_r4_findings import BRIEF, _call, _rec, _usage

    conn = db.connect(tmp_path / "r6.db")
    db.init_db(conn)
    run_b, run_a = db.create_run(conn, {"mock": False}), db.create_run(conn, {"mock": False})
    try:
        _call(conn, run_a, [_usage(), _usage("reasons_v4_repair")], None)  # A: original + repair fail (c0)
    except ValueError:
        pass
    produced = _call(conn, run_b, [_usage()], _rec())  # B pays for c0 and caches it
    hit = _call(conn, run_a, [], None, cache_only=True)  # A reuses B's cached c0
    key = llm_cache_key("k", "reasons_v4", "m", BRIEF.model_dump())
    _commit_selected(conn, run_a, "reasons", "c0", key, hit.usage)  # provenance: reused
    _commit_selected(conn, run_b, "reasons", "c0", key, produced.usage)
    db.record_run_result(conn, run_a, "reasons", "c4", None, hit.usage, "unknown")  # legacy c4, producer unverifiable
    for run_id, creator in ((run_a, "c0"), (run_a, "c4"), (run_b, "c0")):
        rec = _rec().model_copy(update={"creator_id": creator})
        conn.execute("INSERT INTO recommendations VALUES (?,?,1,0,?)", (run_id, creator, rec.model_dump_json()))
    conn.commit()
    assert conn.execute("SELECT provenance FROM run_results WHERE run_id=? AND subject='c0'", (run_a,)).fetchone()[0] == "reused"
    result = aggregate(conn, run_a)
    assert result["stages_total"]["S4"]["calls"] == 2
    assert result["stages_success"]["S4"]["calls"] == 0 and result["totals_success"]["usd"] == 0  # A never paid for a retained result
    assert result["success_estimated_stages"] == ["S4"]  # still flagged: c4 is unknown
    assert aggregate(conn, run_b)["stages_success"]["S4"]["calls"] == 1  # B keeps its confirmed producer


def test_r7_f1_read_only_benchmark_of_legacy_schema_run_without_results(tmp_path):
    """Older schema (no run_results, no llm_cache.call_id), opened read-only, run with paid spend but no retained results."""
    import sqlite3
    from koc.benchmark import build

    path = tmp_path / "legacy.db"
    conn = db.connect(path)
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 1, "mock": False})
    conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (run_id, "content", "h", "m", "content_v3", 50, 50, 1, 0.01, 0, "t"))
    conn.execute("DROP TABLE run_results")  # schema from before run_results existed
    conn.commit()
    conn.close()
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    result = build(ro, run_id)
    assert result["totals_total"]["calls"] == 1 and result["totals_total"]["usd"] == 0.01
    assert result["totals_success"]["calls"] == 0 and result["totals_success"]["usd"] == 0
    assert result["success_estimated"] is True and result["success_estimated_stages"] == ["S3"]
