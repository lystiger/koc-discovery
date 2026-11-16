import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from koc import db, queries
from koc.web.app import create_app
from koc.web import campaigns
from koc.web.api import _creator_detail
from koc.web.matching import match
from koc.stages import audience_is_placeholder, placeholder_audience_creators
from koc.web.matching_api import _audience_parts, _reason, get_pool
from tests.web.fixtures.seed import seed_fixture_db


def client_for(tmp_path):
    database = tmp_path / "fixture.db"
    seed_fixture_db(database, tmp_path / "media")
    return TestClient(create_app(str(database), str(tmp_path / "media"))), database


def test_campaign_submit_saves_input_and_ranked_creators(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    recommendation_count = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    conn.close()
    response = client.post("/api/campaigns", json={
        "brand_name": "Mây Daily",
        "product_type": "Chống nắng",
        "budget_vnd": 60_000_000,
        "count": 5,
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
        "avoid_same_mcn": True,
    })
    assert response.status_code == 200
    campaign = response.json()
    assert campaign["input"]["brand_name"] == "Mây Daily"
    assert len(campaign["result"]["picked"]) == 5
    assert campaign["result"]["total_cost_vnd"] <= 60_000_000
    assert len({item["mcn"] for item in campaign["result"]["picked"] if item["mcn"]}) == len(
        [item["mcn"] for item in campaign["result"]["picked"] if item["mcn"]]
    )
    saved = client.get(f"/api/campaigns/{campaign['campaign_id']}").json()
    assert saved["result"]["picked"] == campaign["result"]["picked"]
    conn = db.connect(database)
    assert conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == recommendation_count
    conn.close()


def test_stats_match_direct_database_counts(tmp_path):
    client, database = client_for(tmp_path)
    response = client.get("/api/stats")

    assert response.status_code == 200
    conn = db.connect(database)
    latest_s1_run = conn.execute(
        "SELECT s.run_id FROM scores s JOIN runs r USING (run_id) "
        "WHERE s.stage='S1' ORDER BY r.started_at DESC LIMIT 1"
    ).fetchone()[0]
    expected = {
        "creators_in_pool": conn.execute(
            "SELECT COUNT(DISTINCT creator_id) FROM scores WHERE run_id=? AND stage='S1'",
            (latest_s1_run,),
        ).fetchone()[0],
        "creators_with_s3_score": conn.execute(
            "SELECT COUNT(DISTINCT creator_id) FROM scores WHERE stage='S3'"
        ).fetchone()[0],
        "analyzed_videos": conn.execute(
            "SELECT COUNT(DISTINCT video_id) FROM analyses"
        ).fetchone()[0],
    }
    conn.close()

    assert response.json() == expected


def test_campaign_list_orders_newest_first(tmp_path):
    client, _ = client_for(tmp_path)
    payload = {
        "brand_name": "Mây Daily",
        "product_type": "Chống nắng",
        "budget_vnd": 30_000_000,
        "count": 2,
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": {"gender": "Nữ", "age_groups": ["18-24"]},
        "avoid_same_mcn": True,
    }
    client.post("/api/campaigns", json=payload)
    newest = client.post("/api/campaigns", json={**payload, "brand_name": "Mây Daily mới"}).json()

    assert client.get("/api/campaigns").json()[0]["campaign_id"] == newest["campaign_id"]


def test_invalid_campaign_input_returns_field_error(tmp_path):
    client, _ = client_for(tmp_path)
    response = client.post("/api/campaigns", json={"brand_name": "", "budget_vnd": 10})
    assert response.status_code == 422


def test_age_groups_reject_gaps_and_wrong_order_with_vietnamese_error(tmp_path):
    client, _ = client_for(tmp_path)
    base = {
        "brand_name": "Mây Daily",
        "product_type": "Chống nắng",
        "budget_vnd": 30_000_000,
        "target": {"gender": "Nữ", "age_groups": []},
    }
    invalid_ranges = (
        ([], "Chọn ít nhất một nhóm tuổi."),
        (["18-24", "35-44"], "Chọn các nhóm tuổi liền nhau theo thứ tự từ nhỏ đến lớn."),
        (["25-34", "18-24"], "Chọn các nhóm tuổi liền nhau theo thứ tự từ nhỏ đến lớn."),
        (["18-24", "18-24"], "Chọn các nhóm tuổi liền nhau theo thứ tự từ nhỏ đến lớn."),
    )
    for ages, message in invalid_ranges:
        response = client.post("/api/campaigns", json={**base, "target": {"gender": "Nữ", "age_groups": ages}})
        assert response.status_code == 422
        assert message in response.text


def test_old_campaign_age_groups_load_unchanged(tmp_path):
    client, database = client_for(tmp_path)
    old_input = {"brand_name": "Mây Daily", "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]}}
    conn = db.connect(database)
    campaigns.ensure_table(conn)
    saved = campaigns.save(conn, old_input, {"picked": []})
    conn.close()

    loaded = client.get(f"/api/campaigns/{saved['campaign_id']}").json()
    assert loaded["input"] == old_input


def test_age_fit_supports_35_to_54_and_requires_every_selected_bucket(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    db.upsert_metric(conn, "c_linh_01", "age_35_44_pct", 30, "fixture", "last30Day")
    db.upsert_metric(conn, "c_linh_01", "age_45_54_share", 0.25, "fixture", "last30Day")
    db.upsert_metric(conn, "c_chou_02", "age_35_44_pct", 40, "fixture", "last30Day")
    target = {"gender": "Tất cả", "age_groups": ["35-44", "45-54"]}

    assert _audience_parts({"age_35_44_pct": 30, "age_45_54_share": 0.25}, target) == {"gender": None, "age": 55}
    pool, _ = get_pool(conn, {
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": target,
    }, [{"min_followers": 0, "max_followers": 1_000_000, "vnd_per_video": 1}])
    conn.close()

    audience = {creator["creator_id"]: creator["audience"] for creator in pool}
    assert audience["c_linh_01"] == 55
    assert audience["c_chou_02"] == 55

    accepted = client.post("/api/campaigns", json={
        "brand_name": "Mây Daily",
        "product_type": "Chống nắng",
        "budget_vnd": 30_000_000,
        "target": target,
    })
    assert accepted.status_code == 200
    assert accepted.json()["input"]["target"]["age_groups"] == ["35-44", "45-54"]


def test_missing_age_metric_in_fixture_uses_pool_floor(tmp_path):
    _, database = client_for(tmp_path)
    conn = db.connect(database)
    campaign = {
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": {"gender": "Nữ", "age_groups": ["25-34"]},
    }
    tiers = [{"min_followers": 0, "max_followers": 1_000_000, "vnd_per_video": 1}]
    before, _ = get_pool(conn, campaign, tiers)
    before_fit = next(item["fit"] for item in match(
        {"count": 6, "budget_vnd": 100, "avoid_same_mcn": False}, before
    )["picked"] if item["creator_id"] == "c_linh_01")
    conn.execute("DELETE FROM metrics WHERE creator_id=? AND name=?", ("c_linh_01", "age_25_34_share"))
    after, _ = get_pool(conn, campaign, tiers)
    after_fit = next(item["fit"] for item in match(
        {"count": 6, "budget_vnd": 100, "avoid_same_mcn": False}, after
    )["picked"] if item["creator_id"] == "c_linh_01")
    conn.close()

    assert next(item["audience"] for item in before if item["creator_id"] == "c_linh_01") == 60
    assert next(item["audience"] for item in after if item["creator_id"] == "c_linh_01") < 60
    assert next(item["audience_age_missing"] for item in after if item["creator_id"] == "c_linh_01")
    assert after_fit <= before_fit


def test_search_and_ops_costs_use_existing_queries(tmp_path):
    client, database = client_for(tmp_path)
    assert client.get("/api/creators?q=chou.bea").json()[0]["creator_id"] == "c_chou_02"
    detail = client.get("/api/creators/c_linh_01").json()
    assert detail["reasons"][0]["evidence_ids"]
    assert "metric:" not in detail["reasons"][0]["text"]
    runs = client.get("/api/ops/runs").json()
    conn = db.connect(database)
    expected = queries.run_costs(conn, runs[0]["run_id"])
    conn.close()
    assert runs[0]["costs"] == expected


def test_run_proposal_routes_use_run_scoped_recommendations(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    run_id = conn.execute("SELECT run_id FROM recommendations ORDER BY rowid LIMIT 1").fetchone()[0]
    expected = conn.execute(
        "SELECT COUNT(*),SUM(est_cost_vnd) FROM recommendations WHERE run_id=?", (run_id,)
    ).fetchone()
    creator_id = conn.execute(
        "SELECT creator_id FROM recommendations WHERE run_id=? ORDER BY rank LIMIT 1", (run_id,)
    ).fetchone()[0]
    conn.close()

    response = client.get(f"/api/runs/{run_id}/proposal")
    assert response.status_code == 200
    proposal = response.json()
    assert len(proposal["picks"]) == expected[0]
    assert proposal["total_cost_vnd"] == expected[1]
    assert "metric:" not in proposal["picks"][0]["reason"]
    assert "skincare_revenue_share" not in proposal["picks"][0]["reason"]
    assert isinstance(proposal["picks"][0]["caveats"], list)
    assert all(pick["analysed_video_ids"] for pick in proposal["picks"])
    assert all("metric:" not in caveat for caveat in proposal["picks"][0]["caveats"])
    creator = client.get(f"/api/runs/{run_id}/creators/{creator_id}")
    assert creator.status_code == 200
    assert creator.json()["reasons"]
    assert client.get("/api/runs/missing/proposal").status_code == 404
    assert client.get(f"/api/runs/{run_id}/creators/missing").status_code == 404


def test_latest_run_excludes_mock_data(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    conn.execute("UPDATE runs SET params_json=json_set(params_json, '$.mock', 1)")
    conn.commit()
    conn.close()
    assert client.get("/api/runs/latest").status_code == 404


REAL_RUN_COPY = Path(os.environ.get(
    "KOC_REAL_RUN_COPY",
    "/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/integration/koc.db",
))


def test_real_run_copy_proposal_totals_and_evidence():
    if not REAL_RUN_COPY.is_file():
        import pytest
        pytest.skip("real-run copy is absent")
    media_dir = Path("/home/lystiger/Projects/KOC-Discovery/data/media")
    client = TestClient(create_app(str(REAL_RUN_COPY), str(media_dir)))
    run_id = "7372009b22764b339fbcf0f3efb4bc4e"
    response = client.get(f"/api/runs/{run_id}/proposal")
    assert response.status_code == 200
    proposal = response.json()
    assert len(proposal["picks"]) == 5
    assert proposal["total_cost_vnd"] == 28_500_000
    assert proposal["budget_vnd"] == 30_000_000
    assert all("metric:" not in pick["reason"] and "_share" not in pick["reason"] for pick in proposal["picks"])
    for pick in proposal["picks"]:
        creator = client.get(f"/api/runs/{run_id}/creators/{pick['creator_id']}").json()
        if creator["audience_text"]:
            assert "Không có dữ liệu" in creator["audience_text"]
            assert "S2" not in creator["scores"]
            assert all("female" not in key and "age_" not in key for key in creator["metrics"])
            assert all("metric:" not in item["text"] for item in creator["reasons"] + creator["caveats"])
        assert all(not video["title"].startswith("Video ") or video["title"] == "Video đã phân tích" for video in creator["videos"])
        pick_evidence_ids = [*pick["evidence_ids"], *pick["video_evidence_ids"]]
        pick_evidence_ids.extend(evidence for item in pick["caveat_evidence"] for evidence in item["evidence_ids"])
        assert pick["evidence_count"] <= len(pick_evidence_ids)
        creator_evidence_count = len(creator["video_evidence_ids"]) + sum(len(item["evidence_ids"]) for item in creator["reasons"] + creator["caveats"])
        assert all(len(item["evidence_ids"]) < creator_evidence_count for item in creator["reasons"] + creator["caveats"])
        for video in creator["videos"]:
            for item in video["evidence"]:
                if item["frame_url"]:
                    assert client.get(item["frame_url"]).status_code == 200


def test_real_recommendation_shape_maps_metric_labels_and_cited_evidence(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    recommendation = conn.execute(
        "SELECT run_id,rec_json FROM recommendations WHERE creator_id='c_linh_01' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    run_id, rec_json = recommendation
    rec = json.loads(rec_json)
    rec["reasons_vi"] = ["skincare_revenue_share and video_gpm support this choice."]
    rec["cited_evidence_ids"] = [
        "metric:c_linh_01:skincare_revenue_share",
        "v_c_linh_01_1@15.0s",
    ]
    conn.execute(
        "UPDATE recommendations SET rec_json=? WHERE run_id=? AND creator_id='c_linh_01'",
        (json.dumps(rec, ensure_ascii=False), run_id),
    )
    conn.commit()
    conn.close()

    conn = db.connect(database)
    reason, evidence_ids = _reason(conn, run_id, "c_linh_01", 88, None, 86)
    conn.close()
    assert "skincare_revenue_share" not in reason
    assert "video_gpm" not in reason
    assert "Tỷ trọng doanh thu ngành chăm sóc da" in reason
    assert "GPM video (doanh thu trên 1.000 lượt xem)" in reason
    assert evidence_ids == rec["cited_evidence_ids"]
    detail = client.get(f"/api/runs/{run_id}/creators/c_linh_01").json()
    assert detail["reasons"][0]["evidence_ids"] == ["metric:c_linh_01:skincare_revenue_share"]
    assert "v_c_linh_01_1@15.0s" in detail["video_evidence_ids"]
    assert "metric:" not in " ".join(detail["video_evidence_ids"])


def test_empty_database_has_no_match_pool(tmp_path):
    database = tmp_path / "empty.db"
    conn = db.connect(database)
    db.init_db(conn)
    conn.close()
    client = TestClient(create_app(str(database), str(tmp_path / "media")))
    response = client.post("/api/campaigns", json={
        "brand_name": "Mây Daily",
        "product_type": "Chống nắng",
        "budget_vnd": 60_000_000,
        "count": 5,
        "followers_min": 10_000,
        "followers_max": 300_000,
    })
    assert response.status_code == 200
    assert response.json()["result"]["run_id"] is None


def test_audience_placeholder_signatures_follow_core_rule(tmp_path):
    assert audience_is_placeholder([(None, None, None), (60, 30.5, 39.5)])
    assert audience_is_placeholder([(60, 30.5, 39.5)])
    assert audience_is_placeholder([(70, 20, 40)] * 3)
    assert not audience_is_placeholder([(70, 20, 40), (71, 20, 40), (70, 20, 40)])


def test_run_audience_placeholder_reads_s2_metrics(tmp_path):
    _, database = client_for(tmp_path)
    conn = db.connect(database)
    run_id = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    creator_ids = [row[0] for row in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S2'", (run_id,))]
    for creator_id in creator_ids:
        for name, value in (("female_pct", 60), ("age_18_24_pct", 30.5), ("age_25_34_pct", 39.5)):
            db.upsert_metric(conn, creator_id, name, value, "fixture", "last30Day")
    assert placeholder_audience_creators(conn, run_id) == set(creator_ids)
    campaign_input = {
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
    }
    pool, _ = get_pool(conn, campaign_input, [{"min_followers": 0, "max_followers": 1_000_000, "vnd_per_video": 1}])
    assert pool and all(item["audience"] is None for item in pool)
    result = match({"count": len(pool), "budget_vnd": 10_000_000, "avoid_same_mcn": False}, pool)
    assert all(item["components"]["audience"] is None for item in result["picked"])
    assert all(item["confidence"] != "Đầy đủ" for item in result["picked"])
    conn.close()


def test_no_s2_row_uses_pool_fill_for_fit_but_not_display_or_confidence(tmp_path):
    _, database = client_for(tmp_path)
    conn = db.connect(database)
    campaign_input = {
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
    }
    tiers = [{"min_followers": 0, "max_followers": 1_000_000, "vnd_per_video": 1}]
    before, _ = get_pool(conn, campaign_input, tiers)
    creator_before = next(item for item in before if item["creator_id"] == "c_linh_01")
    before_fit = match({"count": len(before), "budget_vnd": 100, "avoid_same_mcn": False}, before)
    before_fit = next(item["fit"] for item in before_fit["picked"] if item["creator_id"] == "c_linh_01")
    conn.execute("DELETE FROM scores WHERE creator_id=? AND stage='S2'", ("c_linh_01",))
    after, _ = get_pool(conn, campaign_input, tiers)
    scored = match({"count": len(after), "budget_vnd": 100, "avoid_same_mcn": False}, after)
    creator_after = next(item for item in scored["picked"] if item["creator_id"] == "c_linh_01")
    detail = _creator_detail(conn, "c_linh_01")
    conn.close()

    assert creator_before["audience"] is not None
    assert creator_after["components"]["audience"] is None
    assert creator_after["confidence"] == "Một phần"
    assert creator_after["fit"] <= before_fit
    assert "S2" not in detail["scores"]
    assert all(detail["metrics"].get(name, {}).get("value") is None for name in ("female_pct", "age_18_24_pct", "age_25_34_pct"))


def test_creator_detail_hides_placeholder_audience_scores_and_metrics(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    run_id = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    creator_ids = [row[0] for row in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S2'", (run_id,))]
    for creator_id in creator_ids:
        for name, value in (("female_pct", 60), ("age_18_24_pct", 30.5), ("age_25_34_pct", 39.5)):
            db.upsert_metric(conn, creator_id, name, value, "fixture", "last30Day")
    conn.close()

    detail = client.get("/api/creators/c_linh_01").json()
    assert "S2" not in detail["scores"]
    assert "female_pct" not in detail["metrics"]
    assert "age_18_24_pct" not in detail["metrics"]
    assert "age_25_34_pct" not in detail["metrics"]


def test_result_evidence_links_always_have_detail_targets(tmp_path):
    client, _ = client_for(tmp_path)
    campaign = client.post("/api/campaigns", json={
        "brand_name": "Mây Daily",
        "product_type": "Chống nắng",
        "budget_vnd": 60_000_000,
        "count": 5,
        "followers_min": 10_000,
        "followers_max": 300_000,
        "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
        "avoid_same_mcn": True,
    }).json()
    for creator in campaign["result"]["picked"] + campaign["result"]["alternates"]:
        detail = client.get(f"/api/creators/{creator['creator_id']}").json()
        metrics = {f"metric:{detail['creator_id']}:{name}" for name in detail["metrics"]}
        videos = {item["evidence_id"] for video in detail["videos"] for item in video["evidence"]}
        assert set(creator["evidence_ids"]) <= metrics | videos
        for reason in detail["reasons"] + detail["caveats"]:
            assert set(reason["evidence_ids"]) <= metrics | videos


def test_creator_above_rate_card_gets_nearest_estimated_tier(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    row = conn.execute("SELECT creator_id,data_json FROM creators WHERE creator_id='c_linh_01'").fetchone()
    data = json.loads(row["data_json"])
    data["creator_followers"] = 500_000
    conn.execute("UPDATE creators SET data_json=? WHERE creator_id=?", (json.dumps(data), row["creator_id"]))
    conn.commit()
    campaign_input = {
        "followers_min": 500_000,
        "followers_max": 500_000,
        "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
    }
    pool, _ = get_pool(conn, campaign_input, [{"min_followers": 10_000, "max_followers": 49_999, "vnd_per_video": 1_000_000}, {"min_followers": 50_000, "max_followers": 99_999, "vnd_per_video": 2_500_000}, {"min_followers": 100_000, "max_followers": 300_000, "vnd_per_video": 5_000_000}])
    conn.close()
    assert len(pool) == 1
    assert pool[0]["cost_vnd"] == 15_000_000


CAMPAIGN = {
    "brand_name": "Mây Daily", "product_type": "Chống nắng", "budget_vnd": 60_000_000, "count": 5,
    "followers_min": 10_000, "followers_max": 300_000,
    "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]}, "avoid_same_mcn": True,
}


def test_campaign_ok_reports_leftover(tmp_path):
    client, _ = client_for(tmp_path)
    result = client.post("/api/campaigns", json=CAMPAIGN).json()["result"]
    assert result["status"] == "ok" and result["budget_vnd"] == 60_000_000
    assert result["leftover_vnd"] == 60_000_000 - result["total_cost_vnd"] >= 0


def test_campaign_refused_when_budget_cannot_cover_count(tmp_path):
    client, _ = client_for(tmp_path)
    created = client.post("/api/campaigns", json={**CAMPAIGN, "budget_vnd": 3_000_000}).json()
    result = created["result"]
    assert result["status"] == "refused" and result["picks"] == [] and result["picked"] == []
    assert result["warnings"] and set(result["options"]) == {"max_count_within_budget", "min_budget_for_count", "cheaper_follower_band"}
    assert result["options"]["min_budget_for_count"]["budget_vnd"] > 3_000_000
    assert client.get(f"/api/campaigns/{created['campaign_id']}").json()["result"] == result


def test_cheaper_follower_band_option_fits_budget_in_cheaper_tier(tmp_path):
    client, _ = client_for(tmp_path)
    request = {**CAMPAIGN, "budget_vnd": 16_000_000, "count": 2, "followers_min": 100_000}
    result = client.post("/api/campaigns", json=request).json()["result"]
    assert result["status"] == "refused"
    assert result["options"]["cheaper_follower_band"] == {"follower_min": 50_000, "follower_max": 99_999, "cost_vnd": 15_000_000}
    assert result["options"]["max_count_within_budget"] == {"count": 1, "cost_vnd": 15_000_000}
    assert result["options"]["min_budget_for_count"] == {"budget_vnd": 30_000_000}


def test_old_stored_campaign_without_status_still_renders(tmp_path):
    client, database = client_for(tmp_path)
    conn = db.connect(database)
    campaigns.ensure_table(conn)
    saved = campaigns.save(conn, CAMPAIGN, {"picked": [], "alternates": [], "total_cost_vnd": 1_000_000, "warning": None, "ranked_count": 0, "run_id": None, "low_confidence_pool": False})
    conn.close()
    result = client.get(f"/api/campaigns/{saved['campaign_id']}").json()["result"]
    assert result["status"] == "ok" and result["leftover_vnd"] == 59_000_000 and result["warnings"] == []


def test_saved_campaign_without_analysed_video_ids_is_enriched_on_get(tmp_path):
    import json
    client, database = client_for(tmp_path)
    created = client.post("/api/campaigns", json=CAMPAIGN).json()
    stored = created["result"]
    assert stored["picked"] and stored["run_id"]
    old = {**stored, "picked": [{k: v for k, v in c.items() if k != "analysed_video_ids"} for c in stored["picked"]]}
    conn = db.connect(database)
    conn.execute("UPDATE campaigns SET result_json=? WHERE campaign_id=?", (json.dumps(old), created["campaign_id"]))
    conn.commit()
    loaded = client.get(f"/api/campaigns/{created['campaign_id']}").json()["result"]["picked"]
    for creator in loaded:
        expected = [row[0] for row in db.run_analyses(conn, stored["run_id"], creator["creator_id"])]
        assert expected and creator["analysed_video_ids"] == expected
    conn.close()
