"""LLM client factory selecting provider based on configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from koc.llm.pricing import load_pricing_config
from koc.llm.gemini import GeminiClient
from koc.llm.openrouter import OpenRouterClient


def get_llm_client(
    provider: str | None = None,
    *,
    model: str | None = None,
    config_path: str | Path | None = None,
    **kwargs: Any,
) -> GeminiClient | OpenRouterClient:
    """Instantiate the configured or requested LLM client (openrouter or gemini)."""
    cfg = load_pricing_config(config_path)
    chosen_provider = provider or cfg.get("provider", "openrouter")

    if chosen_provider == "openrouter":
        return OpenRouterClient(model=model, config_path=config_path, **kwargs)
    elif chosen_provider == "gemini":
        return GeminiClient(model=model, config_path=config_path, **kwargs)
    else:
        raise ValueError(
            f"Nhà cung cấp LLM '{chosen_provider}' không hợp lệ; chỉ chấp nhận 'openrouter' hoặc 'gemini'"
        )
