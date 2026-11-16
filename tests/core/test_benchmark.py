import json

import pytest
from typer.testing import CliRunner

from koc import db
from koc.benchmark import aggregate, build, project
from koc.benchmark_render import render_markdown
from koc.cli import app

RUN, OTHER = "run-live", "run-stale"


def _api(conn, run_id, endpoint, status, credits, created, request_hash=None, cache_hit=0):
    conn.execute("INSERT INTO api_calls(run_id,endpoint,request_hash,status,credits,latency_ms,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?)",
                 (run_id, endpoint, request_hash or f"{endpoint}-{status}-{created}", status, credits, 1000, cache_hit, created))


def _llm(conn, run_id, kind, h, pv, tin, tout, usd, cache_hit=0):
    conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (run_id, kind, h, "m", pv, tin, tout, 500, usd, cache_hit, "2026-01-01T00:00:00"))


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "bench.db")
    db.init_db(c)
    for run_id in (RUN, OTHER):
        c.execute("INSERT INTO runs VALUES (?,?,NULL,'done',?)", (run_id, "2026-01-01", json.dumps(
            {"limit": 10, "mock": False, "stage_wall_ms": {"S0": 1000, "S1b": 2000, "S2": 3000, "S3": 4000, "S4": 500}})))
    for stage, key, status, at in (("S0", "c", "done", "2026-01-01T00:00:01"), ("S1a", "c1", "done", "2026-01-01T00:00:02"),
                                   ("S1b", "c1", "done", "2026-01-01T00:00:10"), ("S2", "c1", "done", "2026-01-01T00:00:20"),
                                   ("S3", "c1", "done", "2026-01-01T00:00:30"), ("S4", "select", "done", "2026-01-01T00:00:40")):
        c.execute("INSERT INTO tasks VALUES (?,?,?,?,?,0,NULL,?)", (f"{RUN}:{stage}:{key}", RUN, stage, key, status, at))
    # Kalodata calls, run RUN
    _api(c, RUN, "creator/rank", "200", 0.1, "2026-01-01T00:00:01")
    _api(c, RUN, "creator/detail", "200", 0.1, "2026-01-01T00:00:03")
    _api(c, RUN, "creator/detail", "pending", 0.1, "2026-01-01T00:00:04")
    _api(c, RUN, "creator/detail", "200", 0.0, "2026-01-01T00:00:05", cache_hit=1)
    _api(c, RUN, "video/rank", "200", 0.1, "2026-01-01T00:00:06")          # S1b (before S1b ended)
    _api(c, RUN, "video/rank", "200", 0.1, "2026-01-01T00:00:22")          # S3
    _api(c, RUN, "ui/creator_detail", "200", 0.0, "2026-01-01T00:00:15", db.cache_key("ui/creator_detail", {"creator_id": "c1"}))
    _api(c, RUN, "video/url", "200", 0.5, "2026-01-01T00:00:23", db.cache_key("video/url", {"video_id": "v1"}))
    _api(c, RUN, "video/url", "200", 0.5, "2026-01-01T00:00:24", db.cache_key("video/url", {"video_id": "v-orphan"}))
    _api(c, RUN, "video/url", "api_error:1054", 0.0, "2026-01-01T00:00:25")
    # Other run and probes must never be counted.
    _api(c, OTHER, "creator/detail", "200", 5.0, "2026-01-01T00:00:03")
    _api(c, None, "creator/rank", "200", 2.0, "2026-01-01T00:00:03")
    _llm(c, OTHER, "content", "hX", "content_v1", 99999, 99999, 9.0)
    # Final analysis for v1 produced by a repair call after a failed original call.
    c.execute("INSERT INTO creators VALUES ('c1','h',?,'t')", (json.dumps({"creator_followers": 1000}),))
    c.execute("INSERT INTO videos VALUES ('v1','c1',?,NULL,'t')", (json.dumps({"views": 5000}),))
    c.execute("INSERT INTO analyses VALUES ('v1','content_v3_repair','m','{}')")
    c.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES ('h-v1',?,?,'t')", (json.dumps({"video_id": "v1"}), json.dumps({"prompt_version": "content_v3_repair"})))
    _llm(c, RUN, "content", "h-v1", "content_v3", 1000, 100, 0.010)
    _llm(c, RUN, "content", "h-v1", "content_v3_repair", 1100, 110, 0.011)
    _llm(c, RUN, "content", "h-old", "content_v1", 900, 90, 0.009)          # failed attempt, no stored result
    _llm(c, RUN, "content", "h-v1", "content_v3", 0, 0, 0.0, cache_hit=1)
    c.execute("INSERT INTO recommendations VALUES (?,?,1,0,?)", (RUN, "c1", json.dumps({"usage": {"prompt_version": "reasons_v2"}})))
    c.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES ('h-r',?,?,'t')", (json.dumps({"creator_id": "c1"}), json.dumps({"prompt_version": "reasons_v2"})))
    _llm(c, RUN, "reasons", "h-r", "reasons_v2", 200, 20, 0.002)
    c.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES ('h-r1',?,?,'t')", (json.dumps({"creator_id": "c1"}), json.dumps({"prompt_version": "reasons_v1"})))
    _llm(c, RUN, "reasons", "h-r1", "reasons_v1", 150, 15, 0.0015)          # superseded by reasons_v2
    db.upsert_score(c, RUN, "c1", "S3", 70, {})
    c.commit()
    return c


def test_total_counts_failed_attempts_and_success_excludes_them(conn):
    result = aggregate(conn, RUN)
    success, total = result["totals_success"], result["totals_total"]
    # credits: rank 0.1 + detail 0.1 + pending 0.1 + video/rank 0.2 + video/url 1.0
    assert total["credits"] == pytest.approx(1.5)
    # success drops the pending reservation and the orphan video download
    assert success["credits"] == pytest.approx(0.9)
    assert total["tokens_in"] == 1000 + 1100 + 900 + 200 + 150
    assert success["tokens_in"] == 1100 + 200
    assert success["tokens_out"] == 110 + 20
    assert total["usd"] == pytest.approx(0.010 + 0.011 + 0.009 + 0.002 + 0.0015)
    assert success["usd"] == pytest.approx(0.011 + 0.002)
    assert result["waste"]["tokens_in"] == 1000 + 900 + 150
    assert result["failed_calls"] == {"api": 3, "llm": 3}
    assert total["cache_hits"] == 2


def test_stage_attribution(conn):
    stages = aggregate(conn, RUN)["stages_total"]
    assert stages["S0"]["credits"] == pytest.approx(0.1)
    assert stages["S1b"]["credits"] == pytest.approx(0.1 + 0.1 + 0.1)  # detail ok + pending + video/rank before S1b end
    assert stages["S3"]["credits"] == pytest.approx(0.1 + 1.0)
    assert stages["S3"]["tokens_in"] == 1000 + 1100 + 900
    assert stages["S4"]["tokens_in"] == 350
    assert stages["S2"]["wall_time_ms"] == 3000


def test_other_runs_and_probes_are_excluded(conn):
    result = aggregate(conn, RUN)
    assert result["totals_total"]["credits"] == pytest.approx(1.5)
    assert result["excluded_api_calls"] == {"calls": 2, "credits": 7.0}
    assert aggregate(conn, OTHER)["totals_total"]["tokens_in"] == 99999


def test_unit_costs_and_projection_use_config_funnel_caps(conn):
    result = aggregate(conn, RUN)
    assert result["units_total"]["S3"]["denominator"] == 1
    assert result["units_total"]["S3"]["credits"] == pytest.approx(1.1)
    small, large = project(result, 50), project(result, 500)
    assert small["stages"]["S1b"]["candidates"] == 50
    assert large["stages"]["S1b"]["candidates"] == 60
    assert large["stages"]["S3"]["candidates"] == 10
    assert large["stages"]["S0"]["candidates"] == 500
    assert large["totals"]["credits"] > small["totals"]["credits"]


def test_unknown_run_and_calibration_reason(conn):
    with pytest.raises(ValueError):
        aggregate(conn, "missing")
    block = aggregate(conn, RUN)["calibration"]["content_vs_video_gpm"]
    assert block["rho"] is None and "ít nhất 3" in block["reason"]


def test_markdown_is_vietnamese_and_labels_mock_scaling(conn, stable_test_config):
    conn.execute("INSERT INTO runs VALUES ('mock50',?,NULL,'done',?)", ("2026-01-02", json.dumps({"limit": 50, "mock": True})))
    conn.commit()
    result = build(conn, RUN, "mock50")
    text = render_markdown(result)
    assert "Đường thành công" in text and "Tổng thực chi" in text
    assert "MÔ PHỎNG, không phải số liệu thật" in text
    assert "không tính được" in text
    assert "500 ứng viên" in text


def test_cli_benchmark_writes_files(conn, tmp_path, monkeypatch, stable_test_config):
    import koc.cli as cli
    conn.commit()
    path = tmp_path / "bench.db"
    monkeypatch.setattr(cli, "DB_PATH", path)
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["benchmark", "--run", RUN, "--out-dir", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads((out / "reports/benchmark.json").read_text())
    assert data["totals_total"]["credits"] == pytest.approx(1.5)
    assert (out / "docs/BENCHMARK.md").read_text().startswith("# Chuẩn đo KOC Discovery")
