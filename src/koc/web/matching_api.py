import json
import re
import shlex

from koc import db
from koc.brief import check_brief, make_brief
from koc.config import load_config
from koc.estimate import estimate_run
from koc.pricing import VIDEOS_PER_KOC, creator_cost, tier_for
from koc.web.adapter import METRIC_LABELS_VI, analysed_video_ids, excluded_with_videos
from koc.web.matching import _rank, best_set, match, score_creators
from koc.stages import excluded_brand_fit, placeholder_audience_creators


EVIDENCE_PATTERN = re.compile(
    r"(metric:[\w-]+:[\w-]+|(?:v_)?[\w-]+@[\d.]+s?|[A-Za-z][\w-]*:[\w-]+:\d+)"
)


def _json(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def display_reason_text(text: str) -> str:
    text = EVIDENCE_PATTERN.sub("", text)
    text = re.sub(r"\b(\d{2})-(\d{2})\b", r"\1–\2", text)
    for key, label in sorted(METRIC_LABELS_VI.items(), key=lambda item: -len(item[0])):
        text = re.sub(rf"\b{re.escape(key)}\b", label, text)
    text = re.sub(r"\s*\(\s*\)", "", text)
    return " ".join(text.split())


# Ported from feat/koc-mvp:src/koc/stages.py:102-134.
AGE_BUCKET_METRICS = {
    "18-24": ("age_18_24_pct", "age_18_24_share"),
    "25-34": ("age_25_34_pct", "age_25_34_share"),
    "35-44": ("age_35_44_pct", "age_35_44_share"),
    "45-54": ("age_45_54_pct", "age_45_54_share"),
    "55+": ("age_55_plus_pct", "age_55_plus_share"),
}
AUDIENCE_METRIC_NAMES = (
    "female_pct",
    "female_ratio",
    *(name for names in AGE_BUCKET_METRICS.values() for name in names),
)


def _metric(metrics: dict, names: tuple[str, ...]) -> float | None:
    for name in names:
        if name in metrics:
            value = _json(metrics[name], metrics[name])
            if value is not None:
                number = float(value)
                if name.endswith("_ratio") or name.endswith("_share"):
                    number *= 100
                return number
    return None


def _audience_parts(metrics: dict, target: dict) -> dict[str, float | None]:
    gender = target.get("gender", "Nữ")
    female = _metric(metrics, ("female_pct", "female_ratio"))
    gender_fit = None if female is None else (100 - female if gender == "Nam" else female if gender == "Nữ" else None)
    ages = [
        _metric(metrics, AGE_BUCKET_METRICS[age])
        for age in target.get("age_groups", [])
        if age in AGE_BUCKET_METRICS
    ]
    age_fit = min(100, sum(ages)) if ages and all(value is not None for value in ages) else None
    return {"gender": gender_fit, "age": age_fit}


def _apply_audience_floors(pool: list[dict]) -> None:
    parts = [creator.pop("_audience_parts") for creator in pool]
    minima = {
        name: min(values) if (values := [item[name] for item in parts if item[name] is not None]) else None
        for name in ("gender", "age")
    }
    for creator, creator_parts in zip(pool, parts):
        observed = [value for value in creator_parts.values() if value is not None]
        creator["_audience_observed"] = bool(observed)
        creator["audience_age_missing"] = bool(creator_parts["gender"] is not None and creator_parts["age"] is None)
        values = [
            creator_parts[name] if creator_parts[name] is not None else minima[name]
            for name in ("gender", "age")
        ]
        present = [value for value in values if value is not None]
        audience = sum(present) / len(present) if present else None
        if audience is not None and observed and len(observed) < len(present):
            audience = min(audience, sum(observed) / len(observed))
        creator["audience"] = audience


def _reason(conn, run_id: str, creator_id: str, commercial: float, audience: float | None, content: float | None) -> tuple[str, list[str]]:
    row = conn.execute(
        "SELECT rec_json FROM recommendations WHERE run_id=? AND creator_id=?",
        (run_id, creator_id),
    ).fetchone()
    rec = _json(row[0], {}) if row else {}
    reasons = rec.get("reasons_vi", [])
    text = reasons[0] if reasons else f"Điểm thương mại {commercial:.0f}/100" + (f", khán giả {audience:.0f}/100" if audience is not None else "") + (f", nội dung {content:.0f}/100." if content is not None else ".")
    cited_ids = rec.get("cited_evidence_ids", [])
    evidence_ids = list(dict.fromkeys([
        *EVIDENCE_PATTERN.findall(text),
        *(cited_ids if isinstance(cited_ids, list) else []),
    ]))
    evidence_ids = [evidence_id for evidence_id in evidence_ids if isinstance(evidence_id, str) and _evidence_target_exists(conn, creator_id, evidence_id, run_id)]
    return display_reason_text(text), evidence_ids


def _evidence_target_exists(conn, creator_id: str, evidence_id: str, run_id: str | None = None) -> bool:
    if evidence_id.startswith(f"metric:{creator_id}:"):
        name = evidence_id.rsplit(":", 1)[-1]
        return conn.execute("SELECT 1 FROM metrics WHERE creator_id=? AND name=?", (creator_id, name)).fetchone() is not None
    video_id = evidence_id.split(":", 1)[0].split("@", 1)[0]
    if run_id:
        rows = [a[3] for a in db.run_analyses(conn, run_id, creator_id) if a[0] == video_id]
    else:
        rows = [r[0] for r in conn.execute(
            "SELECT a.analysis_json FROM videos v JOIN analyses a ON a.video_id=v.video_id "
            "WHERE v.creator_id=? AND v.video_id=? ORDER BY a.rowid DESC LIMIT 1", (creator_id, video_id))]
    analysis = _json(rows[0], {}) if rows else {}
    return any(item.get("evidence_id") == evidence_id for item in analysis.get("evidence", []))


DEFAULT_PRODUCT_TYPE = "Chống nắng"
DEFAULT_FOLLOWERS = (10_000, 300_000)  # fixed in pipeline._rank_candidates
DEFAULT_RUN_LIMIT = 200  # `koc run --limit` default; the needs_run estimate assumes the command as printed
GENDER_FLAGS = {"Nữ": "nu", "Nam": "nam", "Tất cả": "tat-ca"}
AGE_BOUNDS = {"18-24": (18, 24), "25-34": (25, 34), "35-44": (35, 44), "45-54": (45, 54), "55+": (55, 99)}


def _estimated_cost(followers: int, rate_tiers: list[dict]) -> int:
    return creator_cost(followers, rate_tiers)


def _run_product_type(conn, params_json) -> str:
    brief = _json(params_json, {}).get("brief")
    return (brief.get("product_type") if isinstance(brief, dict) else None) or DEFAULT_PRODUCT_TYPE


def _done_run_ids(conn, product_type: str) -> list[str]:
    rows = conn.execute("SELECT run_id, params_json FROM runs WHERE status='done' ORDER BY started_at DESC, rowid DESC").fetchall()
    return [row["run_id"] for row in rows if _run_product_type(conn, row["params_json"]) == product_type]


def _previous_picks(conn, run_ids) -> set[str]:
    """Final picks of the runs the form asks to leave out (free: no paid run)."""
    return {row[0] for run_id in run_ids or [] for row in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}


def get_pool(conn, campaign_input: dict, rate_tiers: list[dict]) -> tuple[list[dict], str | None]:
    run_ids = _done_run_ids(conn, campaign_input["product_type"]) if "product_type" in campaign_input else None
    run = next((
        row for row in conn.execute(
            "SELECT r.run_id FROM runs r JOIN scores s ON s.run_id=r.run_id AND s.stage='S1' "
            "GROUP BY r.run_id ORDER BY r.started_at DESC, r.rowid DESC"
        ) if run_ids is None or row["run_id"] in run_ids
    ), None)
    if not run:
        return [], None
    run_id = run["run_id"]
    placeholders = placeholder_audience_creators(conn, run_id)
    scores = conn.execute(
        "SELECT s.creator_id, s.score, c.handle, c.data_json FROM scores s "
        "JOIN creators c ON c.creator_id=s.creator_id "
        "WHERE s.run_id=? AND s.stage='S1'",
        (run_id,),
    ).fetchall()
    pool = []
    excluded_ids = {item["id"] for item in excluded_brand_fit(conn, run_id, stage="S1")}
    excluded_ids |= _previous_picks(conn, campaign_input.get("exclude_run_ids"))
    for row in scores:
        if row["creator_id"] in excluded_ids:
            continue
        data = _json(row["data_json"], {})
        followers = int(data.get("creator_followers") or data.get("followers") or 0)
        if not campaign_input["followers_min"] <= followers <= campaign_input["followers_max"]:
            continue
        component_rows = conn.execute(
            "SELECT stage, score FROM scores WHERE run_id=? AND creator_id=? AND stage IN ('S2','S3')",
            (run_id, row["creator_id"]),
        ).fetchall()
        stages = {item["stage"]: item["score"] for item in component_rows}
        metrics = {
            item["name"]: item["value"]
            for item in conn.execute("SELECT name,value FROM metrics WHERE creator_id=?", (row["creator_id"],))
        }
        audience_parts = _audience_parts(metrics, campaign_input["target"])
        is_placeholder = row["creator_id"] in placeholders
        if is_placeholder or "S2" not in stages:
            audience_parts = {"gender": None, "age": None}
        content = stages.get("S3")
        cost = _estimated_cost(followers, rate_tiers)
        pool.append({
            "creator_id": row["creator_id"],
            "nickname": data.get("creator_nickname") or row["handle"] or row["creator_id"],
            "handle": row["handle"] or f"@{row['creator_id']}",
            "followers": followers,
            "avatar": data.get("avatar_thumb") or data.get("avatar"),
            "mcn": data.get("mcn"),
            "commercial": float(row["score"]),
            "audience": None,
            "_audience_parts": audience_parts,
            "content": float(content) if content is not None else None,
            "cost_vnd": int(cost),
            "reason": "",
            "evidence_ids": [],
            "audience_is_placeholder": is_placeholder,
        })
    _apply_audience_floors(pool)
    for creator in pool:
        reason, evidence_ids = _reason(
            conn, run_id, creator["creator_id"], creator["commercial"],
            creator["audience"] if creator["_audience_observed"] else None,
            creator["content"],
        )
        creator["reason"] = reason
        creator["evidence_ids"] = evidence_ids
    return pool, run_id


def _cheaper_band(conn, campaign_input: dict, rate_tiers: list[dict]) -> dict | None:
    low, high = campaign_input["followers_min"], campaign_input["followers_max"]
    current = max(
        tier_for(low, rate_tiers)["vnd_per_video"], tier_for(high, rate_tiers)["vnd_per_video"],
        *(tier["vnd_per_video"] for tier in rate_tiers if tier["min_followers"] <= high and tier["max_followers"] >= low),
    )
    best = None
    for tier in rate_tiers:
        if tier["vnd_per_video"] >= current:
            continue
        band_pool, _ = get_pool(conn, {**campaign_input, "followers_min": tier["min_followers"], "followers_max": tier["max_followers"]}, rate_tiers)
        group = best_set(_rank(band_pool), campaign_input["count"], campaign_input["budget_vnd"], campaign_input["avoid_same_mcn"])
        if group is None:
            continue
        key = (sum(item["fit"] for item in group), -sum(item["cost_vnd"] for item in group))
        if best is None or key > best[0]:
            best = (key, {"follower_min": tier["min_followers"], "follower_max": tier["max_followers"], "cost_vnd": sum(item["cost_vnd"] for item in group)})
    return best[1] if best else None


def run_command(campaign_input: dict) -> tuple[str, list[str]]:
    """The `koc run --dry-run` command for the form, built through koc.brief so it matches the CLI."""
    config = load_config()
    product_type, target = campaign_input["product_type"], campaign_input["target"]
    gender = GENDER_FLAGS[target["gender"]]
    ages = [AGE_BOUNDS[age] for age in target["age_groups"] if age in AGE_BOUNDS]
    age_min, age_max = (ages[0][0], ages[-1][1]) if ages else (None, None)
    specs = (campaign_input.get("product_specs") or "").strip()
    other = product_type == "Khác"
    brief = make_brief(config, product_type=product_type, category_ids=["<id>"] if other else None, gender=gender,
                       age_min=age_min, age_max=age_max, budget=campaign_input["budget_vnd"], count=campaign_input["count"])
    parts = ["koc", "run", "--dry-run", "--product-type", shlex.quote(product_type), "--gender", gender]
    if ages:
        parts += ["--age-min", str(age_min), "--age-max", str(age_max)]
    parts += ["--budget", str(campaign_input["budget_vnd"]), "--count", str(campaign_input["count"])]
    if specs and specs != brief["product"]:
        parts += ["--product", shlex.quote(specs)]
    if other:
        parts += ["--category-ids", '"<id>"']
    for run_id in campaign_input.get("exclude_run_ids") or []:
        parts += ["--exclude-run", shlex.quote(run_id)]
    notes = []
    if error := check_brief(brief, config):
        notes.append(error)
    if (campaign_input["followers_min"], campaign_input["followers_max"]) != DEFAULT_FOLLOWERS:
        notes.append(f"CLI không có tham số follower: lệnh dùng bộ lọc follower của pipeline ({DEFAULT_FOLLOWERS[0]:,}-{DEFAULT_FOLLOWERS[1]:,}), "
                     f"không phải khoảng {campaign_input['followers_min']:,}-{campaign_input['followers_max']:,} trong form.".replace(",", "."))
    if other:
        notes.append("Thay <id> bằng mã ngành Kalodata, tìm bằng `koc categories --keyword <từ khóa>`.")
    return " ".join(parts), notes


def normalize_result(result: dict, campaign_input: dict) -> dict:
    if "status" in result:
        return result
    budget = int(campaign_input.get("budget_vnd", 0))
    warning = result.get("warning")
    return {**result, "status": "ok", "warnings": [warning] if warning else [], "budget_vnd": budget,
            "leftover_vnd": budget - int(result.get("total_cost_vnd", 0))}


def _needs_run(campaign_input: dict, low_confidence: bool, options=None) -> dict:
    command, notes = run_command(campaign_input)
    budget = campaign_input["budget_vnd"]
    return {"status": "needs_run", "picked": [], "picks": [], "alternates": [], "warnings": [], "warning": None,
            "total_cost_vnd": 0, "leftover_vnd": budget, "budget_vnd": budget, "options": options,
            "run_command": command, "run_command_notes": notes, "ranked_count": 0, "run_id": None,
            "low_confidence_pool": low_confidence,
            "run_estimate": estimate_run(load_config(), DEFAULT_RUN_LIMIT, campaign_input["count"])}


POOL_KEYS = ("creator_id", "nickname", "handle", "followers", "avatar", "mcn", "fit", "components", "confidence", "confidence_count", "cost_vnd", "reason", "evidence_ids")


def ranked_pool(pool: list[dict], limit: int = 200) -> list[dict]:
    """Every scored creator that passed the gates (compact), best fit first, for the results-page filter. No paid calls."""
    scored = sorted(score_creators(pool), key=lambda item: (-item["fit"], item["creator_id"]))[:limit]
    return [{**{key: item.get(key) for key in POOL_KEYS}, "price_per_video_vnd": item["cost_vnd"] // VIDEOS_PER_KOC} for item in scored]


def result_for_campaign(conn, campaign_input: dict, rate_tiers: list[dict]) -> dict:
    low_confidence = campaign_input["product_type"] not in {"Chống nắng", "Dưỡng ẩm", "Serum", "Làm sạch"}
    if not _done_run_ids(conn, campaign_input["product_type"]):
        return _needs_run(campaign_input, low_confidence)
    pool, run_id = get_pool(conn, campaign_input, rate_tiers)
    result = match({
        "count": campaign_input["count"],
        "budget_vnd": campaign_input["budget_vnd"],
        "avoid_same_mcn": campaign_input["avoid_same_mcn"],
    }, pool)
    if result["status"] == "refused":
        result["options"]["cheaper_follower_band"] = _cheaper_band(conn, campaign_input, rate_tiers)
        if campaign_input.get("exclude_run_ids") and len(pool) < campaign_input["count"] <= len(get_pool(conn, {**campaign_input, "exclude_run_ids": []}, rate_tiers)[0]):
            # The exclusion itself left too few creators: a new run (with the flags) is the way out.
            # Budget refusals with enough candidates stay refused with their warnings and options.
            return _needs_run(campaign_input, low_confidence, result["options"])
    if run_id:
        for creator in [*result.get("picked", []), *result.get("alternates", [])]:
            creator["analysed_video_ids"] = analysed_video_ids(conn, run_id, creator["creator_id"])
    excluded = excluded_with_videos(conn, run_id, excluded_brand_fit(conn, run_id, stage="S1")) if run_id else []
    return {**result, "run_id": run_id, "brand_fit_excluded": excluded, "low_confidence_pool": low_confidence,
            "ranked_pool": ranked_pool(pool)}
