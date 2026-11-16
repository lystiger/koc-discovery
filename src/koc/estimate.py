"""Pre-run estimate of credits, USD, LLM tokens and minutes, from the per-stage rates of reports/benchmark.json.

Shared by `koc run --dry-run` and the web needs_run payload (`run_estimate`).
The range: low = the successful path, high = everything the live run spent (retries and waste included).
Minutes get a +-TIME_SPREAD band: the benchmark holds one live run and wall time depends on rate limits.
"""
import json
from pathlib import Path

TIME_SPREAD = 0.25
STAGES = ("S0", "S1a", "S1b", "S2", "S3", "S4")
BENCHMARK_PATH = Path(__file__).resolve().parents[2] / "reports/benchmark.json"


def _candidates(config: dict, limit: int, count: int) -> dict:
    """Creators each stage processes under the configured limits."""
    s1 = config["s1"]
    s1b = min(s1["s1a_limit"], limit)
    s2 = min(s1["s2_limit"], s1["s1_limit"], s1b)
    return {"S0": limit, "S1a": limit, "S1b": s1b, "S2": s2, "S3": s2, "S4": count}


def estimate_run(config: dict, limit: int, count: int | None = None, benchmark: dict | None = None, benchmark_path: Path = BENCHMARK_PATH) -> dict | None:
    """Return {"label","credits","usd","tokens","minutes": {"low","high"}, "stages"} or None when no benchmark exists.

    Per stage: the published per-creator units (units_success / units_total) times the creators the stage processes.
    """
    if benchmark is None:
        if not Path(benchmark_path).exists():
            return None
        benchmark = json.loads(Path(benchmark_path).read_text())
    cands = _candidates(config, limit, count if count is not None else config["s1"]["recommendation_count"])
    totals = {"credits": [0.0, 0.0], "usd": [0.0, 0.0], "tokens": [0.0, 0.0], "minutes": [0.0, 0.0]}
    stages = {}
    for stage in STAGES:
        per = []
        for path in ("units_success", "units_total"):
            row = benchmark[path][stage]
            per.append({"credits": row["credits"], "usd": row["usd"], "tokens": row["tokens_in"] + row["tokens_out"], "minutes": row["wall_time_ms"] / 60000})
        n = cands[stage]
        stages[stage] = {"candidates": n, "credits": round(per[1]["credits"] * n, 2), "usd": round(per[1]["usd"] * n, 4),
                         "tokens": round(per[1]["tokens"] * n), "minutes": round(per[1]["minutes"] * n, 1)}
        for key in totals:
            totals[key][0] += per[0][key] * n
            totals[key][1] += per[1][key] * n
    minutes = totals["minutes"]
    return {
        "label": "ước tính",
        "limit": limit,
        "credits": {"low": round(totals["credits"][0], 1), "high": round(totals["credits"][1], 1)},
        "usd": {"low": round(totals["usd"][0], 2), "high": round(totals["usd"][1], 2)},
        "tokens": {"low": round(totals["tokens"][0]), "high": round(totals["tokens"][1])},
        "minutes": {"low": round(minutes[0] * (1 - TIME_SPREAD)), "high": round(minutes[1] * (1 + TIME_SPREAD))},
        "stages": stages,
    }


def estimate_lines_vi(est: dict) -> list[str]:
    """Vietnamese dry-run lines for an estimate_run result."""
    tokens = est["tokens"]
    token_text = f"{tokens['low']:,}–{tokens['high']:,}".replace(",", ".")
    return [
        "Ước tính toàn pipeline (từ reports/benchmark.json, chỉ là ước tính):",
        f"  Tín dụng Kalodata ước tính: {est['credits']['low']:.1f}–{est['credits']['high']:.1f} tín dụng.",
        f"  Chi phí LLM ước tính: {est['usd']['low']:.2f}–{est['usd']['high']:.2f} USD.",
        f"  Token LLM ước tính: {token_text} token.",
        f"  Thời gian ước tính: {est['minutes']['low']}–{est['minutes']['high']} phút.",
    ]
