import inspect
from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel
from google.genai import types, errors

from koc.types import ProviderAccountError, Usage
from koc.llm.gemini import GeminiClient


class DummySchema(BaseModel):
    summary: str
    count: int


def _make_mock_response(
    text: str = '{"summary": "ok", "count": 1}',
    prompt_tokens: int = 100,
    candidate_tokens: int = 50,
    thoughts_tokens: int = 0,
    prompt_details=None,
):
    resp = MagicMock()
    resp.text = text
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = candidate_tokens
    usage.thoughts_token_count = thoughts_tokens
    usage.prompt_tokens_details = prompt_details
    resp.usage_metadata = usage
    return resp


def test_gemini_client_generate_json_success():
    mock_genai_client = MagicMock()
    mock_resp = _make_mock_response()
    mock_genai_client.models.generate_content.return_value = mock_resp

    client = GeminiClient(client=mock_genai_client, model="gemini-3.8-flash")
    text, usage = client.generate_json(
        contents=["Hello test"],
        response_schema=DummySchema,
        prompt_version="test_v1",
        max_output_tokens=1200,
    )

    assert text == '{"summary": "ok", "count": 1}'
    assert isinstance(usage, Usage)
    assert usage.provider == "gemini"
    assert usage.model == "gemini-3.8-flash"
    assert usage.prompt_version == "test_v1"
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cost_usd > 0
    assert usage.latency_ms >= 0
    assert usage.cache_hit is False

    # Verify generate_content called with JSON schema, thinking_budget=0, and max_output_tokens
    mock_genai_client.models.generate_content.assert_called_once()
    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.8-flash"
    cfg = call_kwargs["config"]
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema == DummySchema
    assert cfg.max_output_tokens == 1200
    assert cfg.thinking_config.thinking_budget == 0


def test_gemini_client_multimodal_tokens_and_thoughts():
    mock_genai_client = MagicMock()
    detail_audio = MagicMock()
    detail_audio.modality = types.MediaModality.AUDIO
    detail_audio.token_count = 320

    detail_image = MagicMock()
    detail_image.modality = types.MediaModality.IMAGE
    detail_image.token_count = 2064

    mock_resp = _make_mock_response(
        prompt_tokens=2500,
        candidate_tokens=200,
        thoughts_tokens=50,
        prompt_details=[detail_audio, detail_image],
    )
    mock_genai_client.models.generate_content.return_value = mock_resp

    client = GeminiClient(client=mock_genai_client)
    _, usage = client.generate_json(
        contents=["Multimodal"],
        response_schema=DummySchema,
        prompt_version="test_v1",
    )

    assert usage.audio_tokens == 320
    assert usage.image_tokens == 2064
    assert usage.input_tokens == 2500
    # Output tokens include candidate tokens + thoughts tokens (200 + 50 = 250)
    assert usage.output_tokens == 250


def test_gemini_client_retry_on_transient_error():
    mock_genai_client = MagicMock()
    server_error = errors.ServerError(503, {"error": "Service Unavailable"})
    mock_resp = _make_mock_response()
    mock_genai_client.models.generate_content.side_effect = [server_error, mock_resp]

    client = GeminiClient(client=mock_genai_client)
    text, usage = client.generate_json(
        contents=["Retry test"],
        response_schema=DummySchema,
        prompt_version="test_v1",
    )

    assert text == '{"summary": "ok", "count": 1}'
    assert mock_genai_client.models.generate_content.call_count == 2


@pytest.mark.parametrize("status", [401, 402, 403])
def test_gemini_account_errors_are_run_level(status):
    mock_genai_client = MagicMock()
    mock_genai_client.models.generate_content.side_effect = errors.ClientError(status, {"error": {"message": "account issue"}})
    client = GeminiClient(client=mock_genai_client)

    with pytest.raises(ProviderAccountError):
        client.generate_json(["test"], DummySchema, "test_v1")


def test_gemini_client_fails_after_one_retry():
    mock_genai_client = MagicMock()
    server_error = errors.ServerError(503, {"error": "Service Unavailable"})
    mock_genai_client.models.generate_content.side_effect = [server_error, server_error]

    client = GeminiClient(client=mock_genai_client)
    with pytest.raises(errors.ServerError):
        client.generate_json(
            contents=["Retry fail"],
            response_schema=DummySchema,
            prompt_version="test_v1",
        )

    assert mock_genai_client.models.generate_content.call_count == 2


def test_gemini_client_env_only_key_missing(monkeypatch):
    # Ensure GEMINI_API_KEY is not set
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Also verify no api_key param in __init__
    sig = inspect.signature(GeminiClient.__init__)
    assert "api_key" not in sig.parameters

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiClient()


def test_gemini_client_env_only_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env_secret_key_123")
    with patch("google.genai.Client") as mock_client_cls:
        GeminiClient()
        mock_client_cls.assert_called_once_with(api_key="env_secret_key_123")


def test_gemini_client_refuses_unpriced_model_at_init():
    mock_genai_client = MagicMock()
    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        GeminiClient(client=mock_genai_client, model="arbitrary-unpriced-model")


def test_gemini_client_refuses_unpriced_model_before_generate_json():
    mock_genai_client = MagicMock()
    client = GeminiClient(client=mock_genai_client, model="gemini-3.8-flash")
    # Mutate model to unpriced model after init
    client.model = "arbitrary-unpriced-model"

    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        client.generate_json(
            contents=["Probe test"],
            response_schema=DummySchema,
            prompt_version="probe_v1",
        )

    # API call must NOT be made
    mock_genai_client.models.generate_content.assert_not_called()


def test_gemini_client_pricing_uses_model_actually_sent(tmp_path):
    custom_cfg = tmp_path / "custom_prices.yaml"
    custom_cfg.write_text(
        """
model:
  id: "custom-pinned-model"
pricing_per_1m:
  input_usd: 2.00
  output_usd: 8.00
""",
        encoding="utf-8",
    )

    mock_genai_client = MagicMock()
    mock_resp = _make_mock_response(prompt_tokens=1000, candidate_tokens=500)
    mock_genai_client.models.generate_content.return_value = mock_resp

    client = GeminiClient(
        client=mock_genai_client,
        model="custom-pinned-model",
        config_path=custom_cfg,
    )
    _, usage = client.generate_json(
        contents=["Custom model test"],
        response_schema=DummySchema,
        prompt_version="test_v1",
    )

    assert usage.model == "custom-pinned-model"
    # Cost: 1000 / 1M * 2.00 + 500 / 1M * 8.00 = 0.002 + 0.004 = 0.006 USD
    assert pytest.approx(usage.cost_usd, abs=1e-6) == 0.006000
