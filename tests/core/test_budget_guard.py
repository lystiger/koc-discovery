from types import SimpleNamespace

import pytest

from koc import db
from koc.budget_guard import BudgetGuard, get_cached, llm_cache_key, put_cached
from koc.types import BudgetExceeded


def test_llm_budget_uses_logged_cumulative_cost_and_cache_key(tmp_path):
    conn = db.connect(tmp_path / "llm.db")
    db.init_db(conn)
    guard = BudgetGuard(conn, cap_usd=1, run_id="r1")
    usage = SimpleNamespace(model="model-x", prompt_version="v1", input_tokens=4, output_tokens=2,
                            latency_ms=10, cost_usd=.8, cache_hit=False)
    guard.record(usage)
    with pytest.raises(BudgetExceeded):
        guard.check(.21)
    key = llm_cache_key("media-hash", "v1", "model-x", {"product_vi": "kem chống nắng"})
    put_cached(conn, key, {"text": "ok"}, {"tokens": 6})
    assert get_cached(conn, key) == ({"text": "ok"}, {"tokens": 6})
    assert llm_cache_key("other", "v1", "model-x", {}) != key


def test_completed_overspend_is_logged_before_budget_error(tmp_path):
    conn = db.connect(tmp_path / "overspend.db")
    db.init_db(conn)
    guard = BudgetGuard(conn, cap_usd=1, run_id="r1")
    usage = SimpleNamespace(model="model-x", prompt_version="v1", input_tokens=4, output_tokens=2,
                            latency_ms=10, cost_usd=1.1, cache_hit=False)

    with pytest.raises(BudgetExceeded, match="vượt"):
        guard.record(usage)

    row = conn.execute("SELECT cost_usd FROM llm_calls").fetchone()
    assert row[0] == 1.1
    with pytest.raises(BudgetExceeded):
        guard.check(0)


def test_completed_call_above_checked_estimate_is_logged_then_rejected(tmp_path):
    conn = db.connect(tmp_path / "estimate.db")
    db.init_db(conn)
    guard = BudgetGuard(conn, cap_usd=1, run_id="r1")
    guard.check(.5)
    usage = SimpleNamespace(model="model-x", prompt_version="v1", input_tokens=4, output_tokens=2,
                            latency_ms=10, cost_usd=.6, cache_hit=False)

    with pytest.raises(BudgetExceeded, match="vượt ước tính"):
        guard.record(usage)

    assert conn.execute("SELECT cost_usd FROM llm_calls").fetchone()[0] == .6
