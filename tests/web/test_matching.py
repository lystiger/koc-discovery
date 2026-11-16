import random

import pytest

from koc.web.matching import match
from koc.web.matching_api import normalize_result, EVIDENCE_PATTERN, _apply_audience_floors, _audience_parts, display_reason_text


def test_evidence_cleanup_preserves_clock_times():
    text = "Livestream lúc 20:30:15 tối"
    assert EVIDENCE_PATTERN.sub("", text) == text
    assert EVIDENCE_PATTERN.findall("Khán giả nữ (v_c_linh_01_1@15.0s)") == [
        "v_c_linh_01_1@15.0s"
    ]
    assert EVIDENCE_PATTERN.findall("metric:c_linh_01:female_ratio") == [
        "metric:c_linh_01:female_ratio"
    ]


def creator(creator_id, commercial, audience, content, cost, mcn=None):
    return {
        "creator_id": creator_id,
        "nickname": creator_id,
        "handle": f"@{creator_id}",
        "followers": 50000,
        "mcn": mcn,
        "commercial": commercial,
        "audience": audience,
        "content": content,
        "cost_vnd": cost,
    }


def test_missing_component_uses_pool_minimum_without_changing_confidence():
    result = match(
        {"count": 4, "budget_vnd": 4_000_000, "avoid_same_mcn": False},
        [
            creator("a", 80, 100, None, 1_000_000),
            creator("b", 60, 100, 40, 1_000_000),
            creator("c", 60, 100, 80, 1_000_000),
            creator("d", 60, 100, 100, 1_000_000),
        ],
    )
    picked = next(item for item in result["picked"] if item["creator_id"] == "a")
    assert picked["fit"] == 70.0
    assert picked["confidence"] == "Một phần"
    assert picked["components"]["content"] is None


def test_component_missing_for_entire_pool_is_removed_from_fit():
    result = match(
        {"count": 2, "budget_vnd": 2_000_000, "avoid_same_mcn": False},
        [creator("a", 80, None, None, 1_000_000), creator("b", 60, None, None, 1_000_000)],
    )
    assert {item["creator_id"]: item["fit"] for item in result["picked"]} == {"a": 80, "b": 60}


def test_missing_age_part_uses_pool_minimum_and_cannot_raise_fit():
    pool = [
        {"creator_id": "missing-age", "_audience_parts": {"gender": 82.5, "age": None}},
        {"creator_id": "age-floor", "_audience_parts": {"gender": 82.5, "age": 37.5}},
    ]
    _apply_audience_floors(pool)
    assert pool[0]["audience"] == 60.0

    fixed = creator("missing-age", 80, pool[0]["audience"], 96.9142857143, 1_000_000)
    previous = creator("missing-age", 80, 82.5, 96.9142857143, 1_000_000)
    assert match({"count": 1, "budget_vnd": 1_000_000}, [fixed])["picked"][0]["fit"] == 81.92
    assert match({"count": 1, "budget_vnd": 1_000_000}, [previous])["picked"][0]["fit"] == 86.42


def test_gender_only_target_keeps_gender_part():
    pool = [{"_audience_parts": _audience_parts({"female_pct": 72}, {"gender": "Nữ", "age_groups": ["18-24"]})}]
    _apply_audience_floors(pool)
    assert pool[0]["audience"] == 72
    assert pool[0]["_audience_observed"]
    assert pool[0]["audience_age_missing"]
    gender_only = creator("gender-only", 80, pool[0]["audience"], 90, 1)
    gender_only["_audience_observed"] = pool[0]["_audience_observed"]
    gender_only["audience_age_missing"] = pool[0]["audience_age_missing"]
    scored = match({"count": 1, "budget_vnd": 1}, [gender_only])['picked'][0]
    assert scored["components"]["audience"] == 72
    assert scored["confidence"] == "Đầy đủ"
    assert scored["audience_age_missing"]


def test_missing_age_for_every_creator_drops_age_part_for_everyone():
    pool = [
        {"_audience_parts": {"gender": 72.0, "age": None}},
        {"_audience_parts": {"gender": 48.0, "age": None}},
    ]
    _apply_audience_floors(pool)
    assert [creator["audience"] for creator in pool] == [72, 48]


def test_missing_part_never_raises_average_above_observed_part():
    pool = [
        {"_audience_parts": {"gender": 30.0, "age": None}},
        {"_audience_parts": {"gender": 40.0, "age": 90.0}},
    ]
    _apply_audience_floors(pool)
    assert pool[0]["audience"] == 30


def test_reason_age_ranges_use_en_dash():
    assert display_reason_text("Khán giả nhóm tuổi 25-34 tuổi chiếm 52%") == "Khán giả nhóm tuổi 25–34 tuổi chiếm 52%"
    assert display_reason_text("Phù hợp độ tuổi 18-24; rubric áp dụng 18-30 tuổi") == "Phù hợp độ tuổi 18–24; rubric áp dụng 18–30 tuổi"


def test_single_component_is_preliminary_and_missing_stays_null():
    result = match(
        {"count": 1, "budget_vnd": 1_000_000},
        [creator("a", 80, None, None, 1_000_000)],
    )
    assert result["picked"][0]["fit"] == 80
    assert result["picked"][0]["confidence"] == "Sơ bộ"
    assert result["picked"][0]["components"] == {
        "commercial": 80,
        "audience": None,
        "content": None,
    }


def test_avoids_two_creators_from_same_mcn():
    result = match(
        {"count": 2, "budget_vnd": 10_000_000, "avoid_same_mcn": True},
        [
            creator("a", 99, 99, 99, 2_000_000, "mcn-a"),
            creator("b", 95, 95, 95, 2_000_000, "mcn-a"),
            creator("c", 70, 70, 70, 2_000_000, "mcn-c"),
        ],
    )
    assert {item["creator_id"] for item in result["picked"]} == {"a", "c"}


def test_empty_pool_returns_explanatory_warning():
    result = match({"count": 2, "budget_vnd": 2_000_000}, [])
    assert result["picked"] == []
    assert result["warning"] == "Không có KOC trong khoảng người theo dõi đã chọn."


TRIO = [creator("a", 90, 90, 90, 1_000_000), creator("b", 80, 80, 80, 1_000_000), creator("c", 70, 70, 70, 1_000_000)]


def test_exact_fit_is_ok_with_zero_leftover():
    result = match({"count": 3, "budget_vnd": 3_000_000, "avoid_same_mcn": False}, TRIO)
    assert result["status"] == "ok" and len(result["picked"]) == 3
    assert result["total_cost_vnd"] == 3_000_000 and result["leftover_vnd"] == 0
    assert result["budget_vnd"] == 3_000_000 and result["warnings"] == [] and result["warning"] is None


def test_unused_budget_is_reported_as_leftover():
    result = match({"count": 2, "budget_vnd": 2_500_000, "avoid_same_mcn": False}, TRIO)
    assert result["status"] == "ok" and result["total_cost_vnd"] == 2_000_000
    assert result["leftover_vnd"] == 500_000


def test_budget_too_small_refuses_with_options_and_no_picks():
    result = match({"count": 3, "budget_vnd": 2_000_000, "avoid_same_mcn": False}, TRIO)
    assert result["status"] == "refused"
    assert result["picks"] == [] and result["picked"] == [] and result["total_cost_vnd"] == 0
    assert result["options"]["max_count_within_budget"] == {"count": 2, "cost_vnd": 2_000_000}
    assert result["options"]["min_budget_for_count"] == {"budget_vnd": 3_000_000}
    assert result["options"]["cheaper_follower_band"] is None
    assert len(result["warnings"]) == 1 and "3.000.000" in result["warnings"][0]
    assert result["warning"] == result["warnings"][0]


def test_max_count_option_is_null_when_not_even_one_fits():
    result = match({"count": 2, "budget_vnd": 500_000, "avoid_same_mcn": False}, TRIO)
    assert result["status"] == "refused"
    assert result["options"]["max_count_within_budget"] is None
    assert result["options"]["min_budget_for_count"] == {"budget_vnd": 2_000_000}


def test_max_count_option_picks_best_fit_then_lower_cost():
    pool = [creator("a", 90, 90, 90, 3_000_000), creator("b", 80, 80, 80, 1_000_000), creator("c", 70, 70, 70, 1_000_000),
            creator("d", 60, 60, 60, 1_000_000)]
    result = match({"count": 4, "budget_vnd": 3_000_000, "avoid_same_mcn": False}, pool)
    assert result["options"]["max_count_within_budget"] == {"count": 3, "cost_vnd": 3_000_000}


def test_pool_smaller_than_count_refuses_and_min_budget_is_null():
    result = match({"count": 5, "budget_vnd": 99_000_000, "avoid_same_mcn": False}, TRIO)
    assert result["status"] == "refused" and result["picked"] == []
    assert result["options"]["min_budget_for_count"] is None
    assert result["options"]["max_count_within_budget"] == {"count": 3, "cost_vnd": 3_000_000}
    assert result["warnings"] == ["Chỉ có 3 KOC phù hợp, ít hơn 5 KOC yêu cầu."]


def test_mcn_conflicts_refuse_even_with_big_budget():
    pool = [creator("a", 99, 99, 99, 1_000_000, "m"), creator("b", 95, 95, 95, 1_000_000, "m"), creator("c", 70, 70, 70, 1_000_000, "m")]
    result = match({"count": 2, "budget_vnd": 99_000_000, "avoid_same_mcn": True}, pool)
    assert result["status"] == "refused"
    assert result["options"]["min_budget_for_count"] is None
    assert result["options"]["max_count_within_budget"] == {"count": 1, "cost_vnd": 1_000_000}
    assert result["warnings"] == ["Không đủ KOC khác MCN để chọn 2 KOC."]


def test_empty_pool_refuses_with_all_options_null():
    result = match({"count": 2, "budget_vnd": 2_000_000}, [])
    assert result["status"] == "refused"
    assert result["options"] == {"max_count_within_budget": None, "min_budget_for_count": None, "cheaper_follower_band": None}


def test_budget_warning_does_not_overwrite_pool_warning():
    result = match({"count": 5, "budget_vnd": 1, "avoid_same_mcn": False}, TRIO)
    assert result["warnings"][0].startswith("Chỉ có 3 KOC")
    assert result["warning"] == result["warnings"][0]


def test_warnings_are_never_overwritten_for_budget_refusal():
    result = match({"count": 3, "budget_vnd": 1, "avoid_same_mcn": False}, TRIO)
    assert len(result["warnings"]) == 1 and result["warning"] == result["warnings"][0]
    both = match({"count": 3, "budget_vnd": 1, "avoid_same_mcn": True},
                 [creator("a", 90, 90, 90, 1_000_000, "m"), creator("b", 80, 80, 80, 1_000_000, "m"), creator("c", 70, 70, 70, 1_000_000)])
    assert both["warnings"] == ["Không đủ KOC khác MCN để chọn 3 KOC."]


@pytest.mark.parametrize("seed", range(40))
def test_over_budget_plan_is_never_returned(seed):
    rng = random.Random(seed)
    pool = [creator(f"c{i}", rng.randint(30, 99), rng.randint(30, 99), rng.choice([None, rng.randint(30, 99)]),
                    rng.choice([1, 2, 5]) * 500_000, rng.choice([None, "m1", "m2"])) for i in range(rng.randint(0, 8))]
    for _ in range(10):
        count, budget = rng.randint(1, 6), rng.randint(0, 20) * 500_000
        mcn = rng.random() < 0.5
        result = match({"count": count, "budget_vnd": budget, "avoid_same_mcn": mcn}, pool)
        assert result["total_cost_vnd"] <= budget
        if result["status"] == "ok":
            assert len(result["picked"]) == count and result["leftover_vnd"] == budget - result["total_cost_vnd"] >= 0
            mcns = [item["mcn"] for item in result["picked"] if item["mcn"]]
            assert not mcn or len(mcns) == len(set(mcns))
        else:
            assert result["picked"] == [] and result["picks"] == [] and result["warnings"]
            option = result["options"]["max_count_within_budget"]
            assert option is None or (option["count"] < count and option["cost_vnd"] <= budget)
            floor = result["options"]["min_budget_for_count"]
            assert floor is None or floor["budget_vnd"] > budget


def test_old_stored_result_without_status_renders_as_ok():
    old = {"picked": [], "alternates": [], "total_cost_vnd": 4_000_000, "warning": "Tìm thấy 2/3 KOC phù hợp với yêu cầu.", "ranked_count": 3}
    result = normalize_result(old, {"budget_vnd": 5_000_000})
    assert result["status"] == "ok" and result["leftover_vnd"] == 1_000_000 and result["budget_vnd"] == 5_000_000
    assert result["warnings"] == [old["warning"]] and result["warning"] == old["warning"]
    new = match({"count": 1, "budget_vnd": 1_000_000}, TRIO)
    assert normalize_result(new, {}) is new
