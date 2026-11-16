import json
from pathlib import Path

from koc import db
from koc.stages import s1_shortlist, score_creator, score_creator_rank


def test_s1_score_uses_fixture_creator_values():
    fixture_path = Path(__file__).parents[2] / "reports/api_probe_2026-11-15.json"
    fixture = next(row["body"]["data"] for row in json.loads(fixture_path.read_text()) if row["need_extra"])
    scored = score_creator(fixture["creator_id"], fixture, [])
    assert scored["metrics"]["video_gpm"] == 150931.01
    assert scored["metrics"]["video_vs_live_share"] == fixture["video_revenue"] / (fixture["video_revenue"] + fixture["live_revenue"])
    assert scored["metrics"]["skincare_revenue_share"] is None
    assert scored["score"] == round(
        35 + 0 + scored["breakdown"]["revenue_trend_slope"] * .15
        + scored["breakdown"]["video_vs_live_share"] * .15,
        4,
    )
    assert scored["evidence"]["video_gpm"] == f"metric:{fixture['creator_id']}:video_gpm"


def test_s1_engagement_breaks_score_ties(tmp_path):
    conn = db.connect(tmp_path / "rank.db")
    db.init_db(conn)
    db.upsert_score(conn, "r1", "c-low", "S1", 80, {})
    db.upsert_score(conn, "r1", "c-high", "S1", 80, {})
    db.upsert_metric(conn, "c-low", "engagement_per_view", .1, "fixture")
    db.upsert_metric(conn, "c-high", "engagement_per_view", .2, "fixture")
    assert s1_shortlist(conn, "r1", 1) == ["c-high"]


def test_s1_shortlist_treats_null_engagement_as_zero(tmp_path):
    conn = db.connect(tmp_path / "null-engagement.db")
    db.init_db(conn)
    db.upsert_score(conn, "r1", "c-null", "S1", 80, {})
    db.upsert_metric(conn, "c-null", "engagement_per_view", None, "fixture")
    db.upsert_score(conn, "r1", "c-zero", "S1", 80, {})
    db.upsert_metric(conn, "c-zero", "engagement_per_view", 0.0, "fixture")
    assert s1_shortlist(conn, "r1", 2) == ["c-null", "c-zero"]


def test_s1a_uses_only_rank_row_fields():
    first = score_creator_rank({"revenue": 1000, "revenue_growth_rate": 20, "video_revenue": 700,
                                "live_revenue": 300, "creator_followers": 70000,
                                "category_list": ["Beauty", "Skincare"]})
    second = score_creator_rank({"revenue": 1000, "revenue_growth_rate": 1, "video_revenue": 100,
                                 "live_revenue": 900, "creator_followers": 5000,
                                 "category_list": ["Fashion"]})
    assert first > second
