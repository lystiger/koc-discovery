import json
import socket

import pytest
from typer.testing import CliRunner

import koc.cli as cli
import koc.pipeline as pipeline
from koc import db
from koc.brief import brand_brief, check_brief, make_brief, run_brief
from koc.pipeline import MockKalodataClient, leftover_line, resume, start
from koc.stages import audience_score
from koc.types import BrandBrief, Recommendation, Usage
from tests.analysis_seed import seed_brand_fit

METRICS = {"female_pct": 70.0, "age_18_24_pct": 30.0, "age_25_34_pct": 40.0}


def _conn(tmp_path, monkeypatch, name="brief.db"):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / name)
    db.init_db(conn)
    return conn


def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *_: (_ for _ in ()).throw(AssertionError("network attempted")))


def test_default_brief_equals_todays_hard_coded_values(stable_test_config):
    brief = make_brief(stable_test_config)
    assert (brief["product"], brief["target"], brief["budget_vnd"], brief["count"]) == ("kem chống nắng", "Nữ, 18-30 tuổi", 30_000_000, 5)
    assert brief["category_ids"] == stable_test_config["scoring"]["s0"]["category_ids"]
    assert brand_brief(brief) == BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ, 18-30 tuổi", budget_vnd=30_000_000)


def test_run_without_brief_key_falls_back_to_defaults(tmp_path, stable_test_config):
    conn = db.connect(tmp_path / "old.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 5, "mock": True})
    assert run_brief(conn, run_id, stable_test_config) == make_brief(stable_test_config)


def test_stored_brief_drives_s0_s4_and_reports_leftover(tmp_path, monkeypatch, stable_test_config):
    conn = _conn(tmp_path, monkeypatch)
    seen = []
    real = MockKalodataClient.creator_rank
    monkeypatch.setattr(MockKalodataClient, "creator_rank", lambda self, **kw: seen.append(kw) or real(self, **kw))
    brief = make_brief(stable_test_config, product="serum vitamin C", category_ids=[], count=3, budget=10_000_000)
    run_id = start(conn, limit=20, mock=True, brief=brief)
    assert json.loads(conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])["brief"] == brief
    assert seen[0]["keyword"] == "serum vitamin C" and not seen[0]["category_ids"]
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 3
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"
    total = conn.execute("SELECT SUM(est_cost_vnd) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0]
    assert total == 9_000_000
    assert json.loads(conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])["s4"] == {"total_vnd": 9_000_000, "budget_vnd": 10_000_000, "leftover_vnd": 1_000_000}
    assert "còn dư 1.000.000 VND, không dùng" in leftover_line(conn, run_id)

    seen.clear()
    start(conn, limit=20, mock=True, brief=make_brief(stable_test_config, category_ids=["111", "222"], count=3, budget=10_000_000))
    assert seen[0]["category_ids"] == ["111", "222"] and "keyword" not in seen[0]


def test_brief_reaches_llm_s3_and_s4(tmp_path, monkeypatch, stable_test_config):
    from koc import llm
    conn = _conn(tmp_path, monkeypatch)
    brief = make_brief(stable_test_config, product="kem dưỡng da", gender="nam", age_min=25, age_max=34, budget=12_000_000, count=2)
    run_id = db.create_run(conn, {"brief": brief})
    expected = BrandBrief(product_vi="kem dưỡng da", audience_vi="Nam, 25-34 tuổi", budget_vnd=12_000_000)

    db.upsert_creator(conn, "c1", "creator", {"creator_followers": 30000})
    (tmp_path / "v1.mp4").write_bytes(b"video")
    received = []
    monkeypatch.setattr(llm, "analyze_video", lambda video, b, *, budget_guard, frames_dir: received.append(b) or pipeline._fake_analysis(video))

    class Client:
        def video_rank(self, *_a, **_k):
            return [{"video_id": "v1", "views": 100}]

    pipeline._s3_creator(conn, run_id, Client(), "c1", media_dir=tmp_path)
    assert received == [expected]

    for index in range(3):
        creator_id = f"s{index}"
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        for stage in ("S1", "S2", "S3"):
            db.upsert_score(conn, run_id, creator_id, stage, 70, {})
        seed_brand_fit(conn, creator_id)
        db.upsert_metric(conn, creator_id, "female_pct", 40.0, "test")
    briefs = []

    def fake_cached(conn_, run, kind, key, version, model, b, function, summary, *args, **kwargs):
        briefs.append(b)
        usage = Usage(provider="gemini", model="m", prompt_version=version, input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0)
        return Recommendation(creator_id=summary.creator_id, reasons_vi=["a", "b", "c"], cited_evidence_ids=[], caveats_vi=[], usage=usage)

    monkeypatch.setattr(pipeline, "_cached_call", fake_cached)
    pipeline._s4(conn, run_id)(conn)
    assert briefs == [expected, expected]
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 2


def test_s2_score_honours_gender_and_age(stable_test_config):
    assert audience_score(METRICS) == 70.0
    assert audience_score(METRICS, "nam") == 50.0
    assert audience_score(METRICS, "tat-ca") == 70.0
    assert audience_score(METRICS, "nu", 25, 34) == 55.0
    assert audience_score(METRICS, "nu", 18, 24) == 50.0
    assert audience_score({"age_18_24_pct": 30.0}, "nam") == 15.0
    brief = make_brief(stable_test_config, gender="nam", age_min=25, age_max=34)
    conn = db.connect(":memory:")
    db.init_db(conn)
    pipeline._s2_write("r", "c1", METRICS, "src", brief)(conn)
    assert conn.execute("SELECT score FROM scores WHERE stage='S2'").fetchone()[0] == 35.0


def test_resume_refuses_brief_change(tmp_path, monkeypatch, stable_test_config):
    conn = _conn(tmp_path, monkeypatch)
    start(conn, limit=20, mock=True, brief=make_brief(stable_test_config, count=3, budget=10_000_000))
    with pytest.raises(RuntimeError, match="Không thể đổi brief.*budget_vnd"):
        resume(conn, mock=True, brief={"budget_vnd": 20_000_000, "count": 3})
    resume(conn, mock=True, brief={"budget_vnd": 10_000_000, "count": 3, "product": None})
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "brief.db")
    result = CliRunner().invoke(cli.app, ["resume", "--count", "4"])
    assert result.exit_code == 1 and "Không thể đổi brief" in result.output


@pytest.mark.parametrize("dry", [True, False])
def test_precheck_refuses_before_any_network_or_db(tmp_path, monkeypatch, stable_test_config, dry):
    db_path = tmp_path / "never.db"
    monkeypatch.setattr(cli, "DB_PATH", db_path)
    _no_network(monkeypatch)
    extra = ["--dry-run"] if dry else []
    result = CliRunner().invoke(cli.app, ["run", "--count", "16", *extra])
    assert result.exit_code == 1
    assert "tối đa 15 creator mỗi lượt chạy" in result.output
    result = CliRunner().invoke(cli.app, ["run", "--count", "3", "--budget", "8000000", *extra])
    assert result.exit_code == 1
    for part in ("giảm --count xuống tối đa 2 KOC", "tối thiểu 9.000.000 VND cho 3 KOC", "10k-50k"):
        assert part in result.output
    assert not db_path.exists()


def test_dry_run_other_product_prints_brief(tmp_path, monkeypatch, stable_test_config):
    _no_network(monkeypatch)
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "never.db")
    result = CliRunner().invoke(cli.app, ["run", "--dry-run", "--product", "son môi", "--category-ids", "1,2", "--gender", "tat-ca", "--age-min", "25", "--age-max", "34", "--budget", "9000000", "--count", "3"])
    assert result.exit_code == 0, result.output
    assert "Brief: son môi · Mọi giới, 25-34 tuổi · 3 KOC · ngân sách 9.000.000 VND." in result.output
    assert "Danh mục: 1, 2." in result.output and "S4 chọn 3" in result.output


def test_s4_blocked_lists_three_options_from_actual_creators(tmp_path, monkeypatch, stable_test_config):
    conn = _conn(tmp_path, monkeypatch)
    run_id = db.create_run(conn, {"mock": True, "brief": make_brief(stable_test_config)})
    for creator_id, followers in [("expensive", 100000), *((f"c{i}", 50000) for i in range(1, 5)), ("cheap", 30000)]:
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": followers})
        for stage in ("S1", "S2", "S3"):
            db.upsert_score(conn, run_id, creator_id, stage, 80, {})
        seed_brand_fit(conn, creator_id)
        db.upsert_metric(conn, creator_id, "female_pct", 70, "test")
    db.add_task(conn, run_id, "S4", "select")
    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    pipeline.execute(conn, run_id, object(), 1, mock=True)
    error = db.get_task(conn, f"{run_id}:S4:select")["error"]
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 0
    for part in ("(1) giảm còn 4 KOC (tốn 25.500.000 VND)", "(2) tăng ngân sách lên tối thiểu 33.000.000 VND cho 5 KOC", "(3) nhóm follower rẻ nhất trong danh sách là 10k-50k"):
        assert part in error


def test_count_3_budget_9m_runs_end_to_end_in_mock(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "e2e.db")
    result = CliRunner().invoke(cli.app, ["run", "--mock", "--limit", "20", "--count", "3", "--budget", "9000000"])
    assert result.exit_code == 0, result.output
    assert "còn dư 0 VND" in result.output
    status = CliRunner().invoke(cli.app, ["status"])
    assert "brief: kem chống nắng, Nữ, 18-30 tuổi, 3 KOC, 9.000.000 VND" in status.output
    conn = db.connect(tmp_path / "e2e.db")
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 3


def _seed_scored(conn, run_id, count, followers=30000):
    for index in range(count):
        creator_id = f"c{index}"
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": followers})
        for stage in ("S1", "S2", "S3"):
            db.upsert_score(conn, run_id, creator_id, stage, 80, {})
        seed_brand_fit(conn, creator_id)
        db.upsert_metric(conn, creator_id, "female_pct", 70, "test")


def test_top5_returns_full_selection_for_count_above_five(tmp_path, stable_test_config):
    from koc import queries
    from koc.web.adapter import get_top5_with_details
    conn = db.connect(tmp_path / "six.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"mock": True, "brief": make_brief(stable_test_config, count=6, budget=18_000_000)})
    _seed_scored(conn, run_id, 6)
    db.add_task(conn, run_id, "S4", "select")
    pipeline.execute(conn, run_id, object(), mock=True)
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 6
    assert [row["rank"] for row in queries.top5(conn, run_id)] == [1, 2, 3, 4, 5, 6]
    view = get_top5_with_details(conn, run_id)
    assert (len(view["cards"]), view["total_estimated_cost_vnd"], view["budget_remaining_vnd"]) == (6, 18_000_000, 0)


def test_top5_legacy_run_without_brief_still_capped_at_five(tmp_path):
    from koc import queries
    conn = db.connect(tmp_path / "legacy.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"mock": True})
    for rank in range(1, 8):
        seed_brand_fit(conn, f"c{rank}")
        conn.execute("INSERT INTO recommendations(run_id,creator_id,rank,est_cost_vnd,rec_json) VALUES (?,?,?,?,?)", (run_id, f"c{rank}", rank, 1, "{}"))
    assert [row["rank"] for row in queries.top5(conn, run_id)] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("scored,count,budget,expected", [
    (2, 3, 9_000_000, ["Chưa đủ điểm nội dung để đề xuất: có 2, cần 3.", "(1) giảm còn 2 KOC (tốn 6.000.000 VND)", "(2) không có", "(3) nhóm follower rẻ nhất trong danh sách là 10k-50k"]),
    (0, 1, 3_000_000, ["có 0, cần 1.", "(1) không có", "(2) không có", "(3) không có"]),
])
def test_underfilled_s4_gives_three_options(tmp_path, stable_test_config, scored, count, budget, expected):
    conn = db.connect(tmp_path / "under.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"mock": True, "brief": make_brief(stable_test_config, count=count, budget=budget)})
    _seed_scored(conn, run_id, scored)
    task_id = db.add_task(conn, run_id, "S4", "select")
    pipeline.execute(conn, run_id, object(), mock=True)
    error = db.get_task(conn, task_id)["error"]
    assert all(part in error for part in expected), error
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 0


def test_age_range_overlap_rules(stable_test_config):
    assert audience_score(METRICS, "nu", 35, 44) is None
    assert audience_score(METRICS, "tat-ca", 55, 99) is None
    assert audience_score(METRICS, "nu", 25, 44) == 55.0  # only the 25-34 band overlaps
    assert audience_score(METRICS, "nu", 18, 99) == 70.0
    for age_min, age_max, ok in [(18, 99, True), (35, 44, True), (55, 99, True), (17, 30, False), (18, 100, False), (40, 30, False)]:
        error = check_brief(make_brief(stable_test_config, age_min=age_min, age_max=age_max), stable_test_config)
        assert (error is None) == ok, (age_min, age_max, error)


def test_no_band_overlap_stores_null_s2_and_renormalises(tmp_path, stable_test_config):
    from koc.stages import final_score
    from koc.web.adapter import get_top5_with_details
    conn = db.connect(tmp_path / "age.db")
    db.init_db(conn)
    brief = make_brief(stable_test_config, age_min=35, age_max=44, count=2, budget=6_000_000)
    run_id = db.create_run(conn, {"mock": True, "brief": brief})
    for index, female in enumerate((70.0, 71.0, 72.0)):
        creator_id = f"c{index}"
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.upsert_score(conn, run_id, creator_id, "S1", 80, {})
        db.upsert_score(conn, run_id, creator_id, "S3", 60, {})
        seed_brand_fit(conn, creator_id)
        pipeline._s2_write(run_id, creator_id, {"female_pct": female, "age_18_24_pct": 20.0, "age_25_34_pct": 30.0}, "src", brief)(conn)
    assert conn.execute("SELECT COUNT(*) FROM scores WHERE stage='S2' AND score IS NULL").fetchone()[0] == 3
    assert all(abs(item["final"] - final_score(80, None, 60)) < 1e-9 for item in pipeline._best_five(conn, run_id))
    db.add_task(conn, run_id, "S4", "select")
    pipeline.execute(conn, run_id, object(), mock=True)
    cards = get_top5_with_details(conn, run_id)["cards"]
    assert len(cards) == 2 and all(card["audience_score"] is None for card in cards)


def test_product_categories_keys_match_web_literals_and_chong_nang_keeps_today(stable_test_config):
    from typing import get_args
    from koc.web.api import CampaignInput
    types = stable_test_config["product_categories"]
    assert list(types) == list(get_args(CampaignInput.model_fields["product_type"].annotation))
    assert types["Chống nắng"] == stable_test_config["scoring"]["s0"]["category_ids"]
    assert types["Khác"] == []


def test_product_type_fills_categories_and_explicit_ids_win(stable_test_config):
    brief = make_brief(stable_test_config, product_type="Serum")
    assert (brief["product_type"], brief["product"], brief["category_ids"]) == ("Serum", "serum", ["601619"])
    brief = make_brief(stable_test_config, product_type="Serum", product="vitamin C", category_ids=["1", "2"])
    assert (brief["product"], brief["category_ids"]) == ("vitamin C", ["1", "2"])
    assert make_brief(stable_test_config)["product_type"] is None


def test_product_type_without_ids_is_refused(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "never.db")
    _no_network(monkeypatch)
    result = CliRunner().invoke(cli.app, ["run", "--product-type", "Khác", "--dry-run"])
    assert result.exit_code == 1 and "--category-ids" in result.output and "koc categories --keyword" in result.output
    result = CliRunner().invoke(cli.app, ["run", "--product-type", "Khác", "--category-ids", "1,2", "--dry-run"])
    assert result.exit_code == 0 and "Danh mục: 1, 2." in result.output
    result = CliRunner().invoke(cli.app, ["run", "--product-type", "Nhà cửa", "--dry-run"])
    assert result.exit_code == 1 and "Loại sản phẩm không hợp lệ" in result.output
    assert not (tmp_path / "never.db").exists()


def test_product_type_stored_in_brief_and_used_by_s0(tmp_path, monkeypatch, stable_test_config):
    conn = _conn(tmp_path, monkeypatch)
    seen = []
    real = MockKalodataClient.creator_rank
    monkeypatch.setattr(MockKalodataClient, "creator_rank", lambda self, **kw: seen.append(kw) or real(self, **kw))
    run_id = start(conn, limit=20, mock=True, brief=make_brief(stable_test_config, product_type="Làm sạch", count=2, budget=6_000_000))
    stored = json.loads(conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])["brief"]
    assert stored["product_type"] == "Làm sạch" and stored["category_ids"] == ["601609", "601618"]
    assert seen[0]["category_ids"] == ["601609", "601618"]


def test_all_none_s2_picks_top_s1_creators(tmp_path, stable_test_config):
    conn = db.connect(tmp_path / "order.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"mock": True})
    for index, s1 in enumerate((10, 90, 50, 70)):
        creator_id = f"c{index}"
        db.upsert_score(conn, run_id, creator_id, "S1", s1, {})
        db.upsert_score(conn, run_id, creator_id, "S2", None, {})
        db.upsert_metric(conn, creator_id, "female_pct", 70, "test")
    assert pipeline._s2_top(conn, run_id, 3) == ["c1", "c3", "c2"]
    db.upsert_score(conn, run_id, "c0", "S2", 20, {})  # a real S2 score still beats NULLs
    assert pipeline._s2_top(conn, run_id, 2) == ["c0", "c1"]


def test_operator_view_shows_brief_count_not_five(tmp_path, stable_test_config):
    from fastapi.testclient import TestClient
    from koc.web.app import create_app
    db_path = tmp_path / "view.db"
    conn = db.connect(db_path)
    db.init_db(conn)
    run_id = db.create_run(conn, {"mock": True, "brief": make_brief(stable_test_config, product="serum", count=6, budget=18_000_000)})
    _seed_scored(conn, run_id, 6)
    db.add_task(conn, run_id, "S4", "select")
    pipeline.execute(conn, run_id, object(), mock=True)
    conn.close()
    html = TestClient(create_app(db_path=str(db_path), media_dir=str(tmp_path))).get(f"/runs/{run_id}").text
    assert "6 / 6" in html and "/ 5<" not in html and "serum" in html
