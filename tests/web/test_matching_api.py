import pytest
from fastapi.testclient import TestClient

from koc import db
from koc.config import load_config
from koc.pipeline import _rate
from koc.web.app import create_app
from koc.web.matching_api import _estimated_cost, run_command
from tests.analysis_seed import seed_brand_fit
from tests.web.fixtures.seed import seed_fixture_db

TIERS = load_config()["rate_card"]["tiers"]
FORM = {
    "brand_name": "Mây Daily", "product_type": "Chống nắng", "budget_vnd": 3_000_000, "count": 1,
    "followers_min": 10_000, "followers_max": 300_000, "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
    "avoid_same_mcn": True,
}


def client_with(tmp_path, followers, product_type=None, status="done"):
    tmp_path.mkdir(exist_ok=True)
    database = tmp_path / "web.db"
    conn = db.connect(database)
    db.init_db(conn)
    run_id = db.create_run(conn, {"brief": {"product_type": product_type} if product_type else {}})
    conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
    conn.commit()
    for index, count in enumerate(followers):
        creator_id = f"c{index}"
        db.upsert_creator(conn, creator_id, f"@{creator_id}", {"creator_followers": count, "creator_nickname": creator_id})
        for stage, score in (("S1", 80 - index), ("S2", 70), ("S3", 60)):
            db.upsert_score(conn, run_id, creator_id, stage, score, {})
        seed_brand_fit(conn, creator_id)
    conn.close()
    return TestClient(create_app(str(database), str(tmp_path / "media")))


def post(client, **changes):
    return client.post("/api/campaigns", json={**FORM, **changes}).json()["result"]


@pytest.mark.parametrize("followers", [10_000, 49_999, 50_000, 99_999, 100_000, 300_000])
def test_web_cost_equals_pipeline_rate_in_rate_card(followers):
    assert _estimated_cost(followers, TIERS) == _rate(followers) > 0


def test_one_video_budget_is_refused_and_three_video_budget_fits(tmp_path):
    refused = post(client_with(tmp_path / "a", [20_000]), budget_vnd=1_000_000)
    assert refused["status"] == "refused" and refused["picked"] == []
    assert refused["options"]["min_budget_for_count"] == {"budget_vnd": 3_000_000}
    fits = post(client_with(tmp_path / "b", [20_000]), budget_vnd=3_000_000)
    assert fits["status"] == "ok" and fits["total_cost_vnd"] == 3_000_000 and fits["leftover_vnd"] == 0


def test_minimum_budget_option_uses_three_video_rate(tmp_path):
    result = post(client_with(tmp_path, [150_000]), budget_vnd=1_000_000)
    assert result["options"]["min_budget_for_count"] == {"budget_vnd": _rate(150_000)} == {"budget_vnd": 15_000_000}


def test_cheaper_band_found_when_range_is_outside_rate_card(tmp_path):
    result = post(client_with(tmp_path, [500_000, 20_000]), followers_min=400_000, followers_max=600_000)
    assert result["status"] == "refused"
    assert result["options"]["min_budget_for_count"] == {"budget_vnd": 15_000_000}
    assert result["options"]["cheaper_follower_band"] == {"follower_min": 10_000, "follower_max": 49_999, "cost_vnd": 3_000_000}


def test_no_run_for_product_type_needs_run_with_exact_command(tmp_path):
    result = post(client_with(tmp_path, [20_000]), product_type="Serum", budget_vnd=30_000_000, count=5)
    assert result["status"] == "needs_run" and result["picked"] == [] and result["picks"] == []
    assert result["warnings"] == [] and result["warning"] is None and result["options"] is None
    assert result["total_cost_vnd"] == 0 and result["leftover_vnd"] == result["budget_vnd"] == 30_000_000
    assert result["run_command"] == "koc run --dry-run --product-type Serum --gender nu --age-min 18 --age-max 34 --budget 30000000 --count 5"
    assert result["run_command_notes"] == []


def test_needs_run_carries_run_estimate_ranges(tmp_path):
    estimate = post(client_with(tmp_path, [20_000]), product_type="Serum")["run_estimate"]
    assert estimate["label"] == "ước tính"
    for key in ("credits", "usd", "tokens", "minutes"):
        assert estimate[key]["low"] <= estimate[key]["high"]
    assert estimate["credits"] == {"low": 27.6, "high": 29.4}


def test_run_with_matching_product_type_matches(tmp_path):
    assert post(client_with(tmp_path, [20_000], "Serum"), product_type="Serum")["status"] == "ok"


def test_run_that_is_not_done_does_not_count(tmp_path):
    assert post(client_with(tmp_path, [20_000], status="running"))["status"] == "needs_run"


def test_legacy_fixture_db_without_product_type_matches_chong_nang(tmp_path):
    database = tmp_path / "fixture.db"
    seed_fixture_db(database, tmp_path / "media")
    client = TestClient(create_app(str(database), str(tmp_path / "media")))
    assert post(client, budget_vnd=60_000_000, count=5)["status"] == "ok"
    assert post(client, product_type="Trang điểm")["status"] == "needs_run"


def test_khac_adds_category_placeholder_and_note():
    command, notes = run_command({**FORM, "product_type": "Khác"})
    assert command.endswith('--category-ids "<id>"')
    assert notes == ["Thay <id> bằng mã ngành Kalodata, tìm bằng `koc categories --keyword <từ khóa>`."]


def test_precheck_refusal_comes_first_in_notes():
    command, notes = run_command({**FORM, "budget_vnd": 5_000_000, "count": 3, "followers_min": 50_000})
    assert command.startswith("koc run --dry-run --product-type")
    assert notes[0].startswith("Ngân sách 5.000.000 VND không đủ cho 3 KOC") and "giảm --count xuống tối đa 1 KOC" in notes[0]
    assert "nhóm follower rẻ nhất là 10k-50k" in notes[0]
    assert "pipeline" in notes[1]
    assert run_command({**FORM, "budget_vnd": 9_000_000, "count": 3})[1] == []


@pytest.mark.parametrize("groups,expected", [
    (["18-24"], "--age-min 18 --age-max 24"), (["25-34"], "--age-min 25 --age-max 34"),
    (["35-44", "45-54"], "--age-min 35 --age-max 54"), (["55+"], "--age-min 55 --age-max 99"),
    (["45-54", "55+"], "--age-min 45 --age-max 99"), (["18-24", "25-34", "35-44", "45-54", "55+"], "--age-min 18 --age-max 99"),
])
def test_age_groups_map_to_cli_flags(groups, expected):
    assert expected in run_command({**FORM, "target": {"gender": "Nữ", "age_groups": groups}})[0]


@pytest.mark.parametrize("gender,flag", [("Nữ", "nu"), ("Nam", "nam"), ("Tất cả", "tat-ca")])
def test_gender_maps_to_cli_flag(gender, flag):
    assert f"--gender {flag} " in run_command({**FORM, "target": {"gender": gender, "age_groups": ["18-24"]}})[0]


def test_product_text_is_shell_quoted_and_default_is_omitted():
    command, _ = run_command({**FORM, "product_specs": "Kem 'SPF50' $(rm -rf /)"})
    assert command.endswith(""" --product 'Kem '"'"'SPF50'"'"' $(rm -rf /)'""")
    assert "--product " not in run_command({**FORM, "product_specs": "chống nắng"})[0]
    assert "--product " not in run_command(FORM)[0]


def test_pipeline_and_web_share_one_cost_function_with_nearest_tier_fallback():
    from koc.brief import cheapest_tier
    from koc.pricing import creator_cost

    assert [_rate(n) for n in (5_000, 20_000, 500_000)] == [3_000_000, 3_000_000, 15_000_000]
    assert all(_rate(n) == _estimated_cost(n, TIERS) == creator_cost(n, TIERS) > 0 for n in (0, 5_000, 75_000, 1_000_000))
    assert cheapest_tier(load_config())[0] == _rate(20_000)


def test_run_command_appends_exclude_run_flags():
    command, _ = run_command({**FORM, "exclude_run_ids": ["abc123", "d e"]})
    assert command.endswith("--exclude-run abc123 --exclude-run 'd e'")
    assert "--exclude-run" not in run_command(FORM)[0]
    assert "--exclude-run" not in run_command({**FORM, "exclude_run_ids": []})[0]


def test_http_exclude_run_ids_saved_and_in_command(tmp_path):
    ids = ["a" * 32, "0123456789abcdef0123456789abcdef"]
    client = client_with(tmp_path, [20_000])
    body = client.post("/api/campaigns", json={**FORM, "product_type": "Serum", "exclude_run_ids": ids}).json()
    assert body["result"]["run_command"].endswith(" ".join(f"--exclude-run {i}" for i in ids))
    saved = client.get(f"/api/campaigns/{body['campaign_id']}").json()
    assert saved["input"]["exclude_run_ids"] == ids


@pytest.mark.parametrize("bad", ["abc123", "x" * 32, "a; rm -rf /", "A" * 32])
def test_http_exclude_run_ids_rejects_garbage(tmp_path, bad):
    response = client_with(tmp_path, [20_000]).post("/api/campaigns", json={**FORM, "exclude_run_ids": [bad]})
    assert response.status_code == 422


def _client_with_picks(tmp_path, followers, picked):
    client = client_with(tmp_path, followers, "Serum")
    conn = db.connect(tmp_path / "web.db")
    run_id = conn.execute("SELECT run_id FROM runs").fetchone()[0]
    for rank, creator_id in enumerate(picked, 1):
        conn.execute("INSERT INTO recommendations(run_id,creator_id,rank,est_cost_vnd,rec_json) VALUES (?,?,?,?,'{}')", (run_id, creator_id, rank, 3_000_000))
    conn.commit()
    conn.close()
    return client, run_id


def test_http_exclusion_applies_to_cached_matching(tmp_path):
    client, run_id = _client_with_picks(tmp_path, [20_000] * 5, ["c0", "c1"])
    kept = post(client, product_type="Serum", count=2, budget_vnd=30_000_000)
    assert {p["creator_id"] for p in kept["picked"]} == {"c0", "c1"}
    result = post(client, product_type="Serum", count=2, budget_vnd=30_000_000, exclude_run_ids=[run_id])
    assert result["status"] == "ok" and len(result["picked"]) == 2
    assert not {p["creator_id"] for p in result["picked"]} & {"c0", "c1"}


def test_http_exclusion_leaving_too_few_gives_needs_run_with_flags(tmp_path):
    client, run_id = _client_with_picks(tmp_path, [20_000] * 3, ["c0", "c1"])
    result = post(client, product_type="Serum", count=2, budget_vnd=30_000_000, exclude_run_ids=[run_id])
    assert result["status"] == "needs_run" and result["picks"] == []
    assert result["run_command"].endswith(f"--exclude-run {run_id}")
    assert result["options"] is not None


def test_http_budget_refusal_stays_refused_with_exclusion(tmp_path):
    client, run_id = _client_with_picks(tmp_path, [20_000] * 2, [])
    other = db.connect(tmp_path / "web.db")
    run2 = db.create_run(other, {})
    other.execute("INSERT INTO recommendations(run_id,creator_id,rank,est_cost_vnd,rec_json) VALUES (?,?,?,?,'{}')", (run2, "outside", 1, 3_000_000))
    other.commit()
    other.close()
    result = post(client, product_type="Serum", count=2, budget_vnd=1_000_000, exclude_run_ids=[run2])
    assert result["status"] == "refused" and result["warnings"] and result["options"]["min_budget_for_count"]


def test_previous_runs_lists_done_runs_with_picks(tmp_path):
    client, run_id = _client_with_picks(tmp_path, [20_000] * 3, ["c0", "c1"])
    rows = client.get("/api/runs/previous", params={"product_type": "Serum"}).json()
    assert rows == [{"run_id": run_id, "started_at": rows[0]["started_at"], "creator_ids": ["c0", "c1"]}]
    assert client.get("/api/runs/previous", params={"product_type": "Chống nắng"}).json() == []
    assert client.get("/api/runs/previous").json() == []


def test_previous_runs_skips_runs_without_picks(tmp_path):
    client = client_with(tmp_path, [20_000], "Serum")
    assert client.get("/api/runs/previous", params={"product_type": "Serum"}).json() == []


def test_creator_search_ignores_diacritics(tmp_path):
    client = client_with(tmp_path, [20_000], "Serum")
    conn = db.connect(tmp_path / "web.db")
    db.upsert_creator(conn, "cv", "@chong_nang", {"creator_followers": 20_000, "creator_nickname": "Chống nắng Đẹp"})
    conn.commit()
    conn.close()
    for query in ("chong nang", "chống nắng", "dep"):
        assert [row["creator_id"] for row in client.get("/api/creators", params={"q": query}).json()] == ["cv"]


def test_previous_runs_get_does_not_modify_database(tmp_path):
    client, _ = _client_with_picks(tmp_path, [20_000] * 3, ["c0"])
    database = tmp_path / "web.db"
    before = database.read_bytes()
    assert client.get("/api/runs/previous", params={"product_type": "Serum"}).status_code == 200
    assert database.read_bytes() == before
    conn = db.connect(database)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='campaigns'").fetchone() is None
    conn.close()


def test_previous_runs_applies_eligibility_before_the_limit_of_ten(tmp_path):
    client, run_id = _client_with_picks(tmp_path, [20_000] * 3, ["c0"])
    conn = db.connect(tmp_path / "web.db")
    for _ in range(10):  # ten newer finished runs without picks
        newer = db.create_run(conn, {"brief": {"product_type": "Serum"}})
        conn.execute("UPDATE runs SET status='done' WHERE run_id=?", (newer,))
    conn.commit()
    conn.close()
    assert [row["run_id"] for row in client.get("/api/runs/previous", params={"product_type": "Serum"}).json()] == [run_id]


def test_campaign_result_sends_scored_pool_with_per_video_price(tmp_path):
    client = client_with(tmp_path, [20_000, 70_000, 150_000, 30_000, 260_000, 90_000, 120_000, 40_000, 45_000, 80_000, 110_000, 200_000], "Serum")
    result = post(client, product_type="Serum", count=2, budget_vnd=30_000_000)
    pool = result["ranked_pool"]
    assert len(pool) == 12 > len(result["picked"]) + len(result["alternates"])
    assert [item["fit"] for item in pool] == sorted((item["fit"] for item in pool), reverse=True)
    assert {item["followers"]: item["price_per_video_vnd"] for item in pool} == {
        20_000: 1_000_000, 30_000: 1_000_000, 40_000: 1_000_000, 45_000: 1_000_000, 80_000: 2_500_000, 110_000: 5_000_000, 200_000: 5_000_000, 70_000: 2_500_000, 90_000: 2_500_000, 120_000: 5_000_000, 150_000: 5_000_000, 260_000: 5_000_000}
    assert all(item["cost_vnd"] == 3 * item["price_per_video_vnd"] for item in pool)
    assert {item["creator_id"] for item in result["picked"]} <= {item["creator_id"] for item in pool}
