from math import fsum
import json
import re

from .config import load_config


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _trend_score(values, reference):
    values = [_number(v) for v in values or []]
    if len(values) < 2:
        return 0.0, None
    mean = fsum(values) / len(values)
    slope = sum((i - (len(values) - 1) / 2) * (v - mean) for i, v in enumerate(values)) / sum((i - (len(values) - 1) / 2) ** 2 for i in range(len(values)))
    return max(0.0, min(100.0, slope / mean / reference * 100)) if mean else 0.0, slope


def score_creator(creator_id: str, creator: dict, videos: list[dict], skincare_revenue: float | None = None) -> dict:
    config = load_config()
    weights = config["scoring"]["s1_weights"]
    normalization = config["scoring"]["normalization"]
    gpm = _number(creator.get("video_gpm"))
    followers = _number(creator.get("creator_followers"))
    video_revenue = _number(creator.get("video_revenue"))
    live_revenue = _number(creator.get("live_revenue"))
    revenue_total = _number(creator.get("revenue"))
    category_revenue = _number(skincare_revenue) if skincare_revenue is not None else 0.0
    share = category_revenue / revenue_total if revenue_total > 0 else 0.0
    trend_score, slope = _trend_score(creator.get("revenue_trend"), normalization["trend_slope_reference"])
    video_share = video_revenue / (video_revenue + live_revenue) if video_revenue + live_revenue else 0.0
    gpm_score = min(100.0, gpm / normalization["video_gpm_reference"] * 100)
    skincare_score = max(0.0, min(100.0, share * 100))
    follower_score = 100.0 if 50_000 <= followers <= 100_000 else (85.0 if 10_000 <= followers <= 300_000 else 0.0)
    components = {
        "video_gpm": gpm_score,
        "skincare_revenue_share": skincare_score,
        "revenue_trend_slope": trend_score,
        "video_vs_live_share": video_share * 100,
        "follower_band_fit": follower_score,
    }
    score = sum(components[name] * weight for name, weight in weights.items()) / 100
    views = sum(_number(video.get("views")) for video in videos)
    engagements = sum(_number(video.get("digg_count")) + _number(video.get("comment_count")) + _number(video.get("share_count")) for video in videos)
    engagement = engagements / views if views else None
    metrics = {
        "video_gpm": gpm,
        "skincare_revenue_share": share if skincare_revenue is not None else None,
        "revenue_trend_slope": slope,
        "video_vs_live_share": video_share,
        "follower_band_fit": follower_score,
        "engagement_per_view": engagement,
    }
    return {
        "score": round(score, 4),
        "breakdown": {**components, "engagement_per_view": engagement},
        "metrics": metrics,
        "evidence": {name: f"metric:{creator_id}:{name}" for name in metrics},
    }


def score_creator_rank(creator: dict) -> float:
    """Cheap S1a estimate using creator/rank fields only."""
    revenue = _number(creator.get("revenue"))
    growth = max(-100.0, min(100.0, _number(creator.get("revenue_growth_rate"))))
    video = _number(creator.get("video_revenue"))
    live = _number(creator.get("live_revenue"))
    followers = _number(creator.get("creator_followers"))
    categories = " ".join(map(str, creator.get("category_list") or [])).lower()
    return round(
        min(100.0, max(0.0, revenue / 1_000_000_000 * 100)) * .25
        + max(0.0, (growth + 100) / 2) * .15
        + (video / (video + live) * 100 if video + live else 0) * .15
        + (100 if 50_000 <= followers <= 100_000 else 85 if 10_000 <= followers <= 300_000 else 0) * .10
        + (100 if any(term in categories for term in ("skincare", "beauty", "làm đẹp")) else 0) * .35,
        4,
    )


def parse_audience_text(text: str) -> dict:
    text = re.sub(r"[\ue000-\uf8ff]", "", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    female = re.search(r"(?:^|\n)(?:Female|Nữ)\n([\d.]+%)", text, re.I)
    block = re.search(r"(?:^|\n)(?:Age|Độ tuổi|Tuổi)\n(.*?)\nTop 5 Locations", text + "\nTop 5 Locations", re.S | re.I)
    ages = dict(re.findall(r"(\d{2}(?:-\d{2}|\+))\n([\d.]+%)", block.group(1) if block else ""))
    return {"female_pct": float(female.group(1)[:-1]) if female else None,
            "age_18_24_pct": float(ages["18-24"][:-1]) if "18-24" in ages else None,
            "age_25_34_pct": float(ages["25-34"][:-1]) if "25-34" in ages else None}


def audience_score(metrics: dict, gender: str = "nu", age_min: int = 18, age_max: int = 30) -> float | None:
    """Share of the audience in the brief's gender and in the stored Kalodata age bands (18-24, 25-34) that overlap its age range.

    None when the range overlaps no stored band: the audience is unknown, not a poor fit."""
    female = min(100.0, max(0.0, metrics.get("female_pct") or 0))
    bands = ((18, 24, "age_18_24_pct"), (25, 34, "age_25_34_pct"))
    overlapping = [name for low, high, name in bands if low <= age_max and high >= age_min]
    if not overlapping:
        return None
    age = min(100.0, max(0.0, sum(metrics.get(name) or 0 for name in overlapping)))
    if gender == "tat-ca":
        return round(age, 4)
    share = female if gender == "nu" else (100 - female if metrics.get("female_pct") is not None else 0.0)
    return round(share * .5 + age * .5, 4)


AUDIENCE_METRIC_NAMES = ("female_pct", "age_18_24_pct", "age_25_34_pct")
# Signature Kalodata shows to plans without audience data (Male 40 / Female 60, 18-24 30.5, 25-34 39.5).
KNOWN_PLACEHOLDER_SIGNATURE = (60.0, 30.5, 39.5)
AUDIENCE_PLACEHOLDER_NOTE_VI = "Không có dữ liệu (Kalodata chỉ hiển thị số liệu mẫu)"


def audience_is_placeholder(signatures: list[tuple]) -> bool:
    """Decide whether captured S2 audience tuples are Kalodata sample data.

    Rule: real audiences differ per creator. If 3 or more creators were captured
    and all share one identical (female_pct, age_18_24_pct, age_25_34_pct) tuple,
    the numbers are a placeholder. Additionally, any non-empty capture that is
    entirely the known placeholder signature counts. Tuples that are all None
    (nothing captured) are ignored.
    """
    captured = [tuple(sig) for sig in signatures if any(v is not None for v in sig)]
    if not captured:
        return False
    if set(captured) == {KNOWN_PLACEHOLDER_SIGNATURE}:
        return True
    return len(captured) >= 3 and len(set(captured)) == 1


def _audience_signatures(conn, run_id: str) -> dict[str, tuple]:
    """Captured (female_pct, age_18_24_pct, age_25_34_pct) per creator with an S2 score in this run."""
    creator_ids = [row[0] for row in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S2'", (run_id,))]
    signatures = {}
    for creator_id in creator_ids:
        values = {row[0]: row[1] for row in conn.execute(
            f"SELECT name,value FROM metrics WHERE creator_id=? AND name IN ({','.join('?' * len(AUDIENCE_METRIC_NAMES))})",
            (creator_id, *AUDIENCE_METRIC_NAMES))}
        signatures[creator_id] = tuple(None if values.get(name) is None else json.loads(values[name]) for name in AUDIENCE_METRIC_NAMES)
    return signatures


def run_audience_is_placeholder(conn, run_id: str) -> bool:
    """True when the S2 audience data captured for this run is a placeholder."""
    return audience_is_placeholder(list(_audience_signatures(conn, run_id).values()))


def placeholder_audience_creators(conn, run_id: str) -> set[str]:
    """Creator ids whose captured audience is placeholder data, decided per creator.

    A capture equal to the known sample signature is a placeholder for that creator no matter what
    other creators captured. The run-level rule (>=3 identical captures) still marks every creator.
    """
    signatures = _audience_signatures(conn, run_id)
    if audience_is_placeholder(list(signatures.values())):
        return set(signatures)
    return {cid for cid, sig in signatures.items() if tuple(sig) == KNOWN_PLACEHOLDER_SIGNATURE}


def brand_fit_gate(conn, run_id: str, creator_id: str, config: dict | None = None) -> dict:
    """D-B7: a KOC is eligible only if a run-selected analysed video has rubric brand_fit >= s4.min_brand_fit.

    Shared by S4 and the web matching pool. A creator with no analysed video has no evidence
    and is not eligible. Returns {"eligible", "max_brand_fit", "min_brand_fit", "reason_vi"}.
    """
    from . import db
    minimum = (config or load_config())["scoring"]["s4"]["min_brand_fit"]
    best = None
    for _vid, _prompt, _model, raw in db.run_analyses(conn, run_id, creator_id):
        for item in json.loads(raw).get("rubric", []):
            if item.get("criterion") == "brand_fit":
                best = item["score"] if best is None else max(best, item["score"])
    eligible = best is not None and best >= minimum
    if best is None:
        reason = "Loại vì chưa có video được phân tích để kiểm tra độ hợp sản phẩm."
    else:
        reason = None if eligible else f"Loại vì video không hợp sản phẩm: độ hợp thương hiệu cao nhất {best}/5 (cần ít nhất {minimum}/5)."
    return {"eligible": eligible, "max_brand_fit": best, "min_brand_fit": minimum, "reason_vi": reason}


def excluded_brand_fit(conn, run_id: str, config: dict | None = None, stage: str = "S3") -> list[dict]:
    """Creators with a `stage` score in the run that fail brand_fit_gate: [{"id","handle","max_brand_fit","reason_vi"}].

    S4 and the run view use S3 (scored content); the web matching pool uses S1, its candidate set.
    """
    config = config or load_config()
    out = []
    for row in conn.execute("SELECT s.creator_id, c.handle FROM scores s LEFT JOIN creators c ON c.creator_id=s.creator_id WHERE s.run_id=? AND s.stage=? AND s.score IS NOT NULL ORDER BY s.creator_id", (run_id, stage)):
        gate = brand_fit_gate(conn, run_id, row[0], config)
        if not gate["eligible"]:
            out.append({"id": row[0], "handle": row[1] or row[0], "max_brand_fit": gate["max_brand_fit"], "reason_vi": gate["reason_vi"]})
    return out


def final_score(s1, s2, s3) -> float:
    """Weighted final score using config final_weights.

    When s2 (audience) is None, its weight is dropped and the others are
    renormalised: (w_commercial*S1 + w_content*S3) / (w_commercial + w_content).
    """
    weights = load_config()["scoring"]["final_weights"]
    parts = {"commercial": s1 or 0, "audience": s2, "content": s3 or 0}
    used = {name: weights[name] for name, value in parts.items() if value is not None}
    return sum(parts[name] * weight for name, weight in used.items()) / sum(used.values())


def s1_shortlist(conn, run_id: str, limit: int = 40) -> list[str]:
    rows = conn.execute(
        "SELECT s.creator_id,s.score,m.value AS engagement FROM scores s LEFT JOIN metrics m "
        "ON m.creator_id=s.creator_id AND m.name='engagement_per_view' "
        "WHERE s.run_id=? AND s.stage='S1'", (run_id,)
    ).fetchall()
    def ordering(row):
        engagement = json.loads(row["engagement"]) if row["engagement"] is not None else 0.0
        engagement = 0.0 if engagement is None else float(engagement)
        return (-row["score"], -engagement, row["creator_id"])

    return [row["creator_id"] for row in sorted(rows, key=ordering)[:limit]]


def s0_categories() -> list[str]:
    return list(load_config()["scoring"]["s0"]["category_ids"])


def s2_audience(*_args, **_kwargs):
    raise NotImplementedError("TODO: S2 audience capture belongs to D2.")


def s3_content(*_args, **_kwargs):
    raise NotImplementedError("TODO: S3 content analysis belongs to D2.")


def s4_select(*_args, **_kwargs):
    raise NotImplementedError("TODO: S4 selection and reasons belong to D2.")
