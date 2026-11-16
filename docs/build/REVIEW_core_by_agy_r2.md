# Đánh giá độc lập mô-đun Core (Đợt 2)

Ngày: 2026-11-15. Người đánh giá: Agy / Gemini 3.8 Flash; tác giả được giao: Codex / Luna 6.

Phạm vi thẩm tra: `src/koc/` (trừ `src/koc/llm/` và `src/koc/web/`), `config/`, `scripts/`, `tests/core/`; đối chiếu `docs/build/SPEC.md`, `docs/build/CONTRACTS.md` (bao gồm Amendment A1), `docs/build/REVIEW_core_by_agy.md` (Đợt 1 - FAIL) và `docs/build/EVIDENCE_core_fix1.md`.
Môi trường: Hoàn toàn ngoại tuyến (no network), không gọi API thật.

**Kết luận chung: PASS.**
Tất cả 7 phát hiện khiếm khuyết từ đợt 1 (gồm 2 P1, 2 P2, 3 P3) đã được tác giả Codex khắc phục triệt để và bổ sung bài kiểm thử hồi quy đầy đủ. Thẩm tra thực nghiệm xác nhận:
1. Metric khán giả S2 (`female_pct`, `age_18_24_pct`, `age_25_34_pct`) được ghi nhận chuẩn xác vào bảng `metrics` trong cả luồng mock lẫn luồng browser.
2. Token LLM và chi phí USD trên cache hit được đưa về 0 tuyệt đối cho cả token văn bản và token đa phương thức (audio/image), thỏa mãn điều kiện rerun của C6.
3. Lỗi `NameError` của `_audience_tasks` đã bị loại bỏ; luồng phân trang hoạt động thống nhất.
4. Dự phóng chi phí 500 ứng viên phân tách tầng chính xác (chỉ nhân S0, giữ nguyên trần phễu hạ nguồn).
5. Thông báo ngoại lệ Kalodata đã được việt hóa hoàn toàn.
6. Đường dẫn Python trong kịch bản kiểm tra ngắt/khôi phục đã dùng đường dẫn tương đối an toàn.
7. Tham số `frames_dir` theo Amendment A1 đã được truyền đúng vào `llm.analyze_video` và đã kiểm chứng tương thích 100% với chữ ký thực tế của mô-đun LLM (đã merge tại `e9e5d0c`).
8. Toàn bộ 88 bài test của repository (`PYTHONPATH=src .venv/bin/python -m pytest -q tests`) và kịch bản `scripts/kill_resume_test.sh` đều PASS hoàn hảo.
Không còn bất kỳ lỗi P1 hay P2 nào mở.

---

## 1. Thẩm tra 7 phát hiện từ đợt 1

### P1-1: Metric đối tượng khán giả S2 không bao giờ được lưu vào cơ sở dữ liệu
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L106-L111) và [pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L331-L338)
- **Mã nguồn đã sửa**:
  ```python
  def _s2_write(run_id, creator_id, metrics, source):
      def write(c):
          for name, value in metrics.items():
              db.upsert_metric(c, creator_id, name, value, source)
          db.upsert_score(c, run_id, creator_id, "S2", audience_score(metrics), metrics)
      return write
  ```
  Tại `execute` (dòng 335 và 338), cả hai nhánh `mock` và `page` đều gọi `write = _s2_write(run_id, creator_id, metrics, source)`.
- **Bằng chứng & Thực nghiệm probe**:
  Chạy lượt chạy mock 5 creator:
  ```python
  from koc import db; from koc.pipeline import start
  conn = db.connect(':memory:'); db.init_db(conn)
  start(conn, limit=5, mock=True)
  rows = conn.execute("SELECT creator_id, name, value FROM metrics WHERE name IN ('female_pct', 'age_18_24_pct', 'age_25_34_pct')").fetchall()
  ```
  Kết quả trả về: 15 bản ghi (3 metric × 5 creator). Bảng `metrics` lưu đầy đủ `female_pct=70.0`, `age_18_24_pct=30.0`, `age_25_34_pct=40.0`. Hàm `queries.creator_detail` hiển thị đầy đủ thông tin khán giả.
  Bài kiểm tra hồi quy `test_mock_run_writes_s2_metrics` và `test_page_path_creates_audience_tasks_and_writes_metrics` đều PASS.

---

### P1-2: Cache hit của LLM trong lượt chạy thật không đặt token về 0
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L141-L150), [pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L159), [pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L178)
- **Mã nguồn đã sửa**:
  ```python
  def _cache_hit_usage(usage_data):
      usage_data["cache_hit"] = True
      usage_data["cost_usd"] = 0.0
      usage_data["input_tokens"] = 0
      usage_data["output_tokens"] = 0
      if "audio_tokens" in usage_data:
          usage_data["audio_tokens"] = 0
      if "image_tokens" in usage_data:
          usage_data["image_tokens"] = 0
      return usage_data
  ```
  Hàm được áp dụng trong cả `_cached_call` (luồng thật) và `_mock_cached` (luồng mock).
- **Bằng chứng & Thực nghiệm probe**:
  Khởi tạo cache có sẵn `input_tokens=1500`, `output_tokens=300`, `audio_tokens=100`, `image_tokens=5`, `cost_usd=0.00225`. Thực hiện `_cached_call`:
  ```python
  res = _cached_call(conn, 'run-1', 'content', 'media-hash-x', 'content_v1', 'gemini-3.8-flash', brief, lambda *a, **kw: None)
  row = conn.execute('SELECT input_tokens, output_tokens, cost_usd, cache_hit FROM llm_calls WHERE run_id="run-1"').fetchone()
  ```
  Kết quả bản ghi DB: `{'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0, 'cache_hit': 1}`.
  Kết quả object trả về: `res.usage.input_tokens == 0`, `res.usage.output_tokens == 0`, `res.usage.audio_tokens == 0`, `res.usage.image_tokens == 0`, `res.usage.cost_usd == 0.0`.
  Kiểm tra thêm qua `queries.run_costs`: Lượt chạy lại đạt đúng 0 credits, 0 LLM tokens, 0.0 USD, tuân thủ hoàn toàn SPEC C6.
  Bài kiểm tra hồi quy `test_cached_llm_call_logs_zero_tokens_and_cost` PASS.

---

### P2-3: Tham chiếu hàm chưa định nghĩa `_audience_tasks` gây crash `NameError`
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L286-L288)
- **Mã nguồn đã sửa**:
  Đoạn rẽ nhánh lỗi `if page is not None: _audience_tasks(...)` đã bị xóa bỏ hoàn toàn. Việc tạo tác vụ S2 được đồng nhất:
  ```python
  if done("S1b") and "S2" not in states:
      for creator_id in s1_shortlist(conn, run_id, config["s1_limit"]):
          db.add_task(conn, run_id, "S2", creator_id)
  ```
- **Bằng chứng & Thực nghiệm probe**:
  Gọi `_advance(conn, 'r1', None, 50, page=object(), mock=False, media_dir=None)`: hàm thực thi thành công, tạo tác vụ `S2` ở trạng thái `pending` mà không xảy ra `NameError`.
  Bài kiểm tra hồi quy `test_page_path_creates_audience_tasks_and_writes_metrics` PASS.

---

### P2-4: Dự phóng chi phí cho 500 ứng viên bị phóng đại sai lệch do nhân tuyến tính phễu
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [report.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/report.py#L82-L86)
- **Mã nguồn đã sửa**:
  ```python
  rank_price = load_config()["kalodata_prices"]["creator_rank_per_100_rows"]
  projected_s0_credits = math.ceil(500 / 100) * rank_price
  projection = {"candidates": 500, "credits": round(total_credits - stages["S0"]["credits"] + projected_s0_credits, 4),
                "tokens_in": total_tokens_in, "tokens_out": total_tokens_out, "usd": round(total_usd, 6)}
  ```
- **Bằng chứng & Thực nghiệm probe**:
  Thử nghiệm với lượt chạy có chi phí S0 = 0.1 credit, S1b = 0.2 credit, S3/S4 = 1,100 tokens vào, 250 tokens ra, 0.012 USD:
  `projection_500` cho kết quả: `credits = 0.7` (0.5 credit cho 5 trang S0 + 0.2 credit downstream), `tokens_in = 1100`, `tokens_out = 250`, `usd = 0.012`. Phễu downstream không còn bị nhân phóng đại 25 lần như trước.
  Bài kiểm tra hồi quy `test_projection_500_keeps_funnel_costs_and_scales_s0_pages` PASS.

---

### P3-5: Thông báo ngoại lệ tiếng Anh tại `src/koc/kalodata.py`
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [kalodata.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/kalodata.py#L139), [kalodata.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/kalodata.py#L145), [kalodata.py](file:///home/lystiger/Projects/KOC-Discovery/src/koc/kalodata.py#L148)
- **Mã nguồn đã sửa**:
  - Dòng 139: `raise RuntimeError(f"Xác thực Kalodata thất bại ({status}).")`
  - Dòng 145: `raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")`
  - Dòng 148: `raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")`
- **Bằng chứng & Thực nghiệm probe**:
  Probe kiểm tra với các mã lỗi HTTP 401, 400, 500 xác nhận chuỗi thông báo chính xác bằng tiếng Việt.
  Bài kiểm tra tham số `test_request_errors_are_in_vietnamese` trong `test_kalodata.py` (3 test cases) PASS 100%.

---

### P3-6: Đường dẫn tuyệt đối hardcoded trong `scripts/kill_resume_test.sh`
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [kill_resume_test.sh](file:///home/lystiger/Projects/KOC-Discovery/scripts/kill_resume_test.sh#L4-L5)
- **Mã nguồn đã sửa**:
  ```bash
  ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
  ```
- **Bằng chứng & Thực nghiệm probe**:
  Kiểm tra cú pháp `bash -n scripts/kill_resume_test.sh` đạt PASS. Chạy script trực tiếp bằng `bash scripts/kill_resume_test.sh` tự động nhận diện đúng môi trường `.venv` của repository, kiểm tra SIGKILL tại S1b và S3 đều PASS.

---

### P3-7: Lỗ hổng trong bộ test: Bỏ sót kiểm tra ghi metric S2 và token cache hit
- **Trạng thái**: **PASS (Đã sửa)**
- **Vị trí sửa**: [test_d2_pipeline.py](file:///home/lystiger/Projects/KOC-Discovery/tests/core/test_d2_pipeline.py#L87-L191) và [test_kalodata.py](file:///home/lystiger/Projects/KOC-Discovery/tests/core/test_kalodata.py#L55-L66)
- **Mô tả bổ sung**:
  Bổ sung 5 bài test đơn vị kiểm tra trực diện các lỗi đã bắt:
  1. `test_mock_run_writes_s2_metrics`: kiểm tra sự tồn tại của 3 metric khán giả sau lượt chạy.
  2. `test_page_path_creates_audience_tasks_and_writes_metrics`: kiểm tra tạo task S2 khi truyền page và assert dữ liệu metric.
  3. `test_cached_llm_call_logs_zero_tokens_and_cost`: kiểm tra cache hit với token ban đầu > 0, xác nhận ghi 0 token vào DB.
  4. `test_s3_passes_frames_directory_to_llm`: kiểm tra core truyền `frames_dir` cho S3.
  5. `test_projection_500_keeps_funnel_costs_and_scales_s0_pages`: kiểm tra toán học dự phóng 500 ứng viên.
  6. `test_request_errors_are_in_vietnamese`: kiểm tra thông báo tiếng Việt khi lỗi mạng Kalodata.
- **Bằng chứng**: Chạy riêng 8 test case mới qua pytest đều PASS; số lượng test của `tests/core/` tăng từ 19 lên 27 bài.

---

## 2. Thẩm tra Amendment A1 & Tương thích với chữ ký thực của mô-đun LLM

### Kiểm tra Core truyền `frames_dir`
Tại [pipeline.py:206](file:///home/lystiger/Projects/KOC-Discovery/src/koc/pipeline.py#L206):
```python
analysis = _mock_cached(conn, run_id, "content", llm_cache_key(media_hash, "content_v1", "mock", brief.model_dump()), lambda: _fake_analysis(item), ContentAnalysis) if mock else _cached_call(conn, run_id, "content", media_hash, "content_v1", load_config()["llm_caps"].get("model", "gemini-3.8-flash"), brief, llm.analyze_video, item, brief, frames_dir="data/media/frames")
```
Khi gọi hàm qua `_cached_call`, `frames_dir="data/media/frames"` được truyền dạng keyword argument vào `function` (`llm.analyze_video`).

### Đối chiếu với chữ ký thực tế của `src/koc/llm/content.py`
Mô-đun LLM đã hoàn tất sửa đổi và merge vào nhánh chính tại commit `e9e5d0c`. Chữ ký thực tế tại [content.py:121-129](file:///home/lystiger/Projects/KOC-Discovery/src/koc/llm/content.py#L121-L129):
```python
def analyze_video(
    video: VideoInput,
    brief: BrandBrief,
    *,
    budget_guard: BudgetGuard,
    client: GeminiClient | None = None,
    frames_dir: str | None = None,
    preprocess_dir: str | None = None,
) -> ContentAnalysis:
```
Chữ ký của `write_reasons` tại [reasons.py:78-82](file:///home/lystiger/Projects/KOC-Discovery/src/koc/llm/reasons.py#L78-L82):
```python
def write_reasons(
    c: CandidateSummary,
    brief: BrandBrief,
    *,
    budget_guard: BudgetGuard,
    client: GeminiClient | None = None,
) -> Recommendation:
```

### Thử nghiệm tích hợp Runtime (End-to-End Core ↔ Real LLM Signature)
Thực hiện chạy thực nghiệm gọi `_s3_creator` và `_s4` với `mock=False` sử dụng trực tiếp hàm `llm.analyze_video` và `llm.write_reasons` thật (giả lập tầng SDK Gemini để giữ môi trường không mạng):
1. `_s3_creator` truyền `frames_dir="data/media/frames"` thành công. `analyze_video` tạo thư mục `data/media/frames/v1/`, trích xuất frame, gán đường dẫn frame cục bộ vào `Evidence.frame_path` theo Amendment A1.
2. `BudgetGuard.record` và `db.update_llm_request_hash` phối hợp chính xác: ghi nhận chi phí vào bảng `llm_calls` với đúng `request_hash`, không bị trùng lặp dòng.
3. `_s4` gọi `llm.write_reasons` với `CandidateSummary` có đầy đủ ID bằng chứng metric (`metric:c1:female_pct`, v.v.), nhận kết quả `Recommendation` và lưu bảng `recommendations` thành công.

---

## 3. Rà soát lỗi mới toàn diện (Sweep for new defects)

Đã quét toàn bộ mã nguồn thuộc phạm vi:
- `src/koc/`: `db.py`, `budget_guard.py`, `kalodata.py`, `pipeline.py`, `queries.py`, `report.py`, `stages.py`, `types.py`, `config.py`, `cli.py`
- `config/`: `scoring.yaml`, `kalodata_prices.yaml`, `llm_caps.yaml`, `llm_prices.yaml`, `pipeline.yaml`, `rate_card.yaml`
- `scripts/`: `kill_resume_test.sh`, `api_probe.py`, `capture_creator.py`
- `tests/core/`: 7 tệp kiểm thử

### Kết quả rà soát:
1. **Quản lý Transaction & Concurrency**:
   - `CreditCounter.reserve` dùng `BEGIN IMMEDIATE` ngăn chặn race condition khi gọi Kalodata API.
   - `complete_task` bọc thao tác ghi kết quả và cập nhật trạng thái tác vụ trong cùng transaction SQLite, đảm bảo tính nguyên tố (atomicity).
   - `reset_running` đưa task dở dang về `pending` khi tiến trình bị ngắt đột ngột.
2. **Bảo mật & Quyền riêng tư (C11)**:
   - Hàm `strip_contacts` loại bỏ đệ quy các trường liên hệ nhạy cảm (`creator_contact_*`, zalo, email, v.v.) trước khi ghi vào `http_cache` và bảng `creators`.
3. **Toán học tính điểm & Tối ưu hóa**:
   - Trọng số S1 (35/25/15/15/10), S2, S3, S4 (45/20/35) khớp chuẩn xác với SPEC.
   - Thuật toán `_best_five` kiểm tra tổ hợp 5 ứng viên, chặn ngân sách <= 30 triệu VND và chặn trùng MCN (`len(mcn) == len(set(mcn))`) chuẩn xác.
4. **Không phát hiện lỗi mới cấp P1/P2/P3**:
   Toàn bộ mã nguồn đạt chuẩn kiến trúc, không có tham chiếu biến lỗi thời, không có rò rỉ kết nối hay sai khác hợp đồng.

---

## 4. Bảng tổng hợp phán quyết từng mục kiểm tra

| STT | Mục kiểm tra | Phán quyết | Bằng chứng & Phân tích chi tiết |
|:---|:---|:---:|:---|
| 1 | P1-1: Ghi metric khán giả S2 (C3) | **PASS** | `pipeline.py:106-111, 335, 338`: Dùng `_s2_write` lặp tường minh; ghi đầy đủ `female_pct`, `age_18_24_pct`, `age_25_34_pct` vào bảng `metrics`. |
| 2 | P1-2: Rerun = 0 credits / 0 LLM tokens (C6) | **PASS** | `pipeline.py:141-150`: `_cache_hit_usage` reset toàn bộ token (text, audio, image) và cost về 0; DB và object trả về đều ghi nhận 0 token, 0.0 USD. |
| 3 | P2-3: Khắc phục NameError `_audience_tasks` | **PASS** | `pipeline.py:286-288`: Đã loại bỏ hoàn toàn `_audience_tasks`; tạo task S2 đồng nhất từ `s1_shortlist` cho cả khi có hoặc không có page. |
| 4 | P2-4: Toán học dự phóng chi phí 500 ứng viên | **PASS** | `report.py:82-86`: Tách riêng S0 (5 trang × 0.1) và giữ nguyên trần phễu downstream; không còn nhân tuyến tính sai lệch. |
| 5 | P3-5: Thông báo ngoại lệ tiếng Việt | **PASS** | `kalodata.py:139, 145, 148`: Đã việt hóa toàn bộ thông báo lỗi xác thực và lỗi yêu cầu Kalodata. |
| 6 | P3-6: Đường dẫn Python trong kịch bản resume | **PASS** | `scripts/kill_resume_test.sh:4-5`: Sử dụng `$ROOT/.venv/bin/python` tương đối thay cho đường dẫn tuyệt đối máy cá nhân. |
| 7 | P3-7: Bộ test bổ sung ca kiểm thử hồi quy | **PASS** | `tests/core/test_d2_pipeline.py` & `test_kalodata.py`: Bổ sung 6 bài kiểm tra hồi quy trực diện, nâng tổng số test core lên 27 bài. |
| 8 | Amendment A1 & LLM signature integration | **PASS** | `pipeline.py:206` truyền `frames_dir="data/media/frames"`; tương thích 100% với signature thực tế của `llm.analyze_video` và `llm.write_reasons`. |
| 9 | Hạn mức tín dụng Kalodata & Gemini (C7) | **PASS** | `CreditCounter.reserve` chặn trước khi gọi mạng; `BudgetGuard.check` chặn trước khi gọi LLM. |
| 10 | Cache keys canonical | **PASS** | `db.cache_key` và `budget_guard.llm_cache_key` băm SHA-256 từ chuỗi JSON chuẩn hóa `sort_keys=True, separators=(',', ':')`. |
| 11 | Checkpoint tác vụ trong cùng transaction | **PASS** | `db.complete_task` bọc ghi kết quả và đánh dấu task 'done' trong một khối transaction nguyên tử. |
| 12 | Khả năng khôi phục sau crash (C5) | **PASS** | `scripts/kill_resume_test.sh` kiểm tra SIGKILL tại S1b và S3 đều khôi phục hoàn hảo mà không gọi lại API tốn phí. |
| 13 | Không lưu trường liên hệ KOC (C11) | **PASS** | `kalodata.strip_contacts` loại bỏ đệ quy tất cả khóa liên hệ trước khi ghi cache hoặc DB. |
| 14 | Toán học tính điểm S1/S2/S4 & Bộ tối ưu ngân sách | **PASS** | Trọng số chuẩn xác; bộ tối ưu chọn đúng 5 KOC điểm cao nhất dưới 30 triệu VND và không trùng MCN. |
| 15 | Dry-run hoàn toàn ngoại tuyến (C2) | **PASS** | `cli.py:31-44`: Cờ `--dry-run` in kế hoạch và thoát ngay, không mở DB hay socket mạng. |
| 16 | Toàn bộ văn bản giao diện bằng tiếng Việt | **PASS** | CLI, nhãn rate card, thông báo lỗi Kalodata và báo cáo benchmark hoàn toàn bằng tiếng Việt. |

---

## 5. Bằng chứng thực nghiệm thực tế

### 1. Kiểm thử toàn bộ bộ test
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 8.43s
```
Trong đó riêng `tests/core/` đạt 27/27 passed.

### 2. Kiểm thử ngắt tiến trình (SIGKILL) và khôi phục
```bash
bash scripts/kill_resume_test.sh
```
Kết quả ghi nhận:
```text
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã tiếp tục lượt chạy e348668510be42d0bf170bc120e47fa3.
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã hoàn tất lượt chạy b423ed47975d449389291b00738c5812.
Đã tiếp tục lượt chạy b423ed47975d449389291b00738c5812.
SIGKILL + resume: S1b PASS
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã tiếp tục lượt chạy 68ca9200ec3a4a75a24d5636cabb6f9f.
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã hoàn tất lượt chạy f0a6e3220d7847d28904d0d5aa080ecb.
Đã tiếp tục lượt chạy f0a6e3220d7847d28904d0d5aa080ecb.
SIGKILL + resume: S3 PASS
```

---

## 6. Kết luận

Mô-đun Core sau đợt sửa thứ nhất (Fix 1) đã khắc phục toàn diện mọi thiếu sót, đạt chất lượng kỹ thuật cao, đáp ứng đầy đủ các ràng buộc kiến trúc của `SPEC.md` và `CONTRACTS.md` (bao gồm Amendment A1).

**Phán quyết cuối cùng: PASS.**
