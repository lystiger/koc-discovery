"""OpenRouter client for multimodal LLM completions with JSON schema enforcement and usage tracking."""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Sequence

import httpx
from pydantic import BaseModel

from koc.types import ProviderAccountError, Usage
from koc.llm.pricing import (
    load_pricing_config,
    calculate_cost_usd,
    get_model_pricing,
    estimate_tokens_and_usd,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def create_image_data_uri(path: str | Path) -> str:
    """Read an image file and return a data URI with base64 encoded payload."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def create_audio_base64(path: str | Path) -> tuple[str, str]:
    """Read an audio file and return (base64_data, format)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    fmt = "mp3" if p.suffix.lower() in (".mp3", "") else p.suffix.lstrip(".").lower()
    return b64, fmt


class OpenRouterClient:
    def __init__(
        self,
        *,
        model: str | None = None,
        config_path: str | Path | None = None,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
        base_url: str = DEFAULT_BASE_URL,
        budget_guard: Any | None = None,
        reasoning: dict[str, Any] | None = None,
        frequency_penalty: float | None = None,
    ):
        self.config_path = config_path
        cfg = load_pricing_config(config_path)
        default_model = cfg.get("model", {}).get("id", "google/gemini-3.8-flash")
        chosen_model = model or default_model
        # Pin models: accept only model ids present in config/llm_prices.yaml with prices
        get_model_pricing(chosen_model, config_path)
        self.model = chosen_model

        env_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not env_key or not str(env_key).strip():
            raise ValueError("Biến môi trường OPENROUTER_API_KEY không được để trống")
        self._api_key = str(env_key).strip()
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=60.0)
        self.budget_guard = budget_guard

        openrouter_cfg = cfg.get("openrouter") if isinstance(cfg.get("openrouter"), dict) else {}
        self.reasoning = reasoning if reasoning is not None else openrouter_cfg.get("reasoning", None)
        self.frequency_penalty = (
            frequency_penalty
            if frequency_penalty is not None
            else openrouter_cfg.get("frequency_penalty", None)
        )
        self.last_finish_reason: str | None = None

    def __repr__(self) -> str:
        # Never log or leak the API key
        return f"OpenRouterClient(model={self.model!r}, base_url={self.base_url!r})"

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extract and format error message from OpenRouter response.
        Includes error.message and error.metadata.raw if present.
        Truncates to 300 characters and redacts API key.
        """
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    msg = str(err.get("message") or "").strip()
                    meta = err.get("metadata")
                    meta_raw = ""
                    if isinstance(meta, dict) and meta.get("raw"):
                        meta_raw = str(meta.get("raw")).strip()
                    if msg and meta_raw:
                        detail = f"{msg} (metadata.raw: {meta_raw})"
                    elif msg:
                        detail = msg
                    elif meta_raw:
                        detail = f"metadata.raw: {meta_raw}"
                elif isinstance(err, str):
                    detail = err.strip()
                elif "message" in body:
                    detail = str(body["message"]).strip()
            elif isinstance(body, str):
                detail = body.strip()
        except Exception:
            detail = response.text or ""

        if not detail:
            detail = response.text or ""

        detail = detail.strip()
        # Redact secret API key
        if self._api_key and self._api_key in detail:
            detail = detail.replace(self._api_key, "[REDACTED]")

        # Redact common key patterns
        detail = re.sub(r"sk-or-v1-[a-zA-Z0-9]+", "[REDACTED]", detail)
        detail = re.sub(r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer [REDACTED]", detail)

        # Truncate to 300 chars
        if len(detail) > 300:
            detail = detail[:300]
        return detail

    def estimate_upper_bound(
        self,
        contents: Sequence[Any],
        response_schema: type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
        system_instruction: str | None = None,
    ) -> tuple[int, float]:
        """Calculate conservative upper bound tokens and USD cost for this request."""
        text_parts: list[str] = []
        n_images = 0
        has_audio = False
        for c in contents:
            if isinstance(c, str):
                text_parts.append(c)
            elif isinstance(c, dict):
                t = c.get("type")
                if t == "text":
                    text_parts.append(c.get("text", ""))
                elif t == "image_url":
                    n_images += 1
                elif t == "input_audio":
                    has_audio = True
            elif hasattr(c, "inline_data") or (hasattr(c, "data") and hasattr(c, "mime_type")):
                inline = getattr(c, "inline_data", c)
                mime = str(getattr(inline, "mime_type", "")).lower()
                if "image" in mime:
                    n_images += 1
                elif "audio" in mime:
                    has_audio = True
                else:
                    text_parts.append(str(c))
            else:
                text_parts.append(str(c))
        if system_instruction:
            text_parts.append(system_instruction)

        cfg = load_pricing_config(self.config_path)
        rates = cfg.get("token_accounting", {})
        max_audio_s = float(rates.get("max_audio_seconds", 180.0)) if has_audio else 0.0

        return estimate_tokens_and_usd(
            n_frames=n_images,
            audio_s=max_audio_s,
            est_output_tokens=max_output_tokens,
            config_path=self.config_path,
            text_parts=text_parts,
            response_schema=response_schema,
            has_audio=has_audio,
            model=self.model,
        )

    def _convert_contents_to_parts(self, contents: Sequence[Any]) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        for c in contents:
            if isinstance(c, str):
                parts.append({"type": "text", "text": c})
            elif isinstance(c, dict):
                parts.append(c)
            elif hasattr(c, "inline_data") and getattr(c, "inline_data", None) is not None:
                inline = c.inline_data
                data_bytes = getattr(inline, "data", b"")
                mime = str(getattr(inline, "mime_type", "")).lower()
                b64 = base64.b64encode(data_bytes).decode("ascii")
                if "image" in mime:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    })
                elif "audio" in mime:
                    fmt = "mp3" if "mp3" in mime else "wav"
                    parts.append({
                        "type": "input_audio",
                        "input_audio": {"data": b64, "format": fmt},
                    })
                else:
                    parts.append({"type": "text", "text": str(c)})
            elif hasattr(c, "data") and hasattr(c, "mime_type"):
                data_bytes = getattr(c, "data", b"")
                mime = str(getattr(c, "mime_type", "")).lower()
                b64 = base64.b64encode(data_bytes).decode("ascii")
                if "image" in mime:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    })
                elif "audio" in mime:
                    fmt = "mp3" if "mp3" in mime else "wav"
                    parts.append({
                        "type": "input_audio",
                        "input_audio": {"data": b64, "format": fmt},
                    })
                else:
                    parts.append({"type": "text", "text": str(c)})
            else:
                parts.append({"type": "text", "text": str(c)})
        return parts

    def generate_json(
        self,
        contents: Sequence[Any],
        response_schema: type[BaseModel],
        prompt_version: str,
        system_instruction: str | None = None,
        max_output_tokens: int | None = None,
        *,
        budget_guard: Any | None = None,
        upper_bound_usd: float | None = None,
        initial_check_done: bool = False,
        est_tokens: int | None = None,
    ) -> tuple[str, Usage]:
        """Call OpenRouter Chat Completions API with JSON schema enforcement.

        Retries up to 2 times with exponential backoff on 429 and 5xx errors.
        Every HTTP attempt (including transport retries) is preceded by budget_guard.check(upper_bound).
        Raises Vietnamese RuntimeError on 402, 429, 5xx, or non-200 with full error detail (key redacted).
        Warns in Vietnamese if reported usage exceeds the conservative estimate.

        Returns:
            tuple[str, Usage]: (raw_json_string, usage_object)
        """
        # Pin models: ensure model has verified pricing before calling
        get_model_pricing(self.model, self.config_path)

        # Build schema
        schema_name = getattr(response_schema, "__name__", "response_schema")
        if hasattr(response_schema, "model_json_schema") and callable(response_schema.model_json_schema):
            schema_dict = response_schema.model_json_schema()
        elif isinstance(response_schema, dict):
            schema_dict = response_schema
        else:
            raise ValueError(f"Schema không hợp lệ: {type(response_schema)}")

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema_dict,
            },
        }

        messages: list[dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        user_parts = self._convert_contents_to_parts(contents)
        messages.append({"role": "user", "content": user_parts})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": response_format,
            "usage": {"include": True},
        }
        if self.reasoning is not None:
            payload["reasoning"] = self.reasoning
        if self.frequency_penalty is not None:
            payload["frequency_penalty"] = float(self.frequency_penalty)
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/lystiger/KOC-Discovery",
            "X-Title": "KOC Discovery",
        }

        # Resolve budget upper bound and token estimate
        active_guard = budget_guard or self.budget_guard
        bound_usd = upper_bound_usd
        est_in_tokens = est_tokens
        if bound_usd is None or est_in_tokens is None:
            calc_tokens, calc_usd = self.estimate_upper_bound(
                contents,
                response_schema=response_schema,
                max_output_tokens=max_output_tokens,
                system_instruction=system_instruction,
            )
            if bound_usd is None:
                bound_usd = calc_usd
            if est_in_tokens is None:
                est_in_tokens = calc_tokens

        url = f"{self.base_url}/chat/completions"
        t0 = time.perf_counter()
        resp: httpx.Response | None = None
        max_retries = 2

        for attempt in range(max_retries + 1):
            # Every HTTP attempt, including transport retries, must be preceded by budget_guard.check
            if active_guard is not None and bound_usd is not None:
                if attempt > 0 or not initial_check_done:
                    active_guard.check(bound_usd)

            try:
                r = self.http_client.post(url, json=payload, headers=headers)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as net_err:
                if attempt < max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise RuntimeError(f"Lỗi kết nối tới OpenRouter: {type(net_err).__name__}") from None

            if r.status_code == 200:
                resp = r
                break

            err_detail = self._extract_error_detail(r)
            detail_suffix = f": {err_detail}" if err_detail else ""

            if r.status_code in (401, 402, 403):
                if r.status_code == 402:
                    message = f"Tài khoản OpenRouter không đủ tín dụng (HTTP 402 Payment Required){detail_suffix}"
                else:
                    message = f"Tài khoản OpenRouter không thể truy cập API (HTTP {r.status_code}){detail_suffix}"
                raise ProviderAccountError(message)
            elif r.status_code == 429 or r.status_code >= 500:
                if attempt < max_retries:
                    retry_after = r.headers.get("Retry-After")
                    sleep_s = None
                    if retry_after:
                        try:
                            sleep_s = float(retry_after)
                        except (ValueError, TypeError):
                            sleep_s = None
                    if sleep_s is None or sleep_s < 0:
                        sleep_s = 0.5 * (2 ** attempt)
                    time.sleep(sleep_s)
                    continue
                else:
                    if r.status_code == 429:
                        raise RuntimeError(f"OpenRouter vượt quá giới hạn tần suất yêu cầu (HTTP 429 Too Many Requests){detail_suffix}")
                    else:
                        raise RuntimeError(f"Máy chủ OpenRouter gặp sự cố (HTTP {r.status_code}){detail_suffix}")
            else:
                raise RuntimeError(f"Yêu cầu OpenRouter thất bại với mã lỗi HTTP {r.status_code}{detail_suffix}")

        t1 = time.perf_counter()
        latency_ms = max(0, int((t1 - t0) * 1000))

        if resp is None:
            raise RuntimeError("OpenRouter không trả về phản hồi")

        resp_data = resp.json()
        choices = resp_data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter không trả về bất kỳ kết quả nào trong 'choices'")

        message = choices[0].get("message") or {}
        raw_text = message.get("content") or ""
        raw_text = raw_text.strip()
        finish_reason = choices[0].get("finish_reason")
        self.last_finish_reason = finish_reason

        # finish_reason='length' with empty content is a billed response: return the empty text
        # with its usage so the caller records the spend, then repairs (budget-checked) or fails.

        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        usage_data = resp_data.get("usage") or {}
        prompt_tokens = int(usage_data.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage_data.get("completion_tokens", 0) or 0)

        audio_tokens: int | None = None
        image_tokens: int | None = None
        details = usage_data.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            if details.get("audio_tokens") is not None:
                audio_tokens = int(details["audio_tokens"])
            if details.get("image_tokens") is not None:
                image_tokens = int(details["image_tokens"])

        if "cost" in usage_data and usage_data["cost"] is not None:
            cost_usd = float(usage_data["cost"])
        else:
            cost_usd = calculate_cost_usd(
                prompt_tokens,
                completion_tokens,
                self.config_path,
                model=self.model,
            )

        # Log warning if actual usage exceeds conservative estimate
        if bound_usd is not None and cost_usd > bound_usd:
            logger.warning(
                "Cảnh báo: Chi phí thực tế (%.6f USD) vượt quá mức ước tính (%.6f USD)",
                cost_usd,
                bound_usd,
            )
        if est_in_tokens is not None and prompt_tokens > est_in_tokens:
            logger.warning(
                "Cảnh báo: Số lượng token đầu vào thực tế (%d) vượt quá mức ước tính (%d)",
                prompt_tokens,
                est_in_tokens,
            )

        usage = Usage(
            provider="openrouter",
            model=self.model,
            prompt_version=prompt_version,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            audio_tokens=audio_tokens,
            image_tokens=image_tokens,
            latency_ms=latency_ms,
            cost_usd=round(cost_usd, 6),
            cache_hit=False,
        )
        return raw_text, usage
