# Yêu Cầu Thay Đổi Hợp Đồng Truy Vấn (CHANGE_REQUEST_web.md)

**Người gửi**: UI Builder (Agy)  
**Khu vực**: `src/koc/queries.py` (thuộc sở hữu Core / Codex)  
**Ngày**: 2026-11-15  
**Trạng thái**: Đề xuất (Trong lúc chờ phê duyệt, Web UI dùng adapter đọc nội bộ tại `src/koc/web/adapter.py`)

---

## 1. Lý do & Bối cảnh

Giao diện người dùng KOC Discovery MVP theo `SPEC.md` (Criteron C9) yêu cầu hiển thị 3 màn hình nghiệp vụ:
1. Danh sách đề xuất Top 5 (`/runs/{run_id}`): Cần `handle`, `followers`, điểm tổng và 3 thành phần điểm (`thương mại`, `khán giả`, `nội dung`), tổng ngân sách so với 30.000.000 ₫, lý do tóm tắt.
2. Chi tiết KOC (`/runs/{run_id}/creators/{creator_id}`): Cần bảng metrics kèm evidence ID, cơ cấu khán giả nữ & độ tuổi, dữ liệu 3 video kèm phân tích (thumbnails frame, timestamp, transcript quote, 7 tiêu chí rubric kèm rationale, rủi ro), lý do + lưu ý có anchor link tới evidence.
3. Bảng điều khiển (`/runs/{run_id}/dashboard`): Cần phễu ứng viên qua các stage (S0 -> S1 -> S2 -> S3 -> S4), trạng thái tasks, tín dụng Kalodata vs hạn mức 100, LLM tokens/USD vs hạn mức $5, thời gian từng stage, tỉ lệ cache hit, hệ số tương quan Spearman.

Hiện tại `src/koc/queries.py` chỉ có:
- `list_runs(conn)`
- `get_run(conn, run_id)`
- `top5(conn, run_id)` (chỉ đọc bảng `recommendations`, thiếu `handle`, `followers`, điểm breakdown từ `scores` và `creators`)
- `creator_detail(conn, run_id, creator_id)` (chỉ đọc `creators`, `metrics`, `scores`; thiếu `videos`, `analyses`, `recommendations`)
- `run_costs(conn, run_id)` (chỉ tính tổng credits, latency, tokens, cost; thiếu phễu, tasks, cache hits, thời gian stage, calibration Spearman).

---

## 2. Đề xuất hàm bổ sung vào `src/koc/queries.py`

### 2.1. Nâng cấp hoặc bổ sung `get_top5_cards(conn, run_id: str)`
Truy vấn bảng `recommendations` kết hợp `creators` và `scores` để trả về đầy đủ:
- `rank`, `creator_id`, `handle`, `followers` (từ `creators.data_json`)
- `est_cost_vnd`
- Điểm số: `final_score`, `commercial_score`, `audience_score`, `content_score`
- `reasons_vi`, `caveats_vi`, `cited_evidence_ids`

### 2.2. Nâng cấp hoặc bổ sung `get_creator_full_detail(conn, run_id: str, creator_id: str)`
Bổ sung vào kết quả của `creator_detail`:
- `recommendation`: bản ghi từ bảng `recommendations` cho KOC này trong `run_id`.
- `videos`: danh sách các video của creator (từ bảng `videos`) kèm bản ghi phân tích từ bảng `analyses` (`analysis_json`: transcript, rubric 7 tiêu chí, risks, evidence list kèm frame_path và timestamp).

### 2.3. Bổ sung `get_run_dashboard(conn, run_id: str)`
Tính toán tổng hợp cho dashboard:
- `funnel`: số lượng ứng viên qua từng stage (S0 candidates, S1 scored, S2 audience, S3 content analyzed, S4 finalists).
- `tasks`: đếm số task theo từng stage và status (`pending`, `running`, `done`, `failed`).
- `costs`: credits sử dụng vs cap (100), LLM tokens in/out, USD vs cap ($5.0).
- `cache`: số cuộc gọi API/LLM và số lần cache hit (`cache_hit=1`).
- `stage_timings`: thời gian bắt đầu, kết thúc hoặc thời lượng ước tính từng stage dựa trên `tasks.updated_at` hoặc log `api_calls`/`llm_calls`.
- `calibration`: Spearman correlation giữa điểm nội dung vs lượt xem/followers và video GPM (lưu trong `scores` breakdown hoặc `runs.params_json`).

---

## 3. Giải pháp tạm thời của Web UI

Theo chỉ dẫn hợp đồng, trong thời gian `src/koc/queries.py` chưa cập nhật, `src/koc/web/adapter.py` sẽ thực hiện các câu truy vấn `SELECT` read-only trực tiếp trên các bảng chuẩn hợp đồng (§3 tables) để đảm bảo không làm gián đoạn tiến độ D2.

## Orchestrator required fix (2026-11-15)
- tests/web/fixtures/seed.py seeds `run_prod_skincare_02` with `"mock": false`: invented data shown without the mock banner. Every seeded run must be `"mock": true`, and run ids must not say "prod". Add a test asserting all fixture runs render the GIẢ LẬP banner.
