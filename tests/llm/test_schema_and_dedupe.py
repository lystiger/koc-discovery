"""Tests for strict reasons schema (bug 1) and evidence de-duplication (bug 2)."""
import json

import httpx

from koc.llm.content import ContentAnalysisPayload, dedupe_payload, _validate_payload, analyze_video
from koc.llm.openrouter import OpenRouterClient
from koc.llm.reasons import (
    RecommendationPayload,
    build_recommendation_schema,
    write_reasons,
    _get_valid_evidence_ids,
)

from tests.llm.test_openrouter import (
    SpyGuard,
    _create_test_video,
    _make_sample_brief,
    _make_sample_video,
    _make_valid_analysis_payload,
)
from tests.llm.test_reasons import _make_sample_candidate, _make_sample_brief as _reasons_brief

OK_USAGE = {"prompt_tokens": 500, "completion_tokens": 200, "cost": 0.001}


def test_reasons_request_schema_required_and_enum(monkeypatch, stable_pricing_config):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    candidate = _make_sample_candidate()
    valid_ids = _get_valid_evidence_ids(candidate)
    bodies = []
    answer = {
        "creator_id": candidate.creator_id,
        "reasons_vi": ["Lý do một.", "Lý do hai.", "Lý do ba."],
        "cited_evidence_ids": [sorted(valid_ids)[0]],
        "caveats_vi": [],
    }

    def handle(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(answer)}}], "usage": OK_USAGE},
        )

    client = OpenRouterClient(http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    rec = write_reasons(candidate, _reasons_brief(), budget_guard=SpyGuard(), client=client)
    assert rec.cited_evidence_ids == answer["cited_evidence_ids"]

    fmt = bodies[0]["response_format"]["json_schema"]
    schema = fmt["schema"]
    assert fmt["strict"] is True
    assert set(schema["required"]) == {"creator_id", "reasons_vi", "cited_evidence_ids", "caveats_vi"}
    props = schema["properties"]
    assert props["reasons_vi"]["minItems"] == 3 and props["reasons_vi"]["maxItems"] == 5
    assert props["cited_evidence_ids"]["minItems"] == 1
    assert props["cited_evidence_ids"]["items"] == {"type": "string", "enum": sorted(valid_ids)}


def test_reasons_class_not_mutated():
    before = RecommendationPayload.model_json_schema()
    build_recommendation_schema({"a"})
    assert RecommendationPayload.model_json_schema() == before


def test_dedupe_payload_keeps_first_and_validates():
    vid = "7703507645981920520"
    data = _make_valid_analysis_payload(vid)
    dup = dict(data["evidence"][0])
    dup["quote_vi"] = "Khung hình khác cùng mốc thời gian"
    data["evidence"].insert(1, dup)
    data["rubric"][0]["evidence_ids"] = [f"{vid}@0.5", f"{vid}@0.5"]

    payload = ContentAnalysisPayload.model_validate(data)
    assert _validate_payload(payload, vid, 10.0)  # duplicate error before fix
    payload = dedupe_payload(payload)
    assert [e.evidence_id for e in payload.evidence].count(f"{vid}@0.5") == 1
    assert payload.evidence[0].quote_vi == "Giơ sản phẩm mở đầu"
    assert payload.rubric[0].evidence_ids == [f"{vid}@0.5"]
    assert _validate_payload(payload, vid, 10.0) == []


def test_analyze_video_survives_duplicate_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    video_path = tmp_path / "v.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    data = _make_valid_analysis_payload(video.video_id)
    data["evidence"].append(dict(data["evidence"][0]))
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": json.dumps(data)}}], "usage": OK_USAGE},
        )

    client = OpenRouterClient(http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    result = analyze_video(
        video, _make_sample_brief(), budget_guard=SpyGuard(), client=client, frames_dir=str(tmp_path / "f")
    )
    assert len(calls) == 1
    assert len(result.evidence) == 5
