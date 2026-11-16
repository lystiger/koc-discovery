#!/usr/bin/env python3
"""Offline preview of the v2 S3 on-topic video selection for a finished run. No network, no LLM, read-only DB.

For each creator of the run's S3: the videos S3 analysed (old) next to the on-topic top 3 the new selection would pick
from the cached video/rank rows, and how many new paid analyses a partial S3 rerun needs (new videos without a
content_v3 analysis), priced with the per-creator S3 units of reports/benchmark.json.

Usage: PYTHONPATH=src python scripts/s3_rerank_preview.py --db <copy of koc.db> [--run-id ID]
Use a copy: sqlite3 -readonly data/koc.db ".backup /tmp/copy.db".
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from koc.brief import run_brief
from koc.config import load_config
from koc.brief import brand_brief
from koc.pipeline import content_analysis_cached
from koc.video_select import score_video, select_videos, topic_terms

ROOT = Path(__file__).resolve().parents[1]
LIVE_RUN = "7372009b22764b339fbcf0f3efb4bc4e"


def _short(title, width=70):
    text = " ".join(str(title or "").split())
    return text if len(text) <= width else text[:width - 1] + "…"


def needs_payment(conn, brief, video_id, media_dir, model, prompt_version="content_v3") -> bool:
    """True when S3 would pay for this video: the production cache lookup (current key, else legacy rows) misses.

    Without the downloaded mp4 the media hash is unknown, so the video counts as paid (a download comes first anyway).
    """
    path = Path(media_dir) / f"{video_id}.mp4"
    if not path.exists():
        return True
    media_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return not content_analysis_cached(conn, media_hash, prompt_version, model, brand_brief(brief), str(video_id))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default=LIVE_RUN)
    parser.add_argument("--media-dir", default="data/media", help="downloaded mp4s, to compute the production cache key")
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    config = load_config()
    brief = run_brief(conn, args.run_id, config)
    benchmark = json.loads((ROOT / "reports/benchmark.json").read_text())
    video_count = config["s1"]["video_count"]

    candidates = {}  # creator_id -> {video_id: row}, from every cached video/rank page
    for (response,) in conn.execute("SELECT response_json FROM http_cache WHERE endpoint='video/rank'"):
        for row in (json.loads(response).get("data") or []):
            if isinstance(row, dict) and row.get("belonged_creator_id") and row.get("video_id"):
                candidates.setdefault(str(row["belonged_creator_id"]), {})[str(row["video_id"])] = row
    model = config["llm_caps"].get("model", "gemini-3.8-flash")
    pay = lambda vid: needs_payment(conn, brief, vid, args.media_dir, model)

    print(f"Run {args.run_id}")
    print(f"Brief: {brief['product']} ({brief['product_type']}); terms: {', '.join(topic_terms(brief, config))}")
    totals = {"creators": 0, "old_off": 0, "new_off": 0, "changed_creators": 0, "new_videos": 0, "no_candidates": 0, "no_on_topic": 0}
    for creator_id, handle, breakdown in conn.execute(
            "SELECT s.creator_id, c.handle, s.breakdown_json FROM scores s LEFT JOIN creators c ON c.creator_id=s.creator_id "
            "WHERE s.run_id=? AND s.stage='S3' ORDER BY s.creator_id", (args.run_id,)):
        rows = candidates.get(creator_id, {})
        recorded = json.loads(breakdown).get("video_ids")
        # old rule replayed on the same cached rows: top 3 by revenue whatever the topic
        old_ids = [str(v["video_id"]) for v in sorted(rows.values(), key=lambda v: float(v.get("revenue") or 0), reverse=True)[:video_count]]
        totals["creators"] += 1
        print(f"\n== {handle or creator_id} ({creator_id}); {len(rows)} cached candidate videos")
        if recorded is not None and set(map(str, recorded)) != set(old_ids):
            print(f"   note: run recorded {recorded}, differs from the replayed old rule (rank pages cached at another time)")
        if not rows:
            totals["no_candidates"] += 1
            print("   (no cached video/rank rows: cannot preview)")
            continue
        terms = topic_terms(brief, config)
        print("   old top 3 (by revenue):")
        for vid in old_ids:
            row = rows.get(vid, {"video_title": "(not in cached rank rows)"})
            info = score_video(row, terms)
            totals["old_off"] += not info["on_topic"]
            print(f"     {vid}  score={info['score']}  {_short(row.get('video_title'))}")
        picked = select_videos(list(rows.values()), brief, config, n=video_count)
        print("   new top 3 (on-topic first):")
        new_ids = []
        for video, info in picked:
            vid = str(video["video_id"])
            new_ids.append(vid)
            totals["new_off"] += not info["on_topic"]
            paid = pay(vid)
            tag = "  [needs paid analysis]" if paid else ""
            print(f"     {vid}  score={info['score']} {'on-topic' if info['on_topic'] else 'OFF-TOPIC'}  {_short(video.get('video_title'))}{tag}")
        if set(new_ids) != set(old_ids):
            totals["changed_creators"] += 1
        if not any(info["on_topic"] for _, info in picked):
            totals["no_on_topic"] += 1
        totals["new_videos"] += sum(1 for vid in new_ids if pay(vid))

    n = totals["new_videos"]
    low, high = benchmark["units_success"]["S3"], benchmark["units_total"]["S3"]
    print("\n== Summary")
    print(f"creators in S3: {totals['creators']}; with cached candidates: {totals['creators'] - totals['no_candidates']}; selection changes: {totals['changed_creators']}")
    print(f"old selection off-topic videos: {totals['old_off']}; new selection off-topic videos: {totals['new_off']}; creators with no on-topic video at all: {totals['no_on_topic']}")
    print(f"new paid analyses needed for a partial S3 rerun: {n} video(s) (production cache lookup misses: no current-key or valid legacy row)")
    print(f"estimate (benchmark S3 units per creator / {video_count} videos, x {n}): "
          f"credits {low['credits'] / video_count * n:.2f}-{high['credits'] / video_count * n:.2f}, "
          f"USD {low['usd'] / video_count * n:.3f}-{high['usd'] / video_count * n:.3f}, "
          f"tokens {(low['tokens_in'] + low['tokens_out']) / video_count * n:,.0f}-{(high['tokens_in'] + high['tokens_out']) / video_count * n:,.0f}")
    print("Cache note: video/rank rows older than cache_ttl_days are refetched on a live rerun (0.1 credit per creator page).")


if __name__ == "__main__":
    main()
