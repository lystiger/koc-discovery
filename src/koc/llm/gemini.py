"""Thin client for Google Gemini API with JSON schema enforcement, usage tracking and retry."""
from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any, Sequence
from google import genai
from google.genai import types, errors
from pydantic import BaseModel

from koc.types import ProviderAccountError, Usage
from koc.llm.pricing import load_pricing_config, calculate_cost_usd, get_model_pricing

# Reusable transient error classes
TRANSIENT_ERRORS = (
    errors.ServerError,
    ConnectionError,
    TimeoutError,
)


def _is_transient_error(e: Exception) -> bool:
    if isinstance(e, TRANSIENT_ERRORS):
        return True
    if isinstance(e, errors.ClientError) and getattr(e, "code", None) == 429:
        return True
    return False


def create_part_from_image(path: str | Path) -> types.Part:
    """Read an image from disk and return a Gemini Part with JPEG mime type."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    data = p.read_bytes()
    return types.Part.from_bytes(data=data, mime_type="image/jpeg")


def create_part_from_audio(path: str | Path) -> types.Part:
    """Read an audio file from disk and return a Gemini Part with audio/mp3 mime type."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    data = p.read_bytes()
    return types.Part.from_bytes(data=data, mime_type="audio/mp3")


class GeminiClient:
    def __init__(
        self,
        *,
        model: str | None = None,
        config_path: str | Path | None = None,
        client: Any = None,
    ):
        self.config_path = config_path
        cfg = load_pricing_config(config_path)
        cfg_model = cfg.get("model", {})
        if cfg_model.get("provider") == "gemini":
            default_model = cfg_model.get("id", "gemini-3.8-flash")
        else:
            default_model = "gemini-3.8-flash"
        chosen_model = model or default_model
        # Pin models: accept only model ids present in config/llm_prices.yaml with prices
        get_model_pricing(chosen_model, config_path)
        self.model = chosen_model

        if client is not None:
            self.client = client
        else:
            env_key = os.getenv("GEMINI_API_KEY")
            if not env_key or not env_key.strip():
                raise ValueError("Biến môi trường GEMINI_API_KEY không được để trống")
            self.client = genai.Client(api_key=env_key.strip())

    def generate_json(
        self,
        contents: Sequence[Any],
        response_schema: type[BaseModel],
        prompt_version: str,
        system_instruction: str | None = None,
        max_output_tokens: int | None = None,
        **kwargs: Any,
    ) -> tuple[str, Usage]:
        """Call Gemini model with JSON response schema enforcement.
        Retries once on transient errors.

        Returns:
            tuple[str, Usage]: (raw_json_string, usage_object)
        """
        # Pin models: ensure model has verified pricing before calling
        get_model_pricing(self.model, self.config_path)

        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": response_schema,
            "system_instruction": system_instruction,
            "thinking_config": types.ThinkingConfig(thinking_budget=0),
        }
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = max_output_tokens

        config = types.GenerateContentConfig(**config_kwargs)

        t0 = time.perf_counter()
        response = None
        last_error = None

        for attempt in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as e:
                if isinstance(e, errors.ClientError) and getattr(e, "code", None) in (401, 402, 403):
                    raise ProviderAccountError(f"Tài khoản Gemini không thể truy cập API (HTTP {e.code}): {e}") from e
                last_error = e
                if attempt == 0 and _is_transient_error(e):
                    time.sleep(0.5)
                    continue
                raise

        t1 = time.perf_counter()
        latency_ms = max(0, int((t1 - t0) * 1000))

        if response is None:
            raise RuntimeError(f"Gemini generation failed: {last_error}")

        # Parse usage metadata, including billable thoughts tokens if present
        usage_meta = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage_meta, "prompt_token_count", 0) or 0)
        candidate_tokens = int(getattr(usage_meta, "candidates_token_count", 0) or 0)
        thoughts_tokens = int(getattr(usage_meta, "thoughts_token_count", 0) or 0)
        output_tokens = candidate_tokens + thoughts_tokens

        audio_tokens: int | None = None
        image_tokens: int | None = None

        details = getattr(usage_meta, "prompt_tokens_details", None)
        if details:
            for d in details:
                mod = str(getattr(d, "modality", "")).upper()
                count = int(getattr(d, "token_count", 0) or 0)
                if "AUDIO" in mod:
                    audio_tokens = (audio_tokens or 0) + count
                elif "IMAGE" in mod:
                    image_tokens = (image_tokens or 0) + count

        cost_usd = calculate_cost_usd(
            input_tokens,
            output_tokens,
            self.config_path,
            model=self.model,
        )

        usage = Usage(
            provider="gemini",
            model=self.model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            audio_tokens=audio_tokens,
            image_tokens=image_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            cache_hit=False,
        )

        raw_text = getattr(response, "text", "") or ""
        return raw_text, usage
