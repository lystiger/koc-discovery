"""Benchmark aggregation for one run: successful path vs total actually spent.

Attribution rules (all derived from the DB, filtered by run_id):
- Kalodata call stage: creator/rank, category/rank -> S0; creator/detail -> S1b; ui/creator_detail -> S2;
  video/url -> S3; video/rank -> S1b when created before the last S1b task finished, else S3.
- LLM call stage: kind content -> S3, reasons -> S4.
- Kalodata call is "successful path" when it is a paid, non-cache call with status 200/not_found that is not a
  duplicate of an earlier paid call, and (video/url) its video ends up in a final analysis, (ui/creator_detail)
  its creator's S2 task finished.
- LLM call is "successful path" when it is the llm_calls row recorded in `run_results` as the producer of a result
  this run selected (run-scoped, includes the model; written in the transaction that commits the result). Repairs, failed attempts and superseded results count only in
  total. A stage whose retained results are not all tracked in `run_results` (older runs) falls back to a hash/prompt-version heuristic, and the result
  carries `success_estimated: true`.
"""
import json
import math
from collections import defaultdict

from . import db
from .config import load_config
from .report import spearman

STAGES = ("S0", "S1a", "S1b", "S2", "S3", "S4")
_API_STAGE = {"creator/rank": "S0", "category/rank": "S0", "creator/detail": "S1b", "ui/creator_detail": "S2", "video/url": "S3"}
_OK_STATUS = {"200", "not_found"}


def _blank():
    return {"calls": 0, "cache_hits": 0, "credits": 0.0, "tokens_in": 0, "tokens_out": 0, "usd": 0.0, "latency_ms": 0}


def _selected(conn, run_id):
    """Run-scoped selected results {kind: {subject: (call_id, model, prompt_version)}}; None if the table is missing."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_results'").fetchone():
        return None  # database created before run_results existed; the benchmark command stays read-only
    out = {"content": {}, "reasons": {}}
    has_provenance = "provenance" in {row[1] for row in conn.execute("PRAGMA table_info(run_results)")}
    columns = "kind,subject,call_id,model,prompt_version" + (",provenance" if has_provenance else ",NULL AS provenance")
    for row in conn.execute(f"SELECT {columns} FROM run_results WHERE run_id=?", (run_id,)):
        out[row["kind"]][row["subject"]] = (row["call_id"], row["model"], row["prompt_version"])
        if row["provenance"] == "unknown" or (row["provenance"] is None and row["call_id"] is None):
            out.setdefault("unknown", {}).setdefault(row["kind"], set()).add(row["subject"])  # producer cannot be verified
    return out


def _retained(conn, run_id, kind):
    """Subjects of the results this run actually kept: video ids (content) or creator ids (reasons)."""
    if kind == "reasons":
        return {row[0] for row in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}
    subjects = set()
    for row in conn.execute("SELECT creator_id,breakdown_json FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL", (run_id,)):
        video_ids = json.loads(row[1]).get("video_ids")
        if video_ids is None:  # score written before video ids were recorded: every analysed video of the creator
            video_ids = [v[0] for v in conn.execute("SELECT DISTINCT a.video_id FROM analyses a JOIN videos v ON v.video_id=a.video_id WHERE v.creator_id=?", (row[0],))]
        subjects.update(video_ids)
    return subjects


def _attribution(conn, run_id, kind):
    """Per-result attribution for one stage: (confirmed producer ids, all known call ids, subjects needing the heuristic).

    Confirmed results count their producer; reused results count nothing; only retained subjects without a
    run_results row, or with unknown provenance, are left to the legacy heuristic.
    """
    selected = _selected(conn, run_id)
    retained = _retained(conn, run_id, kind)
    if selected is None:
        return set(), set(), retained
    rows = selected[kind]
    unknown = selected.get("unknown", {}).get(kind, set())
    confirmed = {info[0] for subject, info in rows.items() if info[0] is not None and subject in retained}
    known = {info[0] for info in rows.values() if info[0] is not None}
    return confirmed, known, {subject for subject in retained if subject not in rows or subject in unknown}


def _exact(conn, run_id, kind):
    """True when no retained result of the stage needs the heuristic (a stage with unknown producers is estimated)."""
    if _selected(conn, run_id) is None:
        return False  # no run_results table (older schema): provenance unknown, the split is an estimate
    return not _attribution(conn, run_id, kind)[2]


def _final_content(conn, run_id, with_model=False):
    if _exact(conn, run_id, "content"):
        selected = _selected(conn, run_id)["content"]
        return {(subject, info[2], info[1]) if with_model else (subject, info[2]) for subject, info in selected.items()}
    rows = conn.execute(
        "SELECT a.video_id,a.prompt_version,a.model FROM analyses a JOIN videos v ON v.video_id=a.video_id "
        "WHERE v.creator_id IN (SELECT creator_id FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL)", (run_id,)).fetchall()
    return {(row[0], row[1], row[2]) if with_model else (row[0], row[1]) for row in rows}


def _final_reasons(conn, run_id):
    result = set()
    for row in conn.execute("SELECT creator_id,rec_json FROM recommendations WHERE run_id=?", (run_id,)):
        usage = json.loads(row[1]).get("usage", {})
        result.add((row[0], usage.get("prompt_version"), usage.get("model")))
    return result


def _classify_llm(conn, run_id):
    """Return list of (stage, is_success, row) for non-cache LLM calls plus cache-hit rows.

    Attribution is per result: a call is successful when it is the confirmed producer of a retained result. Calls
    already known (another result's producer, a producer of a no-longer-retained result) are never claimed by the
    heuristic, which only decides calls whose cached result is a subject with unknown/untracked provenance. Reused
    results and subjects with a known producer therefore keep exact attribution (0 for reused).
    """
    attribution = {kind: _attribution(conn, run_id, kind) for kind in ("content", "reasons")}
    finals = {"content": _final_content(conn, run_id, True), "reasons": _final_reasons(conn, run_id)}
    out = []
    for row in conn.execute("SELECT * FROM llm_calls WHERE run_id=? ORDER BY id", (run_id,)).fetchall():
        stage = "S3" if row["kind"] == "content" else "S4"
        if row["cache_hit"]:
            out.append((stage, None, row))
            continue
        confirmed, known, uncertain = attribution[row["kind"]]
        if row["id"] in confirmed:
            out.append((stage, True, row))
            continue
        success = False
        cached = None if row["id"] in known or not uncertain else conn.execute(
            "SELECT output_json,usage_json FROM llm_cache WHERE request_hash=?", (row["request_hash"],)).fetchone()
        if cached:
            output, usage = json.loads(cached[0]), json.loads(cached[1])
            subject = output.get("video_id") if row["kind"] == "content" else output.get("creator_id")
            success = subject in uncertain and usage.get("prompt_version") == row["prompt_version"] and any(
                f[0] == subject and f[1] == row["prompt_version"] and (f[2] is None or f[2] == row["model"]) for f in finals[row["kind"]])
        out.append((stage, success, row))
    return out


def _final_video_hashes(conn, run_id):
    return {db.cache_key("video/url", {"video_id": video_id}) for video_id, _ in _final_content(conn, run_id)}


def _s2_view_hashes(conn, run_id):
    keys = conn.execute("SELECT key FROM tasks WHERE run_id=? AND stage='S2' AND status='done'", (run_id,)).fetchall()
    return {db.cache_key("ui/creator_detail", {"creator_id": row[0]}) for row in keys}


def _classify_api(conn, run_id):
    s1b_end = conn.execute("SELECT MAX(updated_at) FROM tasks WHERE run_id=? AND stage='S1b'", (run_id,)).fetchone()[0]
    final_videos = _final_video_hashes(conn, run_id)
    s2_views = _s2_view_hashes(conn, run_id)
    paid_seen = set()
    out = []
    for row in conn.execute("SELECT * FROM api_calls WHERE run_id=? ORDER BY id", (run_id,)).fetchall():
        endpoint = row["endpoint"]
        if endpoint == "video/rank":
            stage = "S1b" if s1b_end is not None and row["created_at"] <= s1b_end else "S3"
        else:
            stage = _API_STAGE.get(endpoint)
        if stage is None:
            continue
        if row["cache_hit"]:
            out.append((stage, None, row))
            continue
        success = row["status"] in _OK_STATUS
        if success and row["request_hash"] in paid_seen:
            success = False
        if success and endpoint == "video/url" and row["request_hash"] not in final_videos:
            success = False
        if success and endpoint == "ui/creator_detail" and row["request_hash"] not in s2_views:
            success = False
        if success:
            paid_seen.add(row["request_hash"])
        out.append((stage, success, row))
    return out


def _spearman_block(conn, run_id):
    xs, views, gpms = [], [], []
    finals = conn.execute("SELECT creator_id,score FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL ORDER BY creator_id", (run_id,)).fetchall()
    analysed = {(v, p) for v, p in _final_content(conn, run_id)}
    for row in finals:
        creator_id = row["creator_id"]
        creator = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        followers = float(json.loads(creator[0]).get("creator_followers") or 0) if creator else 0
        total_views = 0
        for video in conn.execute("SELECT video_id,data_json FROM videos WHERE creator_id=?", (creator_id,)):
            if any(video[0] == v for v, _ in analysed):
                total_views += float(json.loads(video[1]).get("views") or 0)
        metric = conn.execute("SELECT value FROM metrics WHERE creator_id=? AND name='video_gpm'", (creator_id,)).fetchone()
        gpm = json.loads(metric[0]) if metric and metric[0] is not None else None
        if followers > 0 and total_views > 0:
            xs.append((row["score"], total_views / followers, gpm))
    def pair(index):
        pts = [(x[0], x[index]) for x in xs if x[index] is not None]
        coef = spearman([p[0] for p in pts], [p[1] for p in pts])
        if len(pts) < 3:
            return {"rho": None, "n": len(pts), "reason": f"chỉ có {len(pts)} ứng viên có đủ dữ liệu (cần ít nhất 3)"}
        if coef is None:
            return {"rho": None, "n": len(pts), "reason": "một trong hai biến không đổi giữa các ứng viên"}
        return {"rho": coef, "n": len(pts), "reason": None}
    return {"content_vs_views_per_follower": pair(1), "content_vs_video_gpm": pair(2)}


def _run_mode(params, models):
    """Stored mode from run params, corrected by the models actually recorded in llm_calls."""
    stored = "mock" if params.get("mock") else "live"
    has_mock = "mock" in models
    has_real = any(m != "mock" for m in models)
    if stored == "live" and has_mock:
        return "mixed"
    if stored == "mock" and has_real:
        return "mixed"
    return stored


def aggregate(conn, run_id):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError(f"Không tìm thấy lượt chạy {run_id}.")
    params = json.loads(run["params_json"])
    wall = params.get("stage_wall_ms", {})
    success = {s: _blank() for s in STAGES}
    total = {s: _blank() for s in STAGES}
    failed_notes = defaultdict(int)
    for stage, ok, row in _classify_api(conn, run_id):
        for bucket, include in ((total, True), (success, ok)):
            if ok is None:
                bucket[stage]["cache_hits"] += 1
            elif include:
                bucket[stage]["calls"] += 1
                bucket[stage]["credits"] += row["credits"] or 0
                bucket[stage]["latency_ms"] += row["latency_ms"] or 0
        if ok is False:
            failed_notes["api"] += 1
    for stage, ok, row in _classify_llm(conn, run_id):
        for bucket, include in ((total, True), (success, ok)):
            if ok is None:
                bucket[stage]["cache_hits"] += 1
            elif include:
                bucket[stage]["calls"] += 1
                bucket[stage]["tokens_in"] += row["input_tokens"] or 0
                bucket[stage]["tokens_out"] += row["output_tokens"] or 0
                bucket[stage]["usd"] += row["cost_usd"] or 0
                bucket[stage]["latency_ms"] += row["latency_ms"] or 0
        if ok is False:
            failed_notes["llm"] += 1
    for bucket in (success, total):
        for stage in STAGES:
            item = bucket[stage]
            item["wall_time_ms"] = wall.get(stage, 0)
            item["credits"] = round(item["credits"], 4)
            item["usd"] = round(item["usd"], 6)

    done = {row[0]: row[1] for row in conn.execute("SELECT stage,COUNT(*) FROM tasks WHERE run_id=? AND status='done' GROUP BY stage", (run_id,))}
    allt = {row[0]: row[1] for row in conn.execute("SELECT stage,COUNT(*) FROM tasks WHERE run_id=? GROUP BY stage", (run_id,))}
    recs = conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0]
    funnel = {
        "S0": (params.get("limit", 0), allt.get("S1a", 0)),
        "S1a": (allt.get("S1a", 0), allt.get("S1b", 0)),
        "S1b": (allt.get("S1b", 0), allt.get("S2", 0)),
        "S2": (allt.get("S2", 0), done.get("S2", 0)),
        "S3": (allt.get("S3", 0), done.get("S3", 0)),
        "S4": (done.get("S3", 0), recs),
    }
    processed = {"S0": allt.get("S1a", 0), "S1a": allt.get("S1a", 0), "S1b": done.get("S1b", 0),
                 "S2": done.get("S2", 0), "S3": done.get("S3", 0), "S4": recs}

    def sums(bucket):
        return {key: round(sum(bucket[s][key] for s in STAGES), 6) for key in ("calls", "cache_hits", "credits", "tokens_in", "tokens_out", "usd", "wall_time_ms")}

    def unit(bucket):
        result = {}
        for stage in STAGES:
            n = processed[stage]
            item = bucket[stage]
            result[stage] = {key: (item[key] / n if n else 0.0) for key in ("credits", "tokens_in", "tokens_out", "usd", "wall_time_ms")}
            result[stage]["denominator"] = n
        return result

    models = {row[0] for row in conn.execute("SELECT DISTINCT model FROM llm_calls WHERE run_id=?", (run_id,))}
    mode = _run_mode(params, models)
    paid_kinds = {row[0] for row in conn.execute("SELECT DISTINCT kind FROM llm_calls WHERE run_id=? AND cache_hit=0", (run_id,))}
    estimated_stages = {"S3": "content" in paid_kinds and not _exact(conn, run_id, "content"),
                        "S4": "reasons" in paid_kinds and not _exact(conn, run_id, "reasons")}
    estimated = any(estimated_stages.values())
    affected, checked = _placeholder_counts(conn, run_id)
    result = {
        "run_id": run_id, "status": run["status"], "mode": mode, "mode_stored": "mock" if params.get("mock") else "live",
        "success_estimated": estimated, "success_estimated_stages": [k for k, v in estimated_stages.items() if v],
        "limit": params.get("limit"), "stages_success": success, "stages_total": total,
        "funnel": {s: {"in": a, "out": b} for s, (a, b) in funnel.items()},
        "totals_success": sums(success), "totals_total": sums(total),
        "failed_calls": dict(failed_notes), "units_success": unit(success), "units_total": unit(total),
        "calibration": _spearman_block(conn, run_id),
        "audience_placeholder": affected > 0,
        "audience_placeholder_creators": affected, "audience_creators_checked": checked,
    }
    waste = {k: round(result["totals_total"][k] - result["totals_success"][k], 6) for k in ("credits", "tokens_in", "tokens_out", "usd")}
    result["waste"] = waste
    others = conn.execute("SELECT COUNT(*),COALESCE(SUM(credits),0) FROM api_calls WHERE run_id IS NOT ?", (run_id,)).fetchone()
    result["excluded_api_calls"] = {"calls": others[0], "credits": round(others[1], 4)}
    return result


def _placeholder_counts(conn, run_id):
    """(creators whose audience capture is placeholder, creators with an S2 capture) using the per-creator S4 rule."""
    from .stages import placeholder_audience_creators
    checked = conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S2'", (run_id,)).fetchone()[0]
    return len(placeholder_audience_creators(conn, run_id)), checked


def project(result, candidates, which="units_total"):
    """Project cost for `candidates` input rows using unit costs and config funnel caps.

    S0, S1a: N; S1b: min(N,s1a_limit); S2: min(S1b, s1_limit, s2_limit);
    S3: S2 count; S4: min(S3, recommendation_count). Stage cost = count * unit cost.
    """
    cfg = load_config()["s1"]
    s1b = min(candidates, cfg["s1a_limit"])
    s2 = min(s1b, cfg["s1_limit"], cfg["s2_limit"])
    s3 = s2
    s4 = min(s3, cfg["recommendation_count"])
    counts = {"S0": candidates, "S1a": candidates, "S1b": s1b, "S2": s2, "S3": s3, "S4": s4}
    stages = {}
    for stage in STAGES:
        u = result[which][stage]
        n = counts[stage]
        stages[stage] = {"candidates": n, "credits": round(u["credits"] * n, 4), "tokens_in": round(u["tokens_in"] * n),
                         "tokens_out": round(u["tokens_out"] * n), "usd": round(u["usd"] * n, 6),
                         "wall_time_s": round(u["wall_time_ms"] * n / 1000, 1)}
    totals = {key: round(sum(s[key] for s in stages.values()), 6) for key in ("credits", "tokens_in", "tokens_out", "usd", "wall_time_s")}
    return {"candidates": candidates, "stages": stages, "totals": totals, "s2_calendar_days": math.ceil(s2 / cfg["daily_ui_limit"]) if s2 else 0}


def build(conn, run_id, scaling_run_id=None):
    result = aggregate(conn, run_id)
    result["funnel_config"] = {k: load_config()["s1"][k] for k in ("s1a_limit", "s1_limit", "s2_limit", "video_count", "recommendation_count", "daily_ui_limit")}
    result["projections"] = {str(n): {"successful_path": project(result, n, "units_success"), "total_spent": project(result, n, "units_total")} for n in (50, 200, 500)}
    from .faithfulness import stored_summary
    if faithfulness := stored_summary(conn, run_id):  # only when `koc faithfulness` has graded this run; units above are unchanged
        result["faithfulness"] = faithfulness
    result["s2_view_credits_observed"] = round(conn.execute("SELECT COALESCE(SUM(credits),0) FROM api_calls WHERE run_id=? AND endpoint='ui/creator_detail'", (run_id,)).fetchone()[0], 4)
    result["s2_view_price_config"] = load_config()["kalodata_prices"]["ui_creator_detail_view"]
    if scaling_run_id:
        scaling = aggregate(conn, scaling_run_id)
        result["scaling_run"] = {key: scaling[key] for key in ("run_id", "status", "mode", "limit", "stages_total", "funnel", "totals_total")}
    return result
