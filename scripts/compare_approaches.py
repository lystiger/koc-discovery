"""Compare KOC selection approaches on the same frozen rated set: quality against the human grades, and cost.

A: Kalodata commercial metrics and deterministic budget selection only (no LLM).
B: the current pipeline (audience check, video analysis by a multimodal model, brand-fit gate).
C: improved pipeline (persona-fit scoring): not run yet, listed as pending.

Read-only on the database. Writes docs/eval/COST_EFFICIENCY.md. Usage:
  PYTHONPATH=src python scripts/compare_approaches.py --db data/koc.db --run <run_id>
"""
import argparse
import csv
import itertools
import json
import math
import sqlite3
from pathlib import Path

from koc.pipeline import _rate
from koc.stages import s1_shortlist

A_STAGES = ("S0", "S1a", "S1b")
BLIND_GRADE = {"@meixiuriviu": 1.0}  # grade before the rater saw the result (docs/eval/METRICS.md)


def vn(x, spec="g"):
    """Vietnamese number: dot thousands, comma decimals."""
    return format(x, spec).replace(",", "_").replace(".", ",").replace("_", ".")


def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def approach_a(c, run, budget, count, pool=15):
    """Top `pool` by commercial score, then the best `count` within budget by summed commercial score."""
    rows = []
    for cid in s1_shortlist(c, run, pool):
        s1 = c.execute("SELECT score FROM scores WHERE run_id=? AND creator_id=? AND stage='S1'", (run, cid)).fetchone()[0]
        h, data = c.execute("SELECT handle, data_json FROM creators WHERE creator_id=?", (cid,)).fetchone()
        rows.append((h, s1, _rate(int(float(json.loads(data).get("creator_followers") or 0)))))
    combos = [cb for cb in itertools.combinations(rows, count) if sum(x[2] for x in cb) <= budget]
    best = max(combos, key=lambda cb: sum(x[1] for x in cb))
    best = sorted(best, key=lambda x: -x[1])
    return [x[0] for x in best], sum(x[2] for x in best)


def quality(picks, grades, verdicts, pool_handles):
    v = [verdicts.get(h) for h in picks]
    if any(x is None for x in v):
        return None
    g = [grades[h] for h in picks]
    ideal = dcg(sorted((grades[h] for h in pool_handles), reverse=True)[:5])  # @5 even when fewer than 5 picks fit
    return {"strict": sum(x == "co" for x in v), "soft": sum({"co": 1, "dieukien": 0.5}.get(x, 0) for x in v),
            "ndcg_pool": dcg(g) / ideal if ideal else 0.0}


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return cov / (sx * sy) if sx and sy else None


def approach_c(c, run, budget, count, persona, soft_gate=False):
    """B's candidates (S3 KOCs) ranked by (45 S1 + 20 persona + 35 S3) / 100, best `count` within budget.

    soft_gate: a KOC whose best video is 2/5 brand fit also passes when its persona score is >= 80 (mean >= 4/5)."""
    from koc.persona import c_final
    from koc.pipeline import _excluded_creators
    from koc.stages import brand_fit_gate
    excluded = _excluded_creators(c, run)  # creators picked in runs the brief excluded (--exclude-run), as in B
    rows = []
    for r in c.execute("SELECT s.creator_id, c.handle, c.data_json FROM scores s JOIN creators c USING(creator_id) "
                       "WHERE s.run_id=? AND s.stage='S3'", (run,)):
        cid = r["creator_id"]
        if cid not in persona or cid in excluded:
            continue
        gate = brand_fit_gate(c, run, cid)
        ok = gate["eligible"] or (soft_gate and (gate["max_brand_fit"] or 0) >= 2 and persona[cid] >= 80)
        if not ok:
            continue
        sc = dict(c.execute("SELECT stage, score FROM scores WHERE run_id=? AND creator_id=?", (run, cid)).fetchall())
        profile = json.loads(r["data_json"])
        cost = _rate(int(float(profile.get("creator_followers") or 0)))
        rows.append((r["handle"], c_final(sc["S1"], persona[cid], sc["S3"]), cost, profile.get("mcn_id")))

    def valid(cb):  # same rules as B's _best_five: budget and no two KOCs from one known MCN
        mcn = [x[3] for x in cb if x[3]]
        return sum(x[2] for x in cb) <= budget and len(mcn) == len(set(mcn))
    combos = [cb for cb in itertools.combinations(rows, min(count, len(rows))) if valid(cb)]
    if not combos:
        return [], 0
    best = sorted(max(combos, key=lambda cb: sum(x[1] for x in cb)), key=lambda x: -x[1])
    return [x[0] for x in best], sum(x[2] for x in best)


def persona_scores(c, run):
    """(creator_id -> persona 0-100, spend, status). Scores only when every analysed video of the run has a stored
    result for one model; otherwise (None, None, "x/y video") so a partial pass is never reported as C."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='persona_fit'").fetchone():
        return None, None, None
    row = c.execute("SELECT model FROM persona_fit WHERE run_id=? AND prompt_version='persona_v1' ORDER BY created_at DESC LIMIT 1", (run,)).fetchone()
    if row is None:
        return None, None, None
    from koc.persona import coverage, per_koc, spend
    have, want = coverage(c, run, row[0])
    if have < want:
        return None, None, f"{have}/{want} video"
    return per_koc(c, run, row[0]), {**spend(c, run, row[0]), "model": row[0]}, None


def verdict_of(grade):
    return "co" if grade >= 2.5 else "dieukien" if grade >= 1.5 else "khong"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/koc.db")
    ap.add_argument("--run", required=True)
    ap.add_argument("--eval", default="docs/eval")
    ap.add_argument("--benchmark", default="reports/benchmark.json")
    a = ap.parse_args()
    c = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    run = a.run
    brief = json.loads(c.execute("SELECT params_json FROM runs WHERE run_id=?", (run,)).fetchone()[0])["brief"]
    b_picks = [h for (h,) in c.execute("SELECT c.handle FROM recommendations r JOIN creators c USING(creator_id) "
                                       "WHERE run_id=? ORDER BY rank", (run,))]
    b_cost = c.execute("SELECT SUM(est_cost_vnd) FROM recommendations WHERE run_id=?", (run,)).fetchone()[0]
    a_picks, a_cost = approach_a(c, run, brief["budget_vnd"], brief["count"])
    persona, p_spend, p_partial = persona_scores(c, run)
    if persona:
        c_picks, c_cost = approach_c(c, run, brief["budget_vnd"], brief["count"], persona)
        c2_picks, c2_cost = approach_c(c, run, brief["budget_vnd"], brief["count"], persona, soft_gate=True)
    rated = list(csv.DictReader(open(Path(a.eval) / "2_koc.csv", encoding="utf-8")))
    post = {r["handle"]: float(r["your_grade_0_3"].replace(",", ".")) for r in rated}
    blind = {**post, **BLIND_GRADE}
    pool = list(post)

    bench = json.loads(Path(a.benchmark).read_text())
    st = bench["stages_success"]
    cost_a = {"credits": sum(st[s]["credits"] for s in A_STAGES), "usd": 0.0,
              "seconds": sum(st[s]["wall_time_ms"] for s in A_STAGES) / 1000}
    tot = bench["totals_success"]
    cost_b = {"credits": tot["credits"], "usd": tot["usd"], "seconds": tot["wall_time_ms"] / 1000}
    cost_b_total = {"credits": bench["totals_total"]["credits"], "usd": bench["totals_total"]["usd"]}
    if persona:
        # Untagged calls (made before calls were tagged) cannot be tied to this run: adding them gives an upper bound.
        extra = p_spend["untagged"]
        cost_c = {"credits": cost_b["credits"], "usd": cost_b["usd"] + p_spend["usd"] + extra["usd"],
                  "seconds": cost_b["seconds"] + p_spend["seconds"] + extra["seconds"], "upper": not p_spend["exact"]}

    def row(name, picks, q, cost, booking):
        if q is None:
            return f"| {name} | chưa chấm đủ | | | | | |"
        le = "≤ " if cost.get("upper") else ""
        return (f"| {name} | {q['strict']}/5 | {vn(q['soft'])}/5 | {vn(q['ndcg_pool'], '.2f')} | {le}{cost['seconds'] / 60:.0f} phút | "
                f"{vn(cost['credits'], '.1f')} | {le}{vn(cost['usd'], '.2f')} USD |")

    L = [f"# Hiệu quả chi phí: ba cách chọn KOC, lượt `{run}`", "",
         f"Cùng brief ({brief['product']}, {vn(brief['budget_vnd'], ',')} đ, {brief['count']} KOC), cùng người chấm, "
         f"cùng {len(pool)} KOC đã chấm ([2_koc.csv](2_koc.csv)). Cả 5 KOC mà A chọn đều nằm trong {len(pool)} KOC đã chấm, "
         "nên không cần chấm thêm.", "",
         "- **A, chỉ số liệu thương mại**: 15 KOC điểm thương mại (S1) cao nhất, chọn 5 KOC có tổng điểm S1 lớn nhất trong ngân sách. Không gọi mô hình, không xem video.",
         "- **B, pipeline hiện tại**: thêm khán giả (S2), phân tích 3 video mỗi KOC bằng mô hình đa phương thức (S3), cổng hợp thương hiệu, chọn theo điểm cuối.",
         ("- **C, B thêm độ hợp chân dung**: mỗi video B đã phân tích được chấm thêm `audience_persona_fit` 1–5 (tuổi ước chừng, phong cách, cách xưng hô so với khán giả mục tiêu; [prompt](../../prompts/persona_v1.md)). "
          "Điểm cuối = (45 thương mại + 20 chân dung + 35 nội dung) / 100; cổng hợp thương hiệu và cách chọn trong ngân sách giữ nguyên. "
          "Phân tích video của B dùng lại nguyên vẹn, nên C chỉ khác B ở trọng số chân dung."
          + ("" if persona else " Chưa chạy.")),
         ("- **C', C với cổng mềm hơn**: KOC có video tốt nhất 2/5 vẫn qua cổng nếu điểm chân dung ≥ 80 (trung bình ≥ 4/5). "
          "Luật này đặt ra sau khi biết người chấm chọn thế nào: chỉ là tham khảo, thiên vị về phía người chấm này." if persona else None), ""]
    L = [x for x in L if x is not None]
    for label, grades in (("Chấm mù", blind), ("Sau khi người chấm đổi @meixiuriviu", post)):
        verdicts = {h: verdict_of(g) for h, g in grades.items()}
        qa, qb = quality(a_picks, grades, verdicts, pool), quality(b_picks, grades, verdicts, pool)
        if persona:
            qc, qc2 = quality(c_picks, grades, verdicts, pool), quality(c2_picks, grades, verdicts, pool)
            c_rows = [row("C", c_picks, qc, cost_c, c_cost), row("C' (cổng mềm, tham khảo)", c2_picks, qc2, cost_c, c2_cost)]
        else:
            c_rows = [f"| C | chưa chấm xong chân dung ({p_partial}) | | | | | |" if p_partial else
                      "| C | chưa chạy | | | | | ước tính khoảng 0,3 USD cho 30 video (`koc persona --dry-run`) |"]
        good = sum(v == "co" for v in verdicts.values())
        L += [f"## {label}", "",
              "| Cách | Precision@5 (\"có\") | Precision@5 (\"có điều kiện\" = 0,5) | nDCG@5 so với 10 KOC | Thời gian lượt đầy đủ | Credit Kalodata | Chi phí mô hình |",
              "|---|---:|---:|---:|---:|---:|---:|",
              row("A", a_picks, qa, cost_a, a_cost), row("B", b_picks, qb, cost_b, b_cost),
              *c_rows,
              f"| Chọn ngẫu nhiên 5 trong {len(pool)} KOC (kỳ vọng) | {vn(5 * good / len(pool))}/5 | | | | | |", ""]
    cols = [a_picks, b_picks] + ([c_picks, c2_picks] if persona else [])
    L += ["## KOC mỗi cách chọn", "", "| # | A | B |" + (" C | C' |" if persona else ""), "|---|---|---|" + ("---|---|" if persona else "")]
    L += [f"| {i} | " + " | ".join(col[i - 1] if i <= len(col) else "" for col in cols) + " |" for i in range(1, 6)]
    if persona:
        from koc.stages import brand_fit_gate
        ids = {h: cid for cid, h in c.execute("SELECT creator_id, handle FROM creators")}
        hs = [h for h in pool if ids.get(h) in persona]
        L += ["", "## Độ hợp chân dung so với người chấm", "",
              (f"{p_spend['calls']} lượt gọi, {vn(p_spend['usd'], '.4f')} USD, mô hình `{p_spend['model']}`. " if p_spend["exact"] else
               f"Mô hình `{p_spend['model']}`. Chi phí là cận trên: {p_spend['calls'] + extra['calls']} lượt gọi, "
               f"{vn(p_spend['usd'] + extra['usd'], '.4f')} USD, gồm {extra['calls']} lượt gọi persona cùng mô hình ghi trước khi có nhãn lượt chạy, "
               "không chứng minh được thuộc lượt này. ")
              + "Điểm chân dung = trung bình 3 video × 20.", "",
              "| KOC | Chân dung (0–100) | Người chấm (0–3, mù) | Qua cổng hợp thương hiệu |", "|---|---:|---:|---|"]
        L += [f"| {h} | {vn(persona[ids[h]], '.0f')} | {vn(blind[h])} | {'có' if brand_fit_gate(c, run, ids[h])['eligible'] else 'không'} |"
              for h in sorted(hs, key=lambda h: -persona[ids[h]])]
        rb = spearman([persona[ids[h]] for h in hs], [blind[h] for h in hs])
        rp = spearman([persona[ids[h]] for h in hs], [post[h] for h in hs])
        L += ["", f"Tương quan hạng Spearman giữa điểm chân dung và người chấm trên {len(hs)} KOC: "
              f"{'không tính được' if rb is None else vn(rb, '.2f')} (chấm mù), {'không tính được' if rp is None else vn(rp, '.2f')} (sau khi đổi). "
              "Gần 1 là chân dung dự đoán đúng thứ tự người chấm; gần 0 là không liên quan. 10 KOC là mẫu rất nhỏ.", ""]
        from koc.stages import final_score

        def stage(h, st):
            r = c.execute("SELECT score FROM scores WHERE run_id=? AND creator_id=? AND stage=?", (run, ids[h], st)).fetchone()
            return r[0] if r else None
        signals = [("Thương mại (S1)", lambda h: stage(h, "S1")), ("Nội dung video (S3)", lambda h: stage(h, "S3")),
                   ("Điểm cuối của B", lambda h: final_score(stage(h, "S1"), None, stage(h, "S3"))), ("Chân dung", lambda h: persona[ids[h]])]
        L += ["| Tín hiệu | Spearman với người chấm (mù) | Sau khi đổi |", "|---|---:|---:|"]
        for name, f in signals:
            xs = [f(h) for h in hs]
            a1, a2 = spearman(xs, [blind[h] for h in hs]), spearman(xs, [post[h] for h in hs])
            L.append(f"| {name} | {'—' if a1 is None else vn(a1, '.2f')} | {'—' if a2 is None else vn(a2, '.2f')} |")
        L += ["", "Với cổng giữ nguyên, chỉ 6 KOC qua cổng và ngân sách buộc giữ 2 KOC giá 3 triệu, nên C chỉ đổi được 1 KOC so với B: "
              "C không thể có Precision@5 cao hơn B trên lượt này.",
              "", "## Kết luận về C", "",
              "- Điểm chân dung khớp người chấm tốt nhất trong mọi tín hiệu đã đo: 4 KOC chân dung cao nhất gồm cả 3 KOC người chấm chọn \"có\" khi chấm mù "
              "(@dunghana2882, @ducvietbe__, @rio100806) và @meixiuriviu (\"có\" sau khi đổi). Mô hình thấy được tuổi và phong cách từ khung hình và giọng nói.",
              "- Nhưng C (giữ cổng) không tốt hơn B: 2 trong 3 KOC đó bị cổng hợp thương hiệu loại, và C chọn @k_dung26 (chân dung 80, người chấm 0: video thô) thay @emduyencantho. "
              "Chân dung đo người, không đo chất lượng video; cần cả hai.",
              "- C' (cổng mềm) đạt bằng A về Precision@5 và nDCG cao nhất sau khi đổi (0,90), nhưng luật cổng mềm được đặt ra sau khi biết người chấm chọn thế nào. "
              "@dunghana2882 vẫn không vào vì phí 15 triệu.",
              "- Chi phí thêm của chân dung: khoảng 0,009 USD mỗi video, 0,28 USD cho 30 video, cộng khoảng 4 phút khi chạy tuần tự.",
              "- Việc tiếp theo: giữ chân dung như một thành phần điểm, đổi cổng từ \"video phải nói về kem chống nắng\" sang \"KOC làm chăm sóc da và hợp chân dung\", "
              "rồi kiểm lại bằng người chấm thứ hai trên một brief mới. Chưa làm: một người chấm, một brief không đủ để đổi luật mặc định."]
    L += ["", f"Phí booking ước tính: A {vn(a_cost, ',')} đ, B {vn(b_cost, ',')} đ" + (f", C {vn(c_cost, ',')} đ, C' {vn(c2_cost, ',')} đ" if persona else "") + " (chi phí chiến dịch, không phải chi phí phần mềm).", "",
          "## Cách đọc", "",
          "- Trên người chấm này, B **không** tốt hơn A. A chọn đúng 2 KOC người chấm muốn (@rio100806, @ducvietbe__) mà không tốn mô hình; "
          "B chọn 1 (chấm mù). Lý do đã biết: người chấm chọn theo tuổi và phong cách Gen Z, mà B không đo; điểm nội dung của B kéo các KOC lớn tuổi lên.",
          "- A cũng có lỗi B tránh được: A chọn @cleanboy.tips (kênh nam) và @gaixinhh114 (nhiều loại sản phẩm). "
          "Cổng hợp thương hiệu của B loại cả hai, và người chấm cũng loại cả hai.",
          "- Cổng đó cũng loại @ducvietbe__ và @dunghana2882, hai KOC người chấm chọn \"có\" (video tốt nhất chỉ 2/5 vì ít nói về kem chống nắng). "
          "Đây là chỗ B thua A nhiều nhất: cổng đo video, người chấm đo người.",
          "- Giá trị của B hiện nằm ở bằng chứng (26/29 trích dẫn đúng, 0 bịa), không ở thứ hạng. Kết quả của C ở mục \"Kết luận về C\".",
          "- Mẫu nhỏ: 1 brief, 1 người chấm, 5 KOC, không có tính toán độ bất định. Các chênh lệch ở đây là quan sát trên một người chấm và một brief, không phải kết luận thống kê; hướng cải tiến là giả thuyết cần kiểm trên nhiều brief và người chấm.",
          "- C được thiết kế sau khi biết người chấm chọn thế nào: chấm C bằng chính người chấm này sẽ thiên vị C. Cần người chấm thứ hai hoặc brief giữ kín.", "",
          "## Chi phí", "",
          f"- Số của A và B lấy từ lượt chạy đầy đủ 200 ứng viên ([BENCHMARK](../BENCHMARK.md)), trên đường thành công. "
          f"Tính cả lần thử lỗi, B là {vn(cost_b_total['credits'], '.1f')} credit và {vn(cost_b_total['usd'], '.2f')} USD.",
          "- Chi phí B lấy từ lượt đầy đủ `7372009b`; 5 KOC của B lấy từ lượt `0e555cac` (cùng dữ liệu S0–S2 từ cache, S3 chọn video theo chủ đề). "
          "Lượt `0e555cac` chỉ tốn 6,5 credit và 0,28 USD cho S3–S4 nhờ cache.",
          "- A dừng sau S1b: các stage S0–S1b của B chính là A. Phần B trả thêm là S2 (thời gian), S3 (credit tải video và chi phí mô hình) và S4.",
          "- Giá tiền của một credit Kalodata chưa biết, nên chi phí dữ liệu ghi bằng credit.",
          "- Phí booking KOC là chi phí chiến dịch, tách khỏi chi phí vận hành phần mềm.", "",
          "## Dự báo 500 ứng viên và recall", "",
          "Dự báo 29,7 credit cho 500 ứng viên rẻ vì chỉ 10 KOC được xem video. KOC tốt nằm ngoài 40 KOC thương mại cao nhất "
          "không bao giờ được xem. Tỷ lệ bỏ sót ở bước này chưa đo: cần chấm một mẫu KOC bị loại ở S1.", "",
          "## Chi phí một chiến dịch khi bán thành sản phẩm", "",
          "Nhãn hàng mua một danh sách KOC đã được nghiên cứu, không mua token. Chi phí một chiến dịch:", "",
          "C_chiến dịch = C_dữ liệu (credit Kalodata) + C_mô hình (USD) + C_máy (giờ máy) + C_duyệt (giờ người duyệt bằng chứng)", "",
          "C_duyệt có thể lớn hơn C_mô hình: kiểm một trích dẫn mất khoảng 30 giây, 46 trích dẫn khoảng 25 phút (ước tính trong [HOW_TO_JUDGE](HOW_TO_JUDGE.md), chưa đo), trong khi C_mô hình của B là 0,43 USD. Giá bán nên theo chiến dịch hoặc theo danh sách, không theo token."]
    out = Path(a.eval) / "COST_EFFICIENCY.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
