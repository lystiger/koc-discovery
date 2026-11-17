"""Compute the human-evaluation metrics from the filled sheets in docs/eval/ and the run in the database.

Read-only on the database. Writes docs/eval/METRICS.md and prints it.
Usage: PYTHONPATH=src python scripts/eval_metrics.py --db data/koc.db --run <run_id> [--eval docs/eval]
"""
import argparse
import csv
import json
import math
import sqlite3
from pathlib import Path

from koc.db import run_analyses

VERDICT = {"co": 1.0, "có": 1.0, "dieukien": 0.5, "dieu_kien": 0.5, "có điều kiện": 0.5, "khong": 0.0, "không": 0.0}
CHECK = {"dung": 1.0, "đúng": 1.0, "motphan": 0.5, "mot_phan": 0.5, "một phần": 0.5, "sai": 0.0}


def rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(str(x).strip().replace(",", "."))
    except ValueError:
        return None


def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def pct(x):
    return "chưa chấm" if x is None else f"{x * 100:.0f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/koc.db")
    ap.add_argument("--run", required=True)
    ap.add_argument("--eval", default="docs/eval")
    a = ap.parse_args()
    ev = Path(a.eval)
    c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    run = a.run
    brief = json.loads(c.execute("SELECT params_json FROM runs WHERE run_id=?", (run,)).fetchone()[0])["brief"]
    picks = c.execute("SELECT c.handle, r.creator_id, r.est_cost_vnd, c.data_json FROM recommendations r "
                      "JOIN creators c USING(creator_id) WHERE run_id=? ORDER BY rank", (run,)).fetchall()
    pick_handles = [p[0] for p in picks]
    analysed = c.execute("SELECT s.creator_id, c.handle FROM scores s JOIN creators c USING(creator_id) "
                         "WHERE s.run_id=? AND s.stage='S3'", (run,)).fetchall()
    ai_video, gate_min = {}, 3
    for cid, h in analysed:
        for vid, _, _, aj in run_analyses(c, run, cid):
            rub = {x["criterion"]: x["score"] for x in json.loads(aj)["rubric"]}
            ai_video[(h, vid)] = rub.get("brand_fit")

    videos = rows(ev / "1_videos.csv")
    kocs = {r["handle"]: r for r in rows(ev / "2_koc.csv")}
    evidence = rows(ev / "3_evidence.csv")

    human_video = {(r["handle"], r["video_id"]): num(r["your_score_1_5"]) for r in videos if num(r["your_score_1_5"]) is not None}
    pairs = [(human_video[k], ai_video[k]) for k in human_video if ai_video.get(k) is not None]
    within1 = sum(abs(h - m) <= 1 for h, m in pairs) / len(pairs) if pairs else None
    gate_side = sum((h >= gate_min) == (m >= gate_min) for h, m in pairs) / len(pairs) if pairs else None
    mae = sum(abs(h - m) for h, m in pairs) / len(pairs) if pairs else None

    def verdict(h):
        v = (kocs.get(h, {}).get("your_verdict_co_dieukien_khong") or "").strip().lower()
        return VERDICT.get(v)

    def grade(h):
        return num(kocs.get(h, {}).get("your_grade_0_3"))

    pv = [verdict(h) for h in pick_handles]
    done = all(v is not None for v in pv)
    p5_strict = sum(v == 1.0 for v in pv) if done else None
    p5_soft = sum(pv) if done else None

    g_picks = [grade(h) for h in pick_handles]
    all_grades = [grade(h) for _, h in analysed]
    ndcg_in = ndcg_pool = None
    if all(g is not None for g in g_picks):
        ideal_in = dcg(sorted(g_picks, reverse=True))
        ndcg_in = dcg(g_picks) / ideal_in if ideal_in else None
        if all(g is not None for g in all_grades):
            ideal_pool = dcg(sorted(all_grades, reverse=True)[:5])
            ndcg_pool = dcg(g_picks) / ideal_pool if ideal_pool else None

    checks = [CHECK.get((r["your_check_dung_motphan_sai"] or "").strip().lower()) for r in evidence]
    judged = [x for x in checks if x is not None]
    ev_acc = sum(judged) / len(judged) if judged else None
    wrong = [r for r, x in zip(evidence, checks) if x == 0.0]

    # Hard requirements checked by code
    total = sum(p[2] for p in picks)
    mcn = [json.loads(p[3] or "{}").get("mcn_id") for p in picks]
    mcn = [m for m in mcn if m]
    code_checks = [
        ("Số KOC = brief", len(picks) == brief["count"], f"{len(picks)} / {brief['count']}"),
        ("Tổng phí ≤ ngân sách", total <= brief["budget_vnd"], f"{total:,} / {brief['budget_vnd']:,} đ".replace(",", ".")),
        ("Không trùng MCN", (len(mcn) == len(set(mcn))) if mcn else None,
         f"{len(mcn)}/{len(picks)} KOC có mã MCN" + ("" if mcn else ": không rõ, dữ liệu đã lưu không có mã MCN")),
        ("Mỗi KOC có video AI chấm hợp thương hiệu ≥ 3", all(
            any((ai_video.get((h, v)) or 0) >= gate_min for (hh, v) in ai_video if hh == h) for h in pick_handles), "cổng D-B7"),
    ]
    # Human hard check: a pick with no video the human rated >= 3 violates "promotes this product type"
    human_viol = None
    if all(any(k[0] == h for k in human_video) for h in pick_handles):
        human_viol = [h for h in pick_handles if not any(s >= gate_min for (hh, _), s in human_video.items() if hh == h)]

    # False negatives: KOCs analysed but not picked, that the human judges suitable
    non_picked = [h for _, h in analysed if h not in pick_handles]
    gate_out = [h for h in non_picked if not any((ai_video.get((hh, v)) or 0) >= gate_min for (hh, v) in ai_video if hh == h)]
    fn = [h for h in non_picked if verdict(h) == 1.0]
    fn_gate = [h for h in gate_out if any(s >= gate_min for (hh, _), s in human_video.items() if hh == h)]
    suitable = [h for _, h in analysed if verdict(h) == 1.0]
    recall = (sum(h in pick_handles for h in suitable) / len(suitable)) if suitable and all(verdict(h) is not None for _, h in analysed) else None

    L = [f"# Đánh giá thủ công, lượt `{run}`", "",
         "Người chấm: người xây hệ thống (không độc lập). Chấm video và KOC trước khi xem điểm hệ thống.", "",
         "| Chỉ số | Kết quả | Mục tiêu |", "|---|---|---|",
         f"| Precision@5 (chỉ tính \"có\") | {'chưa chấm' if p5_strict is None else f'{p5_strict}/5'} | ≥ 4/5 |",
         f"| Precision@5 (\"có điều kiện\" = 0,5) | {'chưa chấm' if p5_soft is None else f'{p5_soft:g}/5'} | ≥ 4/5 |",
         f"| nDCG@5 trong 5 KOC được chọn | {'chưa chấm' if ndcg_in is None else f'{ndcg_in:.2f}'} | ≥ 0,85 |",
         f"| nDCG@5 so với cả {len(analysed)} KOC đã phân tích | {'chưa chấm' if ndcg_pool is None else f'{ndcg_pool:.2f}'} | ≥ 0,85 |",
         f"| Độ đúng bằng chứng ({len(judged)}/{len(evidence)} mục đã kiểm) | {pct(ev_acc)} | ≥ 95% |",
         f"| Đồng thuận hợp thương hiệu, lệch ≤ 1 điểm ({len(pairs)} video) | {pct(within1)} | ≥ 80% |",
         f"| Đồng thuận hợp thương hiệu, cùng phía ngưỡng 3 | {pct(gate_side)} | ≥ 80% |",
         f"| Sai lệch trung bình người và AI | {'chưa chấm' if mae is None else f'{mae:.2f} điểm'} | |",
         f"| Vi phạm yêu cầu cứng (code) | {sum(ok is False for _, ok, _ in code_checks)}/{sum(ok is not None for _, ok, _ in code_checks)} kiểm được | 0 |",
         f"| Vi phạm yêu cầu cứng (người chấm: KOC không có video nào ≥ 3) | {'chưa chấm' if human_viol is None else f'{len(human_viol)}/5'} | 0 |",
         "| Khán giả nữ 18–30 | không xác minh được (gói Kalodata không có dữ liệu khán giả) | xác minh |",
         "| Ngân sách khả thi | không xác minh được (giá ước tính theo bậc follower, chưa hỏi KOC/MCN) | xác minh |",
         f"| Bỏ sót: KOC không được chọn nhưng người chấm thấy phù hợp | {'chưa chấm' if any(verdict(h) is None for h in non_picked) else f'{len(fn)}/{len(non_picked)}'} | 0 |",
         f"| Bỏ sót do cổng hợp thương hiệu (người chấm có video ≥ 3) | {'chưa chấm' if not all(any(k[0] == h for k in human_video) for h in gate_out) else f'{len(fn_gate)}/{len(gate_out)}'} | 0 |",
         f"| Recall trong {len(analysed)} KOC đã phân tích | {pct(recall)} | |",
         "", "## Kiểm tra bằng code", "", "| Yêu cầu | Đạt | Chi tiết |", "|---|---|---|"]
    L += [f"| {n} | {'không rõ' if ok is None else 'đạt' if ok else 'KHÔNG'} | {d} |" for n, ok, d in code_checks]
    if wrong:
        L += ["", "## Bằng chứng sai", ""] + [f"- {r['handle']} `{r['evidence_id']}`: {r['claim']} ({r['note']})" for r in wrong]
    if fn or fn_gate:
        L += ["", "## KOC bị bỏ sót", ""] + [f"- {h}" + (" (bị cổng loại)" if h in fn_gate else "") for h in sorted(set(fn + fn_gate))]
    L += ["", "Recall@10 trên toàn bộ 200 ứng viên chưa đo: cần gán nhãn cả nhóm ứng viên. Chỉ đo được trong các KOC đã phân tích video."]
    text = "\n".join(L) + "\n"
    (ev / "METRICS.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
