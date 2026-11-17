import itertools
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from . import db
from .pricing import creator_cost
from .brief import brand_brief, check_brief, make_brief, run_brief, s4_options, vnd
from .budget_guard import BudgetGuard, get_cached, llm_cache_key, put_cached
from .config import load_config
from .kalodata import CreditCounter, KalodataClient, KalodataNotReady, KalodataRateLimited
from .stages import AUDIENCE_METRIC_NAMES, brand_fit_gate, excluded_brand_fit, audience_score, final_score, placeholder_audience_creators, parse_audience_text, score_creator, score_creator_rank, s1_shortlist
from .video_select import select_videos
from .types import BudgetExceeded, CacheOnlyMiss, CandidateSummary, ContentAnalysis, Evidence, ProviderAccountError, Recommendation, RubricScore, Usage, VideoInput


class S2CaptureEmpty(RuntimeError):
    def __init__(self):
        super().__init__("Không đọc được dữ liệu khán giả từ trang Kalodata; đã dừng để tránh lưu điểm sai.")


class S3AnalysisError(Exception):
    pass


def _data(response):
    return response.get("data", response) if isinstance(response, dict) else response


def run_exclusions(conn, run_ids):
    """{"run_ids", "creator_ids"} for the final picks of the named runs; RuntimeError (Vietnamese) on an unknown run or one with no picks."""
    run_ids = list(dict.fromkeys(run_ids))
    creators = set()
    for run_id in run_ids:
        if conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone() is None:
            raise RuntimeError(f"Không tìm thấy lượt chạy {run_id} để loại KOC. Dùng `koc status` để xem các lượt chạy.")
        picked = {row[0] for row in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}
        if not picked:
            raise RuntimeError(f"Lượt chạy {run_id} chưa có KOC nào được đề xuất nên không có gì để loại.")
        creators |= picked
    return {"run_ids": run_ids, "creator_ids": sorted(creators)}


def _excluded_creators(conn, run_id):
    row = conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return set(json.loads(row[0]).get("exclude", {}).get("creator_ids", [])) if row else set()


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _pause_for_kill(env_name, label):
    if not os.getenv(env_name):
        return
    marker = Path(os.getenv("KOC_TEST_STAGE_MARKER", "/tmp/koc-stage-ready"))
    marker.write_text(label)
    time.sleep(60)


def _rank_candidates(client, limit, brief):
    categories = brief["category_ids"]
    rows = []
    for page_number in range(1, (limit + 99) // 100 + 1):
        batch = _data(client.creator_rank(page_size=min(100, limit - len(rows)), page_number=page_number,
                                          category_ids=categories or None, followers_range="10000-300000",
                                          **({} if categories else {"keyword": brief["product"]}))) or []
        rows.extend(batch)
        if len(batch) < 100 or len(rows) >= limit: break
    rows = [row for row in rows if 10_000 <= _int(row.get("creator_followers")) <= 300_000][:limit]
    return rows


def _s1a(conn, run_id, creator_id):
    row = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
    rank = json.loads(row[0]) if row else {}
    db.upsert_score(conn, run_id, creator_id, "S1a", score_creator_rank(rank), {"rank_only": True})


def _s1a_top(conn, run_id, limit=60):
    return [row[0] for row in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S1a' ORDER BY score DESC,creator_id LIMIT ?", (run_id, limit))]


def _s1(conn, run_id, client, creator_id):
    row = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
    rank = json.loads(row[0]) if row else {}
    categories = run_brief(conn, run_id, load_config())["category_ids"]
    detail = _data(client.creator_detail(creator_id, need_extra=True, **({"category_ids": categories} if categories else {}))) or {}
    videos = _data(client.video_rank(creator_id, page_size=10)) or []
    _pause_for_kill("KOC_TEST_PAUSE_AFTER_S1_API", "S1b")
    commercial_creator = {**rank, **detail}
    commercial_creator["revenue"] = rank.get("revenue", detail.get("revenue"))
    commercial = score_creator(creator_id, commercial_creator, videos, skincare_revenue=detail.get("revenue") if categories else None)

    def write(c):
        db.upsert_creator(c, creator_id, detail.get("creator_handle") or detail.get("creator_nickname") or rank.get("creator_handle"), {**rank, **detail})
        for name, value in commercial["metrics"].items():
            db.upsert_metric(c, creator_id, name, value, f"metric:{creator_id}:{name}")
        for video in videos:
            if video.get("video_id"):
                db.upsert_video(c, str(video["video_id"]), creator_id, video)
        db.upsert_score(c, run_id, creator_id, "S1", commercial["score"], commercial["breakdown"])
    return write


def _browser_page(cdp_url):
    from playwright.sync_api import sync_playwright
    playwright = sync_playwright().start()
    context = playwright.chromium.connect_over_cdp(cdp_url).contexts[0]
    return playwright, context.new_page()


def _strip_contact_lines(text):
    contact = re.compile(r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d\s().-]{6,}\d)|\b(?:zalo|whatsapp|wa\.me|zalo\.me)\b|@[\w.]+)", re.I)
    return "\n".join(line for line in text.splitlines() if not contact.search(line))


def _s2_raw_path(creator_id):
    creator = re.sub(r"[^A-Za-z0-9_.-]", "_", str(creator_id))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return Path("data/raw/s2") / f"{creator}_{timestamp}.txt"


def capture_audience(page, creator_id, previous_load=0.0, sleep=time.sleep, raw_path=None):
    elapsed = time.monotonic() - previous_load
    if previous_load and elapsed < 5:
        sleep(5 - elapsed)
    url = f"https://www.kalodata.com/creator/detail?id={creator_id}"
    page.goto(url)
    page.wait_for_timeout(5000)
    text = re.sub(r"[\ue000-\uf8ff]", "", page.inner_text("body"))
    if raw_path is not None:
        target = Path(raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_strip_contact_lines(text))
    if any(term in text.lower() for term in ("trial accounts are allowed", "access denied", "trial account", "too many requests")):
        raise PermissionError("Giới hạn hoặc từ chối truy cập Kalodata.")
    return parse_audience_text(text), url, time.monotonic()


def _s2_top(conn, run_id, limit=15):
    rows = conn.execute("SELECT s2.creator_id FROM scores s2 LEFT JOIN scores s1 ON s1.run_id=s2.run_id AND s1.creator_id=s2.creator_id AND s1.stage='S1' "
                        "WHERE s2.run_id=? AND s2.stage='S2' ORDER BY s2.score IS NULL,s2.score DESC,s1.score DESC,s2.creator_id", (run_id,)).fetchall()
    eligible = []
    for row in rows:
        metrics = conn.execute("SELECT value FROM metrics WHERE creator_id=? AND name IN ('female_pct','age_18_24_pct','age_25_34_pct')", (row[0],)).fetchall()
        if any(metric[0] is not None and json.loads(metric[0]) is not None for metric in metrics):
            eligible.append(row[0])
        if len(eligible) == limit:
            break
    return eligible


def _s2_write(run_id, creator_id, metrics, source, brief):
    def write(c):
        for name, value in metrics.items():
            db.upsert_metric(c, creator_id, name, value, source)
        db.upsert_score(c, run_id, creator_id, "S2", audience_score(metrics, brief["gender"], brief["age_min"], brief["age_max"]), metrics)
    return write


def _download_video(client, video_id, target, mock=False):
    if target.exists():
        return str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if mock:
        client.video_url(video_id)
        target.write_bytes(f"mock-video:{video_id}".encode())
        return str(target)
    data = _data(client.video_url(video_id))
    url = data.get("video_url") if isinstance(data, dict) else None
    if not url:
        raise RuntimeError(f"Không có URL video {video_id}.")
    with httpx.stream("GET", url, timeout=60) as response:
        response.raise_for_status()
        with target.open("wb") as out:
            for chunk in response.iter_bytes():
                out.write(chunk)
    return str(target)


def _fake_analysis(video):
    usage = Usage(provider="gemini", model="mock", prompt_version="content_v1", input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0)
    evidence = [Evidence(evidence_id=f"{video.video_id}@0.5", video_id=video.video_id, start_s=.5, end_s=1.0, kind="frame", quote_vi="Video kiểm thử", frame_path=None)]
    rubric = [RubricScore(criterion=name, score=3, rationale_vi="Kiểm thử ngoại tuyến.", evidence_ids=[evidence[0].evidence_id]) for name in ("hook", "product_clarity", "demonstration", "claim_quality", "cta", "brand_fit", "production_quality")]
    return ContentAnalysis(video_id=video.video_id, transcript_vi=None, rubric=rubric, risks_vi=[], evidence=evidence, usage=usage)


def _cache_hit_usage(usage_data):
    usage_data["cache_hit"] = True
    usage_data["cost_usd"] = 0.0
    usage_data["input_tokens"] = 0
    usage_data["output_tokens"] = 0
    if "audio_tokens" in usage_data:
        usage_data["audio_tokens"] = 0
    if "image_tokens" in usage_data:
        usage_data["image_tokens"] = 0
    return usage_data


def _key_brief(kind, brief):
    """Brief fields behind a cache key (reasons keep budget_vnd)."""
    return brief.model_dump(exclude={"budget_vnd"}) if kind == "content" else brief.model_dump()


def _content_key(media_hash, prompt_version, model, brief, video_id):
    """Content cache key: media bytes, prompt label, model, product, audience and the video id (identical bytes under
    two video ids must not share an analysis). Budget is not part of it: the prompt does not carry it."""
    return llm_cache_key(media_hash, prompt_version, model, {**_key_brief("content", brief), "video_id": video_id})


def _legacy_content_row(conn, media_hash, prompt_version, model, brief, video_id):
    """(output_json, usage_json, call_id) of a pre-v2 content cache row (key built with budget_vnd, no video id), or None.

    The budget that built the old key is unknown, so try the brief's own and every budget stored in a run's brief.
    The row is used only when its analysis belongs to the requested video. Read-only.
    """
    budgets = {brief.budget_vnd}

    def collect(node):  # every budget_vnd in a run's params (brief.budget_vnd, s4.budget_vnd, ...)
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "budget_vnd" and isinstance(value, int) and not isinstance(value, bool):
                    budgets.add(value)
                else:
                    collect(value)

    for (params,) in conn.execute("SELECT params_json FROM runs"):
        collect(json.loads(params))
    for budget in sorted(budgets):
        legacy = llm_cache_key(media_hash, prompt_version, model, brief.model_copy(update={"budget_vnd": budget}).model_dump())
        row = conn.execute("SELECT output_json,usage_json,call_id FROM llm_cache WHERE request_hash=?", (legacy,)).fetchone()
        if row and (video_id is None or json.loads(row[0]).get("video_id") == video_id):
            return tuple(row)
    return None


def content_analysis_cached(conn, media_hash, prompt_version, model, brief, video_id) -> bool:
    """True when a paid S3 analysis of this video would be served from cache (current key, else a valid legacy row)."""
    if get_cached(conn, _content_key(media_hash, prompt_version, model, brief, video_id)) is not None:
        return True
    return _legacy_content_row(conn, media_hash, prompt_version, model, brief, video_id) is not None


def _cached_call(conn, run_id, kind, media_hash, prompt_version, model, brief, function, *args, cache_only=False, **kwargs):
    if kind == "content":
        video_id = getattr(args[0], "video_id", None) if args else None
        key = _content_key(media_hash, prompt_version, model, brief, video_id)
        if get_cached(conn, key) is None:
            legacy = _legacy_content_row(conn, media_hash, prompt_version, model, brief, video_id)
            if legacy:
                put_cached(conn, key, json.loads(legacy[0]), json.loads(legacy[1]), legacy[2])
    else:
        key = llm_cache_key(media_hash, prompt_version, model, brief.model_dump())
    cached = get_cached(conn, key)
    guard = BudgetGuard(conn, run_id=run_id, kind=kind)
    if cached:
        output, usage_data = cached
        usage_data = _cache_hit_usage(usage_data)
        usage = Usage.model_validate(usage_data)
        output["usage"] = usage.model_dump()
        if kind == "content":
            result = ContentAnalysis.model_validate(output)
            if args:
                from .llm.guard import warn_cached_content
                result = warn_cached_content(result, args[0])
        else:
            result = Recommendation.model_validate(output)
            checked = _validate_cached_reasons(result, args)
            if checked is None:
                if cache_only:
                    raise CacheOnlyMiss(f"LLM {kind} ({prompt_version}): bản lưu không hợp lệ với dữ liệu khán giả hiện tại")
                cached = None  # unsafe legacy entry: drop it and regenerate instead of trusting it
                with db.transaction(conn):
                    conn.execute("DELETE FROM llm_cache WHERE request_hash=?", (key,))
            else:
                from .llm.guard import warn_cached_reasons
                result = warn_cached_reasons(checked)
        if cached:
            db.add_llm_call(conn, run_id, kind, key, usage, True)
            return result
    if cache_only:
        raise CacheOnlyMiss(f"LLM {kind} ({prompt_version})")
    last_call_id = conn.execute("SELECT COALESCE(MAX(id),0) FROM llm_calls").fetchone()[0]
    try:
        result = function(*args, budget_guard=guard, **kwargs)
    finally:
        db.update_llm_request_hash(conn, run_id, kind, key, last_call_id)
    # The call that returned the valid result is the last paid row recorded during this function call.
    producing = conn.execute("SELECT MAX(id) FROM llm_calls WHERE id>? AND run_id IS ? AND kind=? AND cache_hit=0", (last_call_id, run_id, kind)).fetchone()[0]
    put_cached(conn, key, result.model_dump(mode="json"), result.usage.model_dump(mode="json"), producing)
    return result


def _producing_call(conn, run_id, key):
    """(call_id, provenance) of the cache entry's producer.

    confirmed: the stored producer is a paid call of this run; reused: it is a call of another run (cache reuse, no
    paid success here); unknown: legacy entry with no stored producer.
    """
    row = conn.execute("SELECT call_id FROM llm_cache WHERE request_hash=?", (key,)).fetchone()
    if row is None or row[0] is None:
        return None, "unknown"
    mine = conn.execute("SELECT 1 FROM llm_calls WHERE id=? AND run_id IS ? AND cache_hit=0", (row[0], run_id)).fetchone()
    return (row[0], "confirmed") if mine else (None, "reused")


def _commit_selected(c, run_id, kind, subject, key, usage):
    """Record which result this run selected, inside the same transaction that commits the result itself."""
    call_id, provenance = _producing_call(c, run_id, key)
    db.record_run_result(c, run_id, kind, subject, call_id, usage, provenance)


def _validate_cached_reasons(recommendation, args):
    """Re-check a cached recommendation against the current audience state; None when it is unusable."""
    from .llm.reasons import validate_cached_recommendation
    candidate = args[0] if args else None
    if candidate is None:
        return recommendation
    try:
        return validate_cached_recommendation(recommendation, candidate)
    except ValueError:
        return None


def _mock_cached(conn, run_id, kind, key, function, model_type, cache_only=False):
    cached = get_cached(conn, key)
    if cached:
        output, usage_data = cached
        usage_data = _cache_hit_usage(usage_data)
        result = model_type.model_validate({**output, "usage": usage_data})
        db.add_llm_call(conn, run_id, kind, key, result.usage, True)
        return result
    if cache_only:
        raise CacheOnlyMiss(f"LLM {kind} (mô phỏng)")
    result = function()
    call_id = db.add_llm_call(conn, run_id, kind, key, result.usage, False)
    put_cached(conn, key, result.model_dump(mode="json"), result.usage.model_dump(mode="json"), call_id)
    return result


def _s3_creator(conn, run_id, client, creator_id, mock=False, media_dir=Path("data/media"), cache_only=False):
    from . import llm
    videos = _data(client.video_rank(creator_id, page_size=100)) or []
    run_brief_data = run_brief(conn, run_id, load_config())
    picked = select_videos(videos, run_brief_data, load_config(), n=3)  # every candidate competes on brief relevance
    videos = [video for video, _ in picked]
    selection = {str(video["video_id"]): info for video, info in picked}
    analyses = []
    keys = []
    brief = brand_brief(run_brief_data)
    for video in videos:
        vid = str(video["video_id"])
        if cache_only and not mock and not (media_dir / f"{vid}.mp4").exists():
            raise CacheOnlyMiss(f"tệp video {vid}")
        path = Path(_download_video(client, vid, media_dir / f"{vid}.mp4", mock))
        source = video.get("video_url") or ""
        media_hash = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        item = VideoInput(video_id=vid, creator_id=creator_id, title=video.get("video_title"), publish_date=video.get("publish_date"), views=_int(video.get("views")), likes=_int(video.get("digg_count")), comments=_int(video.get("comment_count")), shares=_int(video.get("share_count")), revenue_vnd=video.get("revenue"), mp4_path=str(path))
        if mock:
            keys.append(_content_key(media_hash, "content_v1", "mock", brief, vid))
            analysis = _mock_cached(conn, run_id, "content", keys[-1], lambda: _fake_analysis(item), ContentAnalysis, cache_only)
        else:
            keys.append(_content_key(media_hash, "content_v3", load_config()["llm_caps"].get("model", "gemini-3.8-flash"), brief, vid))
            try:
                analysis = _cached_call(conn, run_id, "content", media_hash, "content_v3", load_config()["llm_caps"].get("model", "gemini-3.8-flash"), brief, llm.analyze_video, item, brief, cache_only=cache_only, frames_dir="data/media/frames")
            except (BudgetExceeded, ProviderAccountError, CacheOnlyMiss):
                raise
            except (ValueError, RuntimeError) as exc:
                raise S3AnalysisError(str(exc)) from exc
        _pause_for_kill("KOC_TEST_PAUSE_AFTER_LLM", "S3")
        analyses.append(analysis)
    score = sum(r.score for a in analyses for r in a.rubric) / (7 * len(analyses)) * 20 if analyses else None
    def write(c):
        for video, analysis, key in zip(videos, analyses, keys):
            vid = str(video["video_id"])
            db.upsert_video(c, vid, creator_id, video, str(media_dir / f"{vid}.mp4"))
            c.execute("INSERT INTO analyses VALUES (?,?,?,?) ON CONFLICT(video_id,prompt_version,model) DO UPDATE SET analysis_json=excluded.analysis_json", (vid, analysis.usage.prompt_version, analysis.usage.model, analysis.model_dump_json()))
            _commit_selected(c, run_id, "content", vid, key, analysis.usage)
        breakdown = {"video_count": len(analyses), "video_ids": [str(video["video_id"]) for video in videos[:len(analyses)]]}
        breakdown["video_selection"] = [{"video_id": vid, **selection[vid]} for vid in breakdown["video_ids"]]
        if not analyses:
            breakdown["caveat_vi"] = "Không tìm thấy video để phân tích nội dung."
        db.upsert_score(c, run_id, creator_id, "S3", score, breakdown)
    return write


def _rate(followers):
    return creator_cost(followers, load_config()["rate_card"]["tiers"])


def _best_five(conn, run_id):
    brief = run_brief(conn, run_id, load_config())
    ids = _s2_top(conn, run_id, 15)
    placeholders = placeholder_audience_creators(conn, run_id)
    excluded = {item["id"] for item in excluded_brand_fit(conn, run_id)} | _excluded_creators(conn, run_id)
    rows = []
    for creator_id in ids:
        scores = {row["stage"]: row["score"] for row in conn.execute("SELECT stage,score FROM scores WHERE run_id=? AND creator_id=?", (run_id, creator_id))}
        if creator_id in placeholders:
            scores["S2"] = None
        if scores.get("S3") is None or creator_id in excluded:
            continue
        creator_row = conn.execute("SELECT data_json,handle FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        profile = json.loads(creator_row["data_json"])
        followers = _int(profile.get("creator_followers"))
        cost = _rate(followers)
        final = final_score(scores.get("S1"), scores.get("S2"), scores["S3"])
        rows.append({"id": creator_id, "profile": profile, "handle": creator_row["handle"] or creator_id, "scores": scores, "cost": cost, "final": final})
    combinations = []
    for combo in itertools.combinations(rows, min(brief["count"], len(rows))):
        total = sum(item["cost"] for item in combo)
        mcn = [item["profile"].get("mcn_id") for item in combo if item["profile"].get("mcn_id")]
        if total <= brief["budget_vnd"] and len(mcn) == len(set(mcn)):
            combinations.append((sum(item["final"] for item in combo), combo))
    return sorted(max(combinations, key=lambda item: item[0])[1], key=lambda item: item["final"], reverse=True) if combinations else []


def _s4_budget_block_reason(conn, run_id, required, shortage=None):
    config = load_config()
    brief = run_brief(conn, run_id, config)
    rows = []
    excluded = {item["id"] for item in excluded_brand_fit(conn, run_id, config)}
    dropped = 0
    for creator_id in _s2_top(conn, run_id, 15):
        scores = {row["stage"]: row["score"] for row in conn.execute("SELECT stage,score FROM scores WHERE run_id=? AND creator_id=?", (run_id, creator_id))}
        if scores.get("S3") is None:
            continue
        if creator_id in excluded:
            dropped += 1
            continue
        creator = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        profile = json.loads(creator[0])
        rows.append((profile.get("mcn_id"), _rate(_int(profile.get("creator_followers")))))
    options, minimum = s4_options(rows, {**brief, "count": required}, config)
    cheapest = vnd(minimum) if minimum is not None else "không xác định"
    note = f" Đã loại {dropped} KOC vì video không hợp sản phẩm (độ hợp thương hiệu cao nhất dưới {config['scoring']['s4']['min_brand_fit']}/5)." if dropped else ""
    if shortage:
        return f"{shortage}{note} Lựa chọn: (1) {options[0]}; (2) {options[1]}; (3) {options[2]}."
    return (f"blocked: không có tổ hợp {required} KOC trong ngân sách {vnd(brief['budget_vnd'])} VND ({len(rows)} KOC có điểm nội dung; tổ hợp rẻ nhất {cheapest} VND).{note} "
            f"Lựa chọn: (1) {options[0]}; (2) {options[1]}; (3) {options[2]}.")


def _s4(conn, run_id, mock=False, cache_only=False):
    from . import llm
    run_params = run_brief(conn, run_id, load_config())
    brief = brand_brief(run_params)
    recommendations = []
    llm_keys = {}
    placeholders = placeholder_audience_creators(conn, run_id)
    picks = _best_five(conn, run_id)
    for rank, item in enumerate(picks, 1):
        placeholder = item["id"] in placeholders
        metric_rows = conn.execute("SELECT name,value FROM metrics WHERE creator_id=?", (item["id"],)).fetchall()
        metrics = {r["name"]: json.loads(r["value"]) for r in metric_rows if not (placeholder and r["name"] in AUDIENCE_METRIC_NAMES)}
        metric_ids = {name: f"metric:{item['id']}:{name}" for name in metrics}
        analyses = [ContentAnalysis.model_validate_json(r[3]) for r in db.run_analyses(conn, run_id, item["id"], mock)]
        summary = CandidateSummary(creator_id=item["id"], handle=item["handle"], followers=_int(item["profile"].get("creator_followers")), commercial_score=item["scores"].get("S1", 0), audience_score=item["scores"].get("S2"), content_score=item["scores"].get("S3", 0), final_score=item["final"], est_cost_vnd=item["cost"], metrics=metrics, metric_evidence_ids=metric_ids, analyses=analyses)
        cache_input = summary.model_dump(mode="json")
        for analysis in cache_input["analyses"]:
            analysis.pop("usage", None)
        key = __import__("hashlib").sha256(json.dumps(cache_input, sort_keys=True).encode()).hexdigest()
        if mock:
            def make_recommendation():
                usage = Usage(provider="gemini", model="mock", prompt_version="reasons_v4", input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0)
                citations = list(metric_ids.values())[:3] or [e.evidence_id for a in analyses for e in a.evidence][:3]
                return Recommendation(creator_id=item["id"], reasons_vi=["Chỉ số bán hàng phù hợp.", "Điểm nội dung video ở mức tốt." if placeholder else "Tệp người xem khớp khách hàng mục tiêu.", "Video có bằng chứng sản phẩm rõ."], cited_evidence_ids=citations, caveats_vi=["Chưa xác minh hồ sơ khán giả (gói Kalodata không có dữ liệu khán giả); cần xác nhận trực tiếp với creator."] if placeholder else [], usage=usage)
            llm_keys[item["id"]] = llm_cache_key(key, "reasons_v4", "mock", brief.model_dump())
            recommendation = _mock_cached(conn, run_id, "reasons", llm_keys[item["id"]], make_recommendation, Recommendation, cache_only)
        else:
            llm_keys[item["id"]] = llm_cache_key(key, "reasons_v4", load_config()["llm_caps"].get("model", "gemini-3.8-flash"), brief.model_dump())
            recommendation = _cached_call(conn, run_id, "reasons", key, "reasons_v4", load_config()["llm_caps"].get("model", "gemini-3.8-flash"), brief, llm.write_reasons, summary, brief, cache_only=cache_only)
        recommendations.append((rank, item, recommendation))
    total = sum(item["cost"] for item in picks)

    def write(c):
        params = json.loads(c.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])
        params["s4"] = {"total_vnd": total, "budget_vnd": run_params["budget_vnd"], "leftover_vnd": run_params["budget_vnd"] - total}
        c.execute("UPDATE runs SET params_json=? WHERE run_id=?", (json.dumps(params, sort_keys=True), run_id))
        # The run's selected reasons results are exactly this committed selection; displaced finalists drop out.
        c.execute("DELETE FROM run_results WHERE run_id=? AND kind='reasons'", (run_id,))
        # The run's recommendation set is replaced as a whole: displaced creators leave no row or S4 score behind.
        keep = [item["id"] for _, item, _ in recommendations]
        marks = ",".join("?" * len(keep))
        c.execute(f"DELETE FROM recommendations WHERE run_id=? AND creator_id NOT IN ({marks})", (run_id, *keep))
        c.execute(f"DELETE FROM scores WHERE run_id=? AND stage='S4' AND creator_id NOT IN ({marks})", (run_id, *keep))
        for rank, item, recommendation in recommendations:
            _commit_selected(c, run_id, "reasons", item["id"], llm_keys[item["id"]], recommendation.usage)
            c.execute("INSERT INTO recommendations(run_id,creator_id,rank,est_cost_vnd,rec_json) VALUES (?,?,?,?,?) ON CONFLICT(run_id,creator_id) DO UPDATE SET rank=excluded.rank,est_cost_vnd=excluded.est_cost_vnd,rec_json=excluded.rec_json", (run_id, item["id"], rank, item["cost"], recommendation.model_dump_json()))
            db.upsert_score(c, run_id, item["id"], "S4", item["final"], {"commercial": item["scores"].get("S1", 0), "audience": item["scores"].get("S2"), "content": item["scores"].get("S3", 0), "brand_fit_max": brand_fit_gate(c, run_id, item["id"])["max_brand_fit"]})
    return write


def _advance(conn, run_id, client, limit, page, mock, media_dir):
    tasks = conn.execute("SELECT stage,status FROM tasks WHERE run_id=?", (run_id,)).fetchall()
    states = {}
    for row in tasks:
        states.setdefault(row["stage"], []).append(row["status"])
    def done(stage):
        terminal = ("done", "skipped", "failed", "blocked") if stage == "S3" else ("done", "skipped")
        return stage in states and all(s in terminal for s in states[stage])
    config = load_config()["s1"]
    if done("S1a") and "S1b" not in states:
        with db.transaction(conn):
            for creator_id in _s1a_top(conn, run_id, config["s1a_limit"]): db.add_task(conn, run_id, "S1b", creator_id)
    if done("S1b") and "S2" not in states:
        for creator_id in s1_shortlist(conn, run_id, config["s1_limit"]):
            db.add_task(conn, run_id, "S2", creator_id)
    if done("S2") and "S3" not in states:
        for creator_id in _s2_top(conn, run_id, config["s2_limit"]): db.add_task(conn, run_id, "S3", creator_id)
    content_scores = conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL", (run_id,)).fetchone()[0]
    if done("S3") and "S4" not in states:
        db.add_task(conn, run_id, "S4", "select")


def _record_stage_time(conn, run_id, stage, elapsed_ms):
    row = conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    params = json.loads(row[0])
    timings = params.setdefault("stage_wall_ms", {})
    timings[stage] = timings.get(stage, 0) + elapsed_ms
    with db.transaction(conn):
        conn.execute("UPDATE runs SET params_json=? WHERE run_id=?", (json.dumps(params, sort_keys=True), run_id))


def execute(conn, run_id: str, client: KalodataClient, limit: int = 200, *, page=None, mock=False, media_dir=Path("data/media"), cache_only=False):
    db.reset_running(conn, run_id)
    brief = run_brief(conn, run_id, load_config())
    skip = _excluded_creators(conn, run_id)
    playwright = None
    previous = 0.0
    while True:
        _advance(conn, run_id, client, limit, page, mock, media_dir)
        tasks = db.pending_tasks(conn, run_id)
        if not tasks:
            break
        task = tasks[0]
        if task["stage"] == "S4":
            content_scores = conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL", (run_id,)).fetchone()[0] - len(excluded_brand_fit(conn, run_id))
            required = brief["count"]
            if content_scores < required:
                db.block_task(conn, task["task_id"], _s4_budget_block_reason(conn, run_id, required, f"Chưa đủ điểm nội dung để đề xuất: có {content_scores}, cần {required}."))
                continue
            if len(_best_five(conn, run_id)) < required:
                db.block_task(conn, task["task_id"], _s4_budget_block_reason(conn, run_id, required))
                continue
        if task["stage"] == "S2":
            s2_limit = load_config()["s1"]["s2_limit"]
            done_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE run_id=? AND stage='S2' AND status='done'", (run_id,)).fetchone()[0]
            if done_count >= s2_limit:
                with db.transaction(conn):
                    conn.execute("UPDATE tasks SET status='skipped',error='vượt s2_limit',updated_at=? WHERE run_id=? AND stage='S2' AND status='pending'", (db.now(), run_id))
                continue
        if task["stage"] == "S2" and page is None and not mock and not cache_only:
            # A supervised browser session is only opened when S2 starts.
            playwright, page = _browser_page("http://127.0.0.1:9333")
        db.mark_task_running(conn, task["task_id"])
        task_started = time.monotonic()
        try:
            stage, creator_id = task["stage"], task["key"]
            if stage == "S0":
                candidates = _rank_candidates(client, limit, brief)
                def write(c):
                    for row in candidates:
                        candidate_id = str(row.get("creator_id", ""))
                        if not candidate_id or candidate_id in skip: continue
                        db.upsert_creator(c, candidate_id, row.get("creator_handle") or row.get("creator_nickname"), row)
                        db.add_task(c, run_id, "S1a", candidate_id)
            elif stage == "S1a": write = lambda c: _s1a(c, run_id, creator_id)
            elif stage == "S1b": write = _s1(conn, run_id, client, creator_id)
            elif stage == "S2":
                if mock:
                    text = "Female\n70%\nAge\n18-24\n30%\n25-34\n40%\nTop 5 Locations"
                    metrics = parse_audience_text(text); source = f"https://www.kalodata.com/creator/detail?id={creator_id}"
                    write = _s2_write(run_id, creator_id, metrics, source, brief)
                else:
                    existing = conn.execute(
                        "SELECT name,value FROM metrics WHERE creator_id=? AND name IN ('female_pct','age_18_24_pct','age_25_34_pct')",
                        (creator_id,),
                    ).fetchall()
                    if existing:
                        metrics = {row["name"]: json.loads(row["value"]) for row in existing}
                        source = f"https://www.kalodata.com/creator/detail?id={creator_id}"
                        empty = all(metrics.get(name) is None for name in ("female_pct", "age_18_24_pct", "age_25_34_pct"))
                        db.add_api_call(conn, run_id, "ui/creator_detail", db.cache_key("ui/creator_detail", {"creator_id": creator_id}), "capture_empty" if empty else "cached", 0, 0, True)
                        if empty:
                            raise S2CaptureEmpty()
                    elif cache_only:
                        raise CacheOnlyMiss(f"dữ liệu khán giả S2 của {creator_id}")
                    else:
                        counter = getattr(client, "counter", CreditCounter(conn))
                        price = load_config()["kalodata_prices"]["ui_creator_detail_view"]
                        try:
                            call_id = counter.reserve(run_id, "ui/creator_detail", db.cache_key("ui/creator_detail", {"creator_id": creator_id}), price)
                        except CreditCounter.CapExceeded as exc:
                            raise BudgetExceeded(str(exc)) from exc
                        metrics, source, previous = capture_audience(page, creator_id, previous, raw_path=_s2_raw_path(creator_id))
                        if metrics["female_pct"] is None and metrics["age_18_24_pct"] is None and metrics["age_25_34_pct"] is None:
                            db.finalize_api_call(conn, call_id, "capture_empty", 0, billed=True)
                            raise S2CaptureEmpty()
                        db.finalize_api_call(conn, call_id, "200", 0, billed=True)
                    write = _s2_write(run_id, creator_id, metrics, source, brief)
            elif stage == "S3": write = _s3_creator(conn, run_id, client, creator_id, mock, media_dir, cache_only)
            elif stage == "S4": write = _s4(conn, run_id, mock, cache_only)
            else: raise RuntimeError(f"Giai đoạn không hợp lệ: {stage}")
            db.complete_task(conn, task["task_id"], write)
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
        except BudgetExceeded as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            reason = str(exc)
            db.block_task(conn, task["task_id"], reason)
            remaining = conn.execute("SELECT task_id FROM tasks WHERE run_id=? AND stage IN ('S3','S4') AND status='pending'", (run_id,)).fetchall()
            with db.transaction(conn):
                for row in remaining:
                    db.block_task(conn, row[0], reason)
            break
        except CacheOnlyMiss as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            db.block_task(conn, task["task_id"], f"blocked: {exc}")
            break
        except ProviderAccountError:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            reason = "blocked: tài khoản LLM (nạp tiền/khóa API)"
            with db.transaction(conn):
                conn.execute("UPDATE tasks SET status='pending',error=?,updated_at=? WHERE task_id=?", (reason, db.now(), task["task_id"]))
            break
        except S3AnalysisError as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            db.fail_task(conn, task["task_id"], f"{type(exc.__cause__).__name__}: {exc}"[:500])
        except S2CaptureEmpty as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            db.block_task(conn, task["task_id"], str(exc))
            break
        except KalodataNotReady:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            db.block_task(conn, task["task_id"], "blocked: video Kalodata chưa sẵn sàng")
        except KalodataRateLimited as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            reason = f"blocked: {exc}"
            db.block_task(conn, task["task_id"], reason)
            remaining = conn.execute("SELECT task_id FROM tasks WHERE run_id=? AND stage=? AND status='pending'", (run_id, task["stage"])).fetchall()
            with db.transaction(conn):
                for row in remaining:
                    db.block_task(conn, row[0], reason)
            break
        except PermissionError as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            db.fail_task(conn, task["task_id"], f"blocked: {exc}")
            remaining = conn.execute("SELECT task_id FROM tasks WHERE run_id=? AND stage='S2' AND status='pending'", (run_id,)).fetchall()
            with db.transaction(conn):
                for row in remaining:
                    conn.execute("UPDATE tasks SET status='failed',error='blocked: giới hạn truy cập',updated_at=? WHERE task_id=?", (db.now(), row[0]))
        except Exception as exc:
            _record_stage_time(conn, run_id, task["stage"], int((time.monotonic() - task_started) * 1000))
            db.fail_task(conn, task["task_id"], str(exc))
            db.finish_run(conn, run_id, "failed")
            if playwright: playwright.stop()
            raise
    if playwright: playwright.stop()
    pending = conn.execute("SELECT 1 FROM tasks WHERE run_id=? AND status='pending' LIMIT 1", (run_id,)).fetchone()
    blocked = conn.execute("SELECT 1 FROM tasks WHERE run_id=? AND stage!='S3' AND (status='blocked' OR error LIKE 'blocked:%') LIMIT 1", (run_id,)).fetchone()
    content_scores = conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL", (run_id,)).fetchone()[0] - len(excluded_brand_fit(conn, run_id))
    required = brief["count"]
    s4_done = conn.execute("SELECT 1 FROM tasks WHERE run_id=? AND stage='S4' AND status='done' LIMIT 1", (run_id,)).fetchone()
    db.finish_run(conn, run_id, "blocked" if blocked or content_scores < required or not s4_done else "done")
    return s1_shortlist(conn, run_id)


def start(conn, limit: int = 200, db_path=None, *, mock=False, page=None, cache_only=False, brief=None, exclude_run_ids=None):
    config = load_config()
    brief = brief or make_brief(config)
    if error := check_brief(brief, config):
        raise RuntimeError(error)
    exclude = run_exclusions(conn, exclude_run_ids) if exclude_run_ids else None  # fails before any spend
    run_id = db.create_run(conn, {"limit": limit, "mock": mock, "brief": brief, **({"exclude": exclude} if exclude else {}), **({"cache_only": True} if cache_only else {})})
    db.add_task(conn, run_id, "S0", "candidates")
    client = MockKalodataClient(conn, run_id, cache_only=cache_only) if mock else KalodataClient(conn, run_id=run_id, cache_only=cache_only)
    execute(conn, run_id, client, limit, mock=mock, page=page, cache_only=cache_only)
    return run_id


class MockKalodataClient:
    def __init__(self, conn, run_id, cache_only=False):
        self.conn, self.run_id, self.cache_only = conn, run_id, cache_only
        probe_path = Path(__file__).resolve().parents[2] / "reports/api_probe_2026-11-15.json"
        probe = json.loads(probe_path.read_text())
        self.creator_fixture = next(item["body"]["data"] for item in probe if item.get("need_extra") is True)
    def _record(self, endpoint, body, data):
        key = db.cache_key(endpoint, body)
        cached = db.http_cache_get(self.conn, key)
        if cached is not None:
            db.add_api_call(self.conn, self.run_id, endpoint, key, "200", 0, 0, True)
            return cached
        if self.cache_only:
            raise CacheOnlyMiss(f"Kalodata {endpoint} (mô phỏng)")
        db.http_cache_put(self.conn, key, endpoint, data)
        db.add_api_call(self.conn, self.run_id, endpoint, key, "200", 0, 0, False)
        return data
    def creator_rank(self, **kwargs):
        sample = self.creator_fixture
        rows = [{"creator_id": str(i), "creator_handle": f"koc{i}", "creator_followers": 30000,
                 "revenue": sample["revenue"], "revenue_growth_rate": 20, "video_revenue": sample["video_revenue"],
                 "live_revenue": sample["live_revenue"], "category_list": ["Beauty"]}
                for i in range(1, min(kwargs["page_size"], 50) + 1)]
        return self._record("creator/rank", kwargs, {"data": rows})
    def creator_detail(self, creator_id, **kwargs):
        # Fake identity per creator: the fixture is one real creator, so its handle, name and bio are not reused.
        sample = {**self.creator_fixture, "creator_id": creator_id, "creator_followers": "30000",
                  "creator_handle": f"koc{creator_id}", "creator_nickname": f"KOC mẫu {creator_id}", "creator_bio": ""}
        return self._record("creator/detail", {"creator_id": creator_id, **kwargs}, {"data": sample})
    def video_rank(self, creator_id, page_size=10, **kwargs):
        return self._record("video/rank", {"creator_id": creator_id, "page_size": page_size, **kwargs}, {"data": [{"video_id": f"{creator_id}-{i}", "revenue": 1000000-i, "views": 10000,
                           "digg_count": 500, "comment_count": 10, "share_count": 5, "video_title": "Kem chống nắng"} for i in range(min(page_size, 3))]})
    def video_url(self, video_id): return self._record("video/url", {"video_id": video_id}, {"data": {"video_url": "mock://video"}})


def resume(conn, limit: int | None = None, *, mock=None, page=None, cache_only=None, retry_failed=False, brief=None):
    run = db.run_latest(conn)
    if run is None: raise ValueError("Chưa có lượt chạy để tiếp tục.")
    stored_mock = bool(json.loads(run["params_json"]).get("mock", False))
    if mock is not None and bool(mock) != stored_mock:
        stored = "mô phỏng (mock)" if stored_mock else "chạy thật (live)"
        raise RuntimeError(f"Không thể đổi chế độ khi tiếp tục lượt chạy: lượt chạy {run['run_id']} được tạo ở chế độ {stored}. Hãy bắt đầu lượt chạy mới.")
    stored_brief = run_brief(conn, run["run_id"], load_config())
    changed = [name for name, value in (brief or {}).items() if value is not None and stored_brief.get(name) != value]
    if changed:
        raise RuntimeError(f"Không thể đổi brief khi tiếp tục lượt chạy: lượt chạy {run['run_id']} đã lưu brief khác ở {', '.join(changed)}. Hãy bắt đầu lượt chạy mới.")
    if run["status"] == "done":
        # A finished run is never resumed implicitly: retrying excluded S3 creators repeats paid calls.
        if not retry_failed:
            return run["run_id"]
        # Explicit retry: S3 inputs change, so the S4 selection and its outputs are invalidated (re-select).
        with db.transaction(conn):
            conn.execute("DELETE FROM recommendations WHERE run_id=?", (run["run_id"],))
            conn.execute("DELETE FROM run_results WHERE run_id=? AND kind='reasons'", (run["run_id"],))
            conn.execute("DELETE FROM scores WHERE run_id=? AND stage='S4'", (run["run_id"],))
            conn.execute("UPDATE tasks SET status='pending',error=NULL,updated_at=? WHERE run_id=? AND stage='S4'", (db.now(), run["run_id"]))
    params = json.loads(run["params_json"])
    limit = limit or params.get("limit", 200)
    with db.transaction(conn):
        conn.execute("UPDATE tasks SET status='pending',error=NULL,updated_at=? WHERE run_id=? AND (status='blocked' OR error LIKE 'blocked:%')", (db.now(), run["run_id"]))
        conn.execute("UPDATE tasks SET status='pending',error=NULL,updated_at=? WHERE run_id=? AND status='failed'", (db.now(), run["run_id"]))
    is_mock = params.get("mock", False) if mock is None else mock
    only = params.get("cache_only", False) if cache_only is None else cache_only
    client = MockKalodataClient(conn, run["run_id"], only) if is_mock else KalodataClient(conn, run_id=run["run_id"], cache_only=only)
    execute(conn, run["run_id"], client, limit, page=page, mock=is_mock, cache_only=only)
    return run["run_id"]


def leftover_line(conn, run_id):
    """Budget summary once S4 has picked KOCs; leftover budget stays unused."""
    row = conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    s4 = json.loads(row[0]).get("s4") if row else None
    if not s4:
        return None
    return f"Tổng phí ước tính {vnd(s4['total_vnd'])} VND trên ngân sách {vnd(s4['budget_vnd'])} VND; còn dư {vnd(s4['leftover_vnd'])} VND, không dùng."
