#!/usr/bin/env python3
"""List the videos a new run's S3 would pick per creator and which of them still need a paid analysis. Offline, no LLM.

Uses the production path: the cached video/rank page (page_size=100, cache-only client), `select_videos`, the mp4 in
data/media and `content_analysis_cached` (current key, then valid legacy rows). `*` = needs download + paid analysis.
The creators are the S3 tasks of --run-id (the finished live run still holds its skipped S3 task).

Usage: PYTHONPATH=src python scripts/s3_pending_videos.py --db <koc.db> [--run-id ID] [--media-dir data/media]
Read-only: --db is opened with mode=ro and copied into memory; the cache-hit logging writes only touch the in-memory copy.
"""
import argparse
import hashlib
import sqlite3
from pathlib import Path

from koc.brief import brand_brief, run_brief
from koc.config import load_config
from koc.kalodata import KalodataClient
from koc.pipeline import _data, content_analysis_cached
from koc.video_select import select_videos

LIVE_RUN = "7372009b22764b339fbcf0f3efb4bc4e"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default=LIVE_RUN)
    parser.add_argument("--media-dir", default="data/media")
    args = parser.parse_args()
    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn = sqlite3.connect(":memory:")
    src.backup(conn)
    src.close()
    conn.row_factory = sqlite3.Row
    config = load_config()
    brief = run_brief(conn, args.run_id, config)
    client = KalodataClient(conn, run_id=None, cache_only=True)
    model = config["llm_caps"].get("model", "gemini-3.8-flash")
    media, total, count = Path(args.media_dir), 0, 0
    for (creator_id,) in conn.execute("SELECT key FROM tasks WHERE run_id=? AND stage='S3' ORDER BY key", (args.run_id,)).fetchall():
        picked = select_videos(_data(client.video_rank(creator_id, page_size=100)) or [], brief, config, n=3)
        cells = []
        for video, info in picked:
            vid = str(video["video_id"])
            path = media / f"{vid}.mp4"
            paid = not path.exists() or not content_analysis_cached(conn, hashlib.sha256(path.read_bytes()).hexdigest(), "content_v3", model, brand_brief(brief), vid)
            total, count = total + paid, count + 1
            cells.append(f"{vid}{'*' if paid else ''}{'' if info.get('on_topic') else '(off-topic)'}")
        row = conn.execute("SELECT handle FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        print(creator_id, row[0] if row else "", " ".join(cells))
    print(f"videos picked: {count}; needing paid analysis (*): {total}; video/url cost {total * config['kalodata_prices']['video_url']:.1f} credits")


if __name__ == "__main__":
    main()
