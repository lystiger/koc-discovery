import math
import json
import pytest
from pydantic import BaseModel
from koc.llm.content import ContentAnalysisPayload
from koc.llm.reasons import RecommendationPayload
from koc.llm.pricing import (
    load_pricing_config,
    get_model_pricing,
    calculate_cost_usd,
    estimate_usd,
    calculate_image_tiles,
    serialize_response_schema,
    max_call_upper_bound_usd,
    REQUEST_OVERHEAD_TOKENS,
)


def test_load_pricing_config():
    cfg = load_pricing_config()
    assert isinstance(cfg.get("provider"), str) and cfg["provider"]
    assert isinstance(cfg.get("model"), dict) and cfg["model"].get("id")
    assert cfg["pricing_per_1m"]["input_usd"] > 0
    assert cfg["pricing_per_1m"]["output_usd"] > 0
    assert isinstance(cfg.get("models"), dict) and len(cfg["models"]) > 0
    for model_id, m_cfg in cfg["models"].items():
        assert m_cfg["pricing_per_1m"]["input_usd"] > 0
        assert m_cfg["pricing_per_1m"]["output_usd"] > 0
    acct = cfg.get("token_accounting", {})
    assert acct["image_tokens_per_tile"] > 0
    assert acct["audio_tokens_per_second"] > 0
    assert 0 <= acct["audio_safety_margin_pct"] <= 1.0
    assert 0 < acct["default_content_output_tokens"] <= 65536
    assert 0 < acct["default_reasons_output_tokens"] <= 65536
    assert acct["request_overhead_tokens"] >= 0
    assert acct["max_audio_seconds"] > 0


def test_calculate_cost_usd(stable_pricing_config):
    # 1. OpenRouter default (google/gemini-3.8-flash):
    # 1M input tokens ($0.825) + 1M output tokens ($4.125) = $4.95
    cost = calculate_cost_usd(input_tokens=1_000_000, output_tokens=1_000_000)
    assert pytest.approx(cost, abs=1e-5) == 4.95

    # 10,000 input tokens = $0.00825, 2,000 output tokens = $0.00825 -> $0.0165
    cost_small = calculate_cost_usd(input_tokens=10_000, output_tokens=2_000)
    assert pytest.approx(cost_small, abs=1e-5) == 0.0165

    # 2. Gemini model (gemini-3.8-flash):
    # 1M input tokens ($0.75) + 1M output tokens ($3.75) = $4.50
    cost_gemini = calculate_cost_usd(input_tokens=1_000_000, output_tokens=1_000_000, model="gemini-3.8-flash")
    assert pytest.approx(cost_gemini, abs=1e-5) == 4.50


def test_calculate_image_tiles():
    assert calculate_image_tiles(0, 0) == 0
    assert calculate_image_tiles(360, 360) == 1
    assert calculate_image_tiles(360, 640) == 1
    # Tall image: 360 wide x 1600 high -> 1 x 3 = 3 tiles
    assert calculate_image_tiles(360, 1600) == 3
    # 1000 x 1000 -> 2 x 2 = 4 tiles
    assert calculate_image_tiles(1000, 1000) == 4


def test_estimate_usd_provable_bound_exact(stable_pricing_config):
    # Conservative Upper Bound with 1.5 multimodal safety factor:
    # 8 frames (360x640): 8 * 258 = 2064 base * 1.5 = 3096 tokens
    # 30s audio: ceil(30) * 32 * 1.10 = 960 * 1.10 = 1056 base * 1.5 = 1584 tokens
    # 3000 chars: UTF-8 byte length bound = 3000 tokens
    # Overhead constant: 200 tokens
    # Total input bound: 3096 + 1584 + 3000 + 200 = 7880 tokens
    # Default output: 1200 tokens

    # OpenRouter rates (0.825 / 4.125):
    # Input cost: 7880 / 1M * 0.825 = 0.006501 USD
    # Output cost: 1200 / 1M * 4.125 = 0.004950 USD
    # Total: exact 0.011451 USD
    est_or = estimate_usd(n_frames=8, audio_s=30.0, prompt_chars=3000)
    assert pytest.approx(est_or, abs=1e-6) == 0.011451

    # Gemini rates (0.75 / 3.75):
    # Input cost: 7880 / 1M * 0.75 = 0.005910 USD
    # Output cost: 1200 / 1M * 3.75 = 0.004500 USD
    # Total: exact 0.010410 USD
    est_gemini = estimate_usd(n_frames=8, audio_s=30.0, prompt_chars=3000, model="gemini-3.8-flash")
    assert pytest.approx(est_gemini, abs=1e-6) == 0.010410


def test_estimate_usd_with_tall_frame_sizes(stable_pricing_config):
    # 8 frames of 360x1600 (3 tiles each): 8 * 3 * 258 = 6192 base * 1.5 = 9288 tokens
    # 30s audio: 1056 base * 1.5 = 1584 tokens
    # 3000 chars: 3000 tokens
    # Overhead constant: 200 tokens
    # Total input: 9288 + 1584 + 3000 + 200 = 14072 tokens
    # Output: 1200 tokens
    frame_sizes = [(360, 1600)] * 8

    # OpenRouter:
    # Input cost: 14072 / 1M * 0.825 = 0.0116094 -> 0.011609 USD
    # Output cost: 1200 / 1M * 4.125 = 0.004950 USD
    # Total: 0.016559 USD
    est_or = estimate_usd(
        n_frames=8,
        audio_s=30.0,
        prompt_chars=3000,
        frame_sizes=frame_sizes,
    )
    assert pytest.approx(est_or, abs=1e-6) == 0.016559

    # Gemini:
    # Input cost: 14072 / 1M * 0.75 = 0.010554 USD
    # Output cost: 1200 / 1M * 3.75 = 0.004500 USD
    # Total: exact 0.015054 USD
    est_gemini = estimate_usd(
        n_frames=8,
        audio_s=30.0,
        prompt_chars=3000,
        frame_sizes=frame_sizes,
        model="gemini-3.8-flash",
    )
    assert pytest.approx(est_gemini, abs=1e-6) == 0.015054


def test_estimate_usd_reasons(stable_pricing_config):
    # Reasons: 0 frames, 0s audio, 1500 chars (1500 tokens bound), overhead 200, output ceiling 800 tokens
    # Total input: 1700 tokens

    # OpenRouter:
    # Input: 1700 / 1M * 0.825 = 0.0014025 -> 0.001403 USD
    # Output: 800 / 1M * 4.125 = 0.003300 USD
    # Total: 0.004703 USD
    est_or = estimate_usd(0, 0.0, 1500, est_output_tokens=800)
    assert pytest.approx(est_or, abs=1e-6) == 0.004703

    # Gemini:
    # Input: 1700 / 1M * 0.75 = 0.001275 USD
    # Output: 800 / 1M * 3.75 = 0.003000 USD
    # Total: 0.004275 USD
    est_gemini = estimate_usd(0, 0.0, 1500, est_output_tokens=800, model="gemini-3.8-flash")
    assert pytest.approx(est_gemini, abs=1e-6) == 0.004275


def test_estimate_usd_text_parts_utf8_bound(stable_pricing_config):
    # Multi-byte Vietnamese strings:
    # "Xin chào": 9 UTF-8 bytes
    # "Kem chống nắng kiềm dầu": 31 UTF-8 bytes
    # Overhead: 200 tokens
    # Total input bound = 40 + 200 = 240 tokens
    parts = ["Xin chào", "Kem chống nắng kiềm dầu"]
    est_or = estimate_usd(n_frames=0, audio_s=0.0, text_parts=parts, est_output_tokens=800)
    # Input: 240 / 1M * 0.825 = 0.000198
    # Output: 800 / 1M * 4.125 = 0.003300
    # Total: exact 0.003498 USD
    assert est_or == pytest.approx(0.003498, abs=1e-6)

    est_gemini = estimate_usd(n_frames=0, audio_s=0.0, text_parts=parts, est_output_tokens=800, model="gemini-3.8-flash")
    # Input: 240 / 1M * 0.75 = 0.000180
    # Output: 800 / 1M * 3.75 = 0.003000
    # Total: exact 0.003180 USD
    assert est_gemini == pytest.approx(0.003180, abs=1e-6)


def test_estimate_usd_no_audio_stream(stable_pricing_config):
    # Audio duration passed but has_audio=False -> audio tokens strictly 0
    est_silent = estimate_usd(n_frames=8, audio_s=30.0, prompt_chars=1000, has_audio=False)
    est_zero_audio = estimate_usd(n_frames=8, audio_s=0.0, prompt_chars=1000, has_audio=True)
    assert est_silent == est_zero_audio


def test_estimate_usd_zero(stable_pricing_config):
    # Zero frames, zero audio, zero prompt -> overhead 200 tokens + base output tokens
    est = estimate_usd(n_frames=0, audio_s=0.0, prompt_chars=0, est_output_tokens=1000, model="gemini-3.8-flash")
    expected_in = (200 / 1_000_000) * 0.75
    expected_out = (1000 / 1_000_000) * 3.75
    assert pytest.approx(est, abs=1e-6) == round(expected_in + expected_out, 6)


def test_serialize_response_schema():
    # 1. RecommendationPayload schema bytes matches Codex R2-1 report exact measurement (513 bytes)
    rec_schema_bytes = serialize_response_schema(RecommendationPayload)
    assert rec_schema_bytes == 513

    # 2. ContentAnalysisPayload schema bytes
    content_schema_bytes = serialize_response_schema(ContentAnalysisPayload)
    assert content_schema_bytes == 1767

    # 3. Dict, str, bytes, None handling
    assert serialize_response_schema(None) == 0
    assert serialize_response_schema(b"12345") == 5
    assert serialize_response_schema("Xin chào") == len("Xin chào".encode("utf-8"))
    d = {"type": "object"}
    assert serialize_response_schema(d) == len(json.dumps(d).encode("utf-8"))


def test_estimate_usd_schema_inclusive_bound(stable_pricing_config):
    # Schema-inclusive bound (R2-1 Round 3):
    # 0 frames, 0 audio, prompt text 3039 bytes, RecommendationPayload schema 513 bytes, overhead 200 tokens
    # Total input: 3039 + 513 + 200 = 3752 tokens
    # Output: 800 tokens
    text = "x" * 3039

    # Gemini:
    # Input cost: 3752 / 1M * 0.75 = 0.002814 USD
    # Output cost: 800 / 1M * 3.75 = 0.003000 USD
    # Total: exact 0.005814 USD
    est_gemini = estimate_usd(
        n_frames=0,
        audio_s=0.0,
        text_parts=[text],
        response_schema=RecommendationPayload,
        est_output_tokens=800,
        model="gemini-3.8-flash",
    )
    assert pytest.approx(est_gemini, abs=1e-6) == 0.005814

    # OpenRouter:
    # Input cost: 3752 / 1M * 0.825 = 0.0030954 -> 0.003095 USD
    # Output cost: 800 / 1M * 4.125 = 0.003300 USD
    # Total: exact 0.006395 USD
    est_or = estimate_usd(
        n_frames=0,
        audio_s=0.0,
        text_parts=[text],
        response_schema=RecommendationPayload,
        est_output_tokens=800,
        model="google/gemini-3.8-flash",
    )
    assert pytest.approx(est_or, abs=1e-6) == 0.006395


def test_codex_r3_counterexample_blocked_before_call(stable_pricing_config):
    """Verify Codex R2-1 counterexample:
    Initial spend: 4.9945285 USD
    Checked estimate with schema + overhead: 0.005814 USD
    4.9945285 + 0.005814 = 5.0003425 > 5.000000 USD
    BudgetGuard blocks BEFORE generation!
    """
    import sqlite3
    from koc import db
    from koc.budget_guard import BudgetGuard
    from koc.types import BudgetExceeded

    conn = sqlite3.connect(":memory:")
    db.init_db(conn)

    guard = BudgetGuard(conn, cap_usd=5.0)
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO llm_calls(run_id, kind, request_hash, model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, cache_hit, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run_probe", "reasons", "h0", "gemini-3.8-flash", "reasons_v1", 1000, 100, 200, 4.9945285, 0, db.now()),
        )

    # Estimate with 3039 prompt bytes + RecommendationPayload (513 bytes) + 200 overhead
    est = estimate_usd(
        n_frames=0,
        audio_s=0.0,
        prompt_chars=3039,
        response_schema=RecommendationPayload,
        est_output_tokens=800,
        model="gemini-3.8-flash",
    )
    assert pytest.approx(est, abs=1e-6) == 0.005814

    with pytest.raises(BudgetExceeded):
        guard.check(est)

    # Database recorded spend remains unchanged at 4.9945285 USD
    spent = conn.execute("SELECT SUM(cost_usd) FROM llm_calls").fetchone()[0]
    assert pytest.approx(spent, abs=1e-6) == 4.9945285


def test_unpriced_model_refused(tmp_path):
    # 1. Arbitrary model not in config raises ValueError
    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        get_model_pricing("arbitrary-unpriced-model")

    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        calculate_cost_usd(1000, 1000, model="arbitrary-unpriced-model")

    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        estimate_usd(prompt_chars=1000, model="arbitrary-unpriced-model")

    with pytest.raises(ValueError, match="không tồn tại hoặc chưa có giá"):
        max_call_upper_bound_usd("content", model="arbitrary-unpriced-model")

    # 2. Empty model raises ValueError
    with pytest.raises(ValueError):
        get_model_pricing("")

    # 3. Model present with prices in custom config works and uses its entry
    custom_cfg = tmp_path / "custom_prices.yaml"
    custom_cfg.write_text(
        """
model:
  id: "custom-pinned-model"
pricing_per_1m:
  input_usd: 1.50
  output_usd: 6.00
token_accounting:
  image_tokens_per_tile: 258
  audio_tokens_per_second: 32
  audio_safety_margin_pct: 0.10
  default_content_output_tokens: 1200
  default_reasons_output_tokens: 800
  request_overhead_tokens: 200
  max_audio_seconds: 180
  max_content_text_tokens: 5000
  max_reasons_text_tokens: 4000
""",
        encoding="utf-8",
    )
    prices = get_model_pricing("custom-pinned-model", custom_cfg)
    assert prices["input_usd"] == 1.50
    assert prices["output_usd"] == 6.00

    cost = calculate_cost_usd(1_000_000, 1_000_000, custom_cfg, model="custom-pinned-model")
    assert pytest.approx(cost, abs=1e-5) == 7.50


def test_max_call_upper_bound_usd_values(stable_pricing_config):
    # 1. Content OpenRouter:
    # 8 frames * 258 = 2064 base * 1.5 = 3096 tokens
    # 180s audio = ceil(180) * 32 * 1.10 = 6336 base * 1.5 = 9504 tokens
    # 5000 text tokens
    # ContentAnalysisPayload schema: 1767 tokens
    # Overhead: 200 tokens
    # Total input: 3096 + 9504 + 5000 + 1767 + 200 = 19567 tokens
    # Output: 1200 tokens
    # OpenRouter: 19567 / 1M * 0.825 + 1200 / 1M * 4.125 = 0.0161428 + 0.0049500 = 0.021094 USD
    content_max_or = max_call_upper_bound_usd("content")
    assert pytest.approx(content_max_or, abs=1e-6) == 0.021094

    # Content Gemini:
    # Gemini: 19567 / 1M * 0.75 + 1200 / 1M * 3.75 = 0.01467525 + 0.004500 = 0.019175 USD
    content_max_gemini = max_call_upper_bound_usd("content", model="gemini-3.8-flash")
    assert pytest.approx(content_max_gemini, abs=1e-6) == 0.019175

    # 2. Reasons OpenRouter (0 frames, 0 audio -> 1.5 factor does not apply to 0):
    # 4000 text tokens
    # RecommendationPayload schema: 513 tokens
    # Overhead: 200 tokens
    # Total input: 4000 + 513 + 200 = 4713 tokens
    # Output: 800 tokens
    # OpenRouter: 4713 / 1M * 0.825 + 800 / 1M * 4.125 = 0.003888225 + 0.003300 = 0.007188 USD
    reasons_max_or = max_call_upper_bound_usd("reasons")
    assert pytest.approx(reasons_max_or, abs=1e-6) == 0.007188

    # Reasons Gemini:
    # Gemini: 4713 / 1M * 0.75 + 800 / 1M * 3.75 = 0.00353475 + 0.003000 = 0.006535 USD
    reasons_max_gemini = max_call_upper_bound_usd("reasons", model="gemini-3.8-flash")
    assert pytest.approx(reasons_max_gemini, abs=1e-6) == 0.006535

    # Headroom invariant: content call upper bound is strictly greater than reasons
    assert content_max_or > reasons_max_or > 0
    assert content_max_gemini > reasons_max_gemini > 0

    # 3. Invalid kind raises ValueError
    with pytest.raises(ValueError, match="Loại cuộc gọi LLM"):
        max_call_upper_bound_usd("invalid_kind")


def test_min_image_tokens_per_frame_floor(tmp_path):
    import yaml
    from koc.llm.pricing import estimate_tokens_and_usd, load_pricing_config
    cfg = load_pricing_config(None)
    base, _ = estimate_tokens_and_usd(frame_sizes=[(360, 640)] * 8, est_output_tokens=600)
    cfg["token_accounting"]["min_image_tokens_per_frame"] = 0
    p = tmp_path / "prices.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    tiles_only, _ = estimate_tokens_and_usd(frame_sizes=[(360, 640)] * 8, est_output_tokens=600, config_path=p)
    # 360x640 is one tile (258); the floor raises each of 8 frames to 1120, times the 1.5 safety factor
    assert base - tiles_only == math.ceil(8 * 1120 * 1.5) - math.ceil(8 * 258 * 1.5)
