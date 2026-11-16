"""Accessible, server-rendered charts for the web views."""
from __future__ import annotations

from html import escape
from markupsafe import Markup


BLUE = "#1E40AF"
LIGHT_BLUE = "#3B82F6"
AMBER = "#D97706"
GRID = "#DBEAFE"
TEXT = "#475569"


def _vi_number(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _vi_usd(value: float) -> str:
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    if "." not in formatted:
        formatted += ".00"
    elif len(formatted.partition(".")[2]) == 1:
        formatted += "0"
    return formatted.replace(".", ",")


def _html_chart(title: str, description: str, body: str) -> Markup:
    return Markup(
        f'<div class="chart-bars" role="img" aria-label="{escape(title)}. {escape(description)}">{body}</div>'
    )


def funnel_chart(rows: list[dict]) -> Markup:
    s0_count = next((int(row["candidates_out"]) for row in rows if row["stage"] == "S0"), 0) or 1
    body = []
    for row in rows:
        value = int(row["candidates_out"])
        width = 100 * value / s0_count
        body.append(
            f'<div class="bar-row funnel-row"><span class="bar-label">{escape(row["stage"])}</span>'
            f'<div class="bar-track"><span class="bar-fill" style="width:{width:.1f}%;background:{BLUE}"></span></div>'
            f'<strong class="bar-value">{value}</strong></div>'
        )
    body.append('<p class="bar-axis">Số ứng viên còn lại</p>')
    return _html_chart("Số ứng viên qua phễu S0 đến S4", "Số ứng viên còn lại sau mỗi giai đoạn.", "".join(body))


def bullet_chart(credits: float, credit_cap: float, usd: float, usd_cap: float) -> Markup:
    body = []
    for label, value, cap, suffix, color in (
        ("Kalodata", credits, credit_cap, "credit", BLUE),
        ("Gemini", usd, usd_cap, "$", AMBER),
    ):
        width = 100 * min(value / cap, 1) if cap else 0
        percent = value / cap * 100 if cap else 0
        body.append(
            f'<div class="bullet-row"><span class="bar-label">{label}</span>'
            f'<div class="bar-track"><span class="bar-fill" style="width:{width:.1f}%;background:{color}"></span></div>'
            f'<div class="bar-detail"><strong>{("$" + _vi_usd(value)) if suffix == "$" else _vi_number(value)} / '
            f'{("$" + _vi_usd(cap)) if suffix == "$" else _vi_number(cap)}'
            f'{" " + suffix if suffix != "$" else ""}</strong>'
            f'<span>{_vi_number(percent)}%</span></div></div>'
        )
    body.append('<p class="bar-axis">Tỷ lệ hạn mức đã dùng</p>')
    return _html_chart("Mức dùng so với hạn mức", "Credits và USD đã dùng so với hạn mức của đợt chạy.", "".join(body))


def score_chart(rows: list[dict]) -> Markup:
    body = []
    for row in rows:
        parts = ((row["commercial_score"] * .45, BLUE), ((row["audience_score"] or 0) * .20, LIGHT_BLUE), (row["content_score"] * .35, AMBER))
        segments = "".join(
            f'<span class="score-segment" style="width:{max(0, min(value, 100)):.1f}%;background:{color}"></span>'
            for value, color in parts
        )
        body.append(
            f'<div class="score-row"><span class="bar-label">{escape(row["nickname"])}</span>'
            f'<div class="score-track">{segments}</div>'
            f'<strong class="bar-value">{_vi_number(row["final_score"])}</strong></div>'
        )
    body.append('<p class="bar-axis">Điểm đóng góp có trọng số trên thang 100</p>')
    return _html_chart("Đóng góp điểm theo trọng số", "Mỗi thanh cộng điểm thương mại 45%, khán giả 20% và nội dung 35%.", "".join(body))


def scatter_chart(rows: list[dict], budget: int) -> Markup:
    left, top, plot_w, plot_h = 64, 18, 590, 190
    costs = [int(row["est_cost_vnd"]) / 1_000_000 for row in rows]
    min_cost = min(costs, default=0)
    max_cost = max(costs, default=1)
    cost_pad = max((max_cost - min_cost) * .1, max_cost * .05, .1)
    x_min = max(0, min_cost - cost_pad)
    x_max = max_cost + cost_pad
    scores = [float(row["final_score"]) for row in rows]
    y_min = max(0, min(scores, default=0) - 5)
    body = [
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="{TEXT}"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="{TEXT}"/>',
    ]
    for tick in range(0, 101, 25):
        if tick < y_min:
            continue
        y = top + plot_h - plot_h * (tick - y_min) / (100 - y_min)
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="{GRID}"/>')
        body.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" fill="{TEXT}" font-size="12">{tick}</text>')
    for index in range(3):
        cost = x_min + (x_max - x_min) * index / 2
        x = left + plot_w * index / 2
        body.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="{GRID}"/>')
        body.append(f'<text x="{x:.1f}" y="{top + plot_h + 18}" text-anchor="middle" fill="{TEXT}" font-size="12">{_vi_number(cost)}</text>')
    for row, cost in zip(rows, costs):
        x = left + plot_w * (cost - x_min) / (x_max - x_min)
        y = top + plot_h - plot_h * (float(row["final_score"]) - y_min) / (100 - y_min)
        color = AMBER if row["selected"] else BLUE
        radius = 6 if row["selected"] else 4
        cost_label = f"{int(row['est_cost_vnd']):,}".replace(",", ".")
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" aria-label="{escape(row["nickname"])}: {cost_label} ₫, điểm {_vi_number(row["final_score"])}"/>')
    body.extend((f'<text x="{left + plot_w / 2}" y="246" text-anchor="middle" fill="{TEXT}" font-size="12">Chi phí (₫ triệu)</text>',
                 f'<text transform="translate(16 {top + plot_h / 2}) rotate(-90)" text-anchor="middle" fill="{TEXT}" font-size="12">Điểm</text>'))
    chart_id = "scatter-cost-score"
    budget_label = f"{budget:,}".replace(",", ".")
    description = f"{len(rows)} ứng viên; chi phí tính bằng triệu đồng, điểm trên thang 100. Ngân sách {budget_label} ₫."
    svg = (f'<svg class="scatter-chart" width="720" height="265" viewBox="0 0 720 265" role="img" '
           f'aria-labelledby="{chart_id}-title {chart_id}-desc" xmlns="http://www.w3.org/2000/svg">'
           f'<title id="{chart_id}-title">Chi phí và điểm của {len(rows)} ứng viên vòng cuối</title>'
           f'<desc id="{chart_id}-desc">{escape(description)}</desc>{"".join(body)}</svg>')
    return Markup(f'<div class="scatter-scroll"><p class="table-hint">Biểu đồ co theo chiều rộng màn hình.</p>{svg}</div>')


def bar_chart(title: str, rows: list[tuple[str, float]], scale: float = 100) -> Markup:
    body = []
    for label, value in rows:
        width = 100 * max(0, min(float(value) / scale, 1))
        suffix = "%" if scale == 100 else "/5"
        body.append(
            f'<div class="bar-row"><span class="bar-label">{escape(label)}</span>'
            f'<div class="bar-track"><span class="bar-fill" style="width:{width:.1f}%;background:{BLUE}"></span></div>'
            f'<strong class="bar-value">{_vi_number(float(value))}{suffix}</strong></div>'
        )
    axis = "Điểm trên 5" if scale == 5 else "Tỷ lệ (%)"
    body.append(f'<p class="bar-axis">{axis}</p>')
    description = "; ".join(f"{label}: {_vi_number(float(value))}" for label, value in rows)
    return _html_chart(title, description, "".join(body))
