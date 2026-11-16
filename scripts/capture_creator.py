"""Capture one Kalodata creator detail page (already open in the supervised browser) to raw JSON.

Authorized-UI extraction only: reads visible page text and DOM of the tab the operator opened.
Connects to a local Chromium over CDP; never reads cookies, headers or network bodies.

Usage: python scripts/capture_creator.py ITEM_SOLD OUT_JSON [--cdp http://127.0.0.1:9333] [--videos 2]
ITEM_SOLD comes from the creator list row (not shown on the detail page).
"""
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROW_JS = """() => [...document.querySelectorAll('tr')].map(tr => {
  const m = tr.innerHTML.match(/tiktok\\.video\\/(\\d+)\\/cover/);
  return m ? {id: m[1], text: tr.innerText} : null }).filter(Boolean)"""


def grab(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


def main(item_sold: str, out: str, cdp: str = "http://127.0.0.1:9333", n_videos: int = 2) -> None:
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        page = [x for x in ctx.pages if "creator/detail" in x.url][-1]
        for _ in range(6):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1000)
        # drop icon-font glyphs (Unicode private-use area) and blank lines between labels and values
        text = re.sub(r"[\ue000-\uf8ff]", "", page.inner_text("body"))
        text = re.sub(r"\n\s*\n", "\n", text)
        rows = page.evaluate(ROW_JS)
        title = page.title()

    q = parse_qs(urlparse(page.url).query)
    creator_id = q["id"][0]
    period = "..".join(json.loads(q["dateRange"][0]))
    source = f"https://www.kalodata.com/creator/detail?id={creator_id}"
    handle = title.split()[0].lstrip("@")
    now = datetime.now(timezone.utc).isoformat()

    age_block = grab(r"\nAge\n(.*?)\nTop 5 Locations", text + "\nTop 5 Locations") or ""
    ages = dict(re.findall(r"(\d{2}(?:-\d{2}|\+))\n([\d.]+%)", age_block))
    creator = {
        "type": "creator", "source": source, "period": period, "collected_at": now,
        "fields": {
            "Creator ID": creator_id,
            "Handle": handle,
            "View on TikTok": f"https://www.tiktok.com/@{handle}",
            "Followers": grab(r"Followers:\n(\S+)", text),
            "Follower gender: Female": grab(r"\nFemale\n([\d.]+%)", text),
            "Follower age": ages or None,
            "Revenue": grab(r"\(\d\d/\d\d ~ \d\d/\d\d\)\nRevenue\n(₫\S+)", text),
            "Item Sold": item_sold,
            "Video Revenue": grab(r"\nVideo Revenue\n(₫\S+)", text),
            "Live Revenue": grab(r"\nLive Revenue\n(₫\S+)", text),
            "_missing_notes": {
                "Category": "Kalodata creator detail shows no creator category (only a filter)",
                "Top 5 Locations": "locked on trial plan: requires credits",
            },
            "_field_sources": {"Item Sold": "https://www.kalodata.com/creator"},
        },
    }
    records = [creator]
    for row in rows[:n_videos]:
        cells = row["text"]
        records.append({
            "type": "video", "source": source,
            "period": period, "collected_at": now,
            "fields": {
                "Video ID": row["id"],
                "Creator ID": creator_id,
                "View on TikTok": f"https://www.tiktok.com/@{handle}/video/{row['id']}",
                "Publish Date": grab(r"(\d\d/\d\d/\d{4})", cells),
                "Views": grab(r"₫\S+\s+(\S+)", cells),
                "Revenue": grab(r"(₫\S+)", cells),
                "Cover": f"https://img.kalocdn.com/tiktok.video/{row['id']}/cover.png",
                "Media Access": "player_mp4_listed (not downloaded)",
                "Transcript": "none_from_source",
                "_missing_notes": {
                    lbl: "not shown on Kalodata video list or detail page"
                    for lbl in ("Likes", "Comments", "Shares")
                },
            },
        })
    with open(out, "w") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(json.dumps(records, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    args = sys.argv[1:]
    n = int(args[args.index("--videos") + 1]) if "--videos" in args else 2
    cdp = args[args.index("--cdp") + 1] if "--cdp" in args else "http://127.0.0.1:9333"
    main(args[0], args[1], cdp=cdp, n_videos=n)
