from pathlib import Path
from typing import Annotated, Literal
import re
import sqlite3
import unicodedata

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from koc import db, queries
from koc.web import campaigns
from koc.stages import placeholder_audience_creators
from koc.web.adapter import METRIC_LABELS_VI, analysed_video_ids, legacy_scoring_note, get_run_proposal, media_web_url
from koc.web.matching_api import AUDIENCE_METRIC_NAMES, EVIDENCE_PATTERN, _done_run_ids, _estimated_cost, _evidence_target_exists, _json, _reason, display_reason_text, normalize_result, result_for_campaign


class Target(BaseModel):
    gender: Literal["Nữ", "Nam", "Tất cả"] = "Nữ"
    age_groups: list[Literal["18-24", "25-34", "35-44", "45-54", "55+"]] = Field(default_factory=lambda: ["18-24", "25-34"])

    @field_validator("age_groups")
    @classmethod
    def age_groups_are_contiguous(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Chọn ít nhất một nhóm tuổi.")
        order = {age: index for index, age in enumerate(("18-24", "25-34", "35-44", "45-54", "55+"))}
        indices = [order[age] for age in value]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            raise ValueError("Chọn các nhóm tuổi liền nhau theo thứ tự từ nhỏ đến lớn.")
        return value


class CampaignInput(BaseModel):
    brand_name: str = Field(min_length=1, max_length=80)
    product_type: Literal["Chống nắng", "Dưỡng ẩm", "Serum", "Làm sạch", "Trang điểm", "Khác"]
    product_specs: str = Field(default="", max_length=1000)
    budget_vnd: int = Field(ge=1_000_000, le=10_000_000_000)
    count: int = Field(default=5, ge=1, le=10)
    followers_min: int = Field(default=10_000, ge=0)
    followers_max: int = Field(default=300_000, ge=0)
    target: Target = Field(default_factory=Target)
    avoid_same_mcn: bool = True
    exclude_run_ids: list[Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]] = Field(default_factory=list, max_length=10)

    @field_validator("brand_name")
    @classmethod
    def brand_name_has_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nhập tên thương hiệu.")
        return value


router = APIRouter(prefix="/api")
ROOT = Path(__file__).resolve().parents[3]


@router.get("/stats")
def get_stats(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        latest_s1_run = conn.execute(
            "SELECT s.run_id FROM scores s JOIN runs r USING (run_id) "
            "WHERE s.stage='S1' ORDER BY r.started_at DESC LIMIT 1"
        ).fetchone()
        creators_in_pool = 0
        if latest_s1_run:
            creators_in_pool = conn.execute(
                "SELECT COUNT(DISTINCT creator_id) FROM scores WHERE run_id=? AND stage='S1'",
                (latest_s1_run["run_id"],),
            ).fetchone()[0]
        creators_with_s3_score = conn.execute(
            "SELECT COUNT(DISTINCT creator_id) FROM scores WHERE stage='S3'"
        ).fetchone()[0]
        analyzed_videos = conn.execute(
            "SELECT COUNT(DISTINCT video_id) FROM analyses"
        ).fetchone()[0]
        return {
            "creators_in_pool": creators_in_pool,
            "creators_with_s3_score": creators_with_s3_score,
            "analyzed_videos": analyzed_videos,
        }
    finally:
        conn.close()


def _conn(request: Request):
    conn = db.connect(request.app.state.db_path)
    campaigns.ensure_table(conn)
    return conn


def _rate_tiers():
    with (ROOT / "config/rate_card.yaml").open() as source:
        return yaml.safe_load(source)["tiers"]


def _normalise_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _audience_caveat(text: str) -> bool:
    value = _normalise_text(text)
    return "khán giả" in value and (
        "kalodata" in value or re.search(r"chưa\s+(?:được\s+)?xác minh", value) is not None
    )


def _split_point_evidence(conn, creator_id, text, evidence_ids, run_id=None):
    point_ids = []
    video_ids = []
    normalized = _normalise_text(text)
    for evidence_id in dict.fromkeys(evidence_ids):
        if not isinstance(evidence_id, str) or not _evidence_target_exists(conn, creator_id, evidence_id, run_id):
            continue
        if evidence_id.startswith(f"metric:{creator_id}:"):
            key = evidence_id.rsplit(":", 1)[-1]
            label = METRIC_LABELS_VI.get(key, "")
            if key.casefold() in normalized or (label and _normalise_text(label) in normalized):
                point_ids.append(evidence_id)
        else:
            video_ids.append(evidence_id)
    return point_ids, video_ids


def _format_review(conn, creator_id, texts, cited_ids, run_id=None):
    points = []
    video_ids = []
    for text in texts:
        if not isinstance(text, str):
            continue
        candidates = [*EVIDENCE_PATTERN.findall(text), *(cited_ids if isinstance(cited_ids, list) else [])]
        point_ids, point_video_ids = _split_point_evidence(conn, creator_id, text, candidates, run_id)
        points.append({"text": display_reason_text(text), "evidence_ids": point_ids})
        video_ids.extend(point_video_ids)
    return points, list(dict.fromkeys(video_ids))


def _campaign_review_data(conn, result):
    for creator in [*result.get("result", {}).get("picked", []), *result.get("result", {}).get("alternates", []), *result.get("result", {}).get("ranked_pool", [])]:
        saved_run_id = result.get("result", {}).get("run_id")
        if saved_run_id:  # campaigns saved before analysed_video_ids existed are enriched from their recorded run
            creator["analysed_video_ids"] = analysed_video_ids(conn, saved_run_id, creator["creator_id"])
        score_run = conn.execute(
            "SELECT run_id FROM scores WHERE creator_id=? ORDER BY rowid DESC LIMIT 1",
            (creator["creator_id"],),
        ).fetchone()
        recommendation = conn.execute(
            "SELECT rec_json FROM recommendations WHERE creator_id=? AND run_id=?",
            (creator["creator_id"], score_run["run_id"] if score_run else ""),
        ).fetchone()
        rec = _json(recommendation[0], {}) if recommendation else {}
        creator["scoring_note"] = legacy_scoring_note(conn, saved_run_id or (score_run["run_id"] if score_run else None), creator["creator_id"])
        cited = rec.get("cited_evidence_ids", [])
        creator["reasons"], reason_video_ids = _format_review(conn, creator["creator_id"], rec.get("reasons_vi", []), cited)
        creator["caveats"], caveat_video_ids = _format_review(conn, creator["creator_id"], rec.get("caveats_vi", []), cited)
        creator["video_evidence_ids"] = list(dict.fromkeys([*reason_video_ids, *caveat_video_ids]))
        audience_notes = [item for item in creator["caveats"] if _audience_caveat(item["text"])]
        if audience_notes:
            creator["audience_note"] = audience_notes[0]["text"]
            creator["caveats"] = [item for item in creator["caveats"] if not _audience_caveat(item["text"])]
    return result


def _creator_detail(conn, creator_id: str, run_id: str | None = None):
    creator_row = conn.execute("SELECT * FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
    if not creator_row:
        return None
    data = _json(creator_row["data_json"], {})
    score_run = run_id or (conn.execute(
        "SELECT run_id FROM scores WHERE creator_id=? ORDER BY rowid DESC LIMIT 1", (creator_id,)
    ).fetchone() or {"run_id": None})["run_id"]
    placeholder_audience = bool(score_run and creator_id in placeholder_audience_creators(conn, score_run))
    has_audience_score = bool(score_run and conn.execute(
        "SELECT 1 FROM scores WHERE creator_id=? AND run_id=? AND stage='S2'",
        (creator_id, score_run),
    ).fetchone())
    missing_audience = placeholder_audience or not has_audience_score
    metrics = {
        row["name"]: {
            "value": _json(row["value"], row["value"]),
            "source": row["source"],
        }
        for row in conn.execute("SELECT * FROM metrics WHERE creator_id=? ORDER BY name", (creator_id,))
        if not (missing_audience and row["name"] in AUDIENCE_METRIC_NAMES)
    }
    scores = {
        row["stage"]: float(row["score"])
        for row in conn.execute(
            "SELECT stage,score FROM scores WHERE creator_id=? AND run_id=?",
            (creator_id, score_run),
        )
    }
    if missing_audience:
        scores.pop("S2", None)
    recommendation = conn.execute(
        "SELECT rec_json FROM recommendations WHERE creator_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1",
        (creator_id, score_run),
    ).fetchone() if score_run else None
    rec = _json(recommendation[0], {}) if recommendation else {}
    selected = {a[0]: a[3] for a in db.run_analyses(conn, score_run, creator_id)} if score_run else {}
    videos_by_id = {}
    if selected:
        placeholders = ",".join("?" for _ in selected)
        order = list(selected)
        for video in sorted(conn.execute(f"SELECT * FROM videos WHERE creator_id=? AND video_id IN ({placeholders})", (creator_id, *order)), key=lambda v: order.index(v["video_id"])):
            videos_by_id[video["video_id"]] = video
    else:
        for video in conn.execute("SELECT * FROM videos WHERE creator_id=? ORDER BY rowid LIMIT 5", (creator_id,)):
            videos_by_id[video["video_id"]] = video
    videos = []
    for video in videos_by_id.values():
        payload = _json(video["data_json"], {})
        analysis_row = (selected.get(video["video_id"]),) if selected else conn.execute("SELECT analysis_json FROM analyses WHERE video_id=? ORDER BY rowid DESC LIMIT 1", (video["video_id"],)).fetchone()
        analysis = _json(analysis_row[0], {}) if analysis_row and analysis_row[0] else {}
        evidence = []
        analysis_evidence = analysis.get("evidence", [])
        for item in analysis_evidence:
            frame = item.get("frame_path")
            if not frame:
                nearest = min(
                    (candidate for candidate in analysis_evidence if candidate.get("frame_path")),
                    key=lambda candidate: abs(float(candidate.get("start_s", 0)) - float(item.get("start_s", 0))),
                    default=None,
                )
                if nearest and abs(float(nearest.get("start_s", 0)) - float(item.get("start_s", 0))) <= 3:
                    frame = nearest["frame_path"]
            evidence.append({**item, "frame_url": media_web_url(frame) if frame else None})
        videos.append({
            "video_id": video["video_id"],
            "title": payload.get("title") or "Video đã phân tích",
            "views": payload.get("views"),
            "transcript_vi": analysis.get("transcript_vi"),
            "rubric": [
                {**item, "rationale_vi": display_reason_text(item.get("rationale_vi", ""))}
                for item in analysis.get("rubric", [])
            ],
            "risks_vi": analysis.get("risks_vi", []),
            "evidence": evidence,
        })
    cited_evidence_ids = rec.get("cited_evidence_ids", [])
    reasons, reason_video_ids = _format_review(conn, creator_id, rec.get("reasons_vi", []), cited_evidence_ids, score_run)
    caveats, caveat_video_ids = _format_review(conn, creator_id, rec.get("caveats_vi", []), cited_evidence_ids, score_run)
    audience_notes = [item for item in caveats if _audience_caveat(item["text"])]
    if audience_notes:
        caveats = [item for item in caveats if not _audience_caveat(item["text"])]
    return {
        "creator_id": creator_id,
        "nickname": data.get("creator_nickname") or creator_row["handle"] or creator_id,
        "handle": creator_row["handle"] or f"@{creator_id}",
        "followers": int(data.get("creator_followers") or data.get("followers") or 0),
        "cost_vnd": _estimated_cost(int(data.get("creator_followers") or data.get("followers") or 0), _rate_tiers()),
        "avatar": data.get("avatar_thumb") or data.get("avatar"),
        "bio": data.get("bio", ""),
        "mcn": data.get("mcn"),
        "metrics": metrics,
        "audience_text": "Không có dữ liệu (Kalodata chỉ hiển thị số liệu mẫu)" if placeholder_audience else None,
        "audience_note": audience_notes[0]["text"] if audience_notes else None,
        "scores": scores,
        "scoring_note": legacy_scoring_note(conn, score_run, creator_id),
        "reasons": reasons,
        "caveats": caveats,
        "video_evidence_ids": list(dict.fromkeys([*reason_video_ids, *caveat_video_ids])),
        "videos": videos,
    }


@router.get("/runs/latest")
def get_latest_run(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        row = conn.execute(
            "SELECT r.run_id FROM runs r JOIN recommendations rec USING (run_id) "
            "WHERE json_extract(r.params_json, '$.mock') IS NOT 1 "
            "GROUP BY r.run_id ORDER BY r.started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Chưa có đề xuất mẫu.")
        return {"run_id": row["run_id"]}
    finally:
        conn.close()


@router.get("/runs/previous")
def previous_runs(request: Request, product_type: str = ""):
    """Finished runs of a product type with their final picks (read-only; feeds the form's exclusion checkbox)."""
    path = Path(request.app.state.db_path)
    if not path.exists():
        return []
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)  # read-only: this GET must not create tables or commit
    conn.row_factory = sqlite3.Row
    try:
        result = []
        for run_id in _done_run_ids(conn, product_type):
            if not re.fullmatch(r"[0-9a-f]{32}", run_id):
                continue  # the exclusion request only accepts 32-hex run ids
            ids = [row[0] for row in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=? ORDER BY rank", (run_id,))]
            if ids:
                started = conn.execute("SELECT started_at FROM runs WHERE run_id=?", (run_id,)).fetchone()[0]
                result.append({"run_id": run_id, "started_at": started, "creator_ids": ids})
            if len(result) == 10:
                break
        return result
    finally:
        conn.close()


@router.get("/runs/{run_id}/proposal")
def get_run_proposal_api(run_id: str, request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        proposal = get_run_proposal(conn, run_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
        if not proposal["picks"]:
            raise HTTPException(status_code=404, detail="Lượt chạy chưa có đề xuất.")
        for pick in proposal["picks"]:
            parts = pick["score_parts"]
            pick["analysed_video_ids"] = analysed_video_ids(conn, run_id, pick["creator_id"])
            recommendation = conn.execute(
                "SELECT rec_json FROM recommendations WHERE run_id=? AND creator_id=?",
                (run_id, pick["creator_id"]),
            ).fetchone()
            rec = _json(recommendation[0], {}) if recommendation else {}
            cited_ids = rec.get("cited_evidence_ids", [])
            pick["reasons"], video_ids = _format_review(conn, pick["creator_id"], rec.get("reasons_vi", []), cited_ids, run_id)
            if not pick["reasons"]:
                reason, evidence_ids = _reason(
                    conn,
                    run_id,
                    pick["creator_id"],
                    parts["commercial"] or 0,
                    parts["audience"],
                    parts["content"],
                )
                pick["reasons"], video_ids = _format_review(conn, pick["creator_id"], [reason], evidence_ids, run_id)
                cited_ids = evidence_ids
            pick["scoring_note"] = legacy_scoring_note(conn, run_id, pick["creator_id"])
            pick["reason"] = pick["reasons"][0]["text"]
            pick["evidence_ids"] = list(dict.fromkeys(value for item in pick["reasons"] for value in item["evidence_ids"]))
            caveats = [
                display_reason_text(text)
                for text in rec.get("caveats_vi", [])
                if isinstance(text, str)
            ]
            caveat_evidence, caveat_video_ids = _format_review(conn, pick["creator_id"], rec.get("caveats_vi", []), cited_ids, run_id)
            audience_notes = [item["text"] for item in caveat_evidence if _audience_caveat(item["text"])]
            pick["audience_note"] = audience_notes[0] if audience_notes else None
            pick["caveats"] = [text for text in caveats if not _audience_caveat(text)]
            pick["caveat_evidence"] = [item for item in caveat_evidence if not _audience_caveat(item["text"])]
            pick["video_evidence_ids"] = list(dict.fromkeys([*video_ids, *caveat_video_ids]))
            pick["evidence_count"] = len(dict.fromkeys([
                *pick["evidence_ids"],
                *(value for item in pick["caveat_evidence"] for value in item["evidence_ids"]),
                *pick["video_evidence_ids"],
            ]))
        return proposal
    finally:
        conn.close()


@router.get("/runs/{run_id}/creators/{creator_id}")
def get_run_creator(run_id: str, creator_id: str, request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        if not queries.get_run(conn, run_id):
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
        result = _creator_detail(conn, creator_id, run_id)
        if not result or not conn.execute(
            "SELECT 1 FROM recommendations WHERE run_id=? AND creator_id=?",
            (run_id, creator_id),
        ).fetchone():
            raise HTTPException(status_code=404, detail="Không tìm thấy KOC trong đề xuất này.")
        return result
    finally:
        conn.close()


@router.get("/campaigns")
def list_campaigns(request: Request):
    conn = _conn(request)
    try:
        return campaigns.list_all(conn)
    finally:
        conn.close()


@router.post("/campaigns")
def create_campaign(payload: CampaignInput, request: Request):
    if payload.followers_min > payload.followers_max:
        raise HTTPException(status_code=422, detail=[{"loc": ["body", "followers_min"], "msg": "Mức tối thiểu phải nhỏ hơn mức tối đa."}])
    campaign_input = payload.model_dump()
    conn = _conn(request)
    try:
        result = result_for_campaign(conn, campaign_input, _rate_tiers())
        saved = campaigns.save(conn, campaign_input, result)
        return _campaign_review_data(conn, saved)
    finally:
        conn.close()


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, request: Request):
    conn = _conn(request)
    try:
        result = campaigns.get(conn, campaign_id)
        if not result:
            raise HTTPException(status_code=404, detail="Không tìm thấy chiến dịch.")
        return _campaign_review_data(conn, {**result, "result": normalize_result(result["result"], result["input"])})
    finally:
        conn.close()


def _fold(value: str) -> str:
    """Casefold and strip Vietnamese diacritics so "chong nang" finds "chống nắng"."""
    text = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


@router.get("/creators")
def search_creators(request: Request, q: str = ""):
    conn = _conn(request)
    try:
        rows = conn.execute("SELECT creator_id,handle,data_json FROM creators ORDER BY creator_id").fetchall()
        query = _fold(q).lstrip("@")
        return [
            {"creator_id": row["creator_id"], "handle": row["handle"], "nickname": (_json(row["data_json"], {}).get("creator_nickname") or row["handle"])}
            for row in rows
            if query in _fold(row["creator_id"])
            or query in _fold(row["handle"] or "").lstrip("@")
            or query in _fold(_json(row["data_json"], {}).get("creator_nickname") or "")
        ]
    finally:
        conn.close()


@router.get("/creators/{creator_id}")
def get_creator(creator_id: str, request: Request):
    conn = _conn(request)
    try:
        result = _creator_detail(conn, creator_id)
        if not result:
            raise HTTPException(status_code=404, detail="Không tìm thấy KOC.")
        return result
    finally:
        conn.close()


@router.get("/ops/runs")
def list_ops_runs(request: Request):
    conn = _conn(request)
    try:
        result = []
        for run in queries.list_runs(conn):
            costs = queries.run_costs(conn, run["run_id"])
            tasks = conn.execute("SELECT stage,status,COUNT(*) AS count FROM tasks WHERE run_id=? GROUP BY stage,status", (run["run_id"],)).fetchall()
            params = _json(run["params_json"], {})
            result.append({**run, "costs": costs, "tasks": [dict(row) for row in tasks], "calibration": params.get("calibration", {})})
        return result
    finally:
        conn.close()


@router.get("/ops/runs/{run_id}")
def get_ops_run(run_id: str, request: Request):
    conn = _conn(request)
    try:
        run = queries.get_run(conn, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
        costs = queries.run_costs(conn, run_id)
        tasks = [dict(row) for row in conn.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY stage,key", (run_id,))]
        stages = [dict(row) for row in conn.execute("SELECT stage,COUNT(*) AS creators,AVG(score) AS mean_score FROM scores WHERE run_id=? GROUP BY stage ORDER BY stage", (run_id,))]
        return {**run, "costs": costs, "tasks": tasks, "stages": stages, "calibration": _json(run["params_json"], {}).get("calibration", {})}
    finally:
        conn.close()
