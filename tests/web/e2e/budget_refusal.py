from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
SHOTS = ROOT / "docs/build/shots/readability"
AXE = ROOT / "web/node_modules/axe-core/axe.min.js"
INPUT = {
    "brand_name": "Mây Da",
    "product_type": "Chống nắng",
    "product_specs": "SPF 50, không gây bết",
    "budget_vnd": 5_000_000,
    "count": 5,
    "followers_min": 10_000,
    "followers_max": 300_000,
    "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
    "avoid_same_mcn": True,
}
OPTIONS = {
    "max_count_within_budget": {"count": 2, "cost_vnd": 4_000_000},
    "min_budget_for_count": {"budget_vnd": 12_000_000},
    "cheaper_follower_band": {"follower_min": 10_000, "follower_max": 50_000, "cost_vnd": 4_500_000},
}
WARNINGS = ["Ngân sách hiện tại chỉ đủ cho 2 KOC.", "Tăng ngân sách hoặc đổi khoảng người theo dõi."]
CREATOR = {
    "creator_id": "c-one", "nickname": "Linh Trần", "handle": "@linh.tran", "followers": 25_000,
    "fit": 82, "confidence": "Đầy đủ", "confidence_count": 3,
    "components": {"commercial": 78, "audience": 84, "content": 81}, "cost_vnd": 8_000_000,
    "reason": "Nội dung phù hợp với sản phẩm.", "evidence_ids": ["metric:c-one:video_gpm"], "video_evidence_ids": [],
    "reasons": [{"text": "Tỷ lệ tương tác ổn định.", "evidence_ids": ["metric:c-one:video_gpm"]}, {"text": "Nội dung phù hợp với sản phẩm.", "evidence_ids": []}],
    "caveats": [{"text": "Thiếu dữ liệu về lịch đăng.", "evidence_ids": ["metric:c-one:skincare_revenue_share"]}],
}


def campaign(campaign_id: str, input_data=None, refused=False, options=None):
    input_data = input_data or INPUT
    if refused:
        return {
            "campaign_id": campaign_id, "created_at": "2026-11-16T00:00:00Z", "input": input_data,
            "result": {"status": "refused", "picked": [], "warnings": WARNINGS, "options": options,
                       "budget_vnd": input_data["budget_vnd"], "leftover_vnd": input_data["budget_vnd"]},
        }
    return {
        "campaign_id": campaign_id, "created_at": "2026-11-16T00:00:00Z", "input": input_data,
        "result": {"status": "ok", "picked": [CREATOR], "alternates": [], "total_cost_vnd": 8_000_000,
                   "warnings": [], "leftover_vnd": max(0, input_data["budget_vnd"] - 8_000_000),
                   "ranked_count": 1, "run_id": "run-1", "low_confidence_pool": False},
    }


def run_proposal():
    return {
        "run_id": "run-1", "started_at": "2026-11-16T00:00:00Z", "product": "Kem chống nắng", "target": "Khán giả nữ, 18–34 tuổi",
        "picks": [{
            "creator_id": "c-one", "rank": 1, "nickname": "Linh Trần", "handle": "@linh.tran", "followers": 25_000,
            "cost_vnd": 8_000_000, "score": 82, "score_parts": {"commercial": 78, "audience": 84, "content": 81},
            "audience_text": None, "reason": "Nội dung phù hợp với sản phẩm.",
            "reasons": [{"text": "Tỷ lệ tương tác ổn định.", "evidence_ids": ["metric:c-one:video_gpm"]}, {"text": "Nội dung phù hợp với sản phẩm.", "evidence_ids": []}],
            "caveats": ["Thiếu dữ liệu về lịch đăng."], "caveat_evidence": [{"text": "Thiếu dữ liệu về lịch đăng.", "evidence_ids": ["metric:c-one:skincare_revenue_share"]}],
            "audience_note": None, "video_evidence_ids": [], "evidence_count": 0, "evidence_ids": [],
        }],
        "total_cost_vnd": 8_000_000, "budget_vnd": 10_000_000,
    }


def mock_route(route, posts):
    request = route.request
    path = request.url.split("/api", 1)[-1]
    if request.method == "POST" and path == "/campaigns":
        body = request.post_data_json
        posts.append(body)
        route.fulfill(json=campaign(f"created-{len(posts)}", body))
    elif path == "/campaigns":
        route.fulfill(json=[{
            "campaign_id": "c-refused", "created_at": "2026-11-16T00:00:00Z", "input": INPUT,
            "picked_count": 0, "result": {"status": "refused"},
        }])
    elif path == "/campaigns/c-refused":
        route.fulfill(json=campaign("c-refused", refused=True, options=OPTIONS))
    elif path.startswith("/campaigns/created-"):
        route.fulfill(json=campaign(path.rsplit("/", 1)[-1], posts[-1]))
    elif path == "/campaigns/c-success":
        route.fulfill(json=campaign("c-success", {**INPUT, "budget_vnd": 10_000_000}))
    elif path == "/latestRun":
        route.fulfill(json={"run_id": "run-1"})
    elif path == "/runs/run-1/proposal":
        route.fulfill(json=run_proposal())
    elif path == "/stats":
        route.fulfill(json={"creators_in_pool": 10, "creators_with_s3_score": 8, "analyzed_videos": 20})
    else:
        route.fulfill(status=404, json={"detail": f"Unhandled mock route: {path}"})


def check_axe(page):
    page.add_script_tag(path=str(AXE))
    serious = page.evaluate("async () => (await axe.run(document)).violations.filter(v => ['serious', 'critical'].includes(v.impact)).map(v => `${v.id}: ${v.description}`)")
    assert not serious, serious


def wait_for_server(process, base):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Vite exited before it became ready")
        try:
            with urlopen(base, timeout=1):
                return
        except Exception:
            time.sleep(0.2)
    raise TimeoutError("Vite did not start")


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        port = port_probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [str(ROOT / "web/node_modules/.bin/vite"), "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT / "web", env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        wait_for_server(server, base)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True)
            posts = []
            page = browser.new_page(viewport={"width": 1440, "height": 1600})
            page.route("**/api/**", lambda route: mock_route(route, posts))
            page.goto(f"{base}/chien-dich/c-refused", wait_until="networkidle")
            assert page.get_by_role("heading", name="Ngân sách chưa đủ cho 5 KOC").is_visible()
            assert page.locator(".refusal-warnings li").all_text_contents() == WARNINGS
            assert page.locator(".refusal-option").count() == 3
            assert page.get_by_role("link", name="Xem bản đề xuất").count() == 0
            page.screenshot(path=str(SHOTS / "refuse_1440.png"), full_page=True)
            check_axe(page)

            for index, (name, expected) in enumerate([
                ("count", {"count": 2}), ("budget", {"budget_vnd": 12_000_000}),
                ("followers", {"followers_min": 10_000, "followers_max": 50_000}),
            ]):
                page.goto(f"{base}/chien-dich/c-refused", wait_until="networkidle")
                page.locator(".refusal-option").nth(index).click()
                page.wait_for_url("**/chien-dich/created-*")
                page.wait_for_selector(".budget-panel")
                assert page.get_by_role("heading", name="Mây Da").is_visible(), page.locator("body").inner_text()
                submitted = posts[-1]
                assert submitted["brand_name"] == INPUT["brand_name"]
                assert submitted["product_type"] == INPUT["product_type"]
                assert submitted["product_specs"] == INPUT["product_specs"]
                assert submitted["target"] == INPUT["target"]
                assert submitted["avoid_same_mcn"] is True
                assert all(submitted[key] == value for key, value in expected.items()), name

            page.route("**/api/campaigns/c-refused", lambda route: route.fulfill(json=campaign("c-refused", refused=True, options={"max_count_within_budget": OPTIONS["max_count_within_budget"], "min_budget_for_count": None, "cheaper_follower_band": None})))
            page.goto(f"{base}/chien-dich/c-refused", wait_until="networkidle")
            assert page.locator(".refusal-option").count() == 1

            page.goto(f"{base}/chien-dich", wait_until="networkidle")
            assert page.get_by_text("Ngân sách chưa đủ", exact=True).is_visible()
            assert page.get_by_role("link", name="Bản đề xuất").count() == 0

            for width in (375, 1440):
                refused_page = browser.new_page(viewport={"width": width, "height": 2000})
                refused_page.route("**/api/**", lambda route: mock_route(route, posts))
                refused_page.goto(f"{base}/chien-dich/c-refused", wait_until="networkidle")
                refused_page.get_by_role("heading", name="Ngân sách chưa đủ cho 5 KOC").wait_for()
                refused_page.screenshot(path=str(SHOTS / f"refuse_{width}.png"), full_page=True)
                check_axe(refused_page)
                result_page = browser.new_page(viewport={"width": width, "height": 2000})
                result_page.route("**/api/**", lambda route: mock_route(route, posts))
                result_page.goto(f"{base}/chien-dich/c-success", wait_until="networkidle")
                result_page.get_by_text("Còn lại 2.000.000 ₫ chưa dùng").wait_for()
                assert result_page.locator(".review-columns section").count() == 2
                assert result_page.locator(".review-columns ul").first.evaluate("element => getComputedStyle(element).listStyleType") == "disc"
                assert result_page.locator(".review-columns li .evidence-markers").count() > 0
                result_page.screenshot(path=str(SHOTS / f"lists_{width}.png"), full_page=True)
                check_axe(result_page)
                proposal_page = browser.new_page(viewport={"width": width, "height": 2000})
                proposal_page.route("**/api/**", lambda route: mock_route(route, posts))
                proposal_page.goto(f"{base}/chien-dich/c-success/de-xuat", wait_until="networkidle")
                proposal_page.get_by_text("Còn lại 2.000.000 ₫ chưa dùng").wait_for()
                check_axe(proposal_page)
                run_page = browser.new_page(viewport={"width": width, "height": 2000})
                run_page.route("**/api/**", lambda route: mock_route(route, posts))
                run_page.goto(f"{base}/de-xuat/run-1", wait_until="networkidle")
                run_page.get_by_text("Còn lại 2.000.000 ₫ chưa dùng").wait_for()
                assert run_page.locator(".review-columns section").count() == 2
                assert run_page.locator(".review-columns ul").first.evaluate("element => getComputedStyle(element).listStyleType") == "disc"
                assert run_page.locator(".review-columns li .evidence-markers").count() > 0
                check_axe(run_page)
                result_page.close()
                refused_page.close()
                proposal_page.close()
                run_page.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    main()
