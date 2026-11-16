from itertools import combinations


WEIGHTS = {"commercial": 45, "audience": 20, "content": 35}
# Mirrors src/koc/stages.py:final_score and config/scoring.yaml final_weights.
CONFIDENCE = {3: "Đầy đủ", 2: "Một phần", 1: "Sơ bộ", 0: "Sơ bộ"}


def score_creators(creators: list[dict]) -> list[dict]:
    components = ("commercial", "audience", "content")
    present = {name for name in components if any(creator.get(name) is not None for creator in creators)}
    fills = {
        name: min(values)
        for name in components
        if (values := [float(creator[name]) for creator in creators if creator.get(name) is not None])
    }
    scored = []
    for creator in creators:
        actual = {name: creator.get(name) for name in components}
        confidence_components = {
            **actual,
            "audience": actual["audience"] if creator.get("_audience_observed", actual["audience"] is not None) else None,
        }
        available = [name for name, value in confidence_components.items() if value is not None]
        total_weight = sum(WEIGHTS[name] for name in present)
        fit = sum((actual[name] if actual[name] is not None else fills[name]) * WEIGHTS[name] for name in present) / total_weight if total_weight else 0
        scored.append({
            **{key: value for key, value in creator.items() if key != "_audience_observed"},
            "fit": round(fit, 2),
            "components": confidence_components,
            "confidence": CONFIDENCE[len(available)],
            "confidence_count": len(available),
        })
    return scored


def _valid_selection(selection: tuple[dict, ...], avoid_same_mcn: bool) -> bool:
    if not avoid_same_mcn:
        return True
    agencies = [item.get("mcn") for item in selection if item.get("mcn")]
    return len(agencies) == len(set(agencies))


def _vnd(value: int) -> str:
    return f"{value:,.0f}".replace(",", ".") + " ₫"


def _rank(pool: list[dict]) -> list[dict]:
    return sorted(
        score_creators(pool),
        key=lambda item: (-item["confidence_count"], -item["fit"], item["creator_id"]),
    )[:15]


def _cost(group) -> int:
    return sum(item["cost_vnd"] for item in group)


def best_set(ranked: list[dict], size: int, budget: int | None, avoid_same_mcn: bool):
    groups = [
        group for group in combinations(ranked, size)
        if _valid_selection(group, avoid_same_mcn) and (budget is None or _cost(group) <= budget)
    ]
    return max(groups, key=lambda group: (sum(item["fit"] for item in group), -_cost(group)), default=None)


def cheapest_set(ranked: list[dict], size: int, avoid_same_mcn: bool):
    groups = [group for group in combinations(ranked, size) if _valid_selection(group, avoid_same_mcn)]
    return min(groups, key=lambda group: (_cost(group), -sum(item["fit"] for item in group)), default=None)


def match(campaign: dict, pool: list[dict]) -> dict:
    ranked = _rank(pool)
    count = int(campaign.get("count", 5))
    budget = int(campaign.get("budget_vnd", 0))
    avoid_same_mcn = bool(campaign.get("avoid_same_mcn", True))
    selected = best_set(ranked, count, budget, avoid_same_mcn) if count > 0 else None
    selected_ids = {item["creator_id"] for item in selected or ()}
    alternates = [item for item in ranked if item["creator_id"] not in selected_ids][:5]
    base = {"budget_vnd": budget, "ranked_count": len(ranked)}
    if selected is not None:
        picked = sorted(selected, key=lambda item: (-item["confidence_count"], -item["fit"], item["creator_id"]))
        total = _cost(picked)
        return {**base, "status": "ok", "picked": picked, "alternates": alternates, "total_cost_vnd": total,
                "leftover_vnd": budget - total, "warning": None, "warnings": []}
    warnings = []
    cheapest = cheapest_set(ranked, count, avoid_same_mcn) if count > 0 else None
    if not ranked:
        warnings.append("Không có KOC trong khoảng người theo dõi đã chọn.")
    elif len(ranked) < count:
        warnings.append(f"Chỉ có {len(ranked)} KOC phù hợp, ít hơn {count} KOC yêu cầu.")
    elif cheapest is None:
        warnings.append(f"Không đủ KOC khác MCN để chọn {count} KOC.")
    if cheapest is not None:
        warnings.append(f"Ngân sách {_vnd(budget)} chưa đủ cho {count} KOC: cần tối thiểu {_vnd(_cost(cheapest))}.")
    max_count = None
    for size in range(min(count - 1, len(ranked)), 0, -1):
        group = best_set(ranked, size, budget, avoid_same_mcn)
        if group is not None:
            max_count = {"count": size, "cost_vnd": _cost(group)}
            break
    return {
        **base, "status": "refused", "picks": [], "picked": [], "alternates": [], "total_cost_vnd": 0,
        "leftover_vnd": budget, "warning": warnings[0], "warnings": warnings,
        "options": {
            "max_count_within_budget": max_count,
            "min_budget_for_count": {"budget_vnd": _cost(cheapest)} if cheapest is not None else None,
            "cheaper_follower_band": None,
        },
    }
