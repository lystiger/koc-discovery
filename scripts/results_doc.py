"""Write docs/RESULTS.md: the final KOC proposal of one run with its evidence, cost and time.

Read-only on the database. Usage:
  PYTHONPATH=src python scripts/results_doc.py --db data/koc.db --run <run_id> [--out docs/RESULTS.md]
"""
import argparse
import json
import sqlite3
from pathlib import Path

from koc.db import run_analyses
from koc.faithfulness import split_scores


def vnd(x):
    return f"{int(x):,}".replace(",", ".") + " đ"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/koc.db")
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", default="docs/RESULTS.md")
    a = ap.parse_args()
    c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    run = a.run
    params = json.loads(c.execute("SELECT params_json FROM runs WHERE run_id=?", (run,)).fetchone()[0])
    brief, s4, wall = params["brief"], params.get("s4", {}), params.get("stage_wall_ms", {})
    recs = c.execute(
        "SELECT r.rank, r.creator_id, c.handle, r.est_cost_vnd, r.rec_json FROM recommendations r "
        "JOIN creators c USING(creator_id) WHERE run_id=? ORDER BY rank", (run,)).fetchall()

    def score(stage, cid):
        row = c.execute("SELECT score, breakdown_json FROM scores WHERE run_id=? AND creator_id=? AND stage=?",
                        (run, cid, stage)).fetchone()
        return (row[0], json.loads(row[1] or "{}")) if row else (None, {})

    faith = {}
    has_faith = c.execute("SELECT 1 FROM sqlite_master WHERE name='faithfulness'").fetchone()
    L = [f"# Kết quả: {len(recs)} KOC cho {brief['product']}", "",
         f"Brief: {brief.get('target', '')}, ngân sách {vnd(brief['budget_vnd'])}, {brief['count']} KOC. "
         f"Lượt chạy `{run}`. Tổng phí ước tính {vnd(s4.get('total_vnd', 0))}, còn dư {vnd(s4.get('leftover_vnd', 0))}.", "",
         "Điểm cuối = (45 × thương mại + 35 × nội dung) / 80, vì dữ liệu khán giả của gói Kalodata là số mẫu. "
         "Mỗi KOC có ít nhất một video hợp thương hiệu từ 3/5. Giá booking là ước tính theo bậc follower × 3 video.", "",
         "Điểm dưới đây là điểm đã lưu của lượt chạy, tính theo trọng số S1 cũ (có tỷ trọng ngành proxy 25%). "
         "Với trọng số v2.0 (proxy không tính điểm), điểm cuối giảm 1,3 đến 2,4 và thứ tự 5 KOC không đổi.", "",
         "## Đề xuất", "",
         "| # | KOC | Điểm cuối | Thương mại | Nội dung | Hợp thương hiệu cao nhất | Phí ước tính |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for rank, cid, h, cost, _ in recs:
        fs, fb = score("S4", cid)
        L.append(f"| {rank} | [{h}](https://www.tiktok.com/{h}) | {fs:.1f} | {fb.get('commercial', 0):.1f} | "
                 f"{fb.get('content', 0):.1f} | {fb.get('brand_fit_max', '')}/5 | {vnd(cost)} |")
    for rank, cid, h, cost, rec_json in recs:
        rec = json.loads(rec_json)
        an = run_analyses(c, run, cid)
        ev = {}
        L += ["", f"## {rank}. {h}", ""]
        L.append("Video đã phân tích:")
        for vid, _, _, aj in an:
            d = json.loads(aj)
            rub = {x["criterion"]: x["score"] for x in d["rubric"]}
            for e in d.get("evidence", []):
                ev[e["evidence_id"]] = e
            L.append(f"- [{vid}](https://www.tiktok.com/{h}/video/{vid}): hợp thương hiệu {rub.get('brand_fit')}/5, "
                     f"rõ sản phẩm {rub.get('product_clarity')}/5, trình diễn {rub.get('demonstration')}/5")
        metrics = dict(c.execute("SELECT name, value FROM metrics WHERE creator_id=?", (cid,)).fetchall())
        L += ["", "Lý do và bằng chứng:"]
        cited = rec.get("cited_evidence_ids", [])
        for i, reason in enumerate(rec.get("reasons_vi", []), 1):
            L.append(f"{i}. {reason}")
        quotes = []
        for eid in cited:
            if eid.startswith("metric:"):
                name = eid.split(":")[2]
                val = metrics.get(name)
                quotes.append(f"   - số liệu `{name}` = {json.loads(val) if isinstance(val, str) else val}")
            elif eid in ev:
                e = ev[eid]
                t = int(e.get("start_s") or 0)
                kind = "lời nói" if e.get("kind") == "speech" else "khung hình"
                quotes.append(f"   - {kind} [{e['video_id']} @ {t}s](https://www.tiktok.com/{h}/video/{e['video_id']}): "
                              f"\"{e.get('quote_vi', '')}\"")
        if quotes:
            L += ["", "Bằng chứng được trích:"] + [q.strip() for q in quotes]
        if rec.get("caveats_vi"):
            L += ["", "Lưu ý:"] + [f"- {x}" for x in rec["caveats_vi"]]
        if has_faith:
            row = c.execute("SELECT verdicts_json FROM faithfulness WHERE run_id=? AND creator_id=? ORDER BY created_at DESC LIMIT 1",
                            (run, cid)).fetchone()
            if row:
                faith[h] = split_scores(json.loads(row[0]), len(rec.get("reasons_vi", [])))[0]

    L += ["", "## Chi phí và thời gian của lượt này", "",
          "| Giai đoạn | Thời gian | Tín dụng Kalodata | Lượt gọi LLM | Token vào | Token ra | USD |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    api = dict(c.execute("SELECT 1, COALESCE(SUM(credits),0) FROM api_calls WHERE run_id=?", (run,)).fetchall())
    llm = c.execute("SELECT kind, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(cost_usd) FROM llm_calls "
                    "WHERE run_id=? AND cache_hit=0 GROUP BY kind", (run,)).fetchall()
    by_kind = {k: r for k, *r in llm}
    for st in ("S0", "S1a", "S1b", "S2", "S3", "S4"):
        kinds = {"S3": ("content",), "S4": ("reasons",)}.get(st, ())
        rows = [by_kind[k] for k in by_kind if any(k.startswith(x) for x in kinds)]
        n = sum(r[0] for r in rows); ti = sum(r[1] or 0 for r in rows); to = sum(r[2] or 0 for r in rows)
        usd = sum(r[3] or 0 for r in rows)
        cred = api.get(1, 0) if st == "S3" else 0
        L.append(f"| {st} | {wall.get(st, 0) / 1000:.1f} s | {cred:.2f} | {n} | {ti:,} | {to:,} | {usd:.4f} |")
    L += ["", "S0–S2 dùng dữ liệu đã lưu từ lượt chạy đầy đủ trước (cache, 0 chi phí); chỉ S3 và S4 gọi mạng. "
          "Chi phí lượt chạy đầy đủ từ đầu (200 ứng viên): xem [BENCHMARK](BENCHMARK.md)."]
    if faith:
        L += ["", "## Độ trung thực của lý do", "",
              "Một mô hình thứ hai kiểm tra từng lý do với đúng bằng chứng được trích. Điểm = tỷ lệ câu được bằng chứng chống đỡ.", "",
              "| KOC | Lý do |", "|---|---:|"] + [f"| {h} | {s:.3f} |" for h, s in faith.items()]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(recs)} KOC")


if __name__ == "__main__":
    main()
