import json

import pytest
from pathlib import Path

from typer.testing import CliRunner

from koc.cli import app
from koc.config import load_config
from koc.estimate import estimate_run, estimate_lines_vi

BENCHMARK = json.loads((Path(__file__).resolve().parents[2] / "reports/benchmark.json").read_text())


def test_default_config_projects_published_per_creator_units():
    est = estimate_run(load_config(), limit=200, count=5, benchmark=BENCHMARK)
    assert est["label"] == "ước tính"
    assert est["credits"] == {"low": 27.6, "high": 29.4}
    assert est["usd"] == {"low": 0.48, "high": 1.46}
    assert est["tokens"]["low"] < est["tokens"]["high"]
    # 43.3 min were measured (S2 10.7, S3 26.4); units project S3 at 10 creators, so the range sits around 43-47 min
    assert est["minutes"]["low"] < 43.3 < est["minutes"]["high"]
    assert est["stages"]["S2"]["minutes"] == 10.7 and est["stages"]["S3"]["candidates"] == 10 and est["stages"]["S4"]["candidates"] == 5


def test_s2_limit_scales_s2_and_s3_proportionally():
    config = load_config()
    ten = estimate_run(config, limit=200, count=5, benchmark=BENCHMARK)
    half = estimate_run({**config, "s1": {**config["s1"], "s2_limit": 5}}, limit=200, count=5, benchmark=BENCHMARK)
    assert half["stages"]["S2"]["candidates"] == 5
    assert half["stages"]["S2"]["minutes"] == pytest.approx(ten["stages"]["S2"]["minutes"] / 2, abs=0.1)
    assert half["stages"]["S3"]["credits"] == pytest.approx(ten["stages"]["S3"]["credits"] / 2, abs=0.01)
    assert half["stages"]["S3"]["minutes"] == pytest.approx(ten["stages"]["S3"]["minutes"] / 2, abs=0.1)
    assert half["credits"]["high"] < ten["credits"]["high"] and half["minutes"]["high"] < ten["minutes"]["high"]


def test_count_scales_s4():
    config = load_config()
    assert estimate_run(config, 200, 10, BENCHMARK)["stages"]["S4"]["usd"] == pytest.approx(2 * estimate_run(config, 200, 5, BENCHMARK)["stages"]["S4"]["usd"], abs=1e-3)


def test_smaller_limit_scales_down_and_uses_s2_limit():
    config = load_config()
    small = estimate_run(config, limit=100, benchmark=BENCHMARK)
    big = estimate_run(config, limit=200, benchmark=BENCHMARK)
    assert small["credits"]["high"] < big["credits"]["high"]
    assert small["stages"]["S3"]["candidates"] == config["s1"]["s2_limit"] == 10


def test_lines_are_vietnamese_ranges_labelled_estimate():
    est = estimate_run(load_config(), limit=200, benchmark=BENCHMARK)
    text = "\n".join(estimate_lines_vi(est))
    assert "ước tính" in text.casefold()
    assert "27.6–29.4 tín dụng" in text and "0.48–1.46 USD" in text and "phút" in text and "token" in text


def test_missing_benchmark_gives_none(tmp_path):
    assert estimate_run(load_config(), limit=200, benchmark=None, benchmark_path=tmp_path / "no.json") is None


def test_dry_run_prints_estimate_and_configured_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("KOC_DB", str(tmp_path / "never.db"))
    result = CliRunner().invoke(app, ["run", "--limit", "200", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "ước tính" in result.output.casefold() and "phút" in result.output
    config = load_config()["s1"]
    assert f"S1a lọc còn {config['s1a_limit']}" in result.output
    assert f"S1b chấm điểm còn {config['s1_limit']}" in result.output
    assert f"S2 còn {config['s2_limit']}" in result.output
    assert "S2 còn 15" not in result.output
