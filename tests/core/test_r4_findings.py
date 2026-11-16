"""Regression tests for the round-4 review findings (REVIEW_live_fixes_r4.md)."""
import sqlite3

import pytest

from koc import db
from koc.benchmark import aggregate
from koc.budget_guard import llm_cache_key
from koc.pipeline import _cached_call, _commit_selected, resume
from koc.types import BrandBrief, Recommendation, Usage

BRIEF = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ, 18-30 tuổi", budget_vnd=30_000_000)


def _usage(prompt_version="reasons_v4"):
    return Usage(provider="openrouter", model="m", prompt_version=prompt_version, input_tokens=50, output_tokens=50, latency_ms=1, cost_usd=0.01)


def _rec():
    return Recommendation(creator_id="c0", reasons_vi=["a", "b", "c"], cited_evidence_ids=["metric:c0:video_gpm"], caveats_vi=[], usage=_usage())


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "r4.db")
    db.init_db(c)
    return c


def _call(conn, run_id, usages, result, cache_only=False):
    def function(*_a, budget_guard, **_k):
        for usage in usages:
            budget_guard.record(usage)
        if result is None:
            raise ValueError("invalid")
        return result
    return _cached_call(conn, run_id, "reasons", "k", "reasons_v4", "m", BRIEF, function, cache_only=cache_only)


def test_r4_f1_cache_hit_does_not_promote_this_runs_failed_call(conn):
    run_a, run_b = db.create_run(conn, {"mock": False}), db.create_run(conn, {"mock": False})
    with pytest.raises(ValueError):
        _call(conn, run_a, [_usage(), _usage("reasons_v4_repair")], None)  # A: original + repair fail
    produced = _call(conn, run_b, [_usage()], _rec())  # B produces and caches the result
    hit = _call(conn, run_a, [], None, cache_only=True)  # A resumes from B's cache
    key = llm_cache_key("k", "reasons_v4", "m", BRIEF.model_dump())
    _commit_selected(conn, run_a, "reasons", "c0", key, hit.usage)
    _commit_selected(conn, run_b, "reasons", "c0", key, produced.usage)
    conn.execute("INSERT INTO recommendations VALUES (?,?,1,0,'{}')", (run_a, "c0"))
    conn.execute("INSERT INTO recommendations VALUES (?,?,1,0,'{}')", (run_b, "c0"))
    conn.commit()
    assert conn.execute("SELECT call_id FROM run_results WHERE run_id=?", (run_a,)).fetchone()[0] is None
    a, b = aggregate(conn, run_a), aggregate(conn, run_b)
    assert a["stages_total"]["S4"]["calls"] == 2 and a["stages_success"]["S4"]["calls"] == 0
    assert a["totals_success"]["usd"] == 0
    assert b["stages_success"]["S4"]["calls"] == 1  # the real producer keeps its attribution


def test_r4_f1_existing_cache_gets_nullable_producer_column(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE llm_cache (request_hash TEXT PRIMARY KEY, output_json TEXT NOT NULL, usage_json TEXT NOT NULL, created_at TEXT NOT NULL)")
    raw.execute("INSERT INTO llm_cache VALUES ('h','{}','{}','t')")
    raw.commit()
    raw.close()
    conn = db.connect(path)
    db.init_db(conn)
    db.init_db(conn)
    assert conn.execute("SELECT request_hash,call_id FROM llm_cache").fetchall()[0][1] is None


def test_r4_f2_interrupted_retry_leaves_no_successful_s4_rows(conn, monkeypatch):
    import koc.pipeline as pipeline
    from tests.core.test_audience_placeholder import _seed

    run_id = _seed(conn, [(70.0 + i, 20.0, 30.0) for i in range(5)])
    with db.transaction(conn):
        pipeline._s4(conn, run_id, mock=True)(conn)
    db.finish_run(conn, run_id, "done")
    assert aggregate(conn, run_id)["stages_success"]["S4"]["calls"] == 5
    monkeypatch.setattr(pipeline, "execute", lambda *a, **k: None)  # the retry blocks before S4 commits
    resume(conn, retry_failed=True)
    assert conn.execute("SELECT COUNT(*) FROM run_results WHERE run_id=? AND kind='reasons'", (run_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 0
    assert aggregate(conn, run_id)["stages_success"]["S4"]["calls"] == 0


def test_r4_f2_benchmark_ignores_producers_of_results_no_longer_retained(conn):
    import koc.pipeline as pipeline
    from tests.core.test_audience_placeholder import _seed

    run_id = _seed(conn, [(70.0 + i, 20.0, 30.0) for i in range(5)])
    with db.transaction(conn):
        pipeline._s4(conn, run_id, mock=True)(conn)
    conn.execute("DELETE FROM recommendations WHERE run_id=? AND creator_id='c4'", (run_id,))  # stale reference remains
    conn.commit()
    assert aggregate(conn, run_id)["stages_success"]["S4"]["calls"] == 4
