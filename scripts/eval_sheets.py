"""Write the blind human-evaluation sheets for one run into docs/eval/ (read-only on the database).

Sheets (fill in this order; see docs/eval/HOW_TO_JUDGE.md):
  1_videos.csv    every analysed video of every KOC that reached S3, shuffled, no system scores
  2_koc.csv       the same KOCs, shuffled, no ranks and no "picked" flag
  3_evidence.csv  every claim cited in the final proposal (fill last: it reveals the picks)

Usage: PYTHONPATH=src python scripts/eval_sheets.py --db data/koc.db --run <run_id> [--out docs/eval] [--force]
"""
import argparse
import csv
import json
import random
import sqlite3
from pathlib import Path

from koc.db import run_analyses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/koc.db")
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", default="docs/eval")
    ap.add_argument("--force", action="store_true", help="overwrite sheets that already exist")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / n for n in ("1_videos.csv", "2_koc.csv", "3_evidence.csv")]
    if not a.force and any(t.exists() for t in targets):
        raise SystemExit("sheets exist; refusing to overwrite your ratings (use --force)")
    c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    run = a.run
    kocs = c.execute("SELECT s.creator_id, c.handle FROM scores s JOIN creators c USING(creator_id) "
                     "WHERE s.run_id=? AND s.stage='S3'", (run,)).fetchall()
    rng = random.Random(run)
    rng.shuffle(kocs)
    videos = []
    for cid, h in kocs:
        for vid, *_ in run_analyses(c, run, cid):
            videos.append((h, vid))
    rng.shuffle(videos)
    with open(out / "1_videos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["handle", "video_id", "url", "your_score_1_5", "note"])
        for h, vid in videos:
            w.writerow([h, vid, f"https://www.tiktok.com/{h}/video/{vid}", "", ""])
    with open(out / "2_koc.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["handle", "profile_url", "your_verdict_co_dieukien_khong", "your_grade_0_3", "reason"])
        for _, h in kocs:
            w.writerow([h, f"https://www.tiktok.com/{h}", "", "", ""])
    with open(out / "3_evidence.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["handle", "evidence_id", "kind", "where_to_check", "claim", "your_check_dung_motphan_sai", "note"])
        for cid, h, rec_json in c.execute("SELECT r.creator_id, c.handle, r.rec_json FROM recommendations r "
                                          "JOIN creators c USING(creator_id) WHERE run_id=? ORDER BY rank", (run,)):
            ev = {}
            for _, _, _, aj in run_analyses(c, run, cid):
                for e in json.loads(aj).get("evidence", []):
                    ev[e["evidence_id"]] = e
            metrics = dict(c.execute("SELECT name, value FROM metrics WHERE creator_id=?", (cid,)).fetchall())
            for eid in json.loads(rec_json).get("cited_evidence_ids", []):
                if eid.startswith("metric:"):
                    name = eid.split(":")[2]
                    w.writerow([h, eid, "metric", f"https://www.kalodata.com/creator/detail?id={cid}",
                                f"{name} = {metrics.get(name)}", "", ""])
                elif eid in ev:
                    e = ev[eid]
                    kind = "speech" if e.get("kind") == "speech" else "frame"
                    w.writerow([h, eid, kind, f"https://www.tiktok.com/{h}/video/{e['video_id']} @ {int(e.get('start_s') or 0)}s",
                                e.get("quote_vi", ""), "", ""])
    print(f"wrote {len(videos)} videos, {len(kocs)} KOC, evidence sheet to {out}")


if __name__ == "__main__":
    main()
