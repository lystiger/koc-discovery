import pytest

from koc import db
from koc.report import benchmark
from koc.types import Usage


@pytest.fixture
def measured_run(tmp_path):
    conn = db.connect(tmp_path / "projection.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 20, "stage_wall_ms": {"S2": 24000}})
    for index in range(8):
        db.add_task(conn, run_id, "S2", f"creator-{index}")
    conn.execute("UPDATE tasks SET status='done' WHERE run_id=? AND stage='S2'", (run_id,))
    for endpoint, credits, latency_ms, cache_hit in (
        ("creator/rank", 0.1, 1000, False),
        ("creator/rank", 0.3, 3000, False),
        ("creator/detail", 0.2, 2000, False),
        ("creator/detail", 0, 0, True),
        ("video/rank", 0.4, 4000, False),
        ("video/url", 0.5, 5000, False),
    ):
        db.add_api_call(conn, run_id, endpoint, endpoint, "200", credits, latency_ms, cache_hit)
    for kind, tokens_in, tokens_out, cost, latency_ms, cache_hit in (
        ("content", 1000, 200, 0.01, 6000, False),
        ("content", 0, 0, 0, 0, True),
        ("reasons", 100, 50, 0.002, 3000, False),
    ):
        usage = Usage(provider="gemini", model="test", prompt_version="v1", input_tokens=tokens_in,
                      output_tokens=tokens_out, latency_ms=latency_ms, cost_usd=cost, cache_hit=cache_hit)
        db.add_llm_call(conn, run_id, kind, kind, usage, cache_hit)
    return conn, run_id


def test_projection_scales_funnel_and_uses_non_cache_per_call_units(measured_run, stable_test_config):
    conn, run_id = measured_run

    projection = benchmark(conn, run_id)["projections"]

    assert projection["50"]["s2_calendar_days"] == 1
    assert projection["200"]["s2_calendar_days"] == 4
    assert projection["500"]["s2_calendar_days"] == 10
    assert projection["50"]["stages"]["S1b"]["calls"] == 30
    assert projection["200"]["stages"]["S1b"]["calls"] == 120
    assert projection["500"]["stages"]["S1b"]["calls"] == 300
    assert projection["500"]["stages"]["S1b"]["credits"] == pytest.approx(90)
    assert projection["500"]["stages"]["S2"]["calls"] == 100
    assert projection["500"]["stages"]["S2"]["credits"] == pytest.approx(100)
    assert projection["500"]["stages"]["S2"]["wall_time_seconds"] == pytest.approx(300)
    assert projection["500"]["stages"]["S3"]["tokens_in"] == 114000
    assert projection["500"]["stages"]["S3"]["tokens_out"] == 22800
    assert projection["500"]["stages"]["S3"]["usd"] == pytest.approx(1.14)
    assert projection["500"]["stages"]["S3"]["credits"] == pytest.approx(72.2)
    assert benchmark(conn, run_id)["projection_500"] == projection["500"]
