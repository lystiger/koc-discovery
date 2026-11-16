"""S4 smoke test on a free OpenRouter model: real DB data, zero cost, no DB writes.

Runs the real _s4 summary-building path on a temporary copy of data/koc.db,
replaces only the paid LLM call with a free model, and prints each recommendation.
Usage: OPENROUTER_API_KEY=... python scripts/s4_free_smoke.py [model]
"""
import shutil
import sqlite3
import sys
import tempfile

import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from koc import pipeline  # noqa: E402
from koc.llm.factory import get_llm_client  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else "baidu/ernie-5.5-flash-preview:free"
RUN = "7372009b22764b339fbcf0f3efb4bc4e"
assert MODEL.endswith(":free"), "smoke test only runs on :free models"


class FreeGuard:
    """Refuses any call that reports a cost above zero."""
    total = 0.0
    def check(self, estimated_usd):
        pass
    def record(self, usage):
        self.total += usage.cost_usd
        if usage.cost_usd > 0:
            raise SystemExit(f"STOP: model reported cost {usage.cost_usd} USD")


tmp = Path(tempfile.mkdtemp()) / "koc.db"
shutil.copy("data/koc.db", tmp)
conn = sqlite3.connect(tmp)
conn.row_factory = sqlite3.Row
# price table copy with the free model at 0 USD; the repo config stays untouched
cfg = yaml.safe_load(open("config/llm_prices.yaml"))
cfg["models"][MODEL] = {"id": MODEL, "name": f"{MODEL} (smoke test)", "provider": "openrouter",
                        "pricing_per_1m": {"input_usd": 0.0, "output_usd": 0.0}}
# free models think before answering and ignore effort "minimal"; give them room (still 0 USD)
cfg["token_accounting"]["default_reasons_output_tokens"] = 16384
cfg_path = tmp.parent / "llm_prices.yaml"
yaml.safe_dump(cfg, open(cfg_path, "w"), allow_unicode=True)
client = get_llm_client(model=MODEL, config_path=cfg_path)
guard = FreeGuard()
results = []


def fake_cached_call(conn, run_id, kind, key, prompt_version, model, brief, function, *args, **kwargs):
    kwargs.pop("cache_only", None)  # the smoke run always calls the model; no cache is involved
    rec = function(*args, budget_guard=guard, client=client, **kwargs)
    results.append(rec)
    return rec


pipeline._cached_call = fake_cached_call
pipeline._s4(conn, RUN)  # returns the write callback; never called, so no DB writes
ok = len(results) == 5
for rec in results:
    print(f"\n== {rec.creator_id}  cited={len(rec.cited_evidence_ids)}  reasons={len(rec.reasons_vi)}")
    for r in rec.reasons_vi:
        print("  -", r[:160])
    for cv in rec.caveats_vi:
        print("  ! ", cv[:160])
    audience_cited = [i for i in rec.cited_evidence_ids if "female" in i or ":age_" in i]
    fake_numbers = [r for r in rec.reasons_vi if "60%" in r or "30,5%" in r or "30.5%" in r]
    if audience_cited or fake_numbers:
        print("  FAKE AUDIENCE:", audience_cited, fake_numbers)
    ok &= bool(rec.cited_evidence_ids) and 3 <= len(rec.reasons_vi) <= 5 and not audience_cited and not fake_numbers
print(f"\nRESULT {'PASS' if ok else 'FAIL'}: {len(results)} recommendations, cost {guard.total} USD, model {MODEL}")
sys.exit(0 if ok else 1)
