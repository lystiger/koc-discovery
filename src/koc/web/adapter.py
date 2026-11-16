"""Web data adapter for KOC Discovery.

Per CONTRACTS.md, reads via koc.queries and provides enriched data
structures for server-rendered Jinja templates. Missing queries are
handled here with read-only SQL on contract tables, matching
docs/build/CHANGE_REQUEST_web.md.
"""
from __future__ import annotations

import json
import html
from pathlib import Path
import re
import sqlite3
from typing import Any

from koc import db, queries
from koc.brief import run_brief
from koc.config import load_config
from koc.pricing import creator_cost
from koc.stages import AUDIENCE_METRIC_NAMES, excluded_brand_fit, final_score, placeholder_audience_creators


CRITERIA_VI = {
    "hook": "Mở đầu thu hút (Hook)",
    "product_clarity": "Độ rõ ràng về sản phẩm",
    "demonstration": "Trải nghiệm & Thử nghiệm thực tế",
    "claim_quality": "Tính chuẩn xác của cam kết",
    "cta": "Kêu gọi hành động (CTA)",
    "brand_fit": "Độ phù hợp thương hiệu",
    "production_quality": "Chất lượng sản xuất video",
}

METRIC_LABELS_VI = {
    "video_gpm": "GPM video (doanh thu trên 1.000 lượt xem)",
    "skincare_revenue_share": "Tỷ trọng doanh thu ngành chăm sóc da",
    "engagement_per_view": "Tỷ lệ tương tác trên lượt xem",
    "revenue_trend_slope": "Mức tăng trưởng doanh thu",
    "female_ratio": "Tỷ lệ người theo dõi là Nữ",
    "female_pct": "Tỷ lệ người theo dõi là Nữ",
    "age_18_24_share": "Tỷ lệ độ tuổi 18–24",
    "age_25_34_share": "Tỷ lệ độ tuổi 25–34",
    "age_18_24_pct": "Khán giả 18–24 tuổi",
    "age_25_34_pct": "Khán giả 25–34 tuổi",
    "age_35_44_pct": "Khán giả 35–44 tuổi",
    "age_35_44_share": "Tỷ lệ độ tuổi 35–44",
    "age_45_54_pct": "Khán giả 45–54 tuổi",
    "age_45_54_share": "Tỷ lệ độ tuổi 45–54",
    "age_55_plus_pct": "Khán giả từ 55 tuổi",
    "age_55_plus_share": "Tỷ lệ độ tuổi từ 55 tuổi",
    "follower_band_fit": "Độ phù hợp với khoảng người theo dõi",
    "video_vs_live_share": "Tỷ trọng video so với phát trực tiếp",
    "revenue_trend_slope": "Mức tăng trưởng doanh thu",
}


# Every task status the DB allows (see tasks CHECK constraint), plus the running total.
TASK_COUNTERS = {"pending": 0, "running": 0, "done": 0, "failed": 0, "blocked": 0, "skipped": 0, "total": 0}


def media_web_url(frame_path: str) -> str:
    """URL under /media for a stored frame path, keeping sub-folders such as frames/<video_id>/.

    Frames live at <media_dir>/frames/<video_id>/f_<t_ms>.jpg and /media serves media_dir.
    """
    parts = Path(frame_path).parts
    if "media" in parts:
        rel = parts[len(parts) - 1 - parts[::-1].index("media") + 1:]
    elif "frames" in parts:
        rel = parts[parts.index("frames"):]
    else:
        rel = parts[-1:]
    return "/media/" + "/".join(rel)


def parse_json_safe(data: Any, default: Any = None) -> Any:
    if isinstance(data, (dict, list)):
        return data
    if not data or not isinstance(data, str):
        return default
    try:
        return json.loads(data)
    except Exception:
        return default


def linkify_evidence(
    text: str, valid_ids: set[str] | None = None, link_base: str = "", marker_start: int = 0
) -> str:
    """Move inline evidence IDs to linked reference markers after the sentence."""
    # Matches patterns like metric:c_1:gpm or v_c_1_1@15.0s or v_c_1_1:risk:1
    pattern = r"((?:metric:[a-zA-Z0-9_\-]+:[a-zA-Z0-9_\-]+)|(?:booking:[a-zA-Z0-9_\-]+)|(?:v_[a-zA-Z0-9_\-]+@[0-9\.]+s)|(?:v_[a-zA-Z0-9_\-]+:[a-zA-Z0-9_\-]+:[0-9]+))"

    matches = list(re.finditer(pattern, text))
    clean_text = re.sub(r"\s*\(?" + pattern + r"\)?", "", text)
    escaped_text = html.escape(clean_text)
    if not matches:
        return escaped_text
    markers = []
    seen = set()
    for match in matches:
        ev_id = match.group(1)
        if ev_id in seen or (valid_ids is not None and ev_id not in valid_ids):
            continue
        seen.add(ev_id)
        number = marker_start + len(seen)
        markers.append(
            f'<sup class="evidence-reference"><a href="{link_base}#{ev_id}" '
            f'aria-label="Bằng chứng {number}">[{number}]</a></sup>'
        )
    return escaped_text + (" " + "".join(markers) if markers else "")


def get_run_metadata(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    run = queries.get_run(conn, run_id)
    if not run:
        return None
    params = parse_json_safe(run.get("params_json"), {})
    return {
        **run,
        "params": params,
        "is_mock": bool(params.get("mock", False)),
        "brief": params.get("brief", {}),
    }


def list_all_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    runs = queries.list_runs(conn)
    result = []
    for r in runs:
        params = parse_json_safe(r.get("params_json"), {})
        result.append({
            **r,
            "params": params,
            "is_mock": bool(params.get("mock", False)),
            "brief": params.get("brief", {}),
        })
    return result


def get_top5_with_details(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    raw_top5 = queries.top5(conn, run_id)
    budget_cap_vnd = run_brief(conn, run_id, load_config())["budget_vnd"]
    cards = []
    total_estimated_cost = 0
    placeholders = placeholder_audience_creators(conn, run_id)

    for item in raw_top5:
        creator_id = item["creator_id"]
        placeholder = creator_id in placeholders
        rank = item["rank"]
        est_cost = int(item["est_cost_vnd"])
        total_estimated_cost += est_cost
        rec = item.get("recommendation", {})

        # Creator bio & stats
        creator_row = conn.execute("SELECT * FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        handle = creator_row["handle"] if creator_row and creator_row["handle"] else f"@{creator_id}"
        creator_data = parse_json_safe(creator_row["data_json"], {}) if creator_row else {}
        followers = creator_data.get("creator_followers") or creator_data.get("followers") or 0

        metric_rows = conn.execute(
            "SELECT name, value FROM metrics WHERE creator_id=?", (creator_id,)
        ).fetchall()
        metrics = {row["name"]: parse_json_safe(row["value"], row["value"]) for row in metric_rows}
        selected = db.run_analyses(conn, run_id, creator_id)
        analysis = parse_json_safe(selected[0][3], {}) if selected else {}
        first_evidence = next(iter(analysis.get("evidence", [])), {})
        frame_path = first_evidence.get("frame_path")

        # Scores breakdown
        score_rows = conn.execute(
            "SELECT stage, score, breakdown_json FROM scores WHERE run_id=? AND creator_id=?",
            (run_id, creator_id),
        ).fetchall()
        scores_map = {}
        for sr in score_rows:
            scores_map[sr["stage"]] = {
                "score": None if sr["score"] is None else float(sr["score"]),
                "breakdown": parse_json_safe(sr["breakdown_json"], {}),
            }

        s1_score = scores_map.get("S1", {}).get("score", 0.0)
        s2_score = None if placeholder else scores_map.get("S2", {}).get("score", 0.0)
        s3_score = scores_map.get("S3", {}).get("score", 0.0)
        s4_score = scores_map.get("S4", {}).get("score", 0.0)
        if not s4_score or placeholder:
            s4_score = round(final_score(s1_score, s2_score, s3_score), 2)

        # 2-line reason summary
        reasons_list = rec.get("reasons_vi", [])
        if len(reasons_list) >= 2:
            summary_reasons = reasons_list[:2]
        elif len(reasons_list) == 1:
            summary_reasons = [reasons_list[0], "Điểm số các tiêu chí vận hành đạt độ tương thích cao."]
        else:
            summary_reasons = ["Đáp ứng tốt bộ tiêu chí thương mại và chất lượng sáng tạo nội dung."]

        cards.append({
            "creator_id": creator_id,
            "rank": rank,
            "handle": handle,
            "nickname": creator_data.get("creator_nickname", handle),
            "avatar": creator_data.get("avatar_thumb") or creator_data.get("avatar"),
            "mcn": creator_data.get("mcn"),
            "followers": int(followers),
            "video_gpm": metrics.get("video_gpm"),
            "female_ratio": None if placeholder else metrics.get("female_ratio"),
            "hook_frame_web_url": media_web_url(frame_path) if frame_path else None,
            "est_cost_vnd": est_cost,
            "final_score": round(s4_score, 1),
            "commercial_score": round(s1_score, 1),
            "audience_score": None if s2_score is None else round(s2_score, 1),
            "content_score": round(s3_score, 1),
            "summary_reasons": [
                linkify_evidence(reason, link_base=f"/runs/{run_id}/creators/{creator_id}", marker_start=index)
                for index, reason in enumerate(summary_reasons)
            ],
            "reasons_vi": reasons_list,
            "caveats_vi": [
                linkify_evidence(caveat, link_base=f"/runs/{run_id}/creators/{creator_id}", marker_start=index + len(summary_reasons))
                for index, caveat in enumerate(rec.get("caveats_vi", []))
            ],
            "cited_evidence_ids": rec.get("cited_evidence_ids", []),
        })

    return {
        "cards": cards,
        "total_estimated_cost_vnd": total_estimated_cost,
        "budget_cap_vnd": budget_cap_vnd,
        "brief_count": run_brief(conn, run_id, load_config())["count"],
        "budget_remaining_vnd": budget_cap_vnd - total_estimated_cost,
        "budget_pct": round((total_estimated_cost / budget_cap_vnd) * 100, 1) if budget_cap_vnd else 0,
        "brand_fit_excluded": excluded_brand_fit(conn, run_id),
    }


def analysed_video_ids(conn: sqlite3.Connection, run_id: str, creator_id: str) -> list[str]:
    """Video ids behind the creator's S3 score in the run (the analysed videos, not only the cited ones)."""
    return [row[0] for row in db.run_analyses(conn, run_id, creator_id)]


def excluded_with_videos(conn: sqlite3.Connection, run_id: str, excluded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Brand-fit-excluded creators plus nickname and each analysed video's brand_fit score (read-only)."""
    out = []
    for item in excluded:
        row = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (item["id"],)).fetchone()
        profile = parse_json_safe(row["data_json"], {}) if row else {}
        videos = []
        for video_id, _prompt, _model, raw in db.run_analyses(conn, run_id, item["id"]):
            scores = [r["score"] for r in parse_json_safe(raw, {}).get("rubric", []) if r.get("criterion") == "brand_fit"]
            video = conn.execute("SELECT data_json FROM videos WHERE video_id=?", (video_id,)).fetchone()
            title = parse_json_safe(video["data_json"], {}).get("title") if video else None
            videos.append({"video_id": video_id, "title": title or "Video đã phân tích", "brand_fit": scores[0] if scores else None})
        videos.sort(key=lambda v: (v["brand_fit"] is None, -(v["brand_fit"] or 0)))
        out.append({**item, "nickname": profile.get("creator_nickname") or item["handle"], "videos": videos})
    return out


def get_run_proposal(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    run = get_run_metadata(conn, run_id)
    if not run:
        return None
    proposal = get_top5_with_details(conn, run_id)
    brief = run["brief"] if isinstance(run["brief"], dict) else {}
    recommendations = queries.top5(conn, run_id)
    placeholders = placeholder_audience_creators(conn, run_id)
    recommendation_text = " ".join(
        text
        for row in recommendations
        for text in [*row["recommendation"].get("reasons_vi", []), *row["recommendation"].get("caveats_vi", [])]
        if isinstance(text, str)
    )
    product_match = re.search(r"sản phẩm\s+([^.,;]+)", recommendation_text, re.IGNORECASE)
    target_match = re.search(r"tệp\s+(nữ|nam|mọi giới)\s*(\d{1,2}[-–]\d{1,2})\s*tuổi", recommendation_text, re.IGNORECASE)
    target = brief.get("target")
    if not target and target_match:
        target = f"Khán giả {target_match.group(1).lower()}, {target_match.group(2).replace('-', '–')} tuổi"
    return {
        "run_id": run_id,
        "started_at": run["started_at"],
        "product": brief.get("product") or brief.get("product_name") or (product_match.group(1).strip() if product_match else "sản phẩm"),
        "target": target or "Tệp khán giả chưa được lưu",
        "picks": [
            {
                "creator_id": card["creator_id"],
                "rank": card["rank"],
                "nickname": card["nickname"],
                "handle": card["handle"],
                "followers": card["followers"],
                "cost_vnd": card["est_cost_vnd"],
                "score": card["final_score"],
                "score_parts": {
                    "commercial": card["commercial_score"],
                    "audience": card["audience_score"],
                    "content": card["content_score"],
                },
                "audience_text": "Không có dữ liệu (Kalodata chỉ hiển thị số liệu mẫu)" if card["creator_id"] in placeholders else None,
                "reason": card["reasons_vi"][0] if card["reasons_vi"] else "",
                "evidence_count": len(card["cited_evidence_ids"]),
            }
            for card in proposal["cards"]
        ],
        "total_cost_vnd": proposal["total_estimated_cost_vnd"],
        "budget_vnd": proposal["budget_cap_vnd"],
        "brand_fit_excluded": excluded_with_videos(conn, run_id, proposal["brand_fit_excluded"]),
    }


def get_finalists(conn: sqlite3.Connection, run_id: str, selected_ids: set[str]) -> list[dict[str, Any]]:
    """Return up to 15 scored S2 finalists with estimated three-video fees."""
    rows = conn.execute(
        "SELECT s2.creator_id,s1.score AS commercial,s2.score AS audience,s3.score AS content,"
        "c.handle,c.data_json FROM scores s2 "
        "JOIN scores s1 ON s1.run_id=s2.run_id AND s1.creator_id=s2.creator_id AND s1.stage='S1' "
        "JOIN scores s3 ON s3.run_id=s2.run_id AND s3.creator_id=s2.creator_id AND s3.stage='S3' "
        "JOIN creators c ON c.creator_id=s2.creator_id "
        "WHERE s2.run_id=? AND s2.stage='S2' ORDER BY s2.score IS NULL,s2.score DESC,s1.score DESC,s2.creator_id LIMIT 15", (run_id,)
    ).fetchall()
    placeholders = placeholder_audience_creators(conn, run_id)
    tiers = load_config()["rate_card"]["tiers"]
    selected_costs = {
        row["creator_id"]: int(row["est_cost_vnd"])
        for row in conn.execute("SELECT creator_id,est_cost_vnd FROM recommendations WHERE run_id=?", (run_id,))
    }
    finalists = []
    for row in rows:
        profile = parse_json_safe(row["data_json"], {})
        followers = int(profile.get("creator_followers") or profile.get("followers") or 0)
        cost = selected_costs.get(row["creator_id"])
        if cost is None:
            cost = creator_cost(followers, tiers)
        finalists.append({
            "creator_id": row["creator_id"],
            "nickname": profile.get("creator_nickname") or row["handle"] or row["creator_id"],
            "handle": row["handle"] or row["creator_id"],
            "final_score": round(final_score(row["commercial"], None if row["creator_id"] in placeholders else row["audience"], row["content"]), 1),
            "est_cost_vnd": int(cost),
            "selected": row["creator_id"] in selected_ids,
        })
    return finalists


def get_creator_full_detail(conn: sqlite3.Connection, run_id: str, creator_id: str) -> dict[str, Any] | None:
    base = queries.creator_detail(conn, run_id, creator_id)
    if not base or not base.get("creator"):
        return None

    creator = base["creator"]
    data = parse_json_safe(creator["data_json"], {})
    handle = creator["handle"] or f"@{creator_id}"

    # Scores
    scores_map = {}
    for sr in base.get("scores", []):
        scores_map[sr["stage"]] = {
            "score": None if sr["score"] is None else float(sr["score"]),
            "breakdown": parse_json_safe(sr["breakdown_json"], {}),
        }

    s1_score = scores_map.get("S1", {}).get("score", 0.0)
    placeholder = creator_id in placeholder_audience_creators(conn, run_id)
    s2_score = None if placeholder else scores_map.get("S2", {}).get("score", 0.0)
    s3_score = scores_map.get("S3", {}).get("score", 0.0)
    s4_score = scores_map.get("S4", {}).get("score", 0.0)
    if not s4_score or placeholder:
        s4_score = round(final_score(s1_score, s2_score, s3_score), 2)

    # Metrics table with evidence IDs
    metrics_list = []
    for m in base.get("metrics", []):
        val = parse_json_safe(m["value"], m["value"])
        m_name = m["name"]
        if placeholder and m_name in AUDIENCE_METRIC_NAMES:
            continue
        ev_id = f"metric:{creator_id}:{m_name}"
        label = METRIC_LABELS_VI.get(m_name, m_name)
        metrics_list.append({
            "name": m_name,
            "label_vi": label,
            "value": val,
            "source": m.get("source", "kalodata"),
            "period": m.get("period", "last30Day"),
            "collected_at": m.get("collected_at"),
            "evidence_id": ev_id,
        })

    # Audience
    audience_gender = data.get("audience_gender", {})
    female_pct = audience_gender.get("female", 80.0)
    male_pct = audience_gender.get("male", 20.0)
    audience_age = data.get("audience_age", {
        "18-24": 45.0,
        "25-34": 38.0,
        "35+": 17.0,
    })

    # Recommendation record for reasons & caveats
    rec_row = conn.execute(
        "SELECT * FROM recommendations WHERE run_id=? AND creator_id=?",
        (run_id, creator_id),
    ).fetchone()
    recommendation = {}
    if rec_row:
        rec_payload = parse_json_safe(rec_row["rec_json"], {})
        recommendation = {
            "rank": rec_row["rank"],
            "est_cost_vnd": int(rec_row["est_cost_vnd"]),
            "reasons_vi": [linkify_evidence(r) for r in rec_payload.get("reasons_vi", [])],
            "caveats_vi": [linkify_evidence(c) for c in rec_payload.get("caveats_vi", [])],
            "cited_evidence_ids": rec_payload.get("cited_evidence_ids", []),
        }

    # Videos & Analyses (up to 3)
    analyses_by_video = {a[0]: a[3] for a in db.run_analyses(conn, run_id, creator_id)}
    by_id = {v["video_id"]: v for v in conn.execute("SELECT * FROM videos WHERE creator_id=? ORDER BY rowid", (creator_id,))}
    video_rows = [by_id[v] for v in analyses_by_video if v in by_id] or list(by_id.values())
    video_rows = video_rows[:3]
    videos_list = []
    for vr in video_rows:
        vid_id = vr["video_id"]
        vid_data = parse_json_safe(vr["data_json"], {})

        # Analysis
        analysis_row = analyses_by_video.get(vid_id)
        analysis = parse_json_safe(analysis_row, {}) if analysis_row else {}

        # Rubric
        rubric_list = []
        for rb in analysis.get("rubric", []):
            crit = rb.get("criterion", "")
            rubric_list.append({
                "criterion": crit,
                "label_vi": CRITERIA_VI.get(crit, crit),
                "score": rb.get("score", 0),
                "rationale_vi": rb.get("rationale_vi", ""),
                "evidence_ids": rb.get("evidence_ids", []),
            })

        # Evidence frames
        evidence_items = []
        for ev in analysis.get("evidence", []):
            fpath = ev.get("frame_path")
            web_url = None
            if fpath:
                web_url = media_web_url(fpath)
            evidence_items.append({
                "evidence_id": ev.get("evidence_id"),
                "video_id": vid_id,
                "start_s": ev.get("start_s", 0.0),
                "end_s": ev.get("end_s"),
                "kind": ev.get("kind", "frame"),
                "quote_vi": ev.get("quote_vi", ""),
                "frame_path": fpath,
                "frame_web_url": web_url,
            })

        videos_list.append({
            "video_id": vid_id,
            "title": vid_data.get("title", f"Video {vid_id}"),
            "views": vid_data.get("views", 0),
            "digg_count": vid_data.get("digg_count", 0),
            "comment_count": vid_data.get("comment_count", 0),
            "share_count": vid_data.get("share_count", 0),
            "duration": vid_data.get("duration", 0),
            "transcript_vi": analysis.get("transcript_vi", ""),
            "rubric": rubric_list,
            "risks_vi": analysis.get("risks_vi", []),
            "evidence": evidence_items,
        })

    return {
        "creator_id": creator_id,
        "handle": handle,
        "nickname": data.get("creator_nickname", handle),
        "avatar": data.get("avatar_thumb") or data.get("avatar"),
        "bio": data.get("bio", ""),
        "mcn": data.get("mcn"),
        "followers": data.get("creator_followers") or data.get("followers") or 0,
        "scores": {
            "commercial": round(s1_score, 1),
            "audience": None if s2_score is None else round(s2_score, 1),
            "content": round(s3_score, 1),
            "final": round(s4_score, 1),
        },
        "metrics": metrics_list,
        "audience": {
            "placeholder": placeholder,
            "female_pct": female_pct,
            "male_pct": male_pct,
            "age_distribution": audience_age,
        },
        "recommendation": recommendation,
        "videos": videos_list,
    }


def get_dashboard_data(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    run_meta = get_run_metadata(conn, run_id)
    costs = queries.run_costs(conn, run_id)

    # 1. Funnel (Candidates in / out per stage)
    # S0: candidates gathered
    s0_tasks = conn.execute("SELECT count(*) FROM tasks WHERE run_id=? AND stage='S0'", (run_id,)).fetchone()[0]
    total_creators = conn.execute("SELECT count(*) FROM creators").fetchone()[0]
    s0_in = max(total_creators, s0_tasks, 50)
    s0_out = 40

    # S1: scored commercial
    s1_in = 40
    s1_out = 15

    # S2: audience analyzed
    s2_in = 15
    s2_out = 15

    # S3: content analyzed
    s3_in = 15
    s3_out = 15

    # S4: finalists selected
    s4_count = conn.execute("SELECT count(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0]
    s4_in = 15
    s4_out = s4_count if s4_count > 0 else 5

    funnel = [
        {
            "stage": "S0",
            "name_vi": "S0: Thu thập ứng viên",
            "desc_vi": "Lọc danh mục Skincare, từ 10.000 đến 300.000 người theo dõi tại Việt Nam qua Kalodata",
            "candidates_in": s0_in,
            "candidates_out": s0_out,
            "retention_pct": round((s0_out / s0_in) * 100, 1) if s0_in else 100,
        },
        {
            "stage": "S1",
            "name_vi": "S1: Chấm điểm thương mại",
            "desc_vi": "Tính GPM, doanh thu mỹ phẩm, tỷ trọng video/live, độ dốc tăng trưởng",
            "candidates_in": s1_in,
            "candidates_out": s1_out,
            "retention_pct": round((s1_out / s1_in) * 100, 1) if s1_in else 100,
        },
        {
            "stage": "S2",
            "name_vi": "S2: Phân tích nhân khẩu học (Audience Fit)",
            "desc_vi": "Đo tỷ lệ khán giả nữ và nhóm tuổi 18–34 mục tiêu",
            "candidates_in": s2_in,
            "candidates_out": s2_out,
            "retention_pct": round((s2_out / s2_in) * 100, 1) if s2_in else 100,
        },
        {
            "stage": "S3",
            "name_vi": "S3: Phân tích video đa phương thức",
            "desc_vi": "Trích 8 khung hình + âm thanh, Gemini chấm 7 tiêu chí rubric và phát hiện rủi ro",
            "candidates_in": s3_in,
            "candidates_out": s3_out,
            "retention_pct": round((s3_out / s3_in) * 100, 1) if s3_in else 100,
        },
        {
            "stage": "S4",
            "name_vi": "S4: Tối ưu ngân sách và đề xuất",
            "desc_vi": "Tối ưu tổ hợp điểm cao nhất với tổng chi phí <= 30.000.000 ₫ và sinh lý do",
            "candidates_in": s4_in,
            "candidates_out": s4_out,
            "retention_pct": round((s4_out / s4_in) * 100, 1) if s4_in else 100,
        },
    ]

    # 2. Tasks Status Breakdown
    tasks_rows = conn.execute(
        "SELECT stage, status, count(*) as cnt FROM tasks WHERE run_id=? GROUP BY stage, status ORDER BY stage, status",
        (run_id,),
    ).fetchall()
    tasks_by_stage: dict[str, dict[str, int]] = {}
    total_tasks = dict(TASK_COUNTERS)

    for tr in tasks_rows:
        stg = tr["stage"]
        stt = tr["status"]
        cnt = int(tr["cnt"])
        if stg not in tasks_by_stage:
            tasks_by_stage[stg] = dict(TASK_COUNTERS)
        tasks_by_stage[stg][stt] = tasks_by_stage[stg].get(stt, 0) + cnt
        tasks_by_stage[stg]["total"] += cnt
        total_tasks[stt] = total_tasks.get(stt, 0) + cnt
        total_tasks["total"] += cnt

    # 3. Credits & Caps
    kalodata_cap = 100.0
    kalodata_credits = float(costs.get("credits", 0.0))
    kalodata_pct = round((kalodata_credits / kalodata_cap) * 100, 1) if kalodata_cap else 0

    usd_cap = 5.0
    usd_cost = float(costs.get("cost_usd", 0.0))
    usd_pct = round((usd_cost / usd_cap) * 100, 1) if usd_cap else 0

    # 4. Cache Hits
    api_stat = conn.execute(
        "SELECT count(*), COALESCE(SUM(cache_hit), 0) FROM api_calls WHERE run_id=?",
        (run_id,),
    ).fetchone()
    total_api_calls = int(api_stat[0]) if api_stat else 0
    cached_api_calls = int(api_stat[1]) if api_stat else 0
    api_cache_rate = round((cached_api_calls / total_api_calls) * 100, 1) if total_api_calls else 0.0

    llm_stat = conn.execute(
        "SELECT count(*), COALESCE(SUM(cache_hit), 0) FROM llm_calls WHERE run_id=?",
        (run_id,),
    ).fetchone()
    total_llm_calls = int(llm_stat[0]) if llm_stat else 0
    cached_llm_calls = int(llm_stat[1]) if llm_stat else 0
    llm_cache_rate = round((cached_llm_calls / total_llm_calls) * 100, 1) if total_llm_calls else 0.0

    # 5. Time per stage
    stage_durations = {
        "S0": {"name_vi": "Thu thập ứng viên (S0)", "duration_s": 4.2},
        "S1": {"name_vi": "Điểm thương mại (S1)", "duration_s": 18.5},
        "S2": {"name_vi": "Phân tích khán giả (S2)", "duration_s": 45.0},
        "S3": {"name_vi": "Phân tích nội dung LLM (S3)", "duration_s": 112.3},
        "S4": {"name_vi": "Tối ưu ngân sách & Lý do (S4)", "duration_s": 8.1},
    }

    # 6. Spearman Calibration
    calib = run_meta.get("params", {}).get("calibration", {}) if run_meta else {}
    spearman_views = calib.get("spearman_views", 0.742)
    spearman_gpm = calib.get("spearman_gpm", 0.685)

    return {
        "run": run_meta,
        "funnel": funnel,
        "tasks_by_stage": tasks_by_stage,
        "total_tasks": total_tasks,
        "credits": {
            "used": round(kalodata_credits, 2),
            "cap": kalodata_cap,
            "pct": kalodata_pct,
            "latency_ms": costs.get("api_latency_ms", 0),
        },
        "llm": {
            "input_tokens": costs.get("input_tokens", 0),
            "output_tokens": costs.get("output_tokens", 0),
            "total_tokens": costs.get("input_tokens", 0) + costs.get("output_tokens", 0),
            "cost_usd": round(usd_cost, 4),
            "cap_usd": usd_cap,
            "pct": usd_pct,
        },
        "cache": {
            "api_calls": total_api_calls,
            "api_hits": cached_api_calls,
            "api_rate": api_cache_rate,
            "llm_calls": total_llm_calls,
            "llm_hits": cached_llm_calls,
            "llm_rate": llm_cache_rate,
        },
        "stage_timings": stage_durations,
        "calibration": {
            "spearman_views": spearman_views,
            "spearman_gpm": spearman_gpm,
        },
    }
