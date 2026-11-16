"""Vietnamese Markdown rendering for the benchmark result built by koc.benchmark."""
from .benchmark import STAGES


def _fmt_s(ms):
    return f"{ms / 1000:.1f}"


def _stage_table(stages, funnel):
    lines = ["| Giai đoạn | Thời gian (giây) | Tín dụng | Token vào | Token ra | USD | Số lượt gọi | Cache hit | Ứng viên vào → ra |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for stage in STAGES:
        i = stages[stage]
        f = funnel[stage]
        lines.append(f"| {stage} | {_fmt_s(i['wall_time_ms'])} | {i['credits']:.2f} | {i['tokens_in']:,} | {i['tokens_out']:,} | {i['usd']:.4f} | {i['calls']} | {i['cache_hits']} | {f['in']} → {f['out']} |")
    return lines


def _total_row(t):
    return f"| **Tổng** | {_fmt_s(t['wall_time_ms'])} | {t['credits']:.2f} | {t['tokens_in']:,} | {t['tokens_out']:,} | {t['usd']:.4f} | {t['calls']} | {t['cache_hits']} | |"


def _rho(block):
    if block["rho"] is None:
        return f"không tính được ({block['reason']})"
    return f"{block['rho']:+.3f} (n = {block['n']})"


def _projection_table(projection):
    lines = ["| Giai đoạn | Ứng viên | Tín dụng | Token vào | Token ra | USD | Thời gian (giây) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for stage in STAGES:
        i = projection["stages"][stage]
        lines.append(f"| {stage} | {i['candidates']} | {i['credits']:.2f} | {i['tokens_in']:,} | {i['tokens_out']:,} | {i['usd']:.4f} | {i['wall_time_s']:.0f} |")
    t = projection["totals"]
    lines.append(f"| **Tổng** | | {t['credits']:.2f} | {t['tokens_in']:,} | {t['tokens_out']:,} | {t['usd']:.4f} | {t['wall_time_s']:.0f} |")
    return lines


def render_markdown(r):
    ts, tt, w = r["totals_success"], r["totals_total"], r["waste"]
    cfg = r["funnel_config"]
    mode = r["mode"]
    live = mode == "live"
    mode_label = {"live": "chạy thật (live)", "mock": "mô phỏng (mock)", "mixed": "HỖN HỢP (live + mô phỏng)"}[mode]
    L = ["# Chuẩn đo KOC Discovery", ""]
    L.append(f"Lượt chạy `{r['run_id']}` · trạng thái `{r['status']}` · chế độ `{mode_label}` · yêu cầu {r['limit']} ứng viên.")
    L.append("Số liệu lấy trực tiếp từ bảng `api_calls`, `llm_calls`, `tasks` và `runs.params_json` của đúng lượt chạy này (lọc theo `run_id`); không ước lượng bằng tay.")
    if mode == "mock":
        L.append("**Đây là lượt chạy mô phỏng: chi phí bằng 0 vì dùng dữ liệu giả, không đại diện cho chi phí thật.**")
    elif mode == "mixed":
        L.append("**Cảnh báo: lượt chạy này trộn bước mô phỏng và bước thật (ghi nhận từ mô hình trong `llm_calls`); số liệu không đại diện cho chi phí thật.**")
    if r.get("success_estimated"):
        L.append("Giai đoạn " + ", ".join(r["success_estimated_stages"]) + " chưa được theo dõi đầy đủ trong bảng `run_results` (lượt chạy cũ): cột \"đường thành công\" của LLM ở giai đoạn đó là ƯỚC TÍNH theo khóa yêu cầu và phiên bản prompt, không phải gán chính xác theo từng lượt gọi.")
    L += ["", "## 1. Tóm tắt", "",
          "| Chỉ số | Đường thành công | Tổng thực chi (gồm lần thất bại và sửa lỗi) |", "|---|---:|---:|",
          f"| Tín dụng Kalodata | {ts['credits']:.2f} | {tt['credits']:.2f} |",
          f"| Token LLM vào | {ts['tokens_in']:,} | {tt['tokens_in']:,} |",
          f"| Token LLM ra | {ts['tokens_out']:,} | {tt['tokens_out']:,} |",
          f"| USD LLM | {ts['usd']:.4f} | {tt['usd']:.4f} |",
          f"| Số lượt gọi không qua cache (gồm cả lượt 0 đồng) | {ts['calls']} | {tt['calls']} |", "",
          f"Chênh lệch do lần thử thất bại, sửa lỗi (`_repair`) và kết quả bị thay thế: {w['credits']:.2f} tín dụng, {w['tokens_in']:,} token vào, {w['tokens_out']:,} token ra, {w['usd']:.4f} USD "
          f"({r['failed_calls'].get('api', 0)} lượt gọi Kalodata và {r['failed_calls'].get('llm', 0)} lượt gọi LLM không nằm trên đường thành công).",
          "Thời gian chạy là thời gian thực ghi nhận của giai đoạn, gồm mọi lần thử, chờ giới hạn tốc độ và chờ video Kalodata, nên hai bảng dưới có cùng cột thời gian.", "",
          "## 2. Đường thành công", "",
          "Chỉ tính các lượt gọi tạo ra kết quả được giữ lại: lượt LLM sinh ra phân tích/đề xuất cuối cùng, video thuộc phân tích cuối cùng, lượt xem S2 của KOC đã hoàn tất.", ""]
    L += _stage_table(r["stages_success"], r["funnel"]) + [_total_row(ts), ""]
    L += ["## 3. Tổng thực chi", "",
          "Gồm tất cả lượt gọi của lượt chạy: lần thất bại (`api_error`, `pending`), lượt sửa lỗi (`prompt_version` kết thúc bằng `_repair`), kết quả bị thay thế bởi phiên bản prompt sau, video đã tải nhưng không vào phân tích cuối. Lượt `pending` giữ chỗ 0.1 tín dụng vẫn tính vào tổng để không ẩn chi phí.", ""]
    L += _stage_table(r["stages_total"], r["funnel"]) + [_total_row(tt), ""]
    ex = r["excluded_api_calls"]
    L += [f"Loại khỏi phạm vi (không thuộc lượt chạy này): {ex['calls']} lượt gọi Kalodata của lượt chạy khác (lượt chạy cũ, lượt mô phỏng) và các lượt thăm dò không gắn `run_id`, tổng {ex['credits']:.2f} tín dụng.", ""]
    L += ["## 4. Đơn giá theo ứng viên", "",
          "Đơn giá = chi phí giai đoạn ÷ số ứng viên đã xử lý ở giai đoạn đó (S0 và S1a: số ứng viên xếp hạng; S1b: số KOC chấm xong; S2: số KOC đã lấy khán giả; S3: số KOC có điểm nội dung; S4: số KOC được đề xuất). Mẫu số 0 hiển thị đơn giá 0.", "",
          "| Giai đoạn | Mẫu số | Tín dụng (thành công) | Tín dụng (tổng) | USD (thành công) | USD (tổng) | Token vào (tổng) | Token ra (tổng) | Giây (ghi nhận) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for stage in STAGES:
        a, b = r["units_success"][stage], r["units_total"][stage]
        L.append(f"| {stage} | {b['denominator']} | {a['credits']:.4f} | {b['credits']:.4f} | {a['usd']:.5f} | {b['usd']:.5f} | {b['tokens_in']:,.0f} | {b['tokens_out']:,.0f} | {b['wall_time_ms'] / 1000:.2f} |")
    L += ["", "## 5. Dự báo cho 50, 200 và 500 ứng viên", "",
          "Công thức, với N là số ứng viên đầu vào và các giới hạn phễu lấy từ `config/pipeline.yaml` "
          f"(`s1a_limit` = {cfg['s1a_limit']}, `s1_limit` = {cfg['s1_limit']}, `s2_limit` = {cfg['s2_limit']}, `recommendation_count` = {cfg['recommendation_count']}, `video_count` = {cfg['video_count']}):", "",
          "```", "n(S0) = n(S1a) = N", f"n(S1b) = min(N, {cfg['s1a_limit']})", f"n(S2)  = min(n(S1b), {cfg['s1_limit']}, {cfg['s2_limit']})", "n(S3)  = n(S2)", f"n(S4)  = min(n(S3), {cfg['recommendation_count']})",
          "chi phí giai đoạn = n(giai đoạn) × đơn giá theo ứng viên của giai đoạn (mục 4)", "```", "",
          "Vì phễu bị chặn bởi các giới hạn cố định, chi phí gần như không đổi khi N ≥ 60; chỉ S0 và S1a tăng theo N. "
          f"S3 tính trên {cfg['s2_limit']} KOC trong khi lượt chạy thật chỉ có 9 KOC có điểm (1 KOC bị bỏ qua để tiết kiệm), nên cột 200 ứng viên cao hơn số thực đo một chút. "
          f"S2 cần {r['projections']['500']['total_spent']['s2_calendar_days']} ngày theo giới hạn `daily_ui_limit` = {cfg['daily_ui_limit']} lượt xem giao diện mỗi ngày. "
          "Thời gian dự báo dùng thời gian thực đã ghi nhận (gồm chờ giới hạn tốc độ và chờ video), không phải thời gian gọi API thuần.", ""]
    for n in ("50", "200", "500"):
        p = r["projections"][n]
        L += [f"### {n} ứng viên", "",
              f"Đường thành công: {p['successful_path']['totals']['credits']:.2f} tín dụng, {p['successful_path']['totals']['usd']:.4f} USD. "
              f"Tổng thực chi (giữ tỷ lệ thất bại và sửa lỗi như lượt chạy thật): {p['total_spent']['totals']['credits']:.2f} tín dụng, {p['total_spent']['totals']['usd']:.4f} USD.", "",
              "Bảng tổng thực chi:", ""] + _projection_table(p["total_spent"]) + [""]
    cal = r["calibration"]
    L += ["## 6. Hiệu chuẩn Spearman", "",
          "Hệ số Spearman giữa điểm nội dung S3 và hai chỉ số kết quả thật, tính trên các KOC có điểm S3 (finalist) có dữ liệu video đã phân tích:", "",
          f"- Điểm nội dung ↔ lượt xem/người theo dõi (tổng lượt xem các video đã phân tích ÷ người theo dõi): {_rho(cal['content_vs_views_per_follower'])}.",
          f"- Điểm nội dung ↔ GPM video (`video_gpm` từ S1): {_rho(cal['content_vs_video_gpm'])}.", "",
          "Mẫu rất nhỏ (vài KOC), nên chỉ mang tính tham khảo, không đủ để kết luận về độ tin cậy của điểm nội dung.", ""]
    L += ["## 7. Dữ liệu khán giả S2", ""]
    if r["audience_placeholder"]:
        n, total = r["audience_placeholder_creators"], r["audience_creators_checked"]
        L.append(f"Dữ liệu khán giả S2 của {n}/{total} KOC trong lượt chạy này là dữ liệu mẫu (placeholder) của Kalodata (quy tắc theo từng KOC, giống S4). Với các KOC này điểm khán giả bị bỏ khỏi điểm cuối (trọng số được chia lại) và đề xuất ghi rõ lưu ý; KOC còn lại giữ điểm khán giả.")
    else:
        L.append("Không phát hiện dữ liệu khán giả mẫu (placeholder) trong lượt chạy này.")
    L.append("")
    L.append(f"Chi phí xem trang S2: đo thực tế {r['s2_view_credits_observed']:.2f} tín dụng cho mọi lượt `ui/creator_detail` của lượt chạy; giá cấu hình `ui_creator_detail_view` = {r['s2_view_price_config']} (đã xác minh 2026-11-15: số dư tài khoản không đổi ngoài bộ đếm API).")
    L.append("")
    if "scaling_run" in r:
        s = r["scaling_run"]
        L += ["## 8. Lượt chạy mở rộng 50 ứng viên (MÔ PHỎNG, không phải số liệu thật)", "",
              f"Lượt chạy `{s['run_id']}` · chế độ `{s['mode']}` · `--limit {s['limit']}` · trạng thái `{s['status']}`. "
              "Chạy bằng `koc run --mock --limit 50` để kiểm tra cấu trúc và thời gian của phễu mà không tốn tín dụng. "
              "Tín dụng, token và USD đều bằng 0 vì dùng dữ liệu giả, không dùng để suy ra chi phí thật. Thời gian là thời gian máy chạy mô phỏng, không gồm độ trễ mạng hay LLM.", ""]
        L += _stage_table(s["stages_total"], s["funnel"]) + [_total_row(s["totals_total"]), ""]
    L += ["## 9. Hạn chế", "",
          "- Lượt chạy mới gán \"thành công\" chính xác theo từng lượt gọi LLM qua bảng `run_results` (id lượt gọi tạo ra kết quả, theo `run_id`, kèm mô hình). Lượt chạy cũ không có bảng này nên dùng ước lượng theo khóa yêu cầu (`request_hash`), phiên bản prompt và mô hình; ghi rõ ở đầu tài liệu.",
          "- Thời gian giai đoạn là tổng thời gian ghi nhận của mọi lần thử và lần tiếp tục (`resume`), kể cả thời gian chờ; không tách riêng được thời gian của đường thành công.",
          "- Lượt chạy thật được tiếp tục nhiều lần sau khi sửa lỗi nên có nhiều phiên bản prompt (`content_v1`, `v2`, `v3`).", ""]
    if f := r.get("faithfulness"):
        L += ["## 10. Độ trung thực của lý do S4", "",
              f"Mô hình chấm `{f['model']}` (prompt `{f['prompt_version']}`) chấm từng câu lý do và lưu ý của {f['kocs']} KOC chỉ dựa trên bằng chứng mà đề xuất trích dẫn: đủ cơ sở = 1, một phần = 0,5, không có cơ sở = 0. Điểm KOC là trung bình các câu, điểm lượt chạy là trung bình các KOC. Điểm chính là \"Lý do\" (chỉ các lý do); \"Lưu ý\" tính riêng, không gồm lưu ý khán giả chưa xác minh (câu hệ thống, không chấm).", "",
              f"**Điểm Lý do của lượt chạy: {f['run_score']:.2f} / 1.** Điểm Lý do từng KOC: " + ", ".join(f"`{k}` {v:.2f}" for k, v in f["per_koc"].items()) + ".", "",
              (f"Điểm Lưu ý của lượt chạy: {f['caveat_score']:.2f} / 1. Từng KOC: " + ", ".join(f"`{k}` {v:.2f}" for k, v in f["per_koc_caveats"].items()) + ".") if f.get("caveat_score") is not None else "Không có lưu ý nào được chấm.", "",
              "Đây là chấm bằng mô hình thứ hai, có thể sai; không thay cho việc đọc bằng chứng. Không ảnh hưởng đơn giá mỗi KOC dùng cho ước tính.", ""]
    return "\n".join(L)
