import itertools
import json

from .pricing import video_total
from .types import BrandBrief

GENDERS = {"nu": "Nữ", "nam": "Nam", "tat-ca": "Mọi giới"}
AGE_LIMITS = (18, 99)  # web picker: 18-24 ... 55+ (55+ counts as 55-99)


def vnd(value):
    return f"{int(value):,}".replace(",", ".")


def make_brief(config, *, product=None, product_type=None, category_ids=None, gender=None, age_min=None, age_max=None, budget=None, count=None):
    s1 = config["s1"]
    pick = lambda value, default: default if value is None else value
    if product_type is not None:
        mapped = config.get("product_categories", {}).get(product_type) or []
        product, category_ids = pick(product, product_type.lower()), pick(category_ids, mapped)
    brief = {
        "product": pick(product, "kem chống nắng"), "product_type": product_type,
        "category_ids": [str(i) for i in pick(category_ids, config["scoring"]["s0"]["category_ids"])],
        "gender": pick(gender, "nu"), "age_min": pick(age_min, 18), "age_max": pick(age_max, 30),
        "budget_vnd": pick(budget, s1.get("budget_vnd", 30_000_000)), "count": pick(count, s1.get("recommendation_count", 5)),
    }
    brief["target"] = f"{GENDERS.get(brief['gender'], brief['gender'])}, {brief['age_min']}-{brief['age_max']} tuổi"
    return brief


def run_brief(conn, run_id, config):
    """The run's brief; keys missing from params_json (older runs) fall back to the defaults."""
    row = conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    stored = (json.loads(row[0]) if row else {}).get("brief")
    return {**make_brief(config), **(stored if isinstance(stored, dict) else {})}


def brand_brief(brief):
    return BrandBrief(product_vi=brief["product"], audience_vi=brief["target"], budget_vnd=brief["budget_vnd"])


def cheapest_tier(config):
    tier = min(config["rate_card"]["tiers"], key=lambda t: t["vnd_per_video"])
    return video_total(tier["vnd_per_video"]), tier["min_followers"], tier["max_followers"] + 1


def band_text(low, high):
    return f"{low // 1000}k-{high // 1000}k"


def check_brief(brief, config):
    """Vietnamese refusal message, or None when the brief can run. Pure: no network, no DB."""
    count, budget = brief["count"], brief["budget_vnd"]
    if brief["gender"] not in GENDERS:
        return "Giới tính phải là nu, nam hoặc tat-ca."
    if count < 1 or budget < 1:
        return "Số KOC và ngân sách phải lớn hơn 0."
    low, high = AGE_LIMITS
    if not low <= brief["age_min"] <= brief["age_max"] <= high:
        return f"Độ tuổi phải nằm trong khoảng {low}-{high} (nhóm 55+ tính là 55-{high}) và --age-min không lớn hơn --age-max."
    product_type = brief.get("product_type")
    if product_type is not None:
        types = config.get("product_categories", {})
        if product_type not in types:
            return f"Loại sản phẩm không hợp lệ. Chọn một trong: {', '.join(types)}."
        if not brief["category_ids"]:
            return (f"Loại sản phẩm \"{product_type}\" chưa có danh mục Kalodata. Hãy truyền --category-ids \"id1,id2\" "
                    "(tìm ID bằng `koc categories --keyword <từ khóa>`).")
    limit = config["s1"]["s2_limit"]
    if count > limit:
        return f"Không thể chọn {count} KOC: tài khoản dùng thử chỉ phân tích tối đa {limit} creator mỗi lượt chạy. Hãy đặt --count từ 1 đến {limit}."
    cheapest, low, high = cheapest_tier(config)
    if budget < count * cheapest:
        return (f"Ngân sách {vnd(budget)} VND không đủ cho {count} KOC (KOC rẻ nhất {vnd(cheapest)} VND cho 3 video). Lựa chọn:\n"
                f"  - giảm --count xuống tối đa {budget // cheapest} KOC;\n"
                f"  - hoặc tăng --budget lên tối thiểu {vnd(count * cheapest)} VND cho {count} KOC;\n"
                f"  - nhóm follower rẻ nhất là {band_text(low, high)}.")
    return None


def s4_options(rows, brief, config):
    """The three options for an infeasible S4, from the actual scored creators. rows: [(mcn_id, cost)]."""
    count, budget = brief["count"], brief["budget_vnd"]

    def cheapest_group(size):
        totals = [sum(cost for _, cost in combo) for combo in itertools.combinations(rows, size)
                  if len([m for m, _ in combo if m]) == len({m for m, _ in combo if m})]
        return min(totals) if totals else None

    fit = next(((size, total) for size in range(min(count - 1, len(rows)), 0, -1)
                if (total := cheapest_group(size)) is not None and total <= budget), None)
    minimum = cheapest_group(count) if len(rows) >= count else None
    band = next(((t["min_followers"], t["max_followers"] + 1) for t in config["rate_card"]["tiers"]
                 if rows and video_total(t["vnd_per_video"]) == min(cost for _, cost in rows)), None)
    return [
        f"giảm còn {fit[0]} KOC (tốn {vnd(fit[1])} VND)" if fit else "không có (không có nhóm nhỏ hơn nào nằm trong ngân sách)",
        f"tăng ngân sách lên tối thiểu {vnd(minimum)} VND cho {count} KOC" if minimum is not None else f"không có (chưa đủ {count} KOC có điểm nội dung để tính ngân sách tối thiểu)",
        f"nhóm follower rẻ nhất trong danh sách là {band_text(*band)}" if band else "không có (chưa có KOC nào có điểm nội dung)",
    ], minimum
