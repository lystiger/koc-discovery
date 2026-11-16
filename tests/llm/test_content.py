import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock
import pytest

from koc.types import VideoInput, BrandBrief, ContentAnalysis, BudgetExceeded, Usage
from koc.llm.content import analyze_video, ContentAnalysisPayload
from koc.llm.pricing import estimate_usd, load_pricing_config


def _create_test_video(path: Path, duration_s: float = 3.0, width: int = 360, height: int = 640) -> Path:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size={width}x{height}:rate=10",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_s}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "32k",
        str(path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return path


def _make_sample_video(video_path: Path, video_id: str = "7705660238917143816") -> VideoInput:
    return VideoInput(
        video_id=video_id,
        creator_id="creator_123",
        title="Review kem chống nắng kiềm dầu",
        publish_date="2026-11-01",
        views=150000,
        likes=8500,
        comments=420,
        shares=120,
        revenue_vnd=15000000.0,
        mp4_path=str(video_path),
    )


def _make_sample_brief() -> BrandBrief:
    return BrandBrief(
        product_vi="Kem chống nắng kiềm dầu nâng tông",
        audience_vi="Nữ 18-30 tuổi",
        budget_vnd=30000000,
    )


def _make_valid_analysis_payload(video_id: str = "7705660238917143816") -> dict:
    return {
        "video_id": video_id,
        "transcript_vi": "Xin chào mọi người, hôm nay mình sẽ thử kem chống nắng [không rõ] này nhé.",
        "rubric": [
            {"criterion": "hook", "score": 4, "rationale_vi": "Mở đầu nhanh, giơ sản phẩm trực diện.", "evidence_ids": [f"{video_id}@0.5"]},
            {"criterion": "product_clarity", "score": 5, "rationale_vi": "Thấy rõ bảng thành phần và chỉ số SPF.", "evidence_ids": [f"{video_id}@0.81"]},
            {"criterion": "demonstration", "score": 4, "rationale_vi": "Thoa thử lên mu bàn tay và má.", "evidence_ids": [f"{video_id}@1.12"]},
            {"criterion": "claim_quality", "score": 4, "rationale_vi": "Tuyên bố thực tế về kiềm dầu, không quá đà.", "evidence_ids": [f"{video_id}:transcript:1"]},
            {"criterion": "cta", "score": 4, "rationale_vi": "Kêu gọi bấm vào giỏ hàng góc trái.", "evidence_ids": [f"{video_id}@2.06"]},
            {"criterion": "brand_fit", "score": 5, "rationale_vi": "Rất hợp tệp nữ trẻ 18-30 năng động.", "evidence_ids": [f"{video_id}@0.5"]},
            {"criterion": "production_quality", "score": 4, "rationale_vi": "Ánh sáng tốt, hình ảnh sắc nét.", "evidence_ids": [f"{video_id}@0.5"]},
        ],
        "risks_vi": ["Không có phát ngôn y khoa quá đà."],
        "evidence": [
            {"evidence_id": f"{video_id}@0.5", "video_id": video_id, "start_s": 0.5, "end_s": 0.7, "kind": "frame", "quote_vi": "Giơ sản phẩm mở đầu", "frame_path": None},
            {"evidence_id": f"{video_id}@0.81", "video_id": video_id, "start_s": 0.81, "end_s": 1.0, "kind": "frame", "quote_vi": "Cận cảnh bao bì", "frame_path": None},
            {"evidence_id": f"{video_id}@1.12", "video_id": video_id, "start_s": 1.12, "end_s": 1.5, "kind": "frame", "quote_vi": "Thoa kem lên tay", "frame_path": None},
            {"evidence_id": f"{video_id}:transcript:1", "video_id": video_id, "start_s": 1.5, "end_s": 2.5, "kind": "speech", "quote_vi": "Chất kem mỏng nhẹ thấm nhanh", "frame_path": None},
            {"evidence_id": f"{video_id}@2.06", "video_id": video_id, "start_s": 2.06, "end_s": 2.8, "kind": "frame", "quote_vi": "Chỉ tay vào giỏ hàng", "frame_path": None},
        ],
    }


class SpyGuard:
    def __init__(self):
        self.events = []

    def check(self, estimated_usd: float) -> None:
        self.events.append(("check", estimated_usd))

    def record(self, usage: Usage) -> None:
        self.events.append(("record", usage.cost_usd, usage))


def test_analyze_video_success_order_and_amendment_a1(tmp_path: Path, stable_pricing_config):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    frames_dir = tmp_path / "persistent_frames"
    spy_guard = SpyGuard()

    mock_client = MagicMock()
    valid_payload = _make_valid_analysis_payload(video.video_id)
    mock_usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4024,
        output_tokens=850,
        audio_tokens=96,
        image_tokens=2064,
        latency_ms=1250,
        cost_usd=0.006205,
        cache_hit=False,
    )

    def spy_generate_json(*args, **kwargs):
        spy_guard.events.append(("call", kwargs.get("max_output_tokens")))
        return json.dumps(valid_payload), mock_usage

    mock_client.generate_json.side_effect = spy_generate_json

    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        frames_dir=str(frames_dir),
    )

    # 1. Assert exact event sequence: check -> call -> record (Finding 7)
    event_names = [e[0] for e in spy_guard.events]
    assert event_names == ["check", "call", "record"]

    # Assert exact amounts
    check_amount = spy_guard.events[0][1]
    assert check_amount > 0
    assert spy_guard.events[1][1] == 1200  # max_output_tokens enforced
    record_cost = spy_guard.events[2][1]
    assert record_cost == mock_usage.cost_usd

    # 2. Amendment A1: frames persistent on disk, named f_<t_ms>.jpg, frame_path mapped by code
    target_video_frames = frames_dir / video.video_id
    assert target_video_frames.is_dir()
    persisted_files = list(target_video_frames.glob("f_*.jpg"))
    assert len(persisted_files) == 8

    # Check evidence frame_path mapping
    for ev in analysis.evidence:
        if ev.kind == "frame":
            assert ev.frame_path is not None
            assert Path(ev.frame_path).is_file()
            assert str(target_video_frames) in ev.frame_path
        else:
            assert ev.frame_path is None

    assert analysis.video_id == video.video_id
    assert len(analysis.rubric) == 7
    assert analysis.usage == mock_usage


def test_analyze_video_budget_guard_blocks(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    mock_guard = MagicMock()
    mock_guard.check.side_effect = BudgetExceeded("Hard cap $5.00 exceeded")
    mock_client = MagicMock()

    with pytest.raises(BudgetExceeded):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=mock_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )

    mock_client.generate_json.assert_not_called()
    mock_guard.record.assert_not_called()


def test_analyze_video_repair_on_malformed_json(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    valid_payload = _make_valid_analysis_payload(video.video_id)
    usage1 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=100,
        latency_ms=800,
        cost_usd=0.003375,
    )
    usage2 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1_repair",
        input_tokens=4500,
        output_tokens=850,
        latency_ms=900,
        cost_usd=0.006562,
    )

    # First attempt: malformed JSON "{bad" (Finding 5)
    # Second attempt: valid payload
    mock_client.generate_json.side_effect = [
        ("{bad", usage1),
        (json.dumps(valid_payload), usage2),
    ]

    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    # Both responses recorded into budget guard before validation
    assert len(spy_guard.events) == 4
    assert [e[0] for e in spy_guard.events] == ["check", "record", "check", "record"]
    assert spy_guard.events[1][1] == usage1.cost_usd
    assert spy_guard.events[3][1] == usage2.cost_usd
    assert mock_client.generate_json.call_count == 2

    # Check that repair request contains full original context (Finding 6)
    repair_call_contents = mock_client.generate_json.call_args_list[1].kwargs["contents"]
    # Should contain original prompt, 8 frames, audio, and Vietnamese repair instruction
    assert len(repair_call_contents) > 2
    repair_instruction = repair_call_contents[-1]
    assert "Phản hồi trước đó không hợp lệ" in repair_instruction
    assert "tiếng Việt" in repair_instruction

    assert analysis.video_id == video.video_id
    assert analysis.usage == usage2


def test_analyze_video_fails_when_both_attempts_malformed_json(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    usage1 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=50,
        latency_ms=500,
        cost_usd=0.003,
    )

    mock_client.generate_json.side_effect = [
        ("{bad", usage1),
        ("{bad_again", usage1),
    ]

    with pytest.raises(ValueError, match="JSON"):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=spy_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )

    # Max 2 attempts, both recorded
    assert len(spy_guard.events) == 4
    assert [e[0] for e in spy_guard.events] == ["check", "record", "check", "record"]


def test_analyze_video_repair_on_empty_citations(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # First payload: all rubric criteria have empty citations (Finding 2)
    invalid_payload = _make_valid_analysis_payload(video.video_id)
    for r in invalid_payload["rubric"]:
        r["evidence_ids"] = []

    valid_payload = _make_valid_analysis_payload(video.video_id)

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )

    mock_client.generate_json.side_effect = [
        (json.dumps(invalid_payload), usage),
        (json.dumps(valid_payload), usage),
    ]

    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert mock_client.generate_json.call_count == 2
    assert analysis.video_id == video.video_id


def test_analyze_video_rejects_wrong_video_and_empty_evidence(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path, video_id="7705660238917143816")
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Payload with wrong video_id and empty evidence (Finding 2)
    bad_payload = _make_valid_analysis_payload("wrong_video_id")
    bad_payload["evidence"] = []

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(bad_payload), usage),
    ]

    with pytest.raises(ValueError, match="Video ID không khớp"):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=spy_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )

    assert mock_client.generate_json.call_count == 2


def test_analyze_video_rejects_duplicate_rubric_criteria(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    bad_payload = _make_valid_analysis_payload(video.video_id)
    # Duplicate "hook" criterion
    bad_payload["rubric"][1]["criterion"] = "hook"

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(bad_payload), usage),
    ]

    with pytest.raises(ValueError, match="trùng lặp"):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=spy_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )


def test_analyze_video_repair_blocked_by_budget_guard(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    bad_payload = _make_valid_analysis_payload(video.video_id)
    bad_payload["rubric"][0]["evidence_ids"] = []

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )

    mock_guard = MagicMock()
    # Check 1 passes, check 2 raises BudgetExceeded
    mock_guard.check.side_effect = [None, BudgetExceeded("Exceeded on repair")]

    mock_client = MagicMock()
    mock_client.generate_json.return_value = (json.dumps(bad_payload), usage)

    with pytest.raises(BudgetExceeded):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=mock_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )

    # 1 call made, 1 record made, second call blocked by guard check
    assert mock_client.generate_json.call_count == 1
    assert mock_guard.record.call_count == 1


def test_analyze_video_rejects_evidence_timestamp_past_duration(tmp_path: Path):
    """R2-2: Reject evidence with start_s or end_s > duration_s (e.g. 3.4s in 3.0s video); triggers repair loop."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    bad_payload = _make_valid_analysis_payload(video.video_id)
    # Evidence 0: start_s=3.4, end_s=3.4 in a 3.0s video
    bad_payload["evidence"][0]["start_s"] = 3.4
    bad_payload["evidence"][0]["end_s"] = 3.4
    bad_payload["evidence"][0]["evidence_id"] = f"{video.video_id}@3.4"
    for r in bad_payload["rubric"]:
        if f"{video.video_id}@0.5" in r["evidence_ids"]:
            r["evidence_ids"] = [f"{video.video_id}@3.4" if x == f"{video.video_id}@0.5" else x for x in r["evidence_ids"]]

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )

    mock_guard = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(bad_payload), usage),
    ]

    with pytest.raises(ValueError, match="Mốc thời gian start_s không hợp lệ: 3.4s"):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=mock_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )

    # Verified repair loop was triggered (2 calls made)
    assert mock_client.generate_json.call_count == 2


def test_analyze_video_rejects_nan_timestamp(tmp_path: Path):
    """R2-2: Reject evidence with NaN start_s; triggers repair loop."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    bad_payload = _make_valid_analysis_payload(video.video_id)
    bad_payload["evidence"][0]["start_s"] = float("nan")

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )

    mock_guard = MagicMock()
    mock_client = MagicMock()
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(bad_payload), usage),
    ]

    with pytest.raises(ValueError, match="Mốc thời gian start_s không phải số hữu hạn"):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=mock_guard,
            client=mock_client,
            preprocess_dir=str(tmp_path / "work"),
        )

    assert mock_client.generate_json.call_count == 2


def test_analyze_video_rejects_evidence_id_timestamp_mismatch_at_999(tmp_path: Path):
    """R2-2: Reject evidence where ID timestamp @999 does not match start_s=0.5; triggers repair loop."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    bad_payload = _make_valid_analysis_payload(video.video_id)
    # Timestamp mismatch: evidence_id is @999, but start_s is 0.5
    bad_payload["evidence"][0]["evidence_id"] = f"{video.video_id}@999"
    bad_payload["evidence"][0]["start_s"] = 0.5
    for r in bad_payload["rubric"]:
        if f"{video.video_id}@0.5" in r["evidence_ids"]:
            r["evidence_ids"] = [f"{video.video_id}@999" if x == f"{video.video_id}@0.5" else x for x in r["evidence_ids"]]

    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=1000,
        cost_usd=0.006,
    )

    valid_payload = _make_valid_analysis_payload(video.video_id)

    mock_guard = MagicMock()
    mock_client = MagicMock()
    # Attempt 0: bad @999 payload; Attempt 1: corrected payload
    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage),
        (json.dumps(valid_payload), usage),
    ]

    result = analyze_video(
        video=video,
        brief=brief,
        budget_guard=mock_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert isinstance(result, ContentAnalysis)
    assert mock_client.generate_json.call_count == 2
    # Verify second call included repair instructions naming the timestamp mismatch
    repair_contents = mock_client.generate_json.call_args_list[1].kwargs["contents"]
    repair_text = [c for c in repair_contents if isinstance(c, str)][-1]
    assert "không khớp với start_s" in repair_text


def test_analyze_video_no_audio_stream(tmp_path: Path, stable_pricing_config):
    """R2-3: Video without audio stream:
    - Preprocess returns audio_path=None.
    - analyze_video sends frames only (no audio Part).
    - transcript_vi is None.
    - Missing audio is noted in risks_vi.
    - Budget estimate is computed without audio tokens.
    """
    video_path = tmp_path / "silent_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2.0:size=360x640:rate=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    video = _make_sample_video(video_path)
    brief = _make_sample_brief()
    spy_guard = SpyGuard()

    # Model payload for silent video: frames only, transcript_vi=None
    silent_payload = {
        "video_id": video.video_id,
        "transcript_vi": None,
        "rubric": [
            {"criterion": "hook", "score": 4, "rationale_vi": "Khung hình đầu rõ nét.", "evidence_ids": [f"{video.video_id}@0.5"]},
            {"criterion": "product_clarity", "score": 5, "rationale_vi": "Nhìn rõ bao bì sản phẩm.", "evidence_ids": [f"{video.video_id}@0.81"]},
            {"criterion": "demonstration", "score": 4, "rationale_vi": "Thị phạm sản phẩm trên da.", "evidence_ids": [f"{video.video_id}@1.12"]},
            {"criterion": "claim_quality", "score": 3, "rationale_vi": "Thông tin chữ trên màn hình.", "evidence_ids": [f"{video.video_id}@1.12"]},
            {"criterion": "cta", "score": 4, "rationale_vi": "Chỉ tay vào giỏ hàng.", "evidence_ids": [f"{video.video_id}@1.81"]},
            {"criterion": "brand_fit", "score": 4, "rationale_vi": "Phù hợp tệp khách hàng.", "evidence_ids": [f"{video.video_id}@0.5"]},
            {"criterion": "production_quality", "score": 3, "rationale_vi": "Hình ảnh sáng rõ nhưng thiếu âm thanh.", "evidence_ids": [f"{video.video_id}@0.5"]},
        ],
        "risks_vi": ["Video không có âm thanh."],
        "evidence": [
            {"evidence_id": f"{video.video_id}@0.5", "video_id": video.video_id, "start_s": 0.5, "end_s": 0.7, "kind": "frame", "quote_vi": "Mở đầu sản phẩm", "frame_path": None},
            {"evidence_id": f"{video.video_id}@0.81", "video_id": video.video_id, "start_s": 0.81, "end_s": 1.0, "kind": "frame", "quote_vi": "Bao bì sản phẩm", "frame_path": None},
            {"evidence_id": f"{video.video_id}@1.12", "video_id": video.video_id, "start_s": 1.12, "end_s": 1.5, "kind": "frame", "quote_vi": "Thị phạm sản phẩm", "frame_path": None},
            {"evidence_id": f"{video.video_id}@1.81", "video_id": video.video_id, "start_s": 1.81, "end_s": 1.9, "kind": "frame", "quote_vi": "Chỉ tay giỏ hàng", "frame_path": None},
        ],
    }

    mock_usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v1",
        input_tokens=3000,
        output_tokens=700,
        latency_ms=900,
        cost_usd=0.004875,
    )

    mock_client = MagicMock()
    mock_client.generate_json.return_value = (json.dumps(silent_payload), mock_usage)

    result = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    # 1. Verification of contents sent to Gemini: NO audio Part
    call_args = mock_client.generate_json.call_args
    contents_sent = call_args.kwargs["contents"]
    part_types = [getattr(c, "mime_type", None) for c in contents_sent if hasattr(c, "mime_type")]
    assert "audio/mp3" not in part_types
    assert all(mt == "image/jpeg" for mt in part_types)

    # 2. Verification of budget check: audio tokens was 0
    check_event = spy_guard.events[0]
    assert check_event[0] == "check"
    est_checked = check_event[1]

    # Calculate expected estimate without audio:
    text_parts = [c for c in contents_sent if isinstance(c, str)]
    expected_est = estimate_usd(
        n_frames=8,
        audio_s=0.0,
        est_output_tokens=1200,
        frame_sizes=[(360, 640)] * 8,
        text_parts=text_parts,
        response_schema=ContentAnalysisPayload,
        has_audio=False,
    )
    assert pytest.approx(est_checked, abs=1e-6) == expected_est

    # 3. Verification of ContentAnalysis result
    assert result.transcript_vi is None
    assert any("âm thanh" in r.lower() or "audio" in r.lower() for r in result.risks_vi)


def test_prompt_content_v2_exists_and_contains_limits():
    """Requirement (1): prompts/content_v2.md exists and specifies the exact limits in Vietnamese."""
    prompt_file = Path(__file__).resolve().parents[2] / "prompts" / "content_v2.md"
    assert prompt_file.is_file(), "prompts/content_v2.md must exist"
    content = prompt_file.read_text(encoding="utf-8")

    # Vietnamese limits:
    # 1. transcript_vi: key passages only, max 1200 characters
    assert "1200" in content
    assert "transcript_vi" in content
    assert any(term in content.lower() for term in ["then chốt", "key passages"])
    # 2. quote_vi max 200 characters
    assert "200" in content
    assert "quote_vi" in content
    # 3. rationale_vi max 250 characters
    assert "250" in content
    assert "rationale_vi" in content
    # 4. at most 12 evidence items
    assert "12" in content
    assert "evidence" in content


def test_truncation_helper_word_boundary():
    """Requirement (3): Truncate at word boundary without cutting words in half."""
    from koc.llm.content import truncate_at_word_boundary

    # Under limit
    assert truncate_at_word_boundary("Ngắn", 10) == "Ngắn"
    assert truncate_at_word_boundary("", 10) == ""
    assert truncate_at_word_boundary(None, 10) is None

    # Exact limit
    assert truncate_at_word_boundary("Chính xác", 9) == "Chính xác"

    # Truncate at space
    sample = "Xin chào các bạn hôm nay mình review kem chống nắng"
    # Cut at 15: "Xin chào các bạ" -> last space is before "bạn", so "Xin chào các"
    truncated = truncate_at_word_boundary(sample, 15)
    assert truncated == "Xin chào các"
    assert len(truncated) <= 15

    # Boundary right at space
    assert truncate_at_word_boundary("Xin chào các", 8) == "Xin chào"

    # Single long word without spaces: hard truncate at max_chars
    long_word = "A" * 300
    assert truncate_at_word_boundary(long_word, 200) == "A" * 200


def test_defensive_enforcement_of_limits_on_parsed_payload(tmp_path: Path):
    """Requirement (3): After parsing, defensive truncation enforces limits before validation."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    base_payload = _make_valid_analysis_payload(video.video_id)

    # Transcript ~1300 chars
    long_transcript = "Đoạn lời thoại then chốt của video rất dài. " * 30
    assert len(long_transcript) > 1200
    base_payload["transcript_vi"] = long_transcript

    # Quote > 200 chars
    long_quote = "Trích dẫn bằng chứng rất chi tiết và vượt quá giới hạn hai trăm ký tự. " * 4
    assert len(long_quote) > 200
    base_payload["evidence"][0]["quote_vi"] = long_quote

    # Rationale > 250 chars
    long_rationale = "Giải trình cho tiêu chí hook cực kỳ chi tiết, phân tích từng giây mở đầu và cảm xúc người xem. " * 3
    assert len(long_rationale) > 250
    base_payload["rubric"][0]["rationale_vi"] = long_rationale

    # 15 evidence items
    extra_evidence = []
    for i in range(5, 15):
        t = round(0.5 + (i - 4) * 0.2, 2)
        extra_evidence.append({
            "evidence_id": f"{video.video_id}@{t}",
            "video_id": video.video_id,
            "start_s": t,
            "end_s": round(t + 0.1, 2),
            "kind": "frame",
            "quote_vi": f"Khung hình phụ thứ {i}",
            "frame_path": None,
        })
    base_payload["evidence"].extend(extra_evidence)
    assert len(base_payload["evidence"]) == 15

    spy_guard = SpyGuard()
    mock_client = MagicMock()
    mock_usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v2",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=900,
        cost_usd=0.005,
    )
    mock_client.generate_json.return_value = (json.dumps(base_payload), mock_usage)

    # Should succeed on attempt 0 without triggering repair
    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert mock_client.generate_json.call_count == 1
    assert len(analysis.transcript_vi) <= 1200
    assert not analysis.transcript_vi.endswith(" ")
    assert len(analysis.evidence[0].quote_vi) <= 200
    assert len(analysis.rubric[0].rationale_vi) <= 250
    assert len(analysis.evidence) <= 12


def test_analyze_video_passes_content_v3_prompt_version(tmp_path: Path):
    """Requirement (1): prompt_version must be content_v3 on initial and content_v3_repair on retry."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()
    valid_payload = _make_valid_analysis_payload(video.video_id)
    usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v3",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=900,
        cost_usd=0.005,
    )
    mock_client.generate_json.side_effect = [
        ("{malformed", usage),
        (json.dumps(valid_payload), usage),
    ]

    analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert mock_client.generate_json.call_count == 2
    assert mock_client.generate_json.call_args_list[0].kwargs["prompt_version"] == "content_v3"
    assert mock_client.generate_json.call_args_list[1].kwargs["prompt_version"] == "content_v3_repair"


def test_long_video_budget_estimate_uses_clipped_duration_and_rejects_out_of_window_timestamps(tmp_path: Path):
    """Requirements (2) & (4): Budget uses clipped duration (<=90s); evidence beyond window rejected."""
    video_path = tmp_path / "video_100s.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=100:size=360x640:rate=1",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=100",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "32k",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Payload with evidence at 95.0s (beyond 90s analyzed window)
    bad_payload = _make_valid_analysis_payload(video.video_id)
    bad_payload["evidence"][0]["evidence_id"] = f"{video.video_id}@95.0"
    bad_payload["evidence"][0]["start_s"] = 95.0
    bad_payload["evidence"][0]["end_s"] = 96.0
    bad_payload["rubric"][0]["evidence_ids"] = [f"{video.video_id}@95.0"]

    valid_payload = _make_valid_analysis_payload(video.video_id)

    usage1 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v3",
        input_tokens=4000,
        output_tokens=100,
        latency_ms=800,
        cost_usd=0.003,
    )
    usage2 = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v3_repair",
        input_tokens=4500,
        output_tokens=850,
        latency_ms=900,
        cost_usd=0.006,
    )

    mock_client.generate_json.side_effect = [
        (json.dumps(bad_payload), usage1),
        (json.dumps(valid_payload), usage2),
    ]

    analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    # 1. Initial call failed due to timestamp 95s exceeding 90s analyzed window, trigger repair
    assert mock_client.generate_json.call_count == 2
    repair_instruction = mock_client.generate_json.call_args_list[1].kwargs["contents"][-1]
    assert "start_s" in repair_instruction or "90.0" in repair_instruction

    # 2. Budget estimation was based on clipped duration (90s, not 100s)
    call1_contents = mock_client.generate_json.call_args_list[0].kwargs["contents"]
    text_parts = [c for c in call1_contents if isinstance(c, str)]
    cfg = load_pricing_config()
    max_out = int(cfg.get("token_accounting", {}).get("default_content_output_tokens", 4096))
    expected_est_usd = estimate_usd(
        n_frames=8,
        audio_s=90.0,
        est_output_tokens=max_out,
        frame_sizes=[(360, 640)] * 8,
        text_parts=text_parts,
        response_schema=ContentAnalysisPayload,
        has_audio=True,
    )
    assert pytest.approx(spy_guard.events[0][1], abs=1e-6) == expected_est_usd


def test_prompt_content_v3_exists_and_has_no_transcript_vi():
    """Requirement (1): prompts/content_v3.md exists, specifies limits in Vietnamese, and has NO transcript_vi."""
    prompt_file = Path(__file__).resolve().parents[2] / "prompts" / "content_v3.md"
    assert prompt_file.is_file(), "prompts/content_v3.md must exist"
    content = prompt_file.read_text(encoding="utf-8")

    assert "transcript_vi" not in content
    # quote_vi max 200 characters
    assert "200" in content
    assert "quote_vi" in content
    # rationale_vi max 250 characters
    assert "250" in content
    assert "rationale_vi" in content
    # at most 12 evidence items
    assert "12" in content
    assert "evidence" in content


def test_schema_has_no_transcript_vi_and_has_limits():
    """Requirement (1) & (2): ContentAnalysisPayload schema has no transcript_vi, has maxLength and maxItems."""
    schema = ContentAnalysisPayload.model_json_schema()

    assert "transcript_vi" not in schema["properties"], "transcript_vi must be removed from schema"
    assert schema["properties"]["evidence"].get("maxItems") == 12, "evidence must have maxItems=12"

    defs = schema.get("$defs", {})
    ev_props = defs["EvidenceItemPayload"]["properties"]
    assert ev_props["quote_vi"].get("maxLength") == 200, "quote_vi must have maxLength=200"

    rubric_props = defs["RubricScorePayload"]["properties"]
    assert rubric_props["rationale_vi"].get("maxLength") == 250, "rationale_vi must have maxLength=250"


def test_transcript_vi_built_from_speech_evidence_in_time_order(tmp_path: Path):
    """Requirement (1): ContentAnalysis.transcript_vi is built in code by joining speech evidence in time order, capped at 1200 chars."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Evidence out of order and mixed kinds (speech, frame, on_screen_text)
    # The speech quotes should be sorted by start_s: 0.5s -> 1.5s -> 2.0s
    payload = {
        "video_id": video.video_id,
        "rubric": [
            {"criterion": "hook", "score": 4, "rationale_vi": "Mở đầu nhanh", "evidence_ids": [f"{video.video_id}@0.5"]},
            {"criterion": "product_clarity", "score": 5, "rationale_vi": "Bao bì rõ ràng", "evidence_ids": [f"{video.video_id}@0.81"]},
            {"criterion": "demonstration", "score": 4, "rationale_vi": "Thoa kem", "evidence_ids": [f"{video.video_id}@1.12"]},
            {"criterion": "claim_quality", "score": 4, "rationale_vi": "Tuyên bố thực tế", "evidence_ids": [f"{video.video_id}:transcript:1"]},
            {"criterion": "cta", "score": 4, "rationale_vi": "Kêu gọi hành động", "evidence_ids": [f"{video.video_id}@2.0"]},
            {"criterion": "brand_fit", "score": 5, "rationale_vi": "Hợp tệp", "evidence_ids": [f"{video.video_id}@0.5"]},
            {"criterion": "production_quality", "score": 4, "rationale_vi": "Ánh sáng tốt", "evidence_ids": [f"{video.video_id}@0.5"]},
        ],
        "risks_vi": [],
        "evidence": [
            {"evidence_id": f"{video.video_id}@2.0", "video_id": video.video_id, "start_s": 2.0, "end_s": 2.5, "kind": "speech", "quote_vi": "Bấm vào giỏ hàng nhé."},
            {"evidence_id": f"{video.video_id}@0.5", "video_id": video.video_id, "start_s": 0.5, "end_s": 0.8, "kind": "speech", "quote_vi": "Xin chào mọi người."},
            {"evidence_id": f"{video.video_id}@0.81", "video_id": video.video_id, "start_s": 0.81, "end_s": 1.0, "kind": "frame", "quote_vi": "Khung hình cận cảnh bao bì"},
            {"evidence_id": f"{video.video_id}@1.12", "video_id": video.video_id, "start_s": 1.12, "end_s": 1.5, "kind": "on_screen_text", "quote_vi": "Chữ giảm giá 20%"},
            {"evidence_id": f"{video.video_id}:transcript:1", "video_id": video.video_id, "start_s": 1.5, "end_s": 1.9, "kind": "speech", "quote_vi": "Hôm nay mình review kem chống nắng."},
        ],
    }

    mock_usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v3",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=900,
        cost_usd=0.005,
    )
    mock_client.generate_json.return_value = (json.dumps(payload), mock_usage)

    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    # Built from speech evidence quotes in time order (0.5s -> 1.5s -> 2.0s)
    expected_transcript = "Xin chào mọi người. Hôm nay mình review kem chống nắng. Bấm vào giỏ hàng nhé."
    assert analysis.transcript_vi == expected_transcript


def test_transcript_vi_capped_at_1200_chars(tmp_path: Path):
    """Requirement (1): transcript_vi is capped at 1200 characters at word boundary."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # 10 speech quotes each 150 chars -> 1500 chars total > 1200 limit
    ev_list = []
    for i in range(10):
        t = round(0.5 + i * 0.2, 2)
        quote = f"Đoạn lời thoại speech số {i} với độ dài vừa phải để kiểm tra giới hạn bóc băng. " * 2
        ev_list.append({
            "evidence_id": f"{video.video_id}@{t}",
            "video_id": video.video_id,
            "start_s": t,
            "end_s": round(t + 0.1, 2),
            "kind": "speech",
            "quote_vi": quote[:150],
        })

    payload = {
        "video_id": video.video_id,
        "rubric": [
            {"criterion": "hook", "score": 4, "rationale_vi": "Mở đầu nhanh", "evidence_ids": [f"{video.video_id}@0.5"]},
            {"criterion": "product_clarity", "score": 5, "rationale_vi": "Bao bì rõ ràng", "evidence_ids": [f"{video.video_id}@0.7"]},
            {"criterion": "demonstration", "score": 4, "rationale_vi": "Thoa kem", "evidence_ids": [f"{video.video_id}@0.9"]},
            {"criterion": "claim_quality", "score": 4, "rationale_vi": "Tuyên bố thực tế", "evidence_ids": [f"{video.video_id}@1.1"]},
            {"criterion": "cta", "score": 4, "rationale_vi": "Kêu gọi hành động", "evidence_ids": [f"{video.video_id}@1.3"]},
            {"criterion": "brand_fit", "score": 5, "rationale_vi": "Hợp tệp", "evidence_ids": [f"{video.video_id}@0.5"]},
            {"criterion": "production_quality", "score": 4, "rationale_vi": "Ánh sáng tốt", "evidence_ids": [f"{video.video_id}@0.5"]},
        ],
        "risks_vi": [],
        "evidence": ev_list,
    }

    mock_usage = Usage(
        provider="gemini",
        model="gemini-3.8-flash",
        prompt_version="content_v3",
        input_tokens=4000,
        output_tokens=800,
        latency_ms=900,
        cost_usd=0.005,
    )
    mock_client.generate_json.return_value = (json.dumps(payload), mock_usage)

    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert analysis.transcript_vi is not None
    assert len(analysis.transcript_vi) <= 1200
    assert not analysis.transcript_vi.endswith(" ")


def test_repair_on_truncation_does_not_contain_broken_text(tmp_path: Path):
    """Requirement (3): Truncated first reply -> repair request does NOT contain the broken text; retries with short instruction to be brief."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    spy_guard = SpyGuard()
    mock_client = MagicMock()

    # Broken truncated JSON output (simulating 4081-token truncation ending mid-string)
    broken_output = '{"video_id": "' + video.video_id + '", "rubric": [{"criterion": "hook", "score": 4, "rationale_vi": "Bị cắt ngang ở đây và không hoàn thành'
    valid_payload = _make_valid_analysis_payload(video.video_id)

    usage1 = Usage(
        provider="openrouter",
        model="google/gemini-3.8-flash",
        prompt_version="content_v3",
        input_tokens=4000,
        output_tokens=4081,
        latency_ms=2500,
        cost_usd=0.02,
    )
    usage2 = Usage(
        provider="openrouter",
        model="google/gemini-3.8-flash",
        prompt_version="content_v3_repair",
        input_tokens=4200,
        output_tokens=800,
        latency_ms=1200,
        cost_usd=0.007,
    )

    mock_client.generate_json.side_effect = [
        (broken_output, usage1),
        (json.dumps(valid_payload), usage2),
    ]

    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert mock_client.generate_json.call_count == 2

    # Verify attempt 1 (repair call) contents:
    repair_call_contents = mock_client.generate_json.call_args_list[1].kwargs["contents"]
    all_text_contents = " ".join(c for c in repair_call_contents if isinstance(c, str))

    # Broken output must NOT be appended into repair request!
    assert broken_output not in all_text_contents
    assert "Bị cắt ngang ở đây" not in all_text_contents

    # Must contain short instruction to be brief:
    repair_inst = repair_call_contents[-1]
    assert "cắt ngắn" in repair_inst or "ngắn gọn" in repair_inst or "súc tích" in repair_inst

    assert analysis.video_id == video.video_id


def test_repair_on_schema_error_under_and_over_4000_chars(tmp_path: Path):
    """Requirement (3): Schema error repair may include broken output ONLY if under 4000 chars."""
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    valid_payload = _make_valid_analysis_payload(video.video_id)
    usage = Usage(
        provider="openrouter",
        model="google/gemini-3.8-flash",
        prompt_version="content_v3",
        input_tokens=4000,
        output_tokens=500,
        latency_ms=1000,
        cost_usd=0.005,
    )

    # Case A: Schema error with output < 4000 chars -> included in repair prompt
    spy_guard = SpyGuard()
    mock_client = MagicMock()
    short_bad_payload = dict(valid_payload)
    short_bad_payload["rubric"] = []  # invalid: empty rubric
    short_bad_str = json.dumps(short_bad_payload)
    assert len(short_bad_str) < 4000

    mock_client.generate_json.side_effect = [
        (short_bad_str, usage),
        (json.dumps(valid_payload), usage),
    ]

    analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=mock_client,
        preprocess_dir=str(tmp_path / "work_a"),
    )

    repair_inst_a = mock_client.generate_json.call_args_list[1].kwargs["contents"][-1]
    assert short_bad_str in repair_inst_a

    # Case B: Schema error with output >= 4000 chars -> NOT included in repair prompt
    spy_guard_b = SpyGuard()
    mock_client_b = MagicMock()
    long_bad_payload = dict(valid_payload)
    long_bad_payload["rubric"] = []
    # Add large filler field to push over 4000 chars without breaking JSON syntax
    long_bad_payload["filler"] = "A" * 4500
    long_bad_str = json.dumps(long_bad_payload)
    assert len(long_bad_str) >= 4000

    mock_client_b.generate_json.side_effect = [
        (long_bad_str, usage),
        (json.dumps(valid_payload), usage),
    ]

    analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard_b,
        client=mock_client_b,
        preprocess_dir=str(tmp_path / "work_b"),
    )

    repair_inst_b = mock_client_b.generate_json.call_args_list[1].kwargs["contents"][-1]
    assert long_bad_str not in repair_inst_b
    assert "filler" not in repair_inst_b




def test_empty_length_response_is_recorded_and_cap_enforced(tmp_path: Path, stable_pricing_config, monkeypatch):
    """F1: HTTP 200 + finish_reason=length + empty content is billed; the ledger holds it and the cap stops later sends."""
    import httpx
    from koc import db
    from koc.budget_guard import BudgetGuard
    from koc.llm.openrouter import OpenRouterClient

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    conn = db.connect(tmp_path / "f1.db")
    db.init_db(conn)
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(1)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 4096, "cost": 0.02},
        })

    client = OpenRouterClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    guard = BudgetGuard(conn, cap_usd=0.05)
    outcomes = []
    for i in range(3):
        before = len(sent)
        with pytest.raises(Exception) as exc_info:
            analyze_video(video=video, brief=brief, budget_guard=guard, client=client,
                          preprocess_dir=str(tmp_path / f"work{i}"))
        outcomes.append((len(sent) - before, type(exc_info.value).__name__))
    ledger = conn.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM llm_calls").fetchone()
    assert ledger[0] == len(sent)  # every paid HTTP response is in the ledger
    assert ledger[1] == pytest.approx(0.02 * len(sent))
    assert len(sent) < 6  # the cap stops sends: not two paid attempts for all three operations
    assert outcomes[-1] == (0, "BudgetExceeded")  # third operation refused before sending
