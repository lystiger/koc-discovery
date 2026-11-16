import json
import hashlib

from . import db
from .config import load_config
from .types import BudgetExceeded


class BudgetGuard:
    def __init__(self, conn, cap_usd: float | None = None, run_id: str | None = None, kind: str = "content"):
        self.conn = conn
        self.cap_usd = cap_usd if cap_usd is not None else load_config()["llm_caps"]["usd_cap"]
        self.run_id = run_id
        self.kind = kind
        self.checked_estimate_usd = None

    def check(self, estimated_usd: float) -> None:
        spent = self._spent()
        if spent + estimated_usd > self.cap_usd:
            raise BudgetExceeded(f"Hạn mức LLM {self.cap_usd:.2f} USD đã bị vượt.")
        self.checked_estimate_usd = estimated_usd

    def _spent(self) -> float:
        return self.conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM llm_calls").fetchone()[0]

    def record(self, usage) -> None:
        with db.transaction(self.conn):
            self.conn.execute(
                "INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (self.run_id, self.kind, "", usage.model, usage.prompt_version, usage.input_tokens, usage.output_tokens,
                 usage.latency_ms, usage.cost_usd, int(usage.cache_hit), db.now()),
            )
        checked_estimate = self.checked_estimate_usd
        if self._spent() > self.cap_usd:
            raise BudgetExceeded(f"Hạn mức LLM {self.cap_usd:.2f} USD đã bị vượt.")
        if checked_estimate is not None and usage.cost_usd > checked_estimate:
            raise BudgetExceeded(
                f"Chi phí LLM thực tế {usage.cost_usd:.6f} USD vượt ước tính đã kiểm tra "
                f"{checked_estimate:.6f} USD; chi phí đã được ghi nhận."
            )


def get_cached(conn, key: str):
    row = conn.execute("SELECT output_json,usage_json FROM llm_cache WHERE request_hash=?", (key,)).fetchone()
    return (json.loads(row[0]), json.loads(row[1])) if row else None


def put_cached(conn, key: str, output, usage, call_id: int | None = None) -> None:
    with db.transaction(conn):
        conn.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at,call_id) VALUES (?,?,?,?,?) ON CONFLICT(request_hash) DO NOTHING",
                     (key, json.dumps(output, sort_keys=True), json.dumps(usage, sort_keys=True), db.now(), call_id))


def llm_cache_key(media_sha256: str, prompt_version: str, model: str, brief: dict) -> str:
    value = json.dumps({"media_sha256": media_sha256, "prompt_version": prompt_version, "model": model, "brief": brief}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()
