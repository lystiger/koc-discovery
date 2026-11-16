# Đánh giá độc lập cam kết 8928651 (Ước tính phễu ứng viên)

- **Cam kết**: `8928651` (`fix(core): scale candidate projections by funnel`)
- **Người đánh giá**: Agy / Gemini 3.8 Flash
- **Môi trường**: Hoàn toàn ngoại tuyến (no network).
- **Kết luận chung**: **PASS** (Không có lỗi P1/P2).

---

## 1. Kết quả kiểm tra theo tiêu chí (Per-check Verdicts)

| Tiêu chí | Kết quả | Vị trí (`file:line`) | Bằng chứng kiểm tra |
|---|---|---|---|
| **1. Per-stage scaling follows funnel config (fraction vs fixed counts)** | **PASS** | [`src/koc/report.py:72-112`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L72-L112)<br>[`config/pipeline.yaml:1-8`](file:///home/lystiger/Projects/KOC-Discovery/config/pipeline.yaml#L1-L8) | Các tầng thu hẹp tỷ lệ (fraction) theo mốc base 200: S1a (`scaled(config["s1a_limit"], candidates)`), S1b (`s1_count = min(s1a_count, scaled(config["s1_limit"], candidates))`), S2 (`s2_count = min(s1_count, scaled(config["s2_limit"], candidates))`). Các tham số giữ cố định (fixed counts): `video_count` = 3 cố định mỗi ứng viên vào S3, `recommendation_count` = 5 cố định ở S4, `rank_page_size` = 100 ở S0. |
| **2. Unit costs from non-cache measured calls** | **PASS** | [`src/koc/report.py:38-62`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L38-L62)<br>[`tests/core/test_report_projection.py:16-53`](file:///home/lystiger/Projects/KOC-Discovery/tests/core/test_report_projection.py#L16-L53) | Truy vấn SQL lọc tường minh `WHERE run_id=? AND cache_hit=0` cho cả `api_calls` và `llm_calls`. Đơn giá credits, latency, tokens, cost_usd được tính trung bình chỉ từ các cuộc gọi thực tế không cache. Kiểm thử `test_projection_scales_funnel_and_uses_non_cache_per_call_units` xác nhận các bản ghi `cache_hit=True` không làm sai lệch đơn giá trung bình. |
| **3. S2 calendar days = ceil(views/daily limit)** | **PASS** | [`src/koc/report.py:37`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L37)<br>[`src/koc/report.py:130`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L130)<br>[`config/pipeline.yaml:6`](file:///home/lystiger/Projects/KOC-Discovery/config/pipeline.yaml#L6)<br>[`tests/core/test_report_projection.py:41-43`](file:///home/lystiger/Projects/KOC-Discovery/tests/core/test_report_projection.py#L41-L43) | Cấu hình `daily_ui_limit: 10`. Số lượt xem trang creator ở S2 là `s1_count`. Công thức: `math.ceil(s1_count / daily_ui_limit)`. Kết quả khớp tuyệt đối: 50 ứng viên (10 views) = 1 ngày; 200 ứng viên (40 views) = 4 ngày; 500 ứng viên (100 views) = 10 ngày. |
| **4. Vietnamese text labelled ước tính** | **PASS** | [`src/koc/report.py:209`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L209)<br>[`README.md:70`](file:///home/lystiger/Projects/KOC-Discovery/README.md#L70) | Tiêu đề các bảng dự phóng trong tài liệu xuất ra mang nhãn: `Ước tính cho {n} ứng viên; S2 cần {projection['s2_calendar_days']} ngày theo giới hạn giao diện:`. Tài liệu hướng dẫn `README.md` mở đầu mục bằng: `Báo cáo có ước tính cho 50, 200 và 500 ứng viên.`. Các nhãn tiếng Việt nhất quán dùng "ước tính". |
| **5. README paragraph accurate** | **PASS** | [`README.md:70`](file:///home/lystiger/Projects/KOC-Discovery/README.md#L70)<br>[`src/koc/report.py:38-132`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L38-L132)<br>[`src/koc/pipeline.py:141-150`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L141-L150)<br>[`src/koc/kalodata.py:113`](file:///home/lystiger/Projects/KOC-Discovery/src/koc/kalodata.py#L113) | Toàn bộ 5 mệnh đề trong đoạn văn tại dòng 70 của `README.md` khớp 100% với hành vi mã nguồn: (1) ước tính 50, 200, 500 ứng viên; (2) tỷ lệ S1a, S1b, S2 theo mốc 200, cố định video/creator và đề xuất; (3) số liệu tính từ đơn giá không dùng cache đo trực tiếp từ lượt chạy; (4) lượt cache chạy lại có chi phí, token và thời gian bằng 0 (`_cache_hit_usage`); (5) số ngày lịch S2 làm tròn lên theo giới hạn 10 lượt xem/ngày. Các liên kết markdown hợp lệ. |

---

## 2. Kiểm thử thực nghiệm (Test Suite Run)

Chạy kiểm thử cốt lõi hoàn toàn ngoại tuyến:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q tests/core
.................................                                        [100%]
33 passed in 1.21s
```

Không phát hiện hồi quy hay vi phạm hợp đồng dữ liệu.

---

## 3. Kết luận

- Không có lỗi P1 (blocking/fatal) hoặc P2 (major inaccuracy/regression).
- **Kết luận: PASS**.
