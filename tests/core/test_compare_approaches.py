import pytest
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("compare_approaches", REPO / "scripts" / "compare_approaches.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_vietnamese_number_format():
    assert mod.vn(30_000_000, ",") == "30.000.000"
    assert mod.vn(0.765, ".2f") == "0,77"
    assert mod.vn(1.5) == "1,5"


def test_verdict_thresholds_match_rating_rule():
    assert [mod.verdict_of(g) for g in (3, 2.5, 2, 1.5, 1, 0)] == ["co", "co", "dieukien", "dieukien", "khong", "khong"]


def test_quality_counts_and_ndcg():
    grades = {"a": 3, "b": 3, "c": 0, "d": 1.5, "e": 1, "f": 3}
    verdicts = {h: mod.verdict_of(g) for h, g in grades.items()}
    q = mod.quality(["a", "b", "c", "d", "e"], grades, verdicts, list(grades))
    assert q["strict"] == 2 and q["soft"] == 2.5
    assert 0 < q["ndcg_pool"] < 1
    best = mod.quality(["a", "b", "f", "d", "e"], grades, verdicts, list(grades))
    assert best["ndcg_pool"] == 1.0
    assert mod.quality(["a", "zz"], grades, verdicts, list(grades)) is None


def test_spearman_handles_ties_and_constant_input():
    assert mod.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert mod.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert mod.ranks([5, 1, 5]) == [2.5, 1.0, 2.5]
    assert mod.spearman([1, 1, 1], [1, 2, 3]) is None
