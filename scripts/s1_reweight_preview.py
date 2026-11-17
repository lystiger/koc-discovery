#!/usr/bin/env python3
"""Offline preview: S1 with skincare_revenue_share weight 0 (config/scoring.yaml) vs the stored S1. No network, no LLM, read-only DB.

S1 components are stored in scores.breakdown_json, so the new S1 is the stored components times the current config weights.
Final scores reuse the stored S2/S3 and the production selection (_best_five: placeholder audience dropped, brand-fit gate,
same budget). Creators the new S1 top 40 would add but that have no S3 score need a paid run: they are counted, not scored.

Usage: PYTHONPATH=src python scripts/s1_reweight_preview.py --db <copy of koc.db> [--run-id ID ...]
Use a copy: sqlite3 -readonly data/koc.db ".backup /tmp/copy.db".
"""
import argparse
import json
import sqlite3

from koc.config import load_config
from koc.pipeline import _best_five
from koc.stages import s1_shortlist

RUNS = ["0e555cac95fb4fb49168410e40ea92d5", "7372009b22764b339fbcf0f3efb4bc4e"]
OLD_WEIGHTS = {"video_gpm": 35, "skincare_revenue_share": 25, "revenue_trend_slope": 15, "video_vs_live_share": 15, "follower_band_fit": 10}


def load(path):
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    mem = sqlite3.connect(":memory:")
    src.backup(mem)  # in-memory copy: the S1 rewrite below never touches the file
    mem.row_factory = sqlite3.Row
    return mem


def reweigh(conn, run_id, weights):
    for creator_id, breakdown in conn.execute("SELECT creator_id,breakdown_json FROM scores WHERE run_id=? AND stage='S1'", (run_id,)).fetchall():
        b = json.loads(breakdown)
        conn.execute("UPDATE scores SET score=? WHERE run_id=? AND creator_id=? AND stage='S1'",
                     (round(sum(b[name] * w for name, w in weights.items()) / 100, 4), run_id, creator_id))


def handle(conn, cid):
    row = conn.execute("SELECT handle FROM creators WHERE creator_id=?", (cid,)).fetchone()
    return row[0] if row and row[0] else cid


def picks(conn, run_id):
    return [(item["id"], item["final"]) for item in _best_five(conn, run_id)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", action="append")
    args = parser.parse_args()
    new_weights = load_config()["scoring"]["s1_weights"]
    print(f"old weights {OLD_WEIGHTS}\nnew weights {dict(new_weights)}")
    for run_id in args.run_id or RUNS:
        conn = load(args.db)
        stored = {r[0]: r[1] for r in conn.execute("SELECT creator_id,score FROM scores WHERE run_id=? AND stage='S1'", (run_id,))}
        old_top = s1_shortlist(conn, run_id, 40)
        old_pick = picks(conn, run_id)
        reweigh(conn, run_id, OLD_WEIGHTS)
        drift = max(abs(r[1] - stored[r[0]]) for r in conn.execute("SELECT creator_id,score FROM scores WHERE run_id=? AND stage='S1'", (run_id,)))
        reweigh(conn, run_id, new_weights)
        new_top = s1_shortlist(conn, run_id, 40)
        new_pick = picks(conn, run_id)
        has_s3 = {r[0] for r in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S3' AND score IS NOT NULL", (run_id,))}
        added = [c for c in new_top if c not in old_top]
        comps = [json.loads(r[0]) for r in conn.execute("SELECT breakdown_json FROM scores WHERE run_id=? AND stage='S1'", (run_id,))]
        print(f"\n== Run {run_id}\nS1 creators {len(stored)}; replay with old weights vs stored: max diff {drift:.4f}")
        print("creators at component 100: " + ", ".join(f"{k} {sum(c[k] >= 99.995 for c in comps)}/{len(comps)}" for k in ("video_gpm", "skincare_revenue_share")))
        print(f"S1 top 40 overlap old/new: {len(set(old_top) & set(new_top))}/40; entering: {len(added)} ({sum(c in has_s3 for c in added)} already have S3, {sum(c not in has_s3 for c in added)} would need a paid S2/S3 run)")
        print("final top 5 old:", [(handle(conn, c), round(f, 2)) for c, f in old_pick])
        print("final top 5 new:", [(handle(conn, c), round(f, 2)) for c, f in new_pick])
        old_rank = {c: i for i, (c, _) in enumerate(old_pick, 1)}
        for i, (c, _) in enumerate(new_pick, 1):
            print(f"  new #{i} {handle(conn, c)}: old rank {old_rank.get(c, 'out')}")
        print("dropped from top 5:", [handle(conn, c) for c in old_rank if c not in {x for x, _ in new_pick}])
    print("\nnote: final scores use only creators that already have S2/S3 in the stored run; a live rerun would also analyse the entering creators.")


if __name__ == "__main__":
    main()
