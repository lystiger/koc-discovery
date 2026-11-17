from __future__ import annotations

import json
import os
import re
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
import time
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from koc import db
from tests.web.fixtures.seed import seed_fixture_db


ROOT = Path(__file__).resolve().parents[3]
BASE = ""
AXE = ROOT / "web/node_modules/axe-core/axe.min.js"
SHOTS = ROOT / "docs/process/build/shots/readability"
SHOTS2 = ROOT / "docs/shots/v2_web2"


def wait_for_server(process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("KOC server exited before it became ready")
        try:
            with urlopen(BASE, timeout=1):
                return
        except Exception:
            time.sleep(0.2)
    raise TimeoutError("KOC server did not start")


def main():
    global BASE
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        BASE = f"http://127.0.0.1:{port_probe.getsockname()[1]}"
    SHOTS.mkdir(parents=True, exist_ok=True)
    SHOTS2.mkdir(parents=True, exist_ok=True)
    chromium_shots = SHOTS / "chromium"
    chromium_shots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="koc-brand-platform-") as temporary:
        work = Path(temporary)
        database = work / "fixture.db"
        media = work / "media"
        seed_fixture_db(database, media)
        conn = db.connect(database)
        db.upsert_metric(conn, "c_linh_01", "unknown_metric", 17, "fixture", "last30Day")
        analysis_row = conn.execute("SELECT analysis_json FROM analyses WHERE video_id='v_c_linh_01_1'").fetchone()
        analysis = json.loads(analysis_row[0])
        analysis["rubric"].append({"criterion": "unknown_criterion", "score": 3, "rationale_vi": "Tiêu chí thử nghiệm."})
        conn.execute("UPDATE analyses SET analysis_json=? WHERE video_id='v_c_linh_01_1'", (json.dumps(analysis, ensure_ascii=False),))
        conn.commit()
        conn.close()
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        server = subprocess.Popen(
            [sys.executable, "-m", "koc.web", "--db", str(database), "--media-dir", str(media), "--port", BASE.rsplit(":", 1)[1]],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for_server(server)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path="/usr/bin/chromium", headless=True)
                api_client = playwright.request.new_context()
                empty_landing = browser.new_page(viewport={"width": 375, "height": 1200})
                empty_landing.goto(BASE, wait_until="networkidle")
                assert empty_landing.get_by_role("heading", name="Tìm đúng KOC cho thương hiệu của bạn").is_visible()
                assert empty_landing.get_by_role("link", name="Xem một bản đề xuất mẫu").count() == 0
                empty_landing.close()
                start = time.monotonic()
                create_response = api_client.post(f"{BASE}/api/campaigns", data={
                    "brand_name": "Mây Daily",
                    "product_type": "Chống nắng",
                    "product_specs": "SPF50+ cho da dầu",
                    "budget_vnd": 65_000_000,
                    "count": 5,
                    "followers_min": 10_000,
                    "followers_max": 300_000,
                    "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
                    "avoid_same_mcn": True,
                })
                assert create_response.ok, create_response.text()
                campaign = create_response.json()
                match_seconds = time.monotonic() - start
                assert len(campaign["result"]["picked"]) == 5
                assert campaign["result"]["total_cost_vnd"] <= campaign["input"]["budget_vnd"]
                assert len({item["mcn"] for item in campaign["result"]["picked"] if item["mcn"]}) == len([item["mcn"] for item in campaign["result"]["picked"] if item["mcn"]])
                assert match_seconds < 2, f"Matching took {match_seconds:.3f}s"

                landing = browser.new_page(viewport={"width": 375, "height": 1600})
                landing.goto(BASE, wait_until="networkidle")
                landing.get_by_role("link", name="Bắt đầu chiến dịch").first.click()
                landing.wait_for_url("**/chien-dich/moi")
                landing.goto(BASE, wait_until="networkidle")
                landing.get_by_role("link", name="Xem một bản đề xuất mẫu").click()
                landing.wait_for_url(f"**/chien-dich/{campaign['campaign_id']}/de-xuat")
                landing.goto(BASE, wait_until="networkidle")
                landing.get_by_role("link", name="Bắt đầu chiến dịch").last.click()
                landing.wait_for_url("**/chien-dich/moi")
                landing.close()

                cancel = browser.new_page(viewport={"width": 375, "height": 900})
                cancel.goto(f"{BASE}/chien-dich/moi", wait_until="networkidle")
                cancel.get_by_role("link", name="Hủy").click()
                cancel.wait_for_url("**/chien-dich")
                cancel.close()

                empty_campaign = api_client.post(f"{BASE}/api/campaigns", data={
                    "brand_name": "Mây Daily",
                    "product_type": "Chống nắng",
                    "budget_vnd": 30_000_000,
                    "count": 2,
                    "followers_min": 5_000_000,
                    "followers_max": 6_000_000,
                    "target": {"gender": "Nữ", "age_groups": ["18-24"]},
                    "avoid_same_mcn": True,
                }).json()
                assert empty_campaign["result"]["picked"] == []
                assert empty_campaign["result"]["warning"], empty_campaign
                long_name = "K" * 60
                long_campaign = api_client.post(f"{BASE}/api/campaigns", data={
                    "brand_name": long_name,
                    "product_type": "Chống nắng",
                    "budget_vnd": 30_000_000,
                    "count": 2,
                    "followers_min": 10_000,
                    "followers_max": 300_000,
                    "target": {"gender": "Nữ", "age_groups": ["18-24"]},
                    "avoid_same_mcn": True,
                }).json()
                latest_campaign_id = long_campaign["campaign_id"]
                assert api_client.get(f"{BASE}/api/campaigns").json()[0]["campaign_id"] == latest_campaign_id
                conn = db.connect(database)
                run_id = conn.execute("SELECT run_id FROM recommendations ORDER BY rowid LIMIT 1").fetchone()[0]
                conn.close()
                run_picks = api_client.get(f"{BASE}/api/runs/{run_id}/proposal").json()["picks"]
                run_creator_id = run_picks[0]["creator_id"]

                routes = {
                    "landing": f"{BASE}/",
                    "campaign_list": f"{BASE}/chien-dich",
                    "form": f"{BASE}/chien-dich/moi",
                    "results": f"{BASE}/chien-dich/{campaign['campaign_id']}",
                    "proposal": f"{BASE}/chien-dich/{campaign['campaign_id']}/de-xuat",
                    "run_proposal": f"{BASE}/de-xuat/{run_id}",
                    "run_creator": f"{BASE}/de-xuat/{run_id}/koc/{run_creator_id}",
                    "creator": f"{BASE}/koc/c_linh_01",
                    "operator": f"{BASE}/van-hanh",
                }
                violations = []
                for width in (375, 1440):
                    for name, url in routes.items():
                        page = browser.new_page(viewport={"width": width, "height": 4000}, device_scale_factor=1)
                        page.goto(url, wait_until="networkidle")
                        page.wait_for_selector("h1")
                        page.wait_for_timeout(250)
                        assert page.locator(".site-header").count() == 1
                        assert page.locator(".site-footer").count() == 1
                        assert page.locator(".title-block h1").count() == 1
                        if width == 375 and name not in {"form", "campaign_list"}:
                            header = page.locator(".site-header").bounding_box()
                            cta = page.locator(".site-header .header-cta")
                            assert header["height"] <= 70, f"{name}@{width}: header wrapped to {header['height']}px"
                            assert cta.is_visible()
                            assert cta.get_attribute("aria-label") == "Bắt đầu chiến dịch"
                            assert cta.inner_text().strip() == "Bắt đầu"
                            assert cta.evaluate("element => getComputedStyle(element).whiteSpace") == "nowrap"
                            assert cta.locator(".header-cta-label").bounding_box()["width"] > 0
                            assert cta.bounding_box()["y"] < header["y"] + header["height"]
                        for button in page.locator(".pill-button:not(.header-cta)").evaluate_all("items => items.map(item => { const style = getComputedStyle(item); return {height: style.height, fontSize: style.fontSize}; })"):
                            assert button == {"height": "50px", "fontSize": "16px"}, f"{name}@{width}: {button}"
                        if name == "landing" and width == 375:
                            assert page.locator(".wordmark").bounding_box()["width"] >= 200
                        if name in {"landing", "results", "proposal", "run_proposal"}:
                            strip = page.locator(".budget-strip")
                            assert strip.count() == 1, f"{name}@{width}: shared budget strip missing"
                            assert strip.locator(".budget-breakdown-item").count() == strip.locator("[data-segment='creator']").count()
                            assert all(value.endswith(("tr", "nghìn")) for value in strip.locator(".budget-breakdown-item strong").all_inner_texts())
                            remaining = strip.locator("[data-segment='remaining']")
                            if remaining.count():
                                assert remaining.bounding_box()["width"] > 0, f"{name}@{width}: leftover segment has no width"
                                assert "Còn lại" in remaining.inner_text()
                                assert remaining.locator(".budget-segment-amount").is_visible()
                                assert "chưa dùng" in strip.inner_text()
                            assert strip.locator(".budget-initial").count() == strip.locator("[data-segment='creator']").count()
                            if name != "landing":
                                segments = strip.locator("button.budget-segment")
                                assert segments.count() > 1
                                first_name = segments.first.locator(".budget-segment-name").inner_text()
                                segments.first.focus()
                                page.keyboard.press("ArrowRight")
                                active_state = page.evaluate("({tag: document.activeElement.tagName, label: document.activeElement.querySelector('.budget-segment-name')?.textContent, html: document.activeElement.outerHTML.slice(0, 200)})")
                                assert active_state["label"] != first_name and active_state["tag"] == "BUTTON", active_state
                                focused_name = page.evaluate("document.activeElement.querySelector('.budget-segment-name').textContent")
                                if name == "results":
                                    assert page.locator(".creator-row").filter(has_text=focused_name).get_attribute("data-budget-highlight") == "true"
                                popup = page.locator(".budget-popover")
                                segments.first.hover()
                                popup.wait_for(state="visible", timeout=1500)
                                assert popup.is_visible()
                                assert segments.first.locator(".budget-segment-name").inner_text() in popup.inner_text()
                                assert "₫" in popup.inner_text()
                                assert popup.get_by_role("link", name="Xem KOC").is_visible()
                                assert popup.get_by_text("% ngân sách", exact=False).is_visible()
                                if width == 1440 and name == "results":
                                    page.screenshot(path=str(SHOTS / "money_tooltip_1440.png"))
                                    page.add_script_tag(path=str(AXE))
                                    popup_axe = page.evaluate("async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}})")
                                    serious = [item for item in popup_axe["violations"] if item["impact"] == "serious"]
                                    assert not serious, f"Tooltip axe findings: {serious}"
                                page.keyboard.press("Escape")
                                page.mouse.move(0, 0)
                                segments.first.click()
                                popup.wait_for(state="visible", timeout=1500)
                                page.keyboard.press("Escape")
                                page.mouse.move(0, 0)
                                page.mouse.click(0, 0)
                        if name == "landing":
                            assert page.locator(".landing-art img").get_attribute("width") == "1100"
                            assert page.locator(".landing-art img").get_attribute("height") == "697"
                            if width == 375:
                                assert page.locator(".site-header .header-cta").is_visible()
                                assert page.locator(".landing-hero h1 em").evaluate("element => getComputedStyle(element).fontStyle") == "italic"
                            if width == 1440:
                                assert page.locator(".landing-trust h2").evaluate("element => getComputedStyle(element).textAlign") == "center"
                            sample_href = page.get_by_role("link", name="Xem một bản đề xuất mẫu").get_attribute("href")
                            browser_campaign_ids = page.evaluate("async () => (await (await fetch('/api/campaigns', {cache: 'no-store'})).json()).map(campaign => campaign.campaign_id)")
                            assert sample_href == f"/chien-dich/{browser_campaign_ids[0]}/de-xuat", f"sample href {sample_href}; newest campaign {browser_campaign_ids[0]}"
                            assert page.locator(".landing-trust dd").count() == 3
                            assert all(value.is_visible() for value in page.locator(".landing-trust dd").all())
                            page.locator(".budget-track").scroll_into_view_if_needed()
                            for selector in (".landing-art-floater", ".landing-overlay .handoff"):
                                assert page.locator(selector).first.evaluate("element => element.getAnimations().some(animation => animation.playState === 'running')"), f"Expected motion on {selector}"
                            segment = page.locator(".budget-track .budget-item").first
                            assert segment.evaluate("element => element.getBoundingClientRect().width > 0"), "Budget strip did not reveal its segments"
                            assert segment.evaluate("element => getComputedStyle(element).transitionDuration.includes('0.9s')"), "Budget strip has no reveal transition"
                        if name in {"form", "results", "proposal", "run_proposal", "creator", "run_creator"}:
                            text = page.locator("body").inner_text().lower()
                            for secret in ("token", "credit", "usd", "latency", "task"):
                                assert secret not in text, f"Brand page exposes {secret}"
                        if name == "results":
                            assert "Khán giả nữ, 18–34 tuổi" in page.locator(".results-intro").inner_text()
                            assert page.locator(".step-indicator li[aria-current='step']").inner_text() == "Chọn KOC"
                            assert page.locator(".ranked-list .creator-row").count() == 5
                            evidence_links = page.locator(".creator-row .evidence-link")
                            creator_rows = page.locator(".creator-row")
                            for row in creator_rows.all():
                                row_links = row.locator(".evidence-link")
                                assert row_links.count() <= 1
                                if row_links.count() == 1:
                                    assert row_links.inner_text().startswith("Xem bằng chứng (") and row_links.inner_text().endswith(")")
                                    assert row_links.get_attribute("href").endswith("#evidence")
                            assert evidence_links.count() <= creator_rows.count()
                            results_text = page.locator("body").inner_text()
                            assert "82,5%" in results_text
                            assert "Điểm nội dung S3" not in results_text
                            trinh_row = creator_rows.filter(has=page.locator('a[href="/koc/c_trinh_03"]'))
                            assert trinh_row.locator(".score-box-part").nth(2).locator(".tabular").inner_text() == "91"
                            assert page.locator(".budget-segment-remaining").count() == 1
                            remaining_background = page.locator(".budget-segment-remaining").evaluate("element => getComputedStyle(element).backgroundImage")
                            assert "repeating-linear-gradient" in remaining_background
                            assert page.locator(".budget-segment-remaining .budget-segment-name").is_visible()
                        if name == "form":
                            assert page.locator(".step-indicator li[aria-current='step']").inner_text() == "Sản phẩm"
                            assert page.locator(".step-indicator li span").all_text_contents() == ["Sản phẩm", "Chọn KOC", "Đề xuất"]
                            if width == 375:
                                labels = page.locator(".step-indicator li span").evaluate_all("items => items.map(item => { const box = item.getBoundingClientRect(); return {left: box.left, right: box.right}; })")
                                assert all(left["right"] < right["left"] for left, right in zip(labels, labels[1:]))
                            assert page.get_by_role("link", name="Hủy").get_attribute("href") == "/chien-dich"
                            assert page.locator("#count").input_value() == "5"
                            assert page.locator("#followers-min").input_value() == "10.000"
                            assert page.locator("#brand").get_attribute("maxlength") == "80"
                            assert page.locator("#specs").get_attribute("maxlength") == "1000"
                            assert page.locator("#budget").get_attribute("inputmode") == "numeric"
                            assert page.locator("#followers-max").get_attribute("inputmode") == "numeric"
                            assert page.locator("#count").get_attribute("min") == "1" and page.locator("#count").get_attribute("max") == "10"
                            assert page.locator("#avoid-same-mcn").is_checked()
                            assert page.locator(".select-trigger").first.inner_text().strip() == "Chống nắng"
                            assert page.locator("#gender").count() == 0
                            assert page.locator("[aria-labelledby='gender-label']").get_attribute("role") == "combobox"
                            assert page.locator("#budget").input_value() == "30.000.000"
                            assert page.get_by_role("button", name="18–34").get_attribute("aria-pressed") == "true"
                            assert page.locator(".age-ticks").inner_text().splitlines()[0] == "18–24"
                            assert page.get_by_text("Đang chọn: 18–34 tuổi").is_visible()
                            page.get_by_role("button", name="35–54").click()
                            assert page.get_by_text("Đang chọn: 35–54 tuổi").is_visible()
                            assert page.get_by_role("button", name="35–54").get_attribute("aria-pressed") == "true"
                            assert page.get_by_role("button", name="18–34").get_attribute("aria-pressed") == "false"
                            assert page.get_by_role("slider", name="Tuổi nhỏ nhất").get_attribute("aria-valuetext") == "35–54 tuổi"
                            assert page.get_by_role("slider", name="Tuổi lớn nhất").get_attribute("aria-valuetext") == "35–54 tuổi"
                            page.wait_for_timeout(250)
                        if name == "creator" and width == 375:
                            assert page.get_by_role("dialog").is_visible(), "Mobile creator detail did not open as a sheet"
                        if name == "run_creator" and width == 375:
                            assert page.get_by_role("dialog").is_visible(), "Mobile run creator detail did not open as a sheet"
                        if name in {"creator", "run_creator"}:
                            detail_scope = ".drawer-content .creator-detail" if width == 375 else ".creator-detail"
                            if width == 1440:
                                assert page.locator(".creator-detail").evaluate("el => el.getBoundingClientRect().height") <= 2500
                            if page.locator(".transcript-disclosure").count():
                                page.locator(".transcript-disclosure").first.locator("summary").click()
                            if page.get_by_text("Xem tất cả số liệu").count():
                                page.get_by_text("Xem tất cả số liệu").click()
                            detail_text = page.locator(".creator-detail").inner_text()
                            for raw_key in ("brand_fit", "claim_quality", "product_clarity", "production_quality", "hook", "demonstration", "cta", "unknown_criterion", "unknown_metric", "age_18_24_pct", "age_25_34_pct", "video_vs_live_share"):
                                assert raw_key not in detail_text, f"Creator page exposes key {raw_key}"
                            assert "Mức phù hợp với thương hiệu" in detail_text
                            assert "Tiêu chí khác" in detail_text
                            assert "Chỉ số khác" in detail_text
                            evidence_names = page.locator(detail_scope).last.locator("a.evidence-marker").evaluate_all("links => links.map(link => link.getAttribute('aria-label'))")
                            assert evidence_names and all(evidence_names) and len(evidence_names) == len(set(evidence_names)), evidence_names
                            assert all(name.startswith("Bằng chứng ") for name in evidence_names)
                            targets = page.locator(detail_scope).last.locator("a.evidence-marker").evaluate_all("links => links.map(link => decodeURIComponent(new URL(link.href).hash.slice(1)))")
                            assert all(page.locator(f'[id="{target}"]').count() == 1 for target in targets)
                            sections = page.locator(".creator-detail > section h2").all_text_contents()
                            assert sections[:3] == ["Tóm tắt", "Số liệu chính", "Bằng chứng từ video"]
                            if width == 1440:
                                assert page.locator(".review-columns").first.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 2
                                if page.locator(".frame-trigger").count():
                                    page.locator(".frame-trigger").first.click()
                                    assert page.get_by_role("dialog").is_visible()
                                    page.get_by_role("button", name="Đóng").click()
                            else:
                                assert page.locator(".review-columns").first.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 1
                        if name == "run_proposal":
                            names = page.locator(".run-proposal-list .evidence-marker").evaluate_all("items => items.map(el => el.getAttribute('aria-label'))")
                            assert len(names) == len(set(names))
                            assert page.locator(".budget-accessible-list li").count() == page.locator(".run-proposal-list > li").count() + 1
                            widths = page.locator(".budget-track > .budget-item").evaluate_all("items => items.reduce((sum, item) => sum + item.getBoundingClientRect().width, 0)")
                            track_width = page.locator(".budget-track").evaluate("el => el.getBoundingClientRect().width")
                            assert abs(widths - track_width) < 2, f"budget segments total {widths}px; track {track_width}px"
                            shared_audience = page.locator(".run-proposal-list > li").first.locator(".notice").last.inner_text() if page.locator(".run-proposal-list > li .notice").count() else None
                            if shared_audience:
                                assert page.get_by_text(shared_audience, exact=True).count() == 1
                            if width == 1440:
                                assert page.locator(".run-proposal-list .review-columns").first.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 2
                            else:
                                assert page.locator(".run-proposal-list .review-columns").first.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == 1
                        if name == "operator":
                            assert page.locator(".recharts-bar-rectangle").count() > 0, "Operator chart has no bars"
                            operator_text = page.locator("body").inner_text()
                            for raw_status in ("done", "blocked", "running", "pending", "failed"):
                                assert raw_status not in operator_text
                            assert "Hoàn tất" in operator_text
                            if width == 375:
                                assert page.evaluate("document.documentElement.scrollWidth") == 375
                        shot_path = SHOTS / f"{name}_{width}.png"
                        page.screenshot(path=str(shot_path))
                        if name in {"landing", "results", "proposal", "run_proposal"}:
                            page.screenshot(path=str(SHOTS / f"money_{name}_{width}.png"))
                        subprocess.run([
                            "chromium", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--virtual-time-budget=4000", f"--window-size={width},4000",
                            f"--user-data-dir={work / f'chromium-{name}-{width}'}",
                            f"--screenshot={chromium_shots / f'{name}_{width}.png'}", url,
                        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        page.add_script_tag(path=str(AXE))
                        result = page.evaluate("async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}})")
                        serious = [item for item in result["violations"] if item["impact"] == "serious"]
                        violations.extend(f"{name}@{width}: {item['id']} {item['nodes'][0]['target']}" for item in serious)
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"Horizontal overflow at {width}px on {name}"
                        if name == "results":
                            page.locator(".ranked-list .creator-row .evidence-marker").first.click()
                            page.locator(".creator-detail").wait_for(state="visible")
                            assert page.evaluate("window.location.hash") not in ("", "#evidence")
                            page.locator(".evidence-highlight").wait_for(state="attached", timeout=2500)
                            assert page.locator(".evidence-highlight").count() == 1
                        if name in {"results", "proposal"}:
                            expected_columns = 1 if width == 375 else 2
                            assert page.locator(".review-columns").first.evaluate("el => getComputedStyle(el).gridTemplateColumns.split(' ').length") == expected_columns
                        if name == "form":
                            submit = page.get_by_role("button", name="Tìm KOC phù hợp")
                            page.locator("#brand").fill("")
                            submit.click()
                            assert page.get_by_text("Nhập tên thương hiệu.").is_visible()
                            page.locator("#brand").fill("Mây Daily")
                            page.locator("#budget").fill("100")
                            submit.click()
                            assert page.get_by_text("Ngân sách từ 1.000.000 đến 10.000.000.000 ₫.").is_visible()
                            page.locator("#budget").fill("65000000")
                            assert page.locator("#budget").input_value() == "65.000.000"
                            page.locator("#count").fill("11")
                            submit.click()
                            assert page.get_by_text("Chọn từ 1 đến 10 KOC.").is_visible()
                            page.locator("#count").fill("5")
                            page.locator("#followers-min").fill("300000")
                            page.locator("#followers-max").fill("10000")
                            submit.click()
                            assert page.get_by_text("Khoảng người theo dõi chưa hợp lệ.").is_visible()
                            page.locator("#followers-min").fill("10000")
                            page.locator("#followers-max").fill("300000")
                            assert page.locator("#followers-min").input_value() == "10.000"
                            assert page.locator("#followers-max").input_value() == "300.000"
                            page.get_by_role("slider", name="Tuổi lớn nhất").press("ArrowRight")
                            assert page.get_by_text("Đang chọn: 35 tuổi trở lên").is_visible()
                            assert page.get_by_role("button", name="35–54").get_attribute("aria-pressed") == "false"
                            page.get_by_role("button", name="18–34").click()
                            submit.click()
                            page.locator(".searching-state").wait_for(state="visible", timeout=800)
                            assert page.locator(".searching-strip span").evaluate("element => element.getAnimations().some(animation => animation.playState === 'running')")
                            page.wait_for_function("location.pathname.startsWith('/chien-dich/') && location.pathname !== '/chien-dich/moi'")
                            page.wait_for_selector(".ranked-list .creator-row")
                            assert page.locator(".ranked-list .creator-row").count() == 5
                            assert page.get_by_text("Đã lưu chiến dịch.").is_visible()
                            page.wait_for_timeout(300)
                            for state in ("toast-visible", "palette-open"):
                                if state == "palette-open":
                                    page.keyboard.press("Control+k")
                                    page.locator(".search-dialog").wait_for(state="visible")
                                result = page.evaluate("async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}})")
                                serious = [item for item in result["violations"] if item["impact"] == "serious"]
                                violations.extend(f"{name}@{width}:{state}: {item['id']} {item['nodes'][0]['target']}" for item in serious)
                            page.keyboard.press("Escape")
                        if name == "proposal":
                            assert page.locator(".proposal-brand .brand-logo").is_visible()
                            assert "Khán giả nữ, 18–34 tuổi" in page.locator(".proposal-lede").inner_text()
                            screen_logo_box = page.locator(".proposal-brand .brand-logo").bounding_box()
                            assert screen_logo_box and screen_logo_box["width"] > 0 and screen_logo_box["height"] > 0
                        if name == "proposal" and width == 1440:
                            assert page.locator(".step-indicator li[aria-current='step']").inner_text() == "Đề xuất"
                            proposal_text = page.locator(".proposal").inner_text()
                            assert "KOC Discovery ·" not in proposal_text
                            assert "Ngày tạo" in proposal_text
                            assert "Điểm nội dung S3" not in proposal_text
                            assert page.locator(".proposal-list .creator-summary-line").count() == 5
                            assert page.locator(".proposal-list .review-columns").count() == 5
                            assert "60.000.000 ₫" in proposal_text
                            page.emulate_media(media="print")
                            logo_box = page.locator(".proposal-brand .brand-logo").bounding_box()
                            assert logo_box and logo_box["width"] > 0 and logo_box["height"] > 0
                            assert page.locator(".site-header").evaluate("element => getComputedStyle(element).display") == "none"
                            assert page.locator(".proposal-actions").evaluate("element => getComputedStyle(element).display") == "none"
                            assert page.locator(".skip-link").evaluate("element => getComputedStyle(element).display") == "none"
                            pdf_path = SHOTS / "proposal_1440.pdf"
                            page.pdf(path=str(pdf_path), format="A4", print_background=True)
                            info = subprocess.run(["pdfinfo", str(pdf_path)], check=True, capture_output=True, text=True).stdout
                            pages = int(next(line.split(":", 1)[1] for line in info.splitlines() if line.startswith("Pages:")))
                            assert pages <= 3, f"Proposal printed to {pages} pages"
                            pdf_text = subprocess.run(["pdftotext", str(pdf_path), "-"], check=True, capture_output=True, text=True).stdout
                            assert "Đến nội dung chính" not in pdf_text
                            assert all(creator["nickname"] in pdf_text for creator in campaign["result"]["picked"])
                            assert "Còn lại" in pdf_text and "chưa dùng" in pdf_text
                            assert "5 tr" in pdf_text
                            subprocess.run(["pdftoppm", "-f", str(pages), "-l", str(pages), "-scale-to", "1100", "-png", str(pdf_path), str(SHOTS / "proposal-last-page")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if name == "run_proposal":
                            assert page.locator(".step-indicator li[aria-current='step']").inner_text() == "Đề xuất"
                            assert page.locator(".run-proposal-list > li").count() == len(run_picks)
                            assert "S1" not in page.locator("body").inner_text()
                            assert "token" not in page.locator("body").inner_text().lower()
                        page.close()

                touch = browser.new_page(viewport={"width": 375, "height": 900}, has_touch=True)
                touch.goto(routes["results"], wait_until="networkidle")
                touch.locator(".budget-segment[data-segment='creator']").first.tap()
                assert touch.locator(".budget-popover").first.is_visible()
                touch.close()

                reduced = browser.new_page(viewport={"width": 375, "height": 4000})
                reduced.emulate_media(reduced_motion="reduce")
                reduced.goto(routes["landing"], wait_until="networkidle")
                assert reduced.evaluate("document.getAnimations().filter(animation => animation.playState === 'running').length") == 0
                assert reduced.locator(".landing h1").evaluate("element => getComputedStyle(element).opacity") == "1"
                assert reduced.locator(".landing-art img").is_visible()
                assert reduced.locator(".landing-overlay .heart").first.evaluate("element => getComputedStyle(element).opacity") == "1"
                assert reduced.locator(".landing-overlay .handoff").evaluate("element => getComputedStyle(element).opacity") == "1"
                assert reduced.locator(".landing-step").first.evaluate("element => getComputedStyle(element).opacity") == "1"
                assert reduced.locator(".landing-board").evaluate("element => getComputedStyle(element).opacity") == "1"
                assert reduced.locator(".budget-item").first.evaluate("element => getComputedStyle(element).transitionDuration === '0s'")
                assert reduced.locator(".landing-trust dd").first.is_visible()
                assert reduced.locator(".landing-close .landing-button").is_visible()
                assert reduced.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                reduced.close()

                reduced_form = browser.new_page(viewport={"width": 375, "height": 1000})
                reduced_form.emulate_media(reduced_motion="reduce")
                reduced_form.goto(routes["form"], wait_until="networkidle")
                reduced_form.locator("#brand").fill("Giảm chuyển động")
                reduced_form.get_by_role("button", name="Tìm KOC phù hợp").click()
                reduced_form.wait_for_url("**/chien-dich/*", timeout=3000)
                assert reduced_form.locator(".searching-state").count() == 0
                reduced_form.close()

                search = browser.new_page(viewport={"width": 1440, "height": 1000})
                conn = sqlite3.connect(database)
                conn.execute("DELETE FROM scores WHERE creator_id='c_hoa_06' AND stage IN ('S2','S3')")
                conn.commit()
                conn.close()
                missing = browser.new_page(viewport={"width": 375, "height": 900})
                missing.goto(f"{BASE}/koc/c_hoa_06", wait_until="networkidle")
                missing_scores = missing.locator(".detail-review").inner_text()
                assert "chưa có dữ liệu khán giả" in missing_scores
                assert "chưa có dữ liệu nội dung" in missing_scores
                missing.close()

                conn = db.connect(database)
                run_id = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()[0]
                audience_creators = [row[0] for row in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S2'", (run_id,))]
                for creator_id in audience_creators:
                    for metric, value in (("female_pct", 60), ("age_18_24_pct", 30.5), ("age_25_34_pct", 39.5)):
                        db.upsert_metric(conn, creator_id, metric, value, "fixture", "last30Day")
                conn.close()
                placeholder = browser.new_page(viewport={"width": 375, "height": 900})
                placeholder.goto(f"{BASE}/koc/c_linh_01", wait_until="networkidle")
                placeholder_text = placeholder.locator(".creator-detail").inner_text()
                assert "Không có dữ liệu" in placeholder_text
                assert "Điểm Khán giả" not in placeholder_text
                for placeholder_value in ("Khán giả nữ\n60", "Khán giả 18-24 tuổi\n30,5", "Khán giả 25-34 tuổi\n39,5"):
                    assert placeholder_value not in placeholder_text
                placeholder.close()

                empty_page = browser.new_page(viewport={"width": 375, "height": 900})
                empty_page.goto(f"{BASE}/chien-dich/{empty_campaign['campaign_id']}", wait_until="networkidle")
                assert empty_page.get_by_text("Không có KOC trong khoảng người theo dõi đã chọn.").is_visible()
                assert empty_page.get_by_role("link", name="Sửa yêu cầu").is_visible()
                assert empty_page.get_by_role("link", name="Xem bản đề xuất").count() == 0
                empty_page.add_script_tag(path=str(AXE))
                empty_axe = empty_page.evaluate("async () => await axe.run(document, {runOnly: {type: 'rule', values: ['aria-prohibited-attr']}})")
                assert not empty_axe["violations"], empty_axe["violations"]
                empty_page.close()

                mobile_results = browser.new_page(viewport={"width": 375, "height": 900})
                mobile_results.goto(routes["results"], wait_until="networkidle")
                assert mobile_results.locator(".ranked-list .creator-row").count() == 5
                mobile_results.locator(".creator-name").first.click()
                mobile_results.get_by_role("dialog").wait_for(state="visible")
                assert mobile_results.locator(".ranked-list .creator-row").count() == 5
                mobile_results.close()

                for width in (375, 1440):
                    long_page = browser.new_page(viewport={"width": width, "height": 1200})
                    long_page.goto(f"{BASE}/chien-dich/{long_campaign['campaign_id']}", wait_until="networkidle")
                    assert long_page.locator("h1").inner_text().startswith(long_name)
                    assert long_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    long_page.emulate_media(media="print")
                    assert long_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    long_page.close()

                search.goto(routes["campaign_list"], wait_until="networkidle")
                search.keyboard.press("Control+k")
                search.locator("[cmdk-input]").fill("chou.bea")
                search.get_by_text("Chou Chou Skincare").press("Enter")
                search.wait_for_url("**/koc/c_chou_02")
                search.goto(BASE, wait_until="networkidle")
                search.keyboard.press("Control+k")
                search.locator("[cmdk-input]").fill("Danh sách chiến dịch")
                search.get_by_text("Danh sách chiến dịch").press("Enter")
                search.wait_for_url("**/chien-dich")

                # v2 web: TikTok links, brand-fit-excluded box, score breakdown (hrefs only, no TikTok requests)
                links_page = browser.new_page(viewport={"width": 1440, "height": 1400})
                tiktok_requests = []
                links_page.on("request", lambda request: tiktok_requests.append(request.url) if "tiktok.com" in request.url else None)

                def with_missing_handle_and_excluded(route):
                    response = route.fetch()
                    body = response.json()
                    first = body["result"]["picked"][0]
                    first["handle"] = "@" + first["creator_id"]
                    body["result"]["brand_fit_excluded"] = [
                        {"id": "x1", "handle": "@loai_a", "nickname": "Loại A", "max_brand_fit": 2, "reason_vi": "Loại vì video không hợp sản phẩm.", "videos": [{"video_id": "111", "title": "t", "brand_fit": 2}]},
                        {"id": "x2", "handle": "@chua_xet", "max_brand_fit": None, "reason_vi": "Loại vì chưa có video được phân tích.", "videos": []},
                    ]
                    route.fulfill(response=response, json=body)

                links_page.route(f"**/api/campaigns/{campaign['campaign_id']}", with_missing_handle_and_excluded)
                links_page.goto(f"{BASE}/chien-dich/{campaign['campaign_id']}", wait_until="networkidle")
                link_rows = links_page.locator(".creator-row")
                assert link_rows.nth(0).locator("a.tiktok-link").count() == 0, "missing handle must render plain text"
                second_handle = campaign["result"]["picked"][1]["handle"].lstrip("@")
                second_link = link_rows.nth(1).locator("a.tiktok-link")
                assert second_link.get_attribute("href") == f"https://www.tiktok.com/@{second_handle}"
                assert second_link.get_attribute("target") == "_blank" and second_link.get_attribute("rel") == "noopener noreferrer"
                link_name = second_link.text_content()
                assert "Mở trang TikTok của " in link_name and link_name.endswith("(mở tab mới)")
                assert links_page.locator(".score-box").count() == link_rows.count()
                assert "Chưa có dữ liệu" in links_page.locator(".score-box").first.inner_text() or "/100" in links_page.locator(".score-box").first.inner_text()
                assert links_page.locator("#cach-cham-diem").is_visible()
                assert links_page.get_by_role("heading", name="Đã loại 1 KOC vì không hợp thương hiệu").is_visible()
                links_page.get_by_role("button", name="Loại A").click()
                assert links_page.locator(".excluded-videos a").get_attribute("href") == "https://www.tiktok.com/@loai_a/video/111"
                assert links_page.get_by_text("1 KOC khác chưa có video được phân tích").is_visible()
                links_page.add_script_tag(path=str(AXE))
                links_axe = links_page.evaluate("axe.run().then(result => ({violations: result.violations.map(v => ({id: v.id, impact: v.impact, target: v.nodes[0].target}))}))")
                violations.extend(f"links_results: {item['id']} {item['target']}" for item in links_axe["violations"] if item["impact"] == "serious")
                links_page.goto(f"{BASE}/koc/{campaign['result']['picked'][1]['creator_id']}", wait_until="networkidle")
                assert links_page.locator(".detail-heading a.tiktok-link").get_attribute("href") == f"https://www.tiktok.com/@{second_handle}"
                video_link = links_page.locator(".video-evidence a.tiktok-video-link").first
                assert video_link.get_attribute("href").startswith(f"https://www.tiktok.com/@{second_handle}/video/")
                assert links_page.locator(".score-box").count() == 1 and links_page.locator("#cach-cham-diem-koc").count() == 1
                # every analysed video has an anchor target and a "Nội dung" link
                video_targets = links_page.locator('[id^="video-"]').count()
                assert video_targets >= 1
                assert links_page.locator(".score-box-part").nth(2).locator(".score-box-links a").count() == video_targets
                # D4: transcript evidence without a frame keeps the quote across the full row width
                links_page.goto(f"{BASE}/koc/c_chou_02", wait_until="networkidle")
                no_frame = links_page.locator(".evidence-row.no-frame")
                assert no_frame.count() >= 1, "fixture must contain a transcript row without a frame"
                row_box = no_frame.first.bounding_box()
                quote_box = no_frame.first.locator(".evidence-quote").bounding_box()
                assert quote_box["x"] - row_box["x"] <= 64, f"quote starts {quote_box['x'] - row_box['x']}px into the row (thumbnail column?)"
                assert quote_box["width"] >= row_box["width"] * 0.6, f"quote width {quote_box['width']} of row {row_box['width']}"
                assert not tiktok_requests, f"Requests to TikTok: {tiktok_requests}"
                links_page.close()

                # v2 web wave 2: filter bar, header search diacritics, exclusion checkbox, run estimate
                AXE_SERIOUS = "axe.run().then(result => result.violations.filter(v => v.impact === 'serious').map(v => v.id + ' ' + JSON.stringify(v.nodes[0].target)))"
                ranked = campaign["result"]["ranked_pool"]
                assert {c["creator_id"] for c in campaign["result"]["picked"]} <= {c["creator_id"] for c in ranked}
                # the fixture run ids are not 32-hex; add a finished run with a real-looking id and picks
                conn = db.connect(database)
                hex_run = db.create_run(conn, {"brief": {"product_type": "Chống nắng"}})
                conn.execute("UPDATE runs SET status='done' WHERE run_id=?", (hex_run,))
                conn.execute("INSERT INTO recommendations SELECT ?, creator_id, rank, est_cost_vnd, rec_json FROM recommendations WHERE run_id=?", (hex_run, run_id))
                conn.commit()
                conn.close()
                assert len(ranked) >= 5
                for width in (1440, 375):
                    fpage = browser.new_page(viewport={"width": width, "height": 1500})
                    fpage.goto(routes["results"], wait_until="networkidle")
                    fpage.add_script_tag(path=str(AXE))
                    assert fpage.locator(".filter-bar").is_visible()
                    assert fpage.locator(".ranked-list .creator-row").count() == 5
                    fpage.get_by_label("Lọc KOC theo tên hoặc handle").fill("nghien chong nang")
                    expect(fpage.locator(".ranked-list .creator-row")).to_have_count(1)  # diacritic-insensitive
                    assert "An Nghiện Chống Nắng" in fpage.locator(".ranked-list").inner_text()
                    expect(fpage).to_have_url(re.compile("q=nghien"))
                    shared_url = fpage.url
                    fpage.goto(shared_url, wait_until="networkidle")  # a shared link restores the filter
                    fpage.add_script_tag(path=str(AXE))
                    assert fpage.get_by_label("Lọc KOC theo tên hoặc handle").input_value() == "nghien chong nang"
                    assert fpage.locator(".ranked-list .creator-row").count() == 1
                    fpage.get_by_label("Lọc KOC theo tên hoặc handle").fill("")
                    expect(fpage).not_to_have_url(re.compile("q="))
                    # tier + price + sort, through the drawer on mobile
                    if width == 375:
                        fpage.get_by_role("button", name=re.compile("^Bộ lọc")).click()
                        fpage.get_by_role("dialog").wait_for(state="visible")
                        scope = fpage.get_by_role("dialog")
                    else:
                        scope = fpage.locator(".filter-bar")
                    scope.get_by_role("button", name="50–100 nghìn").click()
                    expected = [c for c in ranked if 50_000 <= c["followers"] < 100_000]
                    assert expected, "fixture needs a 50-100k creator"
                    if width == 375:
                        expect(fpage.get_by_role("button", name=f"Xem {len(expected)} KOC")).to_be_visible(); fpage.wait_for_timeout(600)
                        fpage.screenshot(path=str(SHOTS2 / "filter_drawer_375.png"))
                        violations.extend(f"filter_drawer@375: {item}" for item in fpage.evaluate(AXE_SERIOUS))
                        fpage.get_by_role("button", name=f"Xem {len(expected)} KOC").click()
                        fpage.get_by_role("dialog").wait_for(state="hidden")
                    expect(fpage.locator(".ranked-list .creator-row")).to_have_count(len(expected))
                    expect(fpage).to_have_url(re.compile("tier=50-100"))
                    if width == 375:
                        fpage.get_by_role("button", name=re.compile("^Bộ lọc")).click()
                        fpage.get_by_role("dialog").wait_for(state="visible")
                        scope = fpage.get_by_role("dialog")
                    scope.get_by_role("button", name="Giá cao đến thấp").click()
                    scope.get_by_role("button", name="Giá thấp đến cao").click()
                    if width == 375:
                        fpage.get_by_role("button", name=re.compile("^Xem ")).click()
                        fpage.get_by_role("dialog").wait_for(state="hidden")
                    prices = [int(re.sub(r"\D", "", t)) for t in fpage.locator(".ranked-list .cost-cell strong").all_inner_texts()]
                    assert prices == sorted(prices)
                    assert fpage.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    fpage.wait_for_timeout(400)  # chip colour transition
                    fpage.screenshot(path=str(SHOTS2 / f"results_filtered_{width}.png"), full_page=False)
                    violations.extend(f"filter_results@{width}: {item}" for item in fpage.evaluate(AXE_SERIOUS))
                    brand_text = fpage.locator("body").inner_text().lower()
                    assert not any(word in brand_text for word in ("credit", "usd", "token")), "Filtered state exposes cost internals"
                    # empty result: Vietnamese message and a clear action
                    fpage.goto(f"{routes['results']}?q=zzzz", wait_until="networkidle")
                    fpage.add_script_tag(path=str(AXE))
                    assert fpage.get_by_text("Không có KOC nào khớp bộ lọc").first.is_visible()
                    assert fpage.locator(".ranked-list .creator-row").count() == 0
                    fpage.screenshot(path=str(SHOTS2 / f"results_empty_{width}.png"), full_page=False)
                    violations.extend(f"filter_empty@{width}: {item}" for item in fpage.evaluate(AXE_SERIOUS))
                    brand_text = fpage.locator("body").inner_text().lower()
                    assert not any(word in brand_text for word in ("credit", "usd", "token")), "Empty filter state exposes cost internals"
                    fpage.locator(".filter-empty").get_by_role("button", name="Xóa bộ lọc").click()
                    expect(fpage.locator(".ranked-list .creator-row")).to_have_count(5)
                    assert "?" not in fpage.url
                    body = fpage.locator("body").inner_text().lower()
                    assert not any(word in body for word in ("credit", "usd", "token")), "Brand page exposes cost internals"
                    fpage.close()
                # mixed prices: every price band, every tier, both price sorts, and the default score order with a tie
                base = api_client.get(f"{BASE}/api/campaigns/{campaign['campaign_id']}").json()
                template = base["result"]["ranked_pool"][0]
                synthetic = [
                    {**template, "creator_id": cid, "nickname": name, "handle": f"@{cid}", "followers": followers, "price_per_video_vnd": ppv, "cost_vnd": ppv * 3, "fit": fit}
                    for cid, name, followers, ppv, fit in (
                        ("zz_cheap_b", "Cheap B", 30_000, 1_000_000, 97.0), ("zz_cheap_a", "Cheap A", 20_000, 1_000_000, 97.0),
                        ("zz_cheap_c", "Cheap C", 45_000, 1_000_000, 50.0), ("zz_mid", "Mid", 70_000, 2_500_000, 99.5))
                ]
                mixed = {**base, "result": {**base["result"], "ranked_pool": [*base["result"]["ranked_pool"], *synthetic]}}
                pool_rows = mixed["result"]["ranked_pool"]
                def order(rows, key):
                    return [c["creator_id"] for c in sorted(rows, key=key)]
                by_fit = lambda c: (-c["fit"], c["creator_id"])
                mixed_page = browser.new_page(viewport={"width": 1440, "height": 1500})
                mixed_page.route(f"**/api/campaigns/{campaign['campaign_id']}", lambda route: route.fulfill(json=mixed))
                def shown_ids(query):
                    mixed_page.goto(f"{routes['results']}{query}", wait_until="networkidle")
                    mixed_page.wait_for_selector(".filter-bar")
                    return mixed_page.locator(".ranked-list .creator-row").evaluate_all("rows => rows.map(row => row.dataset.creatorId)")
                for band, test in (("lt2", lambda c: c["price_per_video_vnd"] < 2_000_000), ("2-4", lambda c: 2_000_000 <= c["price_per_video_vnd"] < 4_000_000), ("gte4", lambda c: c["price_per_video_vnd"] >= 4_000_000)):
                    expected_band = order([c for c in pool_rows if test(c)], by_fit)
                    assert expected_band, band
                    assert shown_ids(f"?gia={band}") == expected_band, band
                assert shown_ids("?gia=lt2")[:2] == ["zz_cheap_a", "zz_cheap_b"], "equal fit sorts by creator id"
                for tier, test in (("lt50", lambda c: c["followers"] < 50_000), ("50-100", lambda c: 50_000 <= c["followers"] < 100_000), ("gte100", lambda c: c["followers"] >= 100_000)):
                    assert shown_ids(f"?tier={tier}") == order([c for c in pool_rows if test(c)], by_fit), tier
                assert shown_ids("?sx=price-asc") == order(pool_rows, lambda c: (c["price_per_video_vnd"], -c["fit"], c["creator_id"]))
                assert shown_ids("?sx=price-desc") == order(pool_rows, lambda c: (-c["price_per_video_vnd"], -c["fit"], c["creator_id"]))
                score_ids = shown_ids("?q=%20")  # whitespace filter is inactive: picks layout
                assert len(score_ids) == 5
                # score order across mixed prices (no price sort): sort chip back to the default inside an active filter
                mixed_page.goto(f"{routes['results']}?sx=price-asc", wait_until="networkidle")
                mixed_page.locator(".filter-options").get_by_role("button", name="Điểm cao nhất").click()
                expect(mixed_page).not_to_have_url(re.compile("sx="))
                mixed_page.get_by_label("Lọc KOC theo tên hoặc handle").fill("e")
                fold = lambda text: "".join(ch for ch in unicodedata.normalize("NFD", text.lower().replace("đ", "d")) if not unicodedata.combining(ch))
                with_e = [c for c in pool_rows if "e" in fold(c["nickname"] + " " + c["handle"])]
                expect(mixed_page.locator(".ranked-list .creator-row")).to_have_count(len(with_e))
                assert mixed_page.locator(".ranked-list .creator-row").evaluate_all("rows => rows.map(row => row.dataset.creatorId)") == order(with_e, by_fit)
                assert len({c["price_per_video_vnd"] for c in with_e}) > 1, "mixed prices in the score-order check"
                picked_ids = {c["creator_id"] for c in base["result"]["picked"]}
                mixed_page.goto(f"{routes['results']}?gia=gte4", wait_until="networkidle")
                badges = mixed_page.locator(".ranked-list .creator-row:has(.pick-badge)").evaluate_all("rows => rows.map(row => row.dataset.creatorId)")
                assert set(badges) == picked_ids & {c["creator_id"] for c in pool_rows if c["price_per_video_vnd"] >= 4_000_000}
                mixed_page.close()
                # unknown tier in the URL is ignored, not an error
                bad = browser.new_page(viewport={"width": 1440, "height": 900})
                bad.goto(f"{routes['results']}?tier=bogus&sx=bogus", wait_until="networkidle")
                assert bad.locator(".ranked-list .creator-row").count() == 5
                bad.close()
                # header search is the same palette and ignores diacritics
                search.goto(routes["campaign_list"], wait_until="networkidle")
                search.keyboard.press("Control+k")
                search.locator("[cmdk-input]").fill("trinh my pham")
                search.get_by_text("Trịnh Mỹ Phẩm").first.wait_for(state="visible")
                search.keyboard.press("Escape")

                # exclusion checkbox on the form
                previous = api_client.get(f"{BASE}/api/runs/previous", params={"product_type": "Chống nắng"}).json()
                assert [item["run_id"] for item in previous] == [hex_run], previous
                assert api_client.get(f"{BASE}/api/runs/previous", params={"product_type": "Trang điểm"}).json() == []
                excl_all = [item["run_id"] for item in previous]
                for width in (1440, 375):
                    xform = browser.new_page(viewport={"width": width, "height": 1500})
                    xform.goto(routes["form"], wait_until="networkidle")
                    xform.add_script_tag(path=str(AXE))
                    box = xform.get_by_label("Loại KOC đã đề xuất ở lần trước")
                    box.wait_for(state="visible")
                    assert not box.is_checked()
                    note = xform.locator(".exclude-run-note").inner_text()
                    assert "loại" in note and "KOC" in note, note
                    xform.get_by_label("Tên thương hiệu").fill("Thử loại trùng")
                    box.check()
                    xform.screenshot(path=str(SHOTS2 / f"form_exclude_{width}.png"), full_page=False)
                    violations.extend(f"form_exclude@{width}: {item}" for item in xform.evaluate(AXE_SERIOUS))
                    with xform.expect_request(lambda r: r.url.endswith("/api/campaigns") and r.method == "POST") as posted:
                        xform.get_by_role("button", name="Tìm KOC phù hợp").click()
                    assert posted.value.post_data_json["exclude_run_ids"] == excl_all
                    xform.close()
                unticked = browser.new_page(viewport={"width": 1440, "height": 900})
                unticked.goto(routes["form"], wait_until="networkidle")
                unticked.get_by_label("Tên thương hiệu").fill("Không loại")
                with unticked.expect_request(lambda r: r.url.endswith("/api/campaigns") and r.method == "POST") as posted:
                    unticked.get_by_role("button", name="Tìm KOC phù hợp").click()
                assert "exclude_run_ids" not in posted.value.post_data_json
                unticked.close()
                excluded_campaign = api_client.post(f"{BASE}/api/campaigns", data={
                    "brand_name": "Mây Daily", "product_type": "Chống nắng", "budget_vnd": 30_000_000, "count": 5,
                    "followers_min": 10_000, "followers_max": 300_000, "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
                    "avoid_same_mcn": True, "exclude_run_ids": excl_all,
                }).json()
                assert excluded_campaign.get("result", {}).get("status") == "needs_run", excluded_campaign
                assert all(f"--exclude-run {rid}" in excluded_campaign["result"]["run_command"] for rid in excl_all)
                for width in (1440, 375):
                    xrun = browser.new_page(viewport={"width": width, "height": 1500})
                    xrun.goto(f"{BASE}/chien-dich/{excluded_campaign['campaign_id']}", wait_until="networkidle")
                    xrun.add_script_tag(path=str(AXE))
                    assert xrun.locator(".run-estimate").is_visible()
                    assert "--exclude-run" in xrun.locator(".needs-run-excluded").inner_text()
                    assert "--exclude-run" in xrun.locator(".needs-run-command").first.inner_text()
                    xrun.screenshot(path=str(SHOTS2 / f"needs_run_estimate_{width}.png"), full_page=True)
                    assert xrun.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    violations.extend(f"needs_run_estimate@{width}: {item}" for item in xrun.evaluate(AXE_SERIOUS))
                    xrun.close()
                # null estimate hides the box
                nulled = browser.new_page(viewport={"width": 1440, "height": 900})
                def drop_estimate(route):
                    response = route.fetch()
                    data = response.json()
                    data["result"]["run_estimate"] = None
                    route.fulfill(response=response, json=data)
                nulled.route(f"**/api/campaigns/{excluded_campaign['campaign_id']}", drop_estimate)
                nulled.goto(f"{BASE}/chien-dich/{excluded_campaign['campaign_id']}", wait_until="networkidle")
                assert nulled.locator(".needs-run-panel").is_visible() and nulled.locator(".run-estimate").count() == 0
                nulled.close()

                conn = sqlite3.connect(database)
                conn.execute("DELETE FROM scores")
                conn.execute("UPDATE runs SET status='failed'")  # no finished run -> API status needs_run
                conn.commit()
                conn.close()
                empty_data_campaign = api_client.post(f"{BASE}/api/campaigns", data={
                    "brand_name": "Mây Daily",
                    "product_type": "Chống nắng",
                    "budget_vnd": 30_000_000,
                    "count": 5,
                    "followers_min": 10_000,
                    "followers_max": 300_000,
                    "target": {"gender": "Nữ", "age_groups": ["18-24", "25-34"]},
                    "avoid_same_mcn": True,
                }).json()
                empty_data_page = browser.new_page(viewport={"width": 375, "height": 900})
                empty_data_page.goto(f"{BASE}/chien-dich/{empty_data_campaign['campaign_id']}", wait_until="networkidle")
                assert empty_data_page.get_by_text("Chưa có dữ liệu KOC").is_visible()
                assert empty_data_page.get_by_text("Không có KOC trong khoảng người theo dõi đã chọn.").count() == 0
                estimate = empty_data_page.locator(".run-estimate")
                assert estimate.is_visible()
                estimate_text = estimate.inner_text().lower()
                for word in ("ước tính", "tín dụng", "usd", "token", "phút"):
                    assert word in estimate_text, f"estimate box lacks {word}: {estimate_text}"
                assert estimate.locator("dd").count() == 4 and all("–" in t for t in estimate.locator("dd").all_inner_texts()), "ranges expected"
                assert estimate.bounding_box()["y"] < empty_data_page.locator(".needs-run-command").first.bounding_box()["y"]
                assert empty_data_page.locator(".needs-run-excluded").count() == 0
                empty_data_page.close()
                search.close()
                api_client.dispose()
                browser.close()
                assert not violations, "Serious axe findings: " + ", ".join(violations)
                print(json.dumps({"screenshots": len(routes) * 2 + 9, "serious_axe_violations": violations, "matching_seconds": round(match_seconds, 3), "campaign_id": campaign["campaign_id"]}, ensure_ascii=False))
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
