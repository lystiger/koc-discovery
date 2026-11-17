"""Build data/demo.db: one finished run, read-only demo for reviewers, no keys needed.

Keeps only what the web pages need for that run. Drops raw Kalodata and LLM caches,
creator bios, local media paths and task error text. Usage:
  python scripts/make_demo_db.py --src data/koc.db --run <run_id> [--out data/demo.db]
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

CREATOR_KEEP = ("creator_id", "creator_handle", "creator_nickname", "creator_followers")
VIDEO_KEEP = ("video_id", "video_title", "title", "views", "digg_count", "comment_count", "share_count", "publish_date")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/koc.db")
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", default="data/demo.db")
    a = ap.parse_args()
    out = Path(a.out)
    out.unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{a.src}?mode=ro", uri=True)
    c = sqlite3.connect(out)
    src.backup(c)
    src.close()
    run = a.run
    if not c.execute("SELECT 1 FROM runs WHERE run_id=? AND status='done'", (run,)).fetchone():
        raise SystemExit(f"run {run} not found or not done")

    per_run = [t for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
               if "run_id" in [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]]
    for t in per_run:
        c.execute(f'DELETE FROM "{t}" WHERE run_id IS NOT ?', (run,))
    for t in ("http_cache", "llm_cache", "campaigns"):
        c.execute(f'DELETE FROM "{t}"')

    scored = {cid for (cid,) in c.execute("SELECT DISTINCT creator_id FROM scores")}
    analysed = {cid for (cid,) in c.execute("SELECT creator_id FROM scores WHERE stage='S3'")}
    for cid, data in c.execute("SELECT creator_id, data_json FROM creators").fetchall():
        if cid not in scored:
            c.execute("DELETE FROM creators WHERE creator_id=?", (cid,))
            continue
        d = json.loads(data or "{}")
        c.execute("UPDATE creators SET data_json=? WHERE creator_id=?",
                  (json.dumps({k: d[k] for k in CREATOR_KEEP if k in d}, ensure_ascii=False), cid))
    q = ",".join("?" * len(analysed))
    c.execute(f"DELETE FROM metrics WHERE creator_id NOT IN ({q})", tuple(analysed))
    # Only the analyses behind the run's S3 scores (one per selected video), and only their videos
    from koc.db import run_analyses
    keep = {(vid, pv, model) for cid in analysed for vid, pv, model, _ in run_analyses(c, run, cid)}
    for vid, pv, model, aj in c.execute("SELECT video_id, prompt_version, model, analysis_json FROM analyses").fetchall():
        if (vid, pv, model) not in keep:
            c.execute("DELETE FROM analyses WHERE video_id=? AND prompt_version=? AND model=?", (vid, pv, model))
            continue
        a = json.loads(aj)
        for e in a.get("evidence", []):
            e["frame_path"] = None  # demo ships without media files
        c.execute("UPDATE analyses SET analysis_json=? WHERE video_id=? AND prompt_version=? AND model=?",
                  (json.dumps(a, ensure_ascii=False), vid, pv, model))
    kept_videos = {vid for vid, _, _ in keep}
    for vid, data in c.execute("SELECT video_id, data_json FROM videos").fetchall():
        if vid not in kept_videos:
            c.execute("DELETE FROM videos WHERE video_id=?", (vid,))
            continue
        d = json.loads(data or "{}")
        c.execute("UPDATE videos SET data_json=?, mp4_path=NULL WHERE video_id=?",
                  (json.dumps({k: d[k] for k in VIDEO_KEEP if k in d}, ensure_ascii=False), vid))
    c.execute("UPDATE tasks SET error=NULL")
    c.commit()
    c.execute("VACUUM")

    dump = "\n".join(c.iterdump())
    bad = re.findall(r"/home/\w+|/Users/\w+|data/media|[\w.+-]+@[\w-]+\.(?:com|vn|net|invalid|org)|sk-or-v1-|AIza[0-9A-Za-z_-]{30}"
                     r"|(?<![\d.,])(?:\+84|0)\s?\d{2,3}[\s.-]?\d{3}[\s.-]?\d{3,4}\b", dump)
    c.close()
    if bad:
        out.unlink()
        raise SystemExit(f"private data found, demo db removed: {sorted(set(bad))[:5]}")
    counts = {t: n for t, n in ((t, sqlite3.connect(out).execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
                                for t in ("runs", "creators", "videos", "analyses", "metrics", "recommendations"))}
    print(f"wrote {out}: {out.stat().st_size // 1024} KB, {counts}")


if __name__ == "__main__":
    main()
