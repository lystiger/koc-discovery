import json
import math
from pathlib import Path

from .config import load_config
from .stages import excluded_brand_fit

def _rank(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for pos in range(start, end): ranks[order[pos]] = rank
        start = end
    return ranks


def spearman(left, right):
    if len(left) < 2 or len(left) != len(right): return None
    x, y = _rank(left), _rank(right)
    mx, my = sum(x) / len(x), sum(y) / len(y)
    numerator = sum((a-mx)*(b-my) for a, b in zip(x,y))
    denominator = math.sqrt(sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))
    return round(numerator / denominator, 6) if denominator else None


def _average(rows, field):
    return sum(row[field] or 0 for row in rows) / len(rows) if rows else 0


def _projections(conn, run_id, params):
    config = load_config()["s1"]
    s2_price = load_config()["kalodata_prices"]["ui_creator_detail_view"]
    base = config["projection_base_candidates"]
    daily_ui_limit = config["daily_ui_limit"]
    api_rows = conn.execute(
        "SELECT endpoint,credits,latency_ms FROM api_calls WHERE run_id=? AND cache_hit=0",
        (run_id,),
    ).fetchall()
    llm_rows = conn.execute(
        "SELECT kind,input_tokens,output_tokens,cost_usd,latency_ms FROM llm_calls WHERE run_id=? AND cache_hit=0",
        (run_id,),
    ).fetchall()
    api_units = {}
    for endpoint in {row["endpoint"] for row in api_rows}:
        rows = [row for row in api_rows if row["endpoint"] == endpoint]
        api_units[endpoint] = {
            "credits": _average(rows, "credits"),
            "wall_time_seconds": _average(rows, "latency_ms") / 1000,
        }
    llm_units = {}
    for kind in {row["kind"] for row in llm_rows}:
        rows = [row for row in llm_rows if row["kind"] == kind]
        llm_units[kind] = {
            "tokens_in": _average(rows, "input_tokens"),
            "tokens_out": _average(rows, "output_tokens"),
            "usd": _average(rows, "cost_usd"),
            "wall_time_seconds": _average(rows, "latency_ms") / 1000,
        }

    task_counts = {
        row["stage"]: row["n"]
        for row in conn.execute(
            "SELECT stage,COUNT(*) n FROM tasks WHERE run_id=? AND status='done' GROUP BY stage",
            (run_id,),
        )
    }
    stage_wall_ms = params.get("stage_wall_ms", {})

    def scaled(config_count, candidates):
        return min(candidates, math.ceil(candidates * config_count / base))

    result = {}
    for candidates in (50, 200, 500):
        s1a_count = scaled(config["s1a_limit"], candidates)
        s1_count = min(s1a_count, scaled(config["s1_limit"], candidates))
        s2_count = min(s1_count, scaled(config["s2_limit"], candidates))
        s4_count = min(s2_count, config["recommendation_count"])
        video_count = config["video_count"]
        calls = {
            "S0": math.ceil(candidates / config["rank_page_size"]),
            "S1a": candidates,
            "S1b": 2 * s1a_count,
            "S2": s1_count,
            "S3": s2_count * (1 + 2 * video_count),
            "S4": s4_count,
        }
        stages = {
            name: {"calls": calls[name], "credits": 0.0, "tokens_in": 0,
                   "tokens_out": 0, "usd": 0.0, "wall_time_seconds": 0.0}
            for name in ("S0", "S1a", "S1b", "S2", "S3", "S4")
        }

        def add_api(stage, endpoint, count):
            unit = api_units.get(endpoint, {})
            stages[stage]["credits"] += unit.get("credits", 0) * count
            stages[stage]["wall_time_seconds"] += unit.get("wall_time_seconds", 0) * count

        def add_llm(stage, kind, count):
            unit = llm_units.get(kind, {})
            for key in ("tokens_in", "tokens_out", "usd", "wall_time_seconds"):
                stages[stage][key] += unit.get(key, 0) * count

        add_api("S0", "creator/rank", calls["S0"])
        add_api("S1b", "creator/detail", s1a_count)
        add_api("S1b", "video/rank", s1a_count)
        add_api("S3", "video/rank", s2_count)
        add_api("S3", "video/url", s2_count * video_count)
        stages["S2"]["credits"] += s2_price * s1_count
        add_llm("S3", "content", s2_count * video_count)
        add_llm("S4", "reasons", s4_count)
        if task_counts.get("S2"):
            stages["S2"]["wall_time_seconds"] = (
                stage_wall_ms.get("S2", 0) / 1000 / task_counts["S2"] * s1_count
            )
        if task_counts.get("S1a"):
            stages["S1a"]["wall_time_seconds"] = (
                stage_wall_ms.get("S1a", 0) / 1000 / task_counts["S1a"] * candidates
            )
        for item in stages.values():
            item["credits"] = round(item["credits"], 4)
            item["tokens_in"] = round(item["tokens_in"])
            item["tokens_out"] = round(item["tokens_out"])
            item["usd"] = round(item["usd"], 6)
            item["wall_time_seconds"] = round(item["wall_time_seconds"], 3)
        result[str(candidates)] = {
            "candidates": candidates,
            "stages": stages,
            "s2_calendar_days": math.ceil(s1_count / daily_ui_limit),
        }
    return result


def benchmark(conn, run_id):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run: raise ValueError(f"Không tìm thấy lượt chạy {run_id}.")
    params = json.loads(run["params_json"])
    tasks = conn.execute("SELECT stage,status,COUNT(*) n FROM tasks WHERE run_id=? GROUP BY stage,status", (run_id,)).fetchall()
    task_counts = {}
    for row in tasks: task_counts.setdefault(row["stage"], {})[row["status"]] = row["n"]
    api = conn.execute("SELECT endpoint,credits,latency_ms FROM api_calls WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    llm = conn.execute("SELECT kind,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(cost_usd) usd,SUM(latency_ms) latency_ms,SUM(cache_hit) cache_hits FROM llm_calls WHERE run_id=? GROUP BY kind", (run_id,)).fetchall()
    stages = {name: {"wall_time_ms": 0, "credits": 0.0, "tokens_in": 0, "tokens_out": 0, "usd": 0.0, "cache_hits": 0, "candidates_in": 0, "candidates_out": 0}
              for name in ("S0", "S1a", "S1b", "S2", "S3", "S4")}
    rank_calls_for_s1 = sum(task_counts.get("S1b", {}).values())
    seen_video_ranks = 0
    for row in api:
        stage = {"creator/rank": "S0", "creator/detail": "S1b", "video/url": "S3", "category/rank": "S0", "ui/creator_detail": "S2"}.get(row["endpoint"])
        if row["endpoint"] == "video/rank":
            stage = "S1b" if seen_video_ranks < rank_calls_for_s1 else "S3"
            seen_video_ranks += 1
        if stage:
            stages[stage]["credits"] += row["credits"] or 0
            stages[stage]["wall_time_ms"] += row["latency_ms"] or 0
    for row in llm:
        stage = "S3" if row["kind"] == "content" else "S4"
        for key, source in (("tokens_in", "input_tokens"), ("tokens_out", "output_tokens"), ("usd", "usd"), ("wall_time_ms", "latency_ms"), ("cache_hits", "cache_hits")):
            stages[stage][key] += row[source] or 0
    for stage, duration in params.get("stage_wall_ms", {}).items():
        if stage in stages: stages[stage]["wall_time_ms"] = duration
    counts = {stage: conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage=?", (run_id, stage)).fetchone()[0] for stage in ("S1a", "S1", "S2", "S3")}
    s1b_tasks = sum(task_counts.get("S1b", {}).values())
    stages["S0"].update(candidates_in=params.get("limit", 0), candidates_out=counts["S1a"])
    stages["S1a"].update(candidates_in=counts["S1a"], candidates_out=s1b_tasks)
    s2_tasks = sum(task_counts.get("S2", {}).values())
    s3_tasks = sum(task_counts.get("S3", {}).values())
    stages["S1b"].update(candidates_in=s1b_tasks, candidates_out=s2_tasks)
    stages["S2"].update(candidates_in=s2_tasks, candidates_out=s3_tasks)
    stages["S3"].update(candidates_in=s3_tasks, candidates_out=counts["S3"])
    stages["S4"].update(candidates_in=counts["S3"], candidates_out=conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0])
    finals = conn.execute("SELECT creator_id,score FROM scores WHERE run_id=? AND stage='S3' ORDER BY creator_id", (run_id,)).fetchall()
    contents, ratios, gpms = [], [], []
    for row in finals:
        creator_id = row["creator_id"]
        creator = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        profile = json.loads(creator[0]) if creator else {}
        followers = max(1, int(float(profile.get("creator_followers") or 0)))
        view_total = sum(int(json.loads(video[0]).get("views") or 0) for video in conn.execute("SELECT data_json FROM videos WHERE creator_id=?", (creator_id,)))
        metric = conn.execute("SELECT value FROM metrics WHERE creator_id=? AND name='video_gpm'", (creator_id,)).fetchone()
        contents.append(row["score"]); ratios.append(view_total / followers); gpms.append(float(json.loads(metric[0])) if metric else 0)
    recommendations = conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0]
    total_credits = sum(item["credits"] for item in stages.values())
    total_tokens_in = sum(item["tokens_in"] for item in stages.values())
    total_tokens_out = sum(item["tokens_out"] for item in stages.values())
    total_usd = sum(item["usd"] for item in stages.values())
    candidate_count = stages["S0"]["candidates_in"] or 1
    projections = _projections(conn, run_id, params)
    return {"run_id": run_id, "status": run["status"], "mode": "mock" if params.get("mock") else "live", "stages": stages, "totals": {"credits": round(total_credits, 4), "tokens_in": total_tokens_in, "tokens_out": total_tokens_out, "usd": round(total_usd, 6)},
            "candidates": {"input": candidate_count, "finalists": len(finals), "recommended": recommendations},
            "brand_fit_excluded": excluded_brand_fit(conn, run_id),
            "projections": projections, "projection_500": projections["500"],
            "calibration": {"content_vs_views_per_follower": spearman(contents, ratios), "content_vs_video_gpm": spearman(contents, gpms)}}


def write_benchmark(conn, run_id):
    result = benchmark(conn, run_id)
    report_path = Path("reports/benchmark.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    docs_path = Path("docs/BENCHMARK.md")
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Chuẩn đo KOC Discovery", "", f"Lượt chạy `{run_id}` · trạng thái `{result['status']}` · chế độ `{result['mode']}`."]
    if result["mode"] == "mock":
        lines.append("Số liệu chi phí bằng 0 do dùng fixture ngoại tuyến; không đại diện cho chi phí chạy thật.")
    lines += ["", "| Giai đoạn | Thời gian (ms) | Tín dụng | Token vào | Token ra | USD | Cache hit | Ứng viên vào → ra |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for stage, item in result["stages"].items():
        lines.append(f"| {stage} | {item['wall_time_ms']} | {item['credits']:.2f} | {item['tokens_in']} | {item['tokens_out']} | {item['usd']:.6f} | {item['cache_hits']} | {item['candidates_in']} → {item['candidates_out']} |")
    for n, projection in result["projections"].items():
        lines += ["", f"Ước tính cho {n} ứng viên; S2 cần {projection['s2_calendar_days']} ngày theo giới hạn giao diện:",
                  "", "| Giai đoạn | Lượt gọi | Tín dụng | Token vào | Token ra | USD | Thời gian (giây) |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for stage, item in projection["stages"].items():
            lines.append(f"| {stage} | {item['calls']} | {item['credits']:.4f} | {item['tokens_in']} | {item['tokens_out']} | {item['usd']:.6f} | {item['wall_time_seconds']:.3f} |")
    lines += ["", *[f"- {item['handle']}: {item['reason_vi']}" for item in result["brand_fit_excluded"]]] if result["brand_fit_excluded"] else []
    lines += ["", f"Hiệu chuẩn Spearman: nội dung ↔ lượt xem/người theo dõi = `{result['calibration']['content_vs_views_per_follower']}`; nội dung ↔ GPM video = `{result['calibration']['content_vs_video_gpm']}`.", ""]
    docs_path.write_text("\n".join(lines))
    return result
