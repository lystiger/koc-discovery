import json
from unittest.mock import MagicMock
import pytest

from koc.types import (
    CandidateSummary,
    BrandBrief,
    Recommendation,
    ContentAnalysis,
    RubricScore,
    Evidence,
    Usage,
    BudgetExceeded,
)
from koc.llm.reasons import write_reasons


class SpyGuard:
    def __init__(self):
        self.events = []

    def check(self, estimated_usd: float) -> None:
        self.events.append(("check", estimated_usd))

    def record(self, usage: Usage) -> None:
        self.events.append(("record", usage.cost_usd, usage))


def _make_sample_candidate() -> CandidateSummary:
    video_id = "7705660238917143816"
    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )
    analysis = ContentAnalysis(
        video_id=video_id,
        transcript_vi="Thử kem chống nắng này nhé.",
        rubric=[
            RubricScore(criterion="hook", score=4, rationale_vi="Hook tốt", evidence_ids=[f"{video_id}@0.5"]),
            RubricScore(criterion="product_clarity", score=5, rationale_vi="Rõ ràng", evidence_ids=[f"{video_id}@3.0"]),
            RubricScore(criterion="demonstration", score=4, rationale_vi="Thử thực tế", evidence_ids=[f"{video_id}@6.0"]),
            RubricScore(criterion="claim_quality", score=4, rationale_vi="Khoa học", evidence_ids=[f"{video_id}@6.0"]),
            RubricScore(criterion="cta", score=4, rationale_vi="Rõ CTA", evidence_ids=[f"{video_id}@21.0"]),
            RubricScore(criterion="brand_fit", score=5, rationale_vi="Hợp tệp", evidence_ids=[f"{video_id}@0.5"]),
            RubricScore(criterion="production_quality", score=4, rationale_vi="Đẹp", evidence_ids=[f"{video_id}@0.5"]),
        ],
        risks_vi=[],
        evidence=[
            Evidence(evidence_id=f"{video_id}@0.5", video_id=video_id, start_s=0.5, end_s=1.0, kind="frame", quote_vi="Mở đầu", frame_path=None),
            Evidence(evidence_id=f"{video_id}@3.0", video_id=video_id, start_s=3.0, end_s=4.0, kind="frame", quote_vi="Sản phẩm", frame_path=None),
            Evidence(evidence_id=f"{video_id}@6.0", video_id=video_id, start_s=6.0, end_s=7.0, kind="frame", quote_vi="Bôi thử", frame_path=None),
            Evidence(evidence_id=f"{video_id}@21.0", video_id=video_id, start_s=21.0, end_s=23.0, kind="frame", quote_vi="CTA", frame_path=None),
        ],
        usage=usage,
    )

    return CandidateSummary(
        creator_id="cr_456",
        handle="lananh_skincare",
        followers=120000,
        commercial_score=82.5,
        audience_score=88.0,
        content_score=85.0,
        final_score=84.5,
        est_cost_vnd=5000000,
        metrics={
            "skincare_revenue_share": 0.75,
            "video_gpm": 3200000,
            "female_share": 0.82,
        },
        metric_evidence_ids={
            "skincare_revenue_share": "metric:cr_456:skincare_revenue_share",
            "video_gpm": "metric:cr_456:video_gpm",
            "female_share": "metric:cr_456:female_share",
        },
        analyses=[analysis],
    )


def _make_sample_brief() -> BrandBrief:
    return BrandBrief(
        product_vi="Kem chống nắng kiềm dầu nâng tông",
        audience_vi="Nữ 18-30 tuổi",
        budget_vnd=30000000,
    )


def test_write_reasons_success_order_and_amounts(stable_pricing_config):
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    rec_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": [
            "Doanh thu ngành hàng dưỡng da chiếm tới 75% tổng doanh thu của kênh.",
            "Tệp khán giả nữ chiếm 82%, hoàn toàn khớp với tệp phụ nữ 18-30 của nhãn hàng.",
            "Nội dung video có mở đầu cuốn hút và thị phạm bôi kem trực tiếp lên da rất chân thực.",
            "Chỉ số video GPM đạt 3.2 triệu VNĐ cho thấy hiệu quả chuyển đổi đơn hàng tốt.",
        ],
        "cited_evidence_ids": [
            "metric:cr_456:skincare_revenue_share",
            "metric:cr_456:female_share",
            "7705660238917143816@0.5",
            "7705660238917143816@6.0",
        ],
        "caveats_vi": [
            "Cần kiểm soát kịch bản để nhấn mạnh khả năng kiềm dầu tự nhiên, tránh so sánh tiêu cực với nhãn hàng khác."
        ],
    }

    mock_usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=350,
        latency_ms=650,
        cost_usd=0.002663,
    )

    def spy_generate_json(*args, **kwargs):
        spy_guard.events.append(("call", kwargs.get("max_output_tokens")))
        return json.dumps(rec_payload), mock_usage

    mock_client.generate_json.side_effect = spy_generate_json

    rec = write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)

    # 1. Assert exact sequence: check -> call -> record (Finding 7)
    event_names = [e[0] for e in spy_guard.events]
    assert event_names == ["check", "call", "record"]

    # 2. Assert ceiling output tokens = 800 from config
    assert spy_guard.events[1][1] == 800
    assert spy_guard.events[2][1] == mock_usage.cost_usd

    # 3. Validated output
    assert isinstance(rec, Recommendation)
    assert rec.creator_id == candidate.creator_id
    assert len(rec.reasons_vi) == 4
    assert len(rec.cited_evidence_ids) == 4
    assert rec.usage == mock_usage


def test_write_reasons_budget_guard_blocks():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()

    mock_guard = MagicMock()
    mock_guard.check.side_effect = BudgetExceeded("Hard cap $5.00 exceeded")
    mock_client = MagicMock()

    with pytest.raises(BudgetExceeded):
        write_reasons(candidate, brief, budget_guard=mock_guard, client=mock_client)

    mock_client.generate_json.assert_not_called()
    mock_guard.record.assert_not_called()


def test_write_reasons_repair_on_malformed_json():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    valid_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": [
            "Doanh thu dưỡng da cao.",
            "Tệp khán giả nữ chiếm tỷ lệ lớn.",
            "Video có mở đầu thu hút.",
        ],
        "cited_evidence_ids": [
            "metric:cr_456:skincare_revenue_share",
            "7705660238917143816@0.5",
        ],
        "caveats_vi": [],
    }

    usage1 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=50,
        latency_ms=400,
        cost_usd=0.0015,
    )
    usage2 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1_repair",
        input_tokens=2200,
        output_tokens=300,
        latency_ms=450,
        cost_usd=0.002775,
    )

    # First attempt: malformed JSON "{bad" (Finding 5)
    mock_client.generate_json.side_effect = [
        ("{bad", usage1),
        (json.dumps(valid_payload), usage2),
    ]

    rec = write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)

    # Both usages recorded before validation
    assert len(spy_guard.events) == 4
    assert [e[0] for e in spy_guard.events] == ["check", "record", "check", "record"]
    assert spy_guard.events[1][1] == usage1.cost_usd
    assert spy_guard.events[3][1] == usage2.cost_usd

    # Repair call contains full original context (Finding 6)
    repair_contents = mock_client.generate_json.call_args_list[1].kwargs["contents"]
    assert len(repair_contents) == 2
    assert candidate.creator_id in repair_contents[0]
    assert "Bản đề xuất trước đó không hợp lệ" in repair_contents[1]

    assert rec.creator_id == candidate.creator_id
    assert rec.usage == usage2


def test_write_reasons_fails_when_both_attempts_malformed():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=50,
        latency_ms=400,
        cost_usd=0.0015,
    )
    mock_client.generate_json.side_effect = [
        ("{bad", usage),
        ("{bad_again", usage),
    ]

    with pytest.raises(ValueError, match="JSON"):
        write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)

    assert len(spy_guard.events) == 4
    assert [e[0] for e in spy_guard.events] == ["check", "record", "check", "record"]


def test_write_reasons_rejects_wrong_creator_id():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Wrong creator ID in response (Finding 2) - should not be silently overwritten!
    bad_payload = {
        "creator_id": "wrong_creator_id",
        "reasons_vi": [
            "Doanh thu dưỡng da cao.",
            "Tệp khán giả nữ chiếm tỷ lệ lớn.",
            "Video có mở đầu thu hút.",
        ],
        "cited_evidence_ids": ["metric:cr_456:skincare_revenue_share"],
        "caveats_vi": [],
    }

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=300,
        latency_ms=500,
        cost_usd=0.002,
    )
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(bad_payload), usage),
    ]

    with pytest.raises(ValueError, match="Creator ID không khớp"):
        write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)

    assert mock_client.generate_json.call_count == 2


def test_write_reasons_rejects_empty_citations():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Empty cited_evidence_ids (Finding 2)
    bad_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": [
            "Doanh thu dưỡng da cao.",
            "Tệp khán giả nữ chiếm tỷ lệ lớn.",
            "Video có mở đầu thu hút.",
        ],
        "cited_evidence_ids": [],
        "caveats_vi": [],
    }

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=300,
        latency_ms=500,
        cost_usd=0.002,
    )
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(bad_payload), usage),
    ]

    with pytest.raises(ValueError, match="cited_evidence_ids"):
        write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)


def test_write_reasons_repair_retry_on_invalid_evidence_id():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    invalid_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": ["Lý do 1", "Lý do 2", "Lý do 3"],
        "cited_evidence_ids": [
            "metric:cr_456:skincare_revenue_share",
            "invented_fake_evidence_id",
        ],
        "caveats_vi": [],
    }

    valid_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": ["Lý do 1", "Lý do 2", "Lý do 3"],
        "cited_evidence_ids": [
            "metric:cr_456:skincare_revenue_share",
            "7705660238917143816@0.5",
        ],
        "caveats_vi": [],
    }

    usage1 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=300,
        latency_ms=500,
        cost_usd=0.002,
    )
    usage2 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1_repair",
        input_tokens=2200,
        output_tokens=300,
        latency_ms=450,
        cost_usd=0.0025,
    )

    mock_client.generate_json.side_effect = [
        (json.dumps(invalid_payload), usage1),
        (json.dumps(valid_payload), usage2),
    ]

    rec = write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)

    assert mock_client.generate_json.call_count == 2
    assert rec.cited_evidence_ids == ["metric:cr_456:skincare_revenue_share", "7705660238917143816@0.5"]


def test_write_reasons_rejects_invalid_reason_count():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()
    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Only 1 reason (must be 3-5)
    invalid_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": ["Chỉ có 1 lý do."],
        "cited_evidence_ids": ["metric:cr_456:skincare_revenue_share"],
        "caveats_vi": [],
    }

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=200,
        latency_ms=400,
        cost_usd=0.0015,
    )
    mock_client.generate_json.side_effect = [
        (json.dumps(invalid_payload), usage),
        (json.dumps(invalid_payload), usage),
    ]

    with pytest.raises(ValueError, match="reasons_vi"):
        write_reasons(candidate, brief, budget_guard=spy_guard, client=mock_client)


def test_write_reasons_repair_blocked_by_budget_guard():
    candidate = _make_sample_candidate()
    brief = _make_sample_brief()

    invalid_payload = {
        "creator_id": candidate.creator_id,
        "reasons_vi": ["Chỉ có 1 lý do."],
        "cited_evidence_ids": ["metric:cr_456:skincare_revenue_share"],
        "caveats_vi": [],
    }

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="reasons_v1",
        input_tokens=1800,
        output_tokens=200,
        latency_ms=400,
        cost_usd=0.0015,
    )

    mock_guard = MagicMock()
    mock_guard.check.side_effect = [None, BudgetExceeded("Exceeded on repair")]

    mock_client = MagicMock()
    mock_client.generate_json.return_value = (json.dumps(invalid_payload), usage)

    with pytest.raises(BudgetExceeded):
        write_reasons(candidate, brief, budget_guard=mock_guard, client=mock_client)

    assert mock_client.generate_json.call_count == 1
    assert mock_guard.record.call_count == 1


def test_budget_check_provable_upper_bound_refuses_before_call(stable_pricing_config):
    """R2-1: Prove that when real usage exceeds old heuristic estimate,
    the provable upper bound refuses the call BEFORE execution when near budget cap.
    """
    import sqlite3
    from koc import db
    from koc.budget_guard import BudgetGuard

    conn = sqlite3.connect(":memory:")
    db.init_db(conn)

    # Hard cap $5.00 USD, already spent $4.9955 USD
    guard = BudgetGuard(conn, cap_usd=5.0)
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO llm_calls(run_id, kind, request_hash, model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, cache_hit, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run_probe", "content", "hash0", "gemini-3.8-flash", "content_v1", 1000, 100, 200, 4.9955, 0, db.now()),
        )

    spent_before = conn.execute("SELECT SUM(cost_usd) FROM llm_calls").fetchone()[0]
    assert pytest.approx(spent_before, abs=1e-6) == 4.9955

    candidate = _make_sample_candidate()
    brief = _make_sample_brief()

    mock_client = MagicMock()

    # Under old heuristic (chars / 3): prompt 2557 chars was estimated at 853 tokens + 800 out = $0.003639.
    # 4.9955 + 0.003639 = 4.999139 <= 5.00 (old heuristic would dangerously allow the call).
    # Under provable upper bound (UTF-8 bytes): 3039 bytes in + 800 out = $0.005279.
    # 4.9955 + 0.005279 = 5.000779 > 5.00 (refused before the call).
    with pytest.raises(BudgetExceeded):
        write_reasons(candidate, brief, budget_guard=guard, client=mock_client)

    # Crucial assertion: Gemini client was NEVER called!
    mock_client.generate_json.assert_not_called()

    # Database spent was not changed
    spent_after = conn.execute("SELECT SUM(cost_usd) FROM llm_calls").fetchone()[0]
    assert pytest.approx(spent_after, abs=1e-6) == 4.9955



def test_missing_audience_score_renders_vietnamese_and_prompt_has_caveat_rule(stable_pricing_config):
    candidate = _make_sample_candidate().model_copy(update={"audience_score": None, "metrics": {"video_gpm": 3200000}, "metric_evidence_ids": {"video_gpm": "metric:cr_456:video_gpm"}})
    mock_client = MagicMock()
    mock_usage = Usage(provider="gemini", model="gemini-3.8-flash", prompt_version="reasons_v4", input_tokens=1, output_tokens=1, latency_ms=1, cost_usd=0.0)
    payload = {"creator_id": "cr_456", "reasons_vi": ["a", "b", "c"], "cited_evidence_ids": ["metric:cr_456:video_gpm"], "caveats_vi": ["Chưa xác minh hồ sơ khán giả."]}
    mock_client.generate_json.return_value = (json.dumps(payload), mock_usage)
    write_reasons(candidate, _make_sample_brief(), budget_guard=SpyGuard(), client=mock_client)
    call = mock_client.generate_json.call_args.kwargs
    prompt = call["contents"][0]
    assert call["prompt_version"] == "reasons_v4"
    assert "Điểm khán giả (audience): không có dữ liệu" in prompt
    assert "None" not in prompt and "N/A" not in prompt
    assert "gói Kalodata không có dữ liệu khán giả" in prompt


def _no_audience_candidate():
    return _make_sample_candidate().model_copy(update={
        "audience_score": None,
        "metrics": {"skincare_revenue_share": 0.75},
        "metric_evidence_ids": {"skincare_revenue_share": "metric:cr_456:skincare_revenue_share"},
    })


def _openrouter_client(payloads, monkeypatch):
    import httpx
    from koc.llm.openrouter import OpenRouterClient

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    queue = list(payloads)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(queue.pop(0))}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.0001},
        })

    return OpenRouterClient(http_client=httpx.Client(transport=httpx.MockTransport(handler))), queue


def _reasons_payload(reasons, caveats):
    return {"creator_id": "cr_456", "reasons_vi": reasons, "cited_evidence_ids": ["metric:cr_456:skincare_revenue_share"], "caveats_vi": caveats}


GOOD_REASONS = ["Doanh thu dưỡng da chiếm 75% tổng doanh thu.", "Video có mở đầu thu hút.", "Chi phí nằm trong ngân sách."]


def test_missing_audience_appends_mandatory_caveat_in_code(stable_pricing_config, monkeypatch):
    """F5: empty caveats from the model still yield the unverified-audience caveat; an existing one is not duplicated."""
    from koc.llm.reasons import AUDIENCE_MISSING_CAVEAT_VI

    client, _ = _openrouter_client([_reasons_payload(GOOD_REASONS, [])], monkeypatch)
    rec = write_reasons(_no_audience_candidate(), _make_sample_brief(), budget_guard=SpyGuard(), client=client)
    assert rec.caveats_vi == [AUDIENCE_MISSING_CAVEAT_VI]

    own = ["Hồ sơ khán giả chưa xác minh, cần hỏi creator."]
    client, _ = _openrouter_client([_reasons_payload(GOOD_REASONS, own)], monkeypatch)
    rec = write_reasons(_no_audience_candidate(), _make_sample_brief(), budget_guard=SpyGuard(), client=client)
    assert rec.caveats_vi == own


def test_missing_audience_rejects_demographic_claim_repairs_once_then_fails(stable_pricing_config, monkeypatch):
    bad = _reasons_payload(["Khán giả nữ chiếm 60%.", "Video có mở đầu thu hút.", "Chi phí hợp lý."], [])
    good = _reasons_payload(GOOD_REASONS, [])
    client, queue = _openrouter_client([bad, good], monkeypatch)
    rec = write_reasons(_no_audience_candidate(), _make_sample_brief(), budget_guard=SpyGuard(), client=client)
    assert not queue and rec.reasons_vi == GOOD_REASONS  # repaired exactly once

    client, queue = _openrouter_client([bad, bad], monkeypatch)
    with pytest.raises(ValueError, match="giới tính/độ tuổi"):
        write_reasons(_no_audience_candidate(), _make_sample_brief(), budget_guard=SpyGuard(), client=client)
    assert not queue


@pytest.mark.parametrize("reason", [
    "Tệp khán giả nữ chiếm 60%.", "Độ tuổi 18-24 chiếm 30,5% người xem.", "Nữ giới 60 %, hợp tệp mục tiêu.", "Nhóm 25-34 đạt 39.5%.",
])
def test_audience_claim_detector_flags_demographic_percentages(reason):
    from koc.llm.reasons import _audience_claims

    assert _audience_claims([reason]) == [reason]
    assert _audience_claims(["Doanh thu dưỡng da chiếm 75% tổng doanh thu."]) == []
