"""Pricing calculation and token estimation helper for Gemini and OpenRouter APIs.

Conservative Multimodal Bound Rationale:
----------------------------------------
To guarantee that BudgetGuard.check(upper_bound_usd) prevents budget overruns
BEFORE any API call is executed (including initial calls and repair calls),
this module calculates a conservative upper bound on token usage and cost
accounting for all request materials:

1. Text Tokens Bound:
   Subword BPE and SentencePiece tokenizers merge one or more bytes into tokens;
   no token can ever represent fewer than 1 byte (or 0 bytes). Therefore, the
   number of tokens in any text part cannot exceed its UTF-8 encoded byte length:
       N_tokens(text) <= len(text.encode("utf-8"))
   By summing the UTF-8 byte lengths of all text parts (prompt text, frame/audio
   label metadata, and repair instructions), we obtain a strict upper bound on
   input text tokens:
       text_tokens_bound = sum(len(part.encode("utf-8")) for part in text_parts)
   If only character count is provided without text strings, each character
   is conservatively bounded at >= 1 token.

2. Response Schema Bound:
   Structured outputs enforce a JSON response schema passed via request config.
   The serialized JSON schema adds to prompt tokens. Its token usage cannot exceed
   the UTF-8 byte length of the serialized JSON schema:
       schema_tokens_bound = len(json.dumps(schema.model_json_schema()).encode("utf-8"))

3. Per-Request Overhead Margin:
   A fixed per-request constant of 200 tokens (REQUEST_OVERHEAD_TOKENS) accounts for
   API request framing, role headers, system turn delimiters, and internal
   tokenization margins.

4. Image Tokens (Conservative Estimate with 1.5 Safety Factor):
   Tile math applies: images <= 384x384 use 1 tile (258 tokens). Larger images
   are scaled and tiled into 768x768 tiles:
       tiles = ceil(width / 768) * ceil(height / 768)
       image_tokens = ceil(sum(max(tiles * 258, min_image_tokens_per_frame)) * 1.5)
   min_image_tokens_per_frame (config, default 0) is a measured per-frame floor.

5. Audio Tokens (Conservative Estimate with 1.5 Safety Factor):
   Nominal rate is 32 tokens per second with 10% framing margin, scaled by a 1.5
   safety factor for unverified upstream provider accounting:
       audio_tokens = ceil(32 * ceil(duration_s) * 1.10 * 1.5)
   For videos without an audio stream, audio_tokens is strictly 0.

6. Output Tokens Bound:
   Output tokens are strictly capped by max_output_tokens (e.g. 1200 for content,
   800 for reasons).

7. Model Pinning and Pricing Binding:
   Pricing strictly resolves the price table for the specific model sent.
   Unpriced models are rejected before calling.

8. OpenRouter Token Accounting Rates:
   Image tile token rate (258 tokens per tile) and audio token rate (32 tokens/s)
   for OpenRouter (google/gemini-3.8-flash) are UNVERIFIED upstream rates.
   This bound is a conservative estimate with an explicit 1.5 safety factor applied
   to all image and audio token terms rather than a provable mathematical bound.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence
import yaml

from koc.llm.media import get_jpeg_dimensions

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "llm_prices.yaml"
REQUEST_OVERHEAD_TOKENS = 200


def load_pricing_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Pricing config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_model_pricing(
    model: str,
    config_path: str | Path | None = None,
) -> dict[str, float]:
    """Get verified pricing {"input_usd": float, "output_usd": float} for model from config.
    Raises ValueError if model is not present or has no prices in config.
    """
    if not model or not str(model).strip():
        raise ValueError("Model ID không được để trống")

    cfg = load_pricing_config(config_path)

    # 1. Check 'models' mapping or list
    models_entry = cfg.get("models")
    if isinstance(models_entry, dict) and model in models_entry:
        m_data = models_entry[model]
        if isinstance(m_data, dict):
            prices = m_data.get("pricing_per_1m", m_data)
            if isinstance(prices, dict) and "input_usd" in prices and "output_usd" in prices:
                if prices["input_usd"] is not None and prices["output_usd"] is not None:
                    return {
                        "input_usd": float(prices["input_usd"]),
                        "output_usd": float(prices["output_usd"]),
                    }

    elif isinstance(models_entry, list):
        for m_item in models_entry:
            if isinstance(m_item, dict) and m_item.get("id") == model:
                prices = m_item.get("pricing_per_1m", m_item)
                if isinstance(prices, dict) and "input_usd" in prices and "output_usd" in prices:
                    if prices["input_usd"] is not None and prices["output_usd"] is not None:
                        return {
                            "input_usd": float(prices["input_usd"]),
                            "output_usd": float(prices["output_usd"]),
                        }

    # 2. Check top-level 'model' definition
    model_entry = cfg.get("model")
    if isinstance(model_entry, dict) and model_entry.get("id") == model:
        prices = model_entry.get("pricing_per_1m") or cfg.get("pricing_per_1m")
        if isinstance(prices, dict) and "input_usd" in prices and "output_usd" in prices:
            if prices["input_usd"] is not None and prices["output_usd"] is not None:
                return {
                    "input_usd": float(prices["input_usd"]),
                    "output_usd": float(prices["output_usd"]),
                }

    cfg_label = str(config_path or DEFAULT_CONFIG_PATH)
    raise ValueError(
        f"Mô hình '{model}' không tồn tại hoặc chưa có giá trong cấu hình ({cfg_label})"
    )


def serialize_response_schema(response_schema: Any) -> int:
    """Calculate UTF-8 byte length for serialized response schema."""
    if response_schema is None:
        return 0
    if isinstance(response_schema, bytes):
        return len(response_schema)
    if isinstance(response_schema, str):
        return len(response_schema.encode("utf-8"))
    if hasattr(response_schema, "model_json_schema") and callable(response_schema.model_json_schema):
        schema_dict = response_schema.model_json_schema()
        schema_json = json.dumps(schema_dict, ensure_ascii=False)
        return len(schema_json.encode("utf-8"))
    if isinstance(response_schema, dict):
        schema_json = json.dumps(response_schema, ensure_ascii=False)
        return len(schema_json.encode("utf-8"))
    return 0


def calculate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    config_path: str | Path | None = None,
    *,
    model: str | None = None,
) -> float:
    """Calculate total cost in USD for given input and output tokens using config."""
    cfg = load_pricing_config(config_path)
    target_model = model or cfg.get("model", {}).get("id", "google/gemini-3.8-flash")
    prices = get_model_pricing(target_model, config_path)
    input_price = prices["input_usd"]
    output_price = prices["output_usd"]

    cost_in = (input_tokens / 1_000_000.0) * input_price
    cost_out = (output_tokens / 1_000_000.0) * output_price
    return round(cost_in + cost_out, 6)


def calculate_image_tiles(width: int, height: int) -> int:
    """Calculate Gemini image tiles based on dimensions.
    Images <= 384x384 use 1 tile (258 tokens).
    Larger images are scaled and tiled into 768x768 tiles.
    """
    if width <= 0 or height <= 0:
        return 0
    if width <= 384 and height <= 384:
        return 1
    tiles_x = math.ceil(width / 768)
    tiles_y = math.ceil(height / 768)
    return max(1, tiles_x * tiles_y)


def estimate_tokens_and_usd(
    n_frames: int = 0,
    audio_s: float = 0.0,
    prompt_chars: int = 0,
    est_output_tokens: int | None = None,
    config_path: str | Path | None = None,
    *,
    frame_sizes: Sequence[tuple[int, int]] | None = None,
    frame_paths: Sequence[str | Path] | None = None,
    text_parts: Sequence[str] | str | None = None,
    response_schema: Any = None,
    has_audio: bool = True,
    model: str | None = None,
    overhead_tokens: int | None = None,
) -> tuple[int, float]:
    """Estimate input tokens and total cost in USD using conservative upper bounds.
    Image and audio token rates are UNVERIFIED for OpenRouter and include a 1.5 safety factor.
    Used for BudgetGuard.check(upper_bound_usd) before every call.

    Returns:
        tuple[int, float]: (total_est_input_tokens, est_cost_usd)
    """
    cfg = load_pricing_config(config_path)
    rates = cfg.get("token_accounting", {})
    image_token_rate = int(rates.get("image_tokens_per_tile", 258))
    min_image_tokens = int(rates.get("min_image_tokens_per_frame", 0))
    audio_token_rate = int(rates.get("audio_tokens_per_second", 32))
    audio_margin = float(rates.get("audio_safety_margin_pct", 0.10))
    safety_factor = float(rates.get("multimodal_safety_factor", 1.5))

    if est_output_tokens is None:
        est_output_tokens = int(rates.get("default_content_output_tokens", 1200))

    if overhead_tokens is None:
        overhead_tokens = int(rates.get("request_overhead_tokens", REQUEST_OVERHEAD_TOKENS))

    # Image tokens from real tile math, scaled by 1.5 safety factor
    # Each frame costs at least min_image_tokens_per_frame (0 = tile math only)
    if frame_sizes is not None:
        base_image = sum(max(calculate_image_tiles(w, h) * image_token_rate, min_image_tokens) for w, h in frame_sizes)
    elif frame_paths is not None:
        base_image = sum(max(calculate_image_tiles(*get_jpeg_dimensions(p)) * image_token_rate, min_image_tokens)
                         for p in frame_paths)
    else:
        base_image = max(0, n_frames) * max(image_token_rate, min_image_tokens)

    image_tokens = int(math.ceil(base_image * safety_factor))

    # Audio tokens: 32 tokens/s * ceil(duration) + 10% margin, scaled by 1.5 safety factor; 0 if no audio
    if not has_audio or audio_s <= 0.0:
        audio_tokens = 0
    else:
        ceil_duration = math.ceil(max(0.0, audio_s))
        base_audio = ceil_duration * audio_token_rate
        audio_tokens = int(math.ceil(base_audio * (1.0 + audio_margin) * safety_factor))

    # Text tokens: upper bound via UTF-8 byte count
    if text_parts is not None:
        if isinstance(text_parts, str):
            text_parts = [text_parts]
        text_tokens = sum(len(str(p).encode("utf-8")) for p in text_parts)
    else:
        text_tokens = max(0, prompt_chars)

    # Response schema tokens: UTF-8 bytes of serialized JSON schema
    schema_tokens = serialize_response_schema(response_schema)

    total_est_input_tokens = (
        image_tokens
        + audio_tokens
        + text_tokens
        + schema_tokens
        + overhead_tokens
    )
    cost = calculate_cost_usd(
        total_est_input_tokens,
        est_output_tokens,
        config_path,
        model=model,
    )
    return total_est_input_tokens, cost


def estimate_usd(
    n_frames: int = 0,
    audio_s: float = 0.0,
    prompt_chars: int = 0,
    est_output_tokens: int | None = None,
    config_path: str | Path | None = None,
    *,
    frame_sizes: Sequence[tuple[int, int]] | None = None,
    frame_paths: Sequence[str | Path] | None = None,
    text_parts: Sequence[str] | str | None = None,
    response_schema: Any = None,
    has_audio: bool = True,
    model: str | None = None,
    overhead_tokens: int | None = None,
) -> float:
    """Estimate call cost in USD using a conservative upper bound with 1.5 multimodal safety factor."""
    _, cost = estimate_tokens_and_usd(
        n_frames=n_frames,
        audio_s=audio_s,
        prompt_chars=prompt_chars,
        est_output_tokens=est_output_tokens,
        config_path=config_path,
        frame_sizes=frame_sizes,
        frame_paths=frame_paths,
        text_parts=text_parts,
        response_schema=response_schema,
        has_audio=has_audio,
        model=model,
        overhead_tokens=overhead_tokens,
    )
    return cost


def max_call_upper_bound_usd(
    kind: str,
    config_path: str | Path | None = None,
    *,
    model: str | None = None,
) -> float:
    """Calculate worst-case upper bound in USD for one call of the given kind.
    - 'content': 8 frames + max audio seconds from config + ContentAnalysisPayload schema
                 + overhead + max text tokens + default_content_output_tokens.
    - 'reasons': 0 frames + 0 audio + RecommendationPayload schema + overhead
                 + max text tokens + default_reasons_output_tokens.
    Used by the core to reserve headroom before dispatching calls.
    """
    cfg = load_pricing_config(config_path)
    rates = cfg.get("token_accounting", {})

    if kind == "content":
        from koc.llm.content import ContentAnalysisPayload

        max_audio_s = float(rates.get("max_audio_seconds", 180.0))
        max_output = int(rates.get("default_content_output_tokens", 1200))
        max_text_tokens = int(rates.get("max_content_text_tokens", 5000))
        return estimate_usd(
            n_frames=8,
            audio_s=max_audio_s,
            prompt_chars=max_text_tokens,
            est_output_tokens=max_output,
            config_path=config_path,
            has_audio=True,
            response_schema=ContentAnalysisPayload,
            model=model,
        )
    elif kind == "reasons":
        from koc.llm.reasons import RecommendationPayload

        max_output = int(rates.get("default_reasons_output_tokens", 800))
        max_text_tokens = int(rates.get("max_reasons_text_tokens", 4000))
        return estimate_usd(
            n_frames=0,
            audio_s=0.0,
            prompt_chars=max_text_tokens,
            est_output_tokens=max_output,
            config_path=config_path,
            has_audio=False,
            response_schema=RecommendationPayload,
            model=model,
        )
    else:
        raise ValueError(
            f"Loại cuộc gọi LLM '{kind}' không hợp lệ; chỉ chấp nhận 'content' hoặc 'reasons'"
        )
