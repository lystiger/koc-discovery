"""Customer journey screenshots for the KOC Discovery web app (Vietnamese UI).

Usage: customer_journey.py --db COPY.db --port 8766 [--media-dir data/media]
Starts the server on a COPY of the database (the app writes campaigns), blocks every
non-loopback request, never clicks a run action, blurs every non-asset image.
Writes docs/shots/v2_e2e/NN_name_{1440,375}.png and docs/pitch/assets/e2e/NN_name.webp.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/shots/v2_e2e"
DECK = ROOT / "docs/pitch/assets/e2e"
RUN = "0e555cac95fb4fb49168410e40ea92d5"
BLUR = 'img:not([src*="/assets/"]), video, canvas {filter: blur(14px) !important;}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--media-dir", default=str(ROOT / "data/media"))
    ap.add_argument("--no-server", action="store_true")
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    OUT.mkdir(parents=True, exist_ok=True)
    DECK.mkdir(parents=True, exist_ok=True)
    server = None
    if not a.no_server:
        server = subprocess.Popen([sys.executable, "-m", "koc.web", "--db", a.db, "--media-dir", a.media_dir,
                                   "--port", str(a.port)], cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    creator_id = conn.execute("SELECT creator_id FROM creators WHERE handle LIKE '%rio100806'").fetchone()[0]
    conn.close()
    try:
        for _ in range(100):
            try:
                urlopen(base, timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/chromium", headless=True)
            for width in (1440, 375):
                journey(browser, base, width, creator_id)
            browser.close()
    finally:
        if server:
            server.terminate()
    for f in sorted(OUT.glob("*_1440.png")):
        subprocess.run(["magick", str(f), "-resize", "1600x>", "-quality", "82",
                        str(DECK / f.name.replace("_1440.png", ".webp"))], check=True)


def journey(browser, base, width, creator_id):
    ctx = browser.new_context(viewport={"width": width, "height": 900}, locale="vi-VN")
    ctx.route("**/*", lambda r: r.continue_() if re.match(r"^(http://127\.0\.0\.1|data:|blob:)", r.request.url) else r.abort())
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: print("PAGEERROR", e))
    desktop = width == 1440

    def settle(ms=700, full=True):
        try:
            pg.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        pg.add_style_tag(content=BLUR)
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        if full:  # scroll through so scroll-reveal sections render in full-page shots
            h = pg.evaluate("document.documentElement.scrollHeight")
            for y in range(0, h, 500):
                pg.evaluate(f"window.scrollTo(0, {y})")
                pg.wait_for_timeout(60)
            pg.evaluate("window.scrollTo(0, 0)")
        pg.evaluate("""() => Promise.all([...document.images].map(i => i.complete ? 0 :
            new Promise(r => { i.onload = i.onerror = r; setTimeout(r, 3000); })))""")
        pg.wait_for_timeout(ms)

    def shot(n, name, key=False, locator=None, full=True):
        if not desktop and not key:
            return
        settle(full=full and locator is None)
        f = OUT / f"{n:02d}_{name}_{width}.png"
        if locator is not None:
            locator.scroll_into_view_if_needed()
            locator.screenshot(path=str(f))
        else:
            pg.screenshot(path=str(f), full_page=full)
        print("shot", f.name)

    # 1 landing
    pg.goto(base + "/", wait_until="networkidle")
    shot(1, "landing", True)
    # 2 form
    pg.goto(base + "/chien-dich/moi", wait_until="networkidle")
    pg.fill("#brand", "Anessa")
    pg.locator(".select-trigger").first.click()
    pg.get_by_role("option", name="Chống nắng").click()
    pg.fill("#specs", "Kem chống nắng SPF50+ cho da dầu, nhẹ mặt, dùng hằng ngày")
    pg.fill("#budget", "30000000")
    pg.fill("#count", "5")
    pg.locator(".age-chip").first.click()
    shot(2, "form", True)
    if desktop:
        pg.locator("#exclude-previous").check()
        shot(2, "form_exclude_previous", locator=pg.locator(".exclude-run"))
        pg.locator("#exclude-previous").uncheck()
    # 3 submit result
    pg.get_by_role("button", name="Tìm KOC phù hợp").click()
    pg.wait_for_url(re.compile(r"/chien-dich/[0-9a-f]+$"), timeout=20000)
    cid = pg.url.rsplit("/", 1)[1]
    pg.wait_for_selector(".budget-strip", timeout=15000)
    shot(3, "submit_result")
    # 4 proposal
    pg.goto(f"{base}/de-xuat/{RUN}", wait_until="networkidle")
    pg.wait_for_selector(".budget-strip")
    shot(4, "proposal_top", True, full=False)
    # 5 score boxes
    box = pg.locator(".score-box").first
    shot(5, "score_breakdown", locator=box)
    # 6 excluded box
    ex = pg.locator(".excluded-box")
    ex.scroll_into_view_if_needed()
    trig = ex.locator(".excluded-trigger")
    for i in range(min(2, trig.count())):
        if trig.nth(i).get_attribute("aria-expanded") != "true":
            trig.nth(i).click()
    pg.wait_for_timeout(400)
    shot(6, "excluded_box", locator=ex)
    # 10 method (on proposal page)
    meth = pg.locator("#cach-cham-diem, [id^=cach-cham-diem]").first
    shot(10, "cach_cham_diem", locator=meth.locator("xpath=ancestor-or-self::section[1]"))
    # 7 profile
    pg.goto(f"{base}/de-xuat/{RUN}/koc/{creator_id}", wait_until="networkidle")
    pg.wait_for_selector("text=rio100806")
    pg.wait_for_timeout(800)
    shot(7, "koc_profile", True)
    # 8 campaign results with filters
    pg.goto(f"{base}/chien-dich/{cid}", wait_until="networkidle")
    if desktop:
        shot(8, "filters_sort", True)
    else:
        pg.get_by_role("button", name=re.compile("Bộ lọc")).first.click()
        pg.wait_for_timeout(900)
        shot(8, "filters_drawer", True, full=False)
    # 9 header search
    pg.goto(f"{base}/", wait_until="networkidle")
    pg.locator(".search-trigger").click()
    pg.keyboard.type("rio", delay=60)
    pg.wait_for_timeout(1000)
    shot(9, "search_rio", desktop, full=False)
    ctx.close()


if __name__ == "__main__":
    main()
