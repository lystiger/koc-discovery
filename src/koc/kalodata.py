import json
import os
import time
from collections import deque
from math import ceil

import httpx

from . import db
from .config import load_config
from .types import CacheOnlyMiss


BASE_URL = "https://www.kalodata.com/openapi/v1/tiktok"
CONTACT_KEYS = {"creator_contact_email", "creator_contact_tiktok", "creator_contact_whatsapp", "creator_contact_line", "creator_contact_facebook", "creator_contact_ins", "creator_contact_zalo"}
RATE_LIMIT_DELAYS = (15, 60, 180)


class KalodataRateLimited(RuntimeError):
    def __init__(self):
        super().__init__("Kalodata giới hạn lưu lượng")


class KalodataNotReady(RuntimeError):
    def __init__(self):
        super().__init__("Video Kalodata chưa sẵn sàng")


def strip_contacts(value):
    if isinstance(value, dict):
        return {k: strip_contacts(v) for k, v in value.items() if k.lower() not in CONTACT_KEYS and not k.lower().startswith("creator_contact_")}
    if isinstance(value, list):
        return [strip_contacts(v) for v in value]
    return value


class CreditCounter:
    class CapExceeded(RuntimeError):
        pass

    def __init__(self, conn, cap: float = 100):
        self.conn = conn
        self.cap = cap

    def check(self, credits: float) -> None:
        if db.credits_used(self.conn) + credits > self.cap:
            raise self.CapExceeded(f"Hạn mức tín dụng Kalodata {self.cap:g} đã bị vượt.")

    def reserve(self, run_id: str | None, endpoint: str, request_hash: str, credits: float) -> int:
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if db.credits_used(conn) + credits > self.cap:
                raise self.CapExceeded(f"Hạn mức tín dụng Kalodata {self.cap:g} đã bị vượt.")
            cursor = conn.execute("INSERT INTO api_calls(run_id,endpoint,request_hash,status,credits,latency_ms,cache_hit,created_at) VALUES (?,?,?,'pending',?,0,0,?)", (run_id, endpoint, request_hash, credits, db.now()))
            call_id = cursor.lastrowid
            conn.commit()
            return call_id
        except BaseException:
            conn.rollback()
            raise


class KalodataClient:
    def __init__(self, conn, run_id: str | None = None, api_key: str | None = None, *, transport=None, sleep=time.sleep, credit_cap: float | None = None, client=None, cache_only: bool = False):
        self.conn = conn
        self.cache_only = cache_only
        self.run_id = run_id
        self.api_key = api_key if api_key is not None else os.getenv("KALODATA_API_KEY")
        self.transport = transport
        self.sleep = sleep
        prices = load_config()["kalodata_prices"]
        self.prices = prices
        self.counter = CreditCounter(conn, credit_cap if credit_cap is not None else prices["credits_cap"])
        self.client = client or httpx.Client(timeout=30)
        self._requests: dict[str, deque[float]] = {}
        self._min_interval = load_config()["s1"].get("kalodata_min_interval_s", 2.0)
        self.ttl_days = load_config()["s1"].get("cache_ttl_days")
        self._last_request = None

    def creator_rank(self, *, page_size=100, page_number=1, category_ids=None, **filters):
        body = {"region": "VN", "language": "vi-VN", "currency": "VND", "date_range": "last30Day", "sort_field": {"field": "revenue", "type": "DESC"}, "page_size": page_size, "page_number": page_number, **filters}
        if category_ids:
            body["category_id_list"] = ",".join(map(str, category_ids))
        return self.request("creator/rank", body, self._rank_price(page_size, "creator_rank_per_100_rows"))

    def category_rank(self, *, page_size=100, page_number=1):
        body = {"region": "VN", "language": "vi-VN", "currency": "VND", "date_range": "last30Day",
                "sort_field": {"field": "revenue", "type": "DESC"}, "page_size": page_size,
                "page_number": page_number, "category_level": 3}
        return self.request("category/rank", body, self.prices["creator_rank_per_100_rows"])

    def creator_detail(self, creator_id: str, need_extra=True, **params):
        body = {"region": "VN", "language": "vi-VN", "currency": "VND", "date_range": "last30Day", "creator_id": creator_id, "need_extra": need_extra, **params}
        return self.request("creator/detail", body, self.prices["creator_detail"])

    def video_rank(self, creator_id: str, page_size=100, page_number=1, **params):
        body = {"region": "VN", "language": "vi-VN", "currency": "VND", "date_range": "last30Day", "creator_id": creator_id, "sort_field": {"field": "revenue", "type": "DESC"}, "page_size": page_size, "page_number": page_number, **params}
        return self.request("video/rank", body, self._rank_price(page_size, "video_rank_per_100_rows"))

    def video_url(self, video_id: str):
        return self.request("video/url", {"video_id": video_id}, self.prices["video_url"])

    def _rank_price(self, rows: int, key: str) -> float:
        return self.prices[key] * ceil(rows / 100)

    def _pace(self, endpoint: str):
        now = time.monotonic()
        if self._last_request is not None:
            wait = self._min_interval - (now - self._last_request)
            if wait > 0:
                self.sleep(wait)
        bucket = endpoint
        limit = 10 if endpoint in {"creator/rank", "video/rank", "video/url", "category/rank"} else 100
        requests = self._requests.setdefault(bucket, deque())
        now = time.monotonic()
        while requests and now - requests[0] >= 10:
            requests.popleft()
        if len(requests) >= limit:
            wait = 10 - (now - requests[0])
            self.sleep(wait)
        self._last_request = time.monotonic()
        requests.append(self._last_request)

    def _send(self, endpoint: str, body: dict):
        if self.transport:
            return self.transport(endpoint, body, {"secret-key": self.api_key})
        response = self.client.post(f"{BASE_URL}/{endpoint}", json=body, headers={"secret-key": self.api_key or ""})
        return response

    def request(self, endpoint: str, body: dict, credits: float):
        key = db.cache_key(endpoint, body)
        cached = db.http_cache_get(self.conn, key, None if self.cache_only else self.ttl_days)  # cache-only serves stale rows: no network, no credits
        if cached is not None:
            db.add_api_call(self.conn, self.run_id, endpoint, key, "200", 0, 0, True)
            return cached
        if self.cache_only:
            raise CacheOnlyMiss(f"Kalodata {endpoint}")
        if not self.api_key and self.transport is None:
            raise RuntimeError("Biến môi trường KALODATA_API_KEY chưa được thiết lập.")
        result = None
        rate_limit_attempt = 0
        http_attempt = 0
        for attempt_no in range(4):
            self._pace(endpoint)
            call_id = self.counter.reserve(self.run_id, endpoint, key, credits)
            started = time.monotonic()
            try:
                response = self._send(endpoint, body)
                if isinstance(response, httpx.Response):
                    status = response.status_code
                    try:
                        result = response.json()
                    except ValueError:
                        result = {"body": response.text}
                elif isinstance(response, tuple):
                    status, result = response
                else:
                    status, result = 200, response
            except httpx.HTTPError as exc:
                status, result = 503, {"error": str(exc)}
            latency_ms = int((time.monotonic() - started) * 1000)
            if status in (401, 403):
                db.finalize_api_call(self.conn, call_id, str(status), latency_ms, billed=False)
                raise RuntimeError(f"Xác thực Kalodata thất bại ({status}).")
            if status == 429 or status >= 500:
                db.finalize_api_call(self.conn, call_id, str(status), latency_ms, billed=False)
                if http_attempt < 2:
                    self.sleep(2 ** http_attempt)
                    http_attempt += 1
                    continue
                if status == 429:
                    raise KalodataRateLimited()
                raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")
            if status >= 400:
                db.finalize_api_call(self.conn, call_id, str(status), latency_ms, billed=False)
                raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")
            if status < 200 or status >= 300:
                db.finalize_api_call(self.conn, call_id, str(status), latency_ms, billed=False)
                raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")
            rate_limited = isinstance(result, dict) and result.get("success") is False and (
                result.get("errorCategory") == "RATE_LIMIT" or str(result.get("code")) == "2017"
            )
            if rate_limited:
                db.finalize_api_call(self.conn, call_id, "api_error:2017", latency_ms, billed=False)
                if rate_limit_attempt < len(RATE_LIMIT_DELAYS):
                    self.sleep(RATE_LIMIT_DELAYS[rate_limit_attempt])
                    rate_limit_attempt += 1
                    continue
                raise KalodataRateLimited()
            if isinstance(result, dict) and result.get("success") is False:
                code = result.get("code", "unknown")
                category = result.get("errorCategory")
                message = result.get("message", "Yêu cầu bị từ chối")
                if str(code) == "1054" or "being fetched" in str(message).casefold():
                    db.finalize_api_call(self.conn, call_id, "api_error:1054", latency_ms, billed=False)
                    if rate_limit_attempt < 3 and attempt_no < 3:  # no delay after the last attempt
                        self.sleep((30, 60, 120)[rate_limit_attempt])
                        rate_limit_attempt += 1
                        continue
                    raise KalodataNotReady()
                if (endpoint == "video/rank" and result.get("code") in (None, "") and category in (None, "")
                        and "not found" in str(message).casefold()):
                    result = {"data": [], "not_found": True}
                    with db.transaction(self.conn):
                        self.conn.execute("UPDATE api_calls SET status='not_found',credits=0,latency_ms=? WHERE id=?", (latency_ms, call_id))
                        db.http_cache_put(self.conn, key, endpoint, result)
                    return result
                detail = f"{code} {category}" if category else str(code)
                db.finalize_api_call(self.conn, call_id, f"api_error:{code}", latency_ms, billed=False)
                raise RuntimeError(f"Kalodata từ chối {endpoint} ({detail}): {message}")
            result = strip_contacts(result)
            with db.transaction(self.conn):
                self.conn.execute("UPDATE api_calls SET status=?,latency_ms=? WHERE id=?", (str(status), latency_ms, call_id))
                db.http_cache_put(self.conn, key, endpoint, result)
            return result
        if isinstance(result, dict) and result.get("success") is False and (
            result.get("errorCategory") == "RATE_LIMIT" or str(result.get("code")) == "2017"
        ):
            raise KalodataRateLimited()
        raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")


__all__ = ["KalodataClient", "CreditCounter", "KalodataRateLimited", "KalodataNotReady", "strip_contacts"]
