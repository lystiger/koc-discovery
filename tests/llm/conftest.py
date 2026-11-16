import copy
from typing import Any
import pytest

import koc.llm
import koc.llm.content
import koc.llm.factory
import koc.llm.gemini
import koc.llm.openrouter
import koc.llm.pricing
import koc.llm.reasons

STABLE_TEST_PRICING_CONFIG: dict[str, Any] = {
    "provider": "openrouter",
    "model": {
        "id": "google/gemini-3.8-flash",
        "name": "Google: Gemini 3.8 Flash (OpenRouter)",
        "provider": "openrouter",
        "source_url": "https://openrouter.ai/models/google/gemini-3.8-flash",
        "accessed_date": "2026-11-15",
        "context_window": 1048576,
        "max_output_tokens": 65536,
        "pricing_per_1m": {
            "input_usd": 0.825,
            "output_usd": 4.125,
            "source_url": "https://openrouter.ai/api/v1/models",
            "accessed_date": "2026-11-15",
        },
    },
    "models": {
        "google/gemini-3.8-flash": {
            "id": "google/gemini-3.8-flash",
            "name": "Google: Gemini 3.8 Flash (OpenRouter)",
            "provider": "openrouter",
            "pricing_per_1m": {
                "input_usd": 0.825,
                "output_usd": 4.125,
            },
        },
        "gemini-3.8-flash": {
            "id": "gemini-3.8-flash",
            "name": "Gemini 3.8 Flash (Google AI Studio)",
            "provider": "gemini",
            "pricing_per_1m": {
                "input_usd": 0.75,
                "output_usd": 3.75,
            },
        },
    },
    "pricing_per_1m": {
        "input_usd": 0.825,
        "output_usd": 4.125,
    },
    "token_accounting": {
        "image_tokens_per_tile": 258,
        "bytes_per_text_token_upper_bound": 1.0,
        "audio_tokens_per_second": 32,
        "audio_safety_margin_pct": 0.10,
        "multimodal_safety_factor": 1.5,
        "video_tokens_per_second": 263,
        "default_content_output_tokens": 1200,
        "default_reasons_output_tokens": 800,
        "request_overhead_tokens": 200,
        "max_audio_seconds": 180,
        "max_content_text_tokens": 5000,
        "max_reasons_text_tokens": 4000,
    },
    "openrouter": {
        "reasoning": {"effort": "minimal"},
    },
    "response_schema_mode": {
        "supported": True,
    },
    "usage_metadata_fields": {
        "prompt_token_count": "prompt_tokens",
        "candidates_token_count": "completion_tokens",
        "cost": "cost",
        "prompt_tokens_details": "prompt_tokens_details",
    },
}


@pytest.fixture
def stable_pricing_config(monkeypatch):
    """Inject a fixed loaded pricing config for tests requiring specific token caps or prices."""
    cfg = copy.deepcopy(STABLE_TEST_PRICING_CONFIG)
    orig_load = koc.llm.pricing.load_pricing_config

    def _mock_load_pricing_config(config_path=None):
        if config_path is not None:
            return orig_load(config_path)
        return copy.deepcopy(cfg)

    for mod in (
        koc.llm,
        koc.llm.pricing,
        koc.llm.content,
        koc.llm.reasons,
        koc.llm.gemini,
        koc.llm.openrouter,
        koc.llm.factory,
    ):
        monkeypatch.setattr(mod, "load_pricing_config", _mock_load_pricing_config)

    import sys
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("tests.llm"):
            m = sys.modules[mod_name]
            if hasattr(m, "load_pricing_config"):
                monkeypatch.setattr(m, "load_pricing_config", _mock_load_pricing_config)

    return cfg
