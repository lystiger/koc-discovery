"""Regression tests for the round-3 review findings (REVIEW_live_fixes_r3.md)."""
import json
from unittest.mock import MagicMock

import pytest

from koc import db
from koc.benchmark import aggregate
from koc.llm.reasons import _audience_claims, validate_cached_recommendation, write_reasons
from koc.types import BrandBrief, CandidateSummary, Recommendation, Usage
from tests.analysis_seed import seed_brand_fit

BRIEF = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ, 18-30 tuổi", budget_vnd=30_000_000)


def _usage(cost=0.0, prompt_version="reasons_v4", model="m"):
    return Usage(provider="openrouter", model=model, prompt_version=prompt_version, input_tokens=10, output_tokens=10, latency_ms=1, cost_usd=cost)


def _candidate(audience_score=None):
    return CandidateSummary(creator_id="c1", handle="h", followers=1, commercial_score=80, audience_score=audience_score, content_score=60,
                            final_score=70, est_cost_vnd=1, metrics={"video_gpm": 1.0}, metric_evidence_ids={"video_gpm": "metric:c1:video_gpm"}, analyses=[])


def _rec(reasons):
    return Recommendation(creator_id="c1", reasons_vi=reasons, cited_evidence_ids=["metric:c1:video_gpm"], caveats_vi=[], usage=_usage())


BRAND_TARGET = "Nhãn hàng hướng đến khán giả nữ 18–30 tuổi."
CONVERSION_BYPASS = [
    "Phần lớn khán giả là nữ 18–30 tuổi, nhưng chưa rõ tỷ lệ chuyển đổi.",
    "Khán giả nữ chiếm 60%, nhưng chưa rõ tỷ lệ chuyển đổi.",
]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "r3.db")
    db.init_db(c)
    return c


def _write(reasons, calls=1):
    client = MagicMock()
    payload = {"creator_id": "c1", "reasons_vi": reasons, "cited_evidence_ids": ["metric:c1:video_gpm"], "caveats_vi": []}
    client.generate_json.return_value = (json.dumps(payload), _usage())
    guard = MagicMock()
    return client, lambda: write_reasons(_candidate(), BRIEF, budget_guard=guard, client=client)


def test_r3_f1_brand_target_restatement_is_allowed_fresh_and_cached():
    assert _audience_claims([BRAND_TARGET, "Tệp mục tiêu nữ 18-30 của nhãn hàng phù hợp với dòng kem chống nắng."]) == []
    client, call = _write([BRAND_TARGET, "Doanh thu dưỡng da tốt.", "Chi phí hợp lý."])
    assert call().reasons_vi[0] == BRAND_TARGET and client.generate_json.call_count == 1  # no repair needed
    assert validate_cached_recommendation(_rec([BRAND_TARGET, "Lý do hai.", "Lý do ba."]), _candidate()).reasons_vi[0] == BRAND_TARGET


@pytest.mark.parametrize("reason", [
    "Khán giả của KOC khớp với tệp mục tiêu nữ 18–30 của nhãn hàng.",
    "Nhãn hàng hướng đến nữ 18–30 và khán giả của creator trùng với tệp này.",
])
def test_r3_f1_rejects_claim_that_creator_audience_matches_the_target(reason):
    assert _audience_claims([reason]) == [reason]


@pytest.mark.parametrize("reason", CONVERSION_BYPASS)
def test_r3_f2_uncertainty_about_another_thing_does_not_exempt_an_audience_claim(reason):
    assert _audience_claims([reason]) == [reason]
    client, call = _write([reason, "Doanh thu dưỡng da tốt.", "Chi phí hợp lý."])
    with pytest.raises(ValueError, match="giới tính/độ tuổi"):
        call()
    assert client.generate_json.call_count == 2  # original + one repair
    with pytest.raises(ValueError):
        validate_cached_recommendation(_rec([reason, "Lý do hai.", "Lý do ba."]), _candidate())


def test_r3_f2_same_clause_unverified_marker_is_allowed():
    assert _audience_claims(["Khán giả nữ chiếm 60% (chưa xác minh)."]) == []
    assert _audience_claims(["Giới tính khán giả chưa có dữ liệu, cần xác nhận với creator."]) == []
    assert _audience_claims(["Khán giả nữ chiếm 60%, nhưng cần xác nhận lại."]) == ["Khán giả nữ chiếm 60%, nhưng cần xác nhận lại."]


def _s3_fixture(conn, tmp_path, monkeypatch, fail_second):
    import koc.llm
    import koc.pipeline as pipeline
    from koc.budget_guard import BudgetGuard

    run_id = db.create_run(conn, {"limit": 1, "mock": False})
    db.upsert_creator(conn, "c1", "c1", {"creator_followers": 30000})
    media = tmp_path / "media"
    media.mkdir()
    for vid in ("v0", "v1"):
        (media / f"{vid}.mp4").write_bytes(vid.encode())
    monkeypatch.setattr(pipeline, "_download_video", lambda _c, vid, target, _m: str(media / f"{vid}.mp4"))

    class Client:
        def video_rank(self, *_a, **_k):
            return {"data": [{"video_id": "v0", "revenue": 20}, {"video_id": "v1", "revenue": 10}]}

    def analyze(video, brief, *, budget_guard, **_kw):
        budget_guard.record(_usage(0.01, "content_v3"))
        if video.video_id == "v1" and fail_second:
            raise ValueError("invalid analysis")
        analysis = pipeline._fake_analysis(video)
        return analysis.model_copy(update={"usage": _usage(0.01, "content_v3")})

    monkeypatch.setattr(koc.llm, "analyze_video", analyze)
    return run_id, pipeline, Client(), media


def test_r3_f3_failed_s3_task_leaves_no_selected_result(conn, tmp_path, monkeypatch):
    run_id, pipeline, client, media = _s3_fixture(conn, tmp_path, monkeypatch, fail_second=True)
    with pytest.raises(pipeline.S3AnalysisError):
        pipeline._s3_creator(conn, run_id, client, "c1", False, media)
    assert conn.execute("SELECT COUNT(*) FROM run_results").fetchone()[0] == 0
    result = aggregate(conn, run_id)
    assert result["totals_total"]["calls"] == 2 and result["totals_success"]["calls"] == 0
    assert result["success_estimated"] is False


def test_r3_f3_selected_result_is_committed_with_the_analysis(conn, tmp_path, monkeypatch):
    run_id, pipeline, client, media = _s3_fixture(conn, tmp_path, monkeypatch, fail_second=False)
    write = pipeline._s3_creator(conn, run_id, client, "c1", False, media)
    assert conn.execute("SELECT COUNT(*) FROM run_results").fetchone()[0] == 0  # nothing before the task commit
    with db.transaction(conn):
        write(conn)
    assert {r[0] for r in conn.execute("SELECT subject FROM run_results WHERE kind='content'")} == {"v0", "v1"}
    result = aggregate(conn, run_id)
    assert result["totals_success"]["calls"] == 2 and result["totals_success"]["usd"] == pytest.approx(0.02)
    assert result["success_estimated"] is False


def test_r3_f4_reselection_replaces_reasons_results_with_final_selection(conn):
    from koc.pipeline import _s4
    from tests.core.test_audience_placeholder import _seed

    real = [(70.0 + i, 20.0, 30.0) for i in range(5)]
    run_id = _seed(conn, real)
    with db.transaction(conn):
        _s4(conn, run_id, mock=True)(conn)
    first = {r[0] for r in conn.execute("SELECT subject FROM run_results WHERE run_id=? AND kind='reasons'", (run_id,))}
    assert first == {f"c{i}" for i in range(5)}
    # An explicit retry invalidates recommendations; a better sixth creator then displaces one finalist.
    db.upsert_creator(conn, "c5", "c5", {"creator_followers": 30000})
    for stage, score in (("S1", 80), ("S2", 50), ("S3", 95)):
        db.upsert_score(conn, run_id, "c5", stage, score, {})
    seed_brand_fit(conn, "c5")
    for name, value in zip(("female_pct", "age_18_24_pct", "age_25_34_pct"), (80.0, 21.0, 31.0)):
        db.upsert_metric(conn, "c5", name, value, "test")
    db.upsert_metric(conn, "c5", "video_gpm", 1000, "test")
    conn.execute("DELETE FROM recommendations WHERE run_id=?", (run_id,))
    conn.commit()
    with db.transaction(conn):
        _s4(conn, run_id, mock=True)(conn)
    final = {r[0] for r in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}
    tracked = {r[0] for r in conn.execute("SELECT subject FROM run_results WHERE run_id=? AND kind='reasons'", (run_id,))}
    assert "c5" in final and tracked == final and len(tracked) == 5
    result = aggregate(conn, run_id)
    assert result["stages_total"]["S4"]["calls"] == 6 and result["stages_success"]["S4"]["calls"] == 5
    assert result["success_estimated"] is False


def test_r3_f5_partially_tracked_legacy_run_keeps_content_estimate(conn):
    run_id = db.create_run(conn, {"limit": 5, "mock": False})
    db.upsert_creator(conn, "c1", "c1", {})
    db.upsert_score(conn, run_id, "c1", "S3", 70, {"video_count": 5})  # legacy score: no video_ids
    for i in range(5):
        conn.execute("INSERT INTO videos VALUES (?,?,?,NULL,'t')", (f"v{i}", "c1", "{}"))
        conn.execute("INSERT INTO analyses VALUES (?,?,?,?)", (f"v{i}", "content_v3", "m", "{}"))
        conn.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES (?,?,?,'t')", (f"h{i}", json.dumps({"video_id": f"v{i}"}), json.dumps({"prompt_version": "content_v3"})))
        conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, "content", f"h{i}", "m", "content_v3", 10, 10, 1, 0.01, 0, "t"))
    conn.commit()
    before = aggregate(conn, run_id)
    assert before["totals_success"]["usd"] == pytest.approx(0.05) and before["success_estimated_stages"] == ["S3"]
    # After the upgrade, resume tracks only the new S4 result.
    conn.execute("INSERT INTO recommendations VALUES (?,?,1,0,?)", (run_id, "c1", json.dumps({"usage": {"prompt_version": "reasons_v4", "model": "m"}})))
    db.record_run_result(conn, run_id, "reasons", "c1", None, _usage())
    conn.commit()
    after = aggregate(conn, run_id)
    assert after["totals_success"]["usd"] == pytest.approx(0.05)
    assert after["success_estimated"] is True and after["success_estimated_stages"] == ["S3"]
