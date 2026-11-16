"""Faithfulness judge smoke test on a free OpenRouter model: real DB data, 0 USD, no writes to data/koc.db.

Grades the S4 reasons of one run on a temporary copy of data/koc.db with a :free model, then reruns to prove the
second pass makes 0 calls. Exit 0 PASS, 1 FAIL, 3 when any call reports a cost above zero.
Usage: OPENROUTER_API_KEY=... python scripts/faithfulness_free_smoke.py [model:free] [run_id]
"""
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from koc import db, faithfulness  # noqa: E402
from koc.llm.factory import get_llm_client  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else "baidu/ernie-5.5-flash-preview:free"
RUN = sys.argv[2] if len(sys.argv) > 2 else "7372009b22764b339fbcf0f3efb4bc4e"


class CostSpy:
    """Wraps the client; any reported cost above zero stops the script with exit 3."""
    def __init__(self, client):
        self.client = client
        self.model = client.model
        self.total = 0.0

    def generate_json(self, **kwargs):
        raw, usage = self.client.generate_json(**kwargs)
        self.total += usage.cost_usd
        if usage.cost_usd > 0:
            print(f"STOP: model reported cost {usage.cost_usd} USD", flush=True)
            raise SystemExit(3)
        return raw, usage


def main():
    if not MODEL.endswith(":free"):
        print("STOP: smoke test only runs on :free models")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="faith_smoke_"))
    src = sqlite3.connect("file:data/koc.db?mode=ro", uri=True)
    dst = sqlite3.connect(tmp / "koc.db")
    src.backup(dst)
    src.close()
    dst.close()
    cfg = yaml.safe_load(open("config/llm_prices.yaml"))
    cfg["models"][MODEL] = {"id": MODEL, "name": f"{MODEL} (smoke test)", "provider": "openrouter",
                            "pricing_per_1m": {"input_usd": 0.0, "output_usd": 0.0}}
    cfg["token_accounting"]["default_faithfulness_output_tokens"] = 16384  # free models think first; still 0 USD
    cfg_path = tmp / "llm_prices.yaml"
    yaml.safe_dump(cfg, open(cfg_path, "w"), allow_unicode=True)
    conn = db.connect(tmp / "koc.db")
    spy = CostSpy(get_llm_client(model=MODEL, config_path=cfg_path))
    first = faithfulness.evaluate(conn, RUN, spy, config_path=cfg_path)
    for item, verdicts, score in first["items"]:
        print(f"\n== {item.handle}  score={score:.2f}  sentences={len(item.sentences)}  evidence={len(item.evidence)}")
        for (kind, text), v in zip(item.sentences, verdicts):
            print(f"  [{v['verdict']}] {text[:100]} | {v['why'][:100]}")
    second = faithfulness.evaluate(conn, RUN, spy, config_path=cfg_path)
    ok = bool(first["items"]) and first["calls"] > 0 and second["calls"] == 0 and first["score"] is not None and second["score"] == first["score"]
    print(f"\nRESULT {'PASS' if ok else 'FAIL'}: {len(first['items'])} KOC, run score {first['score']}, calls {first['calls']} then {second['calls']} on rerun, cost {spy.total} USD, model {MODEL}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
