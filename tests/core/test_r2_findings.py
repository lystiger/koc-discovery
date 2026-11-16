"""Regression tests for the round-2 review findings (REVIEW_live_fixes_r2.md)."""
import json

import pytest
from typer.testing import CliRunner

from koc import db
from koc.benchmark import aggregate, build
from koc.benchmark_render import render_markdown
from koc.budget_guard import BudgetGuard
from koc.budget_guard import llm_cache_key
from koc.pipeline import _cached_call, _commit_selected, resume
from koc.types import BrandBrief, CacheOnlyMiss, CandidateSummary, Recommendation, Usage

BRIEF = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ, 18-30 tuổi", budget_vnd=30_000_000)


def _usage(prompt_version="reasons_v4", model="m", cost=0.000001):
    return Usage(provider="openrouter", model=model, prompt_version=prompt_version, input_tokens=50, output_tokens=50, latency_ms=1, cost_usd=cost)


def _recommendation(creator_id="c1", reasons=None, caveats=None, cited=None, usage=None):
    return Recommendation(creator_id=creator_id, reasons_vi=reasons or ["Lý do một.", "Lý do hai.", "Lý do ba."],
                          cited_evidence_ids=cited or [f"metric:{creator_id}:video_gpm"], caveats_vi=caveats or [], usage=usage or _usage())


def _candidate(audience_score=None, creator_id="c1"):
    return CandidateSummary(creator_id=creator_id, handle="h", followers=1, commercial_score=80, audience_score=audience_score,
                            content_score=60, final_score=70, est_cost_vnd=1, metrics={"video_gpm": 1.0},
                            metric_evidence_ids={"video_gpm": f"metric:{creator_id}:video_gpm"}, analyses=[])


def _new_run(conn, params=None):
    return db.create_run(conn, params if params is not None else {"limit": 5, "mock": False})


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "r2.db")
    db.init_db(c)
    return c


def _attempt(conn, run_id, kind, key, usages, result):
    """One _cached_call whose function records `usages` through the real guard, then returns `result` or raises."""
    def function(*_args, budget_guard, **_kw):
        for usage in usages:
            budget_guard.record(usage)
        if result is None:
            raise ValueError("invalid output")
        return result
    return _cached_call(conn, run_id, kind, key, "reasons_v4", "m", BRIEF, function)


def test_r2_f1_failed_call_is_not_successful_after_later_retry_succeeds(conn):
    """R2-F1: only the producing call counts as successful, not every call with the same hash/prompt version."""
    run_id = _new_run(conn)
    with pytest.raises(ValueError):
        _attempt(conn, run_id, "reasons", "k1", [_usage("reasons_v4"), _usage("reasons_v4_repair")], None)
    final = _attempt(conn, run_id, "reasons", "k1", [_usage("reasons_v4")], _recommendation())
    _commit_selected(conn, run_id, "reasons", "c1", llm_cache_key("k1", "reasons_v4", "m", BRIEF.model_dump()), final.usage)  # S4 commit
    conn.execute("INSERT INTO recommendations VALUES (?,?,1,0,'{}')", (run_id, "c1"))
    result = aggregate(conn, run_id)
    assert result["stages_total"]["S4"]["calls"] == 3
    assert result["stages_success"]["S4"]["calls"] == 1
    assert result["totals_success"]["tokens_in"] == 50
    assert result["totals_success"]["usd"] == pytest.approx(0.000001)
    assert result["totals_total"]["usd"] == pytest.approx(0.000003)
    assert result["success_estimated"] is False


def test_r2_f2_other_run_analysis_does_not_change_success_accounting(conn):
    """R2-F2: success is run-scoped and includes the model; another run's analysis cannot flip it."""
    run_a, run_b = _new_run(conn), _new_run(conn)
    db.upsert_creator(conn, "c1", "c1", {})
    db.upsert_score(conn, run_a, "c1", "S3", 70, {})
    conn.execute("INSERT INTO videos VALUES ('v','c1','{}',NULL,'t')")
    # Hand-built legacy run A: ledger row + cache entry, no retained analysis.
    conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (run_a, "content", "h", "m", "content_v3", 1, 1, 1, 0.01, 0, "t"))
    conn.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES ('h',?,?,'t')", (json.dumps({"video_id": "v"}), json.dumps({"prompt_version": "content_v3"})))
    conn.commit()
    before = aggregate(conn, run_a)
    conn.execute("INSERT INTO analyses VALUES ('v','content_v3','other-model','{}')")  # produced for run B with another model
    conn.commit()
    after = aggregate(conn, run_a)
    assert before["totals_success"]["usd"] == after["totals_success"]["usd"] == 0
    assert after["totals_total"]["usd"] == pytest.approx(0.01)
    assert after["success_estimated"] is True  # no run_results rows: heuristic, flagged as estimated
    # With run-scoped results, run B's selection never appears in run A.
    from koc.pipeline import _mock_cached, _fake_analysis
    class Video:  # minimal VideoInput stand-in
        video_id = "v2"
    analysis = _mock_cached(conn, run_b, "content", "kb", lambda: _fake_analysis(Video), type(_fake_analysis(Video)))
    _commit_selected(conn, run_b, "content", "v2", "kb", analysis.usage)
    db.upsert_score(conn, run_b, "c1", "S3", 70, {"video_ids": ["v2"]})
    assert aggregate(conn, run_b)["totals_success"]["calls"] == 1
    assert aggregate(conn, run_a)["totals_success"]["usd"] == 0


def test_r2_f3_resume_refuses_mode_change(conn):
    run_id = _new_run(conn, {"limit": 5, "mock": False})
    db.add_task(conn, run_id, "S0", "candidates")
    with pytest.raises(RuntimeError, match="Không thể đổi chế độ"):
        resume(conn, mock=True)
    mock_run = _new_run(conn, {"limit": 5, "mock": True})
    with pytest.raises(RuntimeError, match="Không thể đổi chế độ"):
        resume(conn, mock=False)
    assert db.run_latest(conn)["run_id"] == mock_run


def test_r2_f3_cli_resume_mode_change_exits_with_vietnamese_error(tmp_path, monkeypatch):
    import koc.cli as cli
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "mode.db")
    c = db.connect(cli.DB_PATH)
    db.init_db(c)
    run_id = _new_run(c, {"limit": 5, "mock": False})
    db.add_task(c, run_id, "S0", "candidates")
    c.close()
    result = CliRunner().invoke(cli.app, ["resume", "--mock"])
    assert result.exit_code == 1 and "Không thể đổi chế độ" in result.output


def test_r2_f3_benchmark_derives_mixed_and_mock_mode_from_llm_models(conn):
    run_id = _new_run(conn, {"limit": 5, "mock": False})
    conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (run_id, "content", "h", "mock", "content_v1", 0, 0, 0, 0, 0, "t"))
    conn.commit()
    result = build(conn, run_id)
    assert result["mode"] == "mixed" and result["mode_stored"] == "live"
    assert "HỖN HỢP" in render_markdown(result) and "trộn bước mô phỏng" in render_markdown(result)
    clean = _new_run(conn, {"limit": 5, "mock": True})
    assert aggregate(conn, clean)["mode"] == "mock"


@pytest.mark.parametrize("reason", [
    "Khán giả nữ chiếm 60 phần trăm.",
    "Phần lớn khán giả là nữ, trong độ tuổi 18–30.",
    "Khán giả chủ yếu ở độ tuổi 18-24.",
    "Creator có độ tuổi 18-30 rất hợp sản phẩm.",
    "Khán giả của creator khớp tệp nữ 18-30 của nhãn hàng.",
])
def test_r2_f4_rejects_spelled_out_and_qualitative_audience_claims(reason):
    from koc.llm.reasons import _audience_claims
    assert _audience_claims([reason]) == [reason]


@pytest.mark.parametrize("reason", [
    "Tệp mục tiêu nữ 18-30 của nhãn hàng phù hợp với dòng kem chống nắng.",
    "Hồ sơ khán giả chưa xác minh nên không nêu độ tuổi hay giới tính.",
    "Doanh thu dưỡng da chiếm 75% tổng doanh thu.",
])
def test_r2_f4_allows_brand_target_and_unverified_statements(reason):
    from koc.llm.reasons import _audience_claims
    assert _audience_claims([reason]) == []


def test_r2_f5_reasons_cache_is_versioned_and_cached_entries_are_revalidated(conn):
    """R2-F5: reasons_v4 invalidates old entries; a hit is re-checked against the current audience state."""
    from koc.budget_guard import llm_cache_key, put_cached
    assert llm_cache_key("k", "reasons_v2", "m", BRIEF.model_dump()) != llm_cache_key("k", "reasons_v4", "m", BRIEF.model_dump())

    run_id = _new_run(conn)
    candidate = _candidate(audience_score=None)
    key = llm_cache_key("k", "reasons_v4", "m", BRIEF.model_dump())
    unsafe = _recommendation(reasons=["Khán giả nữ chiếm 60%.", "Lý do hai.", "Lý do ba."])
    put_cached(conn, key, unsafe.model_dump(mode="json"), unsafe.usage.model_dump(mode="json"))
    calls = []

    def provider(*_a, **_k):
        calls.append(1)
        return _recommendation(usage=_usage(cost=0.0))

    # cache-only: an invalid cached entry blocks and never reaches a provider
    with pytest.raises(CacheOnlyMiss):
        _cached_call(conn, run_id, "reasons", "k", "reasons_v4", "m", BRIEF, provider, candidate, BRIEF, cache_only=True)
    assert not calls
    # normal mode: the unsafe entry is dropped and regenerated, not trusted
    rec = _cached_call(conn, run_id, "reasons", "k", "reasons_v4", "m", BRIEF, provider, candidate, BRIEF)
    assert calls and "60%" not in " ".join(rec.reasons_vi)

    # a safe cached entry without the caveat gets it appended on a hit
    safe = _recommendation(creator_id="c1")
    put_cached(conn, "k-safe-key", safe.model_dump(mode="json"), safe.usage.model_dump(mode="json"))
    key2 = llm_cache_key("k2", "reasons_v4", "m", BRIEF.model_dump())
    put_cached(conn, key2, safe.model_dump(mode="json"), safe.usage.model_dump(mode="json"))
    hit = _cached_call(conn, run_id, "reasons", "k2", "reasons_v4", "m", BRIEF, provider, candidate, BRIEF, cache_only=True)
    assert any("Chưa xác minh hồ sơ khán giả" in cv for cv in hit.caveats_vi)


def test_r2_f7_benchmark_reports_per_creator_placeholder_count(conn):
    from tests.core.test_audience_placeholder import MIXED, _seed
    run_id = _seed(conn, MIXED)
    result = build(conn, run_id)
    assert result["audience_placeholder"] is True
    assert result["audience_placeholder_creators"] == 1 and result["audience_creators_checked"] == 5
    text = render_markdown(result)
    assert "1/5 KOC" in text and "Không phát hiện dữ liệu khán giả mẫu" not in text
