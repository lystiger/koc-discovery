#!/usr/bin/env python3
"""One-shot health check script for configured LLM provider.

Performs one tiny text call, prints OK/FAIL, model, tokens, and cost.
Never logs or leaks the API key.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

# Ensure src is in python path if running standalone
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pydantic import BaseModel
from koc.llm.factory import get_llm_client


class HealthCheckPayload(BaseModel):
    status: str
    message: str


def _sanitize(text: str) -> str:
    # Strip any potential API key patterns or Authorization tokens
    s = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]+", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    s = re.sub(r"(api_key=)[a-zA-Z0-9_\-\.]+", r"\1[REDACTED]", s, flags=re.IGNORECASE)
    s = re.sub(r"(sk-[a-zA-Z0-9_\-\.]+)", r"[REDACTED]", s, flags=re.IGNORECASE)
    for env_var in ("OPENROUTER_API_KEY", "GEMINI_API_KEY"):
        val = os.getenv(env_var)
        if val and len(val) >= 4:
            s = s.replace(val, "[REDACTED]")
    return s


def main() -> int:
    try:
        client = get_llm_client()
        raw_json, usage = client.generate_json(
            contents=["Ping. Trả về status 'ok' và message ngắn bằng tiếng Việt."],
            response_schema=HealthCheckPayload,
            prompt_version="healthcheck_v1",
            max_output_tokens=50,
        )
        print("OK")
        print(f"Provider: {usage.provider}")
        print(f"Model: {usage.model}")
        print(
            f"Tokens: in={usage.input_tokens}, out={usage.output_tokens}, "
            f"total={usage.input_tokens + usage.output_tokens}"
        )
        print(f"Cost: ${usage.cost_usd:.6f}")
        return 0
    except Exception as exc:
        clean_msg = _sanitize(str(exc))
        print(f"FAIL: {clean_msg}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
