"""Tests for OpenRouter LLM client, provider abstraction, and error handling."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock
import httpx
import pytest
from pydantic import BaseModel

from koc.types import (
    Usage,
    VideoInput,
    BrandBrief,
    CandidateSummary,
    ContentAnalysis,
    RubricScore,
    Evidence,
    BudgetExceeded,
    ProviderAccountError,
)
from koc.llm.openrouter import OpenRouterClient
from koc.llm.gemini import GeminiClient, create_part_from_image, create_part_from_audio
from koc.llm.factory import get_llm_client
from koc.llm.content import analyze_video
from koc.llm.reasons import write_reasons


class DummySchema(BaseModel):
    summary: str
    count: int


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


def test_openrouter_missing_key_error(monkeypatch):
    """Missing OPENROUTER_API_KEY environment variable raises Vietnamese ValueError."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Biến môi trường OPENROUTER_API_KEY không được để trống"):
        OpenRouterClient()


def test_openrouter_unpriced_model_refused(monkeypatch):
    """Client refuses unpriced model at init and before generate_json."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        OpenRouterClient(model="arbitrary-unpriced-model")

    client = OpenRouterClient()
    client.model = "unpriced-tampered-model"
    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")


def test_openrouter_request_shape(tmp_path, monkeypatch):
    """Verify request shape: headers, endpoint, image parts, audio part, schema, reasoning off, usage accounting."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-secret-key-xyz")

    # Create dummy image and audio
    img_file = tmp_path / "test_frame.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"fake_jpeg_bytes")
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(b"ID3" + b"fake_mp3_bytes")

    img_part = create_part_from_image(img_file)
    audio_part = create_part_from_audio(audio_file)

    captured_requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "gen-1234",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"summary": "shape test ok", "count": 42}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 180,
                    "completion_tokens": 25,
                    "cost": 0.0002516,
                    "prompt_tokens_details": {
                        "audio_tokens": 32,
                        "image_tokens": 258,
                    },
                },
            },
        )

    transport = httpx.MockTransport(handle_request)
    http_client = httpx.Client(transport=transport)

    client = OpenRouterClient(http_client=http_client)
    raw_json, usage = client.generate_json(
        contents=["Prompt text", img_part, audio_part],
        response_schema=DummySchema,
        prompt_version="shape_v1",
        system_instruction="You are a helpful assistant.",
        max_output_tokens=1200,
    )

    assert len(captured_requests) == 1
    req = captured_requests[0]

    # 1. URL and Method
    assert str(req.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert req.method == "POST"

    # 2. Headers
    assert req.headers["Authorization"] == "Bearer sk-or-v1-secret-key-xyz"
    assert req.headers["Content-Type"] == "application/json"

    # 3. Payload
    body = json.loads(req.content.decode("utf-8"))
    assert body["model"] == "google/gemini-3.8-flash"
    assert body["max_tokens"] == 1200

    # 4. Reasoning omitted by default
    assert body.get("reasoning") == {"effort": "minimal"}

    # 5. Usage accounting requested
    assert body["usage"] == {"include": True}

    # 6. Response format with strict json_schema
    rf = body["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["name"] == "DummySchema"
    assert "properties" in rf["json_schema"]["schema"]

    # 7. Messages structure
    messages = body["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant."

    user_msg = messages[1]
    assert user_msg["role"] == "user"
    user_parts = user_msg["content"]
    assert len(user_parts) == 3

    # Part 0: Text
    assert user_parts[0]["type"] == "text"
    assert user_parts[0]["text"] == "Prompt text"

    # Part 1: Image data URI
    assert user_parts[1]["type"] == "image_url"
    assert user_parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

    # Part 2: Input audio base64 + format mp3
    assert user_parts[2]["type"] == "input_audio"
    assert user_parts[2]["input_audio"]["format"] == "mp3"
    assert len(user_parts[2]["input_audio"]["data"]) > 0

    # 8. Usage parsing
    assert usage.provider == "openrouter"
    assert usage.model == "google/gemini-3.8-flash"
    assert usage.input_tokens == 180
    assert usage.output_tokens == 25
    assert usage.audio_tokens == 32
    assert usage.image_tokens == 258
    assert pytest.approx(usage.cost_usd, abs=1e-6) == 0.000252
    assert usage.cache_hit is False


def test_openrouter_usage_parsing_fallback_price_table(monkeypatch, stable_pricing_config):
    """When usage.cost is not returned by OpenRouter, fallback to local price table."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": '{"summary": "fallback", "count": 1}'}}],
                "usage": {
                    "prompt_tokens": 10000,
                    "completion_tokens": 2000,
                    # No cost returned
                },
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    _, usage = client.generate_json(
        contents=["test"],
        response_schema=DummySchema,
        prompt_version="test_v1",
    )

    # 10,000 / 1M * 0.825 + 2,000 / 1M * 4.125 = 0.00825 + 0.00825 = 0.0165 USD
    assert pytest.approx(usage.cost_usd, abs=1e-6) == 0.016500
    assert usage.audio_tokens is None
    assert usage.image_tokens is None


def test_openrouter_402_no_credits_error(monkeypatch):
    """HTTP 402 raises Vietnamese RuntimeError immediately without retry."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-key-123")

    call_count = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(402, json={"error": {"message": "Your account has insufficient credits"}})

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(ProviderAccountError, match="không đủ tín dụng.*HTTP 402"):
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="test_v1")

    # 402 should not be retried
    assert call_count == 1


@pytest.mark.parametrize("status", [401, 402, 403])
def test_openrouter_account_errors_are_run_level(monkeypatch, status):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": {"message": "account issue"}}))
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(ProviderAccountError):
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="test_v1")


def test_openrouter_429_retry_with_backoff_and_success(monkeypatch):
    """HTTP 429 retries with backoff up to 2 times and succeeds."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    call_count = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return httpx.Response(429, headers={"Retry-After": "0.01"}, json={"error": "Rate limit exceeded"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": '{"summary": "retry success", "count": 3}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.000165},
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    text, usage = client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="test_v1")
    assert call_count == 3  # Initial + 2 retries
    assert "retry success" in text


def test_openrouter_429_exhaustion(monkeypatch):
    """HTTP 429 raises Vietnamese RuntimeError after 2 retries."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    call_count = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, headers={"Retry-After": "0.005"}, json={"error": "Rate limit exceeded"})

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(RuntimeError, match="giới hạn tần suất.*HTTP 429"):
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="test_v1")

    # Initial call + 2 retries = 3 calls total
    assert call_count == 3


def test_openrouter_5xx_retry_and_exhaustion(monkeypatch):
    """HTTP 5xx retries with backoff and raises Vietnamese RuntimeError when exhausted."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    call_count = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(503, json={"error": "Service Unavailable"})

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(RuntimeError, match="Máy chủ OpenRouter gặp sự cố.*HTTP 503"):
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="test_v1")

    assert call_count == 3


def test_openrouter_never_logs_or_exposes_key(monkeypatch):
    """Verify secret API key is never present in repr, exceptions, or error messages."""
    secret_key = "sk-or-super-secret-key-9988776655"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret_key)

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": "Payment Required"})

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    assert secret_key not in repr(client)
    assert secret_key not in str(client)

    try:
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="test_v1")
    except Exception as exc:
        assert secret_key not in str(exc)


def test_openrouter_analyze_video_budget_refusal_before_call(tmp_path, monkeypatch):
    """analyze_video with OpenRouter client checks provable bound and refuses before calling HTTP."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    call_count = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    strict_guard = MagicMock()
    strict_guard.check.side_effect = BudgetExceeded("Hạn mức LLM đã bị vượt.")

    with pytest.raises(BudgetExceeded):
        analyze_video(
            video=video,
            brief=brief,
            budget_guard=strict_guard,
            client=client,
        )

    # Call MUST NOT reach HTTP transport
    assert call_count == 0


def test_openrouter_analyze_video_repair_path(tmp_path, monkeypatch):
    """analyze_video retries once with repair instructions if first response violates schema/rubric."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    call_count = 0
    valid_payload = _make_valid_analysis_payload(video.video_id)

    # First payload is invalid (only 1 rubric criterion instead of 7)
    invalid_payload = dict(valid_payload)
    invalid_payload["rubric"] = [valid_payload["rubric"][0]]

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content.decode("utf-8"))
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": json.dumps(invalid_payload)}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost": 0.00165},
                },
            )
        else:
            # Check repair prompt was included in messages
            user_content = body["messages"][-1]["content"]
            assert any("Phản hồi trước đó không hợp lệ" in str(part.get("text", "")) for part in user_content)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": json.dumps(valid_payload)}}],
                    "usage": {"prompt_tokens": 1200, "completion_tokens": 400, "cost": 0.00264},
                },
            )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    spy_guard = SpyGuard()
    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=client,
    )

    assert call_count == 2
    assert analysis.video_id == video.video_id
    assert len(analysis.rubric) == 7
    assert analysis.usage.provider == "openrouter"
    # Guard checked and recorded both attempts
    assert [e[0] for e in spy_guard.events] == ["check", "record", "check", "record"]


def test_openrouter_write_reasons_success(monkeypatch):
    """write_reasons succeeds with OpenRouter client and enforces citations."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    video_id = "7705660238917143816"
    candidate = CandidateSummary(
        creator_id="creator_abc",
        handle="koc_reviewer",
        followers=500000,
        commercial_score=18.5,
        audience_score=17.0,
        content_score=19.0,
        final_score=18.3,
        est_cost_vnd=15000000,
        metrics={"gmv_30d": 500000000},
        metric_evidence_ids={"gmv_30d": "metric:creator_abc:gmv_30d"},
        analyses=[],
    )
    brief = _make_sample_brief()

    def handle_request(request: httpx.Request) -> httpx.Response:
        rec_json = {
            "creator_id": "creator_abc",
            "reasons_vi": [
                "Doanh thu GMV 30 ngày rất cao đạt 500 triệu.",
                "Điểm thương mại và sáng tạo nội dung đều vượt trội.",
                "Chi phí booking phù hợp ngân sách nhãn hàng.",
            ],
            "cited_evidence_ids": ["metric:creator_abc:gmv_30d"],
            "caveats_vi": ["Cần xác nhận lịch đăng sớm."],
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": json.dumps(rec_json)}}],
                "usage": {"prompt_tokens": 1500, "completion_tokens": 300, "cost": 0.002475},
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    spy_guard = SpyGuard()
    rec = write_reasons(
        c=candidate,
        brief=brief,
        budget_guard=spy_guard,
        client=client,
    )

    assert rec.creator_id == "creator_abc"
    assert len(rec.reasons_vi) == 3
    assert rec.cited_evidence_ids == ["metric:creator_abc:gmv_30d"]
    assert rec.usage.provider == "openrouter"


def test_factory_provider_selection(monkeypatch):
    """get_llm_client selects OpenRouterClient by default or when configured, and GeminiClient when requested."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    # 1. Default (openrouter from config)
    client_default = get_llm_client()
    assert isinstance(client_default, OpenRouterClient)
    assert client_default.model == "google/gemini-3.8-flash"

    # 2. Explicit provider="gemini"
    client_gemini = get_llm_client("gemini")
    assert isinstance(client_gemini, GeminiClient)
    assert client_gemini.model == "gemini-3.8-flash"

    # 3. Invalid provider raises ValueError
    with pytest.raises(ValueError, match="không hợp lệ"):
        get_llm_client("unsupported_provider")


def test_scripts_llm_check(monkeypatch, capsys):
    """scripts/llm_check.py prints OK, model, tokens, cost, and exits 0 on success; never leaks key."""
    from scripts import llm_check

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-real-looking-key-123456789")

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": '{"status": "ok", "message": "Sẵn sàng"}'}}],
                "usage": {"prompt_tokens": 45, "completion_tokens": 12, "cost": 0.000086625},
            },
        )

    transport = httpx.MockTransport(handle_request)
    mock_client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    monkeypatch.setattr(llm_check, "get_llm_client", lambda: mock_client)

    exit_code = llm_check.main()
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "OK" in captured.out
    assert "Provider: openrouter" in captured.out
    assert "Model: google/gemini-3.8-flash" in captured.out
    assert "Tokens: in=45, out=12, total=57" in captured.out
    assert "Cost: $0.000087" in captured.out
    assert "sk-or-real-looking-key" not in captured.out


def test_scripts_llm_check_failure_sanitizes_key(monkeypatch, capsys):
    """scripts/llm_check.py prints FAIL on error and never outputs the key."""
    from scripts import llm_check

    secret_key = "sk-or-top-secret-key-abcdef"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret_key)

    def failing_get_client():
        raise RuntimeError(f"Error with key Bearer {secret_key}")

    monkeypatch.setattr(llm_check, "get_llm_client", failing_get_client)

    exit_code = llm_check.main()
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "FAIL:" in captured.out
    assert secret_key not in captured.out
    assert "[REDACTED]" in captured.out


def test_openrouter_transport_retries_budget_order(monkeypatch):
    """(1) Test with 503, 503, 200 asserting order check, http, check, http, check, http, record."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    events: list[str] = []

    class EventSpyGuard:
        def check(self, amount: float):
            events.append("check")

        def record(self, usage: Any):
            events.append("record")

    valid_payload = {
        "creator_id": "creator_abc",
        "reasons_vi": ["Lý do 1", "Lý do 2", "Lý do 3"],
        "cited_evidence_ids": ["metric:creator_abc:gmv_30d"],
        "caveats_vi": ["Lưu ý 1"],
    }

    attempts = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        events.append("http")
        if attempts in (1, 2):
            return httpx.Response(503, json={"error": {"message": "Service Unavailable"}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": json.dumps(valid_payload)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.0001},
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    candidate = CandidateSummary(
        creator_id="creator_abc",
        handle="koc_reviewer",
        followers=500000,
        commercial_score=18.5,
        audience_score=17.0,
        content_score=19.0,
        final_score=18.3,
        est_cost_vnd=15000000,
        metrics={"gmv_30d": 500000000},
        metric_evidence_ids={"gmv_30d": "metric:creator_abc:gmv_30d"},
        analyses=[],
    )
    brief = _make_sample_brief()
    guard = EventSpyGuard()

    rec = write_reasons(
        c=candidate,
        brief=brief,
        budget_guard=guard,
        client=client,
    )

    assert rec.creator_id == "creator_abc"
    assert events == ["check", "http", "check", "http", "check", "http", "record"]


def test_openrouter_transport_retry_blocked_by_budget(monkeypatch):
    """Transport retry is aborted if budget_guard.check fails before retry HTTP attempt."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    check_calls = 0

    class StrictRetryGuard:
        def check(self, amount: float):
            nonlocal check_calls
            check_calls += 1
            if check_calls > 1:
                from koc.types import BudgetExceeded
                raise BudgetExceeded("Hết ngân sách khi thử lại.")

        def record(self, usage: Any):
            pass

    http_calls = 0

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal http_calls
        http_calls += 1
        return httpx.Response(503, json={"error": {"message": "Service Unavailable"}})

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    from koc.types import BudgetExceeded
    with pytest.raises(BudgetExceeded, match="Hết ngân sách khi thử lại"):
        client.generate_json(
            contents=["test"],
            response_schema=DummySchema,
            prompt_version="v1",
            budget_guard=StrictRetryGuard(),
            upper_bound_usd=0.01,
        )

    # 1 initial HTTP call made, retry was blocked before second HTTP call
    assert http_calls == 1


def test_openrouter_usage_exceeds_estimate_logs_warning(monkeypatch, caplog):
    """(2) If reported usage exceeds the conservative estimate, log a Vietnamese warning with both numbers."""
    import logging
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": '{"summary": "ok", "count": 1}'}}],
                "usage": {"prompt_tokens": 15000, "completion_tokens": 100, "cost": 0.050000},
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with caplog.at_level(logging.WARNING):
        client.generate_json(
            contents=["test prompt"],
            response_schema=DummySchema,
            prompt_version="v1",
            upper_bound_usd=0.005,
            est_tokens=2000,
        )

    # Both numbers must appear in warning messages
    warning_msgs = [rec.message for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any("0.05" in msg and "0.005" in msg for msg in warning_msgs)
    assert any("15000" in msg and "2000" in msg for msg in warning_msgs)
    assert any("Cảnh báo" in msg for msg in warning_msgs)


def test_openrouter_http_400_includes_message_and_metadata_raw_redacted(monkeypatch):
    """(3) Every non-200 RuntimeError must include OpenRouter's error.message and error.metadata.raw (truncated 300, key redacted)."""
    secret_key = "sk-or-v1-secret-key-123456789"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret_key)

    raw_upstream = "Provider error: model google/gemini-3.8-flash does not support thinking"
    error_msg = f"Invalid parameters with Authorization {secret_key}"

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": error_msg,
                    "code": 400,
                    "metadata": {"raw": raw_upstream},
                }
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(RuntimeError) as exc_info:
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")

    err_text = str(exc_info.value)
    assert "HTTP 400" in err_text
    assert secret_key not in err_text
    assert "[REDACTED]" in err_text
    assert "Invalid parameters with Authorization [REDACTED]" in err_text
    assert raw_upstream in err_text


def test_openrouter_error_truncation_to_300_chars(monkeypatch):
    """(3) Long error detail is truncated to 300 characters."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    long_msg = "X" * 500

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": {"message": long_msg}},
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    with pytest.raises(RuntimeError) as exc_info:
        client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")

    err_text = str(exc_info.value)
    # The suffix detail itself should not exceed 300 chars
    assert "X" * 300 in err_text
    assert "X" * 301 not in err_text


def test_openrouter_reasoning_configurable(monkeypatch):
    """(4) Reasoning field is configurable via config or init (default: omitted)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    captured_body = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": '{"summary": "ok", "count": 1}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
            },
        )

    transport = httpx.MockTransport(handle_request)
    # 1. Configured reasoning
    client = OpenRouterClient(
        http_client=httpx.Client(transport=transport),
        reasoning={"effort": "low"},
    )
    client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")
    assert captured_body.get("reasoning") == {"effort": "low"}

    # 2. Default reasoning: from config (effort minimal)
    client_default = OpenRouterClient(
        http_client=httpx.Client(transport=transport),
    )
    client_default.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")
    assert captured_body.get("reasoning") == {"effort": "minimal"}


def test_openrouter_finish_reason_length_empty_content_returns_usage(monkeypatch):
    """F1: finish_reason 'length' with empty content is billed: return empty text plus usage, do not raise."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "   "},
                        "finish_reason": "length",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.0001},
            },
        )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    text, usage = client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")
    assert text == ""
    assert usage.cost_usd == 0.0001
    assert client.last_finish_reason == "length"


def test_openrouter_frequency_penalty_configurable(monkeypatch):
    """Requirement (4): frequency_penalty is configurable and defaults to 0.3 from config."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    captured_body = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": '{"summary": "ok", "count": 1}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.00001},
            },
        )

    transport = httpx.MockTransport(handle_request)

    # 1. Configured frequency_penalty (explicit override)
    client = OpenRouterClient(
        http_client=httpx.Client(transport=transport),
        frequency_penalty=0.5,
    )
    client.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")
    assert captured_body.get("frequency_penalty") == 0.5

    # 2. Default frequency_penalty from config/llm_prices.yaml (0.3)
    client_default = OpenRouterClient(
        http_client=httpx.Client(transport=transport),
    )
    client_default.generate_json(contents=["test"], response_schema=DummySchema, prompt_version="v1")
    assert captured_body.get("frequency_penalty") == 0.3


def test_openrouter_mock_transport_truncation_repair_and_schema(tmp_path, monkeypatch):
    """End-to-end with mocked transport:
    - schema sent to OpenRouter has NO transcript_vi and has maxLength / maxItems.
    - truncated first reply (finish_reason=length / EOF) -> repair request does NOT contain broken text.
    - frequency_penalty of 0.3 sent in payload.
    - transcript_vi built from speech evidence items in time order.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")

    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0)
    video = _make_sample_video(video_path)
    brief = _make_sample_brief()

    call_count = 0
    captured_requests: list[dict] = []

    broken_truncated_json = (
        '{"video_id": "' + video.video_id + '", "rubric": [{"criterion": "hook", "score": 4, '
        '"rationale_vi": "Phân tích mở đầu video đang dở dang thì bị cắt ngang hết token...'
    )

    valid_payload = {
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
            {"evidence_id": f"{video.video_id}@2.0", "video_id": video.video_id, "start_s": 2.0, "end_s": 2.5, "kind": "speech", "quote_vi": "Bấm vào giỏ hàng ngay nhé."},
            {"evidence_id": f"{video.video_id}@0.5", "video_id": video.video_id, "start_s": 0.5, "end_s": 0.8, "kind": "speech", "quote_vi": "Chào các bạn."},
            {"evidence_id": f"{video.video_id}@0.81", "video_id": video.video_id, "start_s": 0.81, "end_s": 1.0, "kind": "frame", "quote_vi": "Khung hình cận cảnh bao bì"},
            {"evidence_id": f"{video.video_id}@1.12", "video_id": video.video_id, "start_s": 1.12, "end_s": 1.5, "kind": "frame", "quote_vi": "Thoa kem lên tay"},
            {"evidence_id": f"{video.video_id}:transcript:1", "video_id": video.video_id, "start_s": 1.2, "end_s": 1.8, "kind": "speech", "quote_vi": "Kem chống nắng này rất tốt."},
        ],
    }

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content.decode("utf-8"))
        captured_requests.append(body)

        if call_count == 1:
            # 1. Verify schema on initial request
            schema = body["response_format"]["json_schema"]["schema"]
            assert "transcript_vi" not in schema["properties"], "Schema must NOT contain transcript_vi"
            assert schema["properties"]["evidence"].get("maxItems") == 12, "Schema evidence must have maxItems=12"
            defs = schema.get("$defs", {})
            assert defs["EvidenceItemPayload"]["properties"]["quote_vi"].get("maxLength") == 200
            assert defs["RubricScorePayload"]["properties"]["rationale_vi"].get("maxLength") == 250

            # 2. Verify frequency_penalty
            assert body.get("frequency_penalty") == 0.3

            # Return truncated reply (finish_reason=length)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": broken_truncated_json},
                            "finish_reason": "length",
                        }
                    ],
                    "usage": {"prompt_tokens": 3000, "completion_tokens": 4081, "cost": 0.019},
                },
            )
        else:
            # Call 2 (repair):
            # Verify repair request does NOT contain the broken text!
            user_content = body["messages"][-1]["content"]
            user_text_combined = " ".join(
                str(part.get("text", "")) for part in user_content if isinstance(part, dict)
            )
            assert broken_truncated_json not in user_text_combined
            assert "Phân tích mở đầu video đang dở dang" not in user_text_combined

            # Verify prompt version is repair
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": json.dumps(valid_payload)},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 3200, "completion_tokens": 600, "cost": 0.005},
                },
            )

    transport = httpx.MockTransport(handle_request)
    client = OpenRouterClient(http_client=httpx.Client(transport=transport))

    spy_guard = SpyGuard()
    analysis = analyze_video(
        video=video,
        brief=brief,
        budget_guard=spy_guard,
        client=client,
        preprocess_dir=str(tmp_path / "work"),
    )

    assert call_count == 2
    # Verify transcript_vi was built from speech evidence in time order
    assert analysis.transcript_vi == "Chào các bạn. Kem chống nắng này rất tốt. Bấm vào giỏ hàng ngay nhé."
    assert analysis.video_id == video.video_id
    assert analysis.usage.prompt_version == "content_v3_repair"
