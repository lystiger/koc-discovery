# Đánh giá độc lập mô-đun Core

Ngày: 2026-11-15. Người đánh giá: Agy / Gemini 3.8 Flash high; tác giả được giao: Codex / Luna 6 high (khác nhà cung cấp theo thông tin giao việc).

Phạm vi: `src/koc/` (trừ `src/koc/llm/` và `src/koc/web/`), `config/`, `scripts/kill_resume_test.sh`, `tests/core/`; đối chiếu `docs/build/SPEC.md` (C1–C8, C11) và `docs/build/CONTRACTS.md`. Không truy cập mạng, không gọi API thật. Không chỉnh sửa bất kỳ tệp nào ngoài báo cáo này.

**Kết luận chung: FAIL.**
Kiến trúc tổng thể chặt chẽ, các phép tính điểm S1/S2/S4, thuật toán tối ưu hóa ngân sách và hàng rào hạn mức tín dụng Kalodata/Gemini hoạt động tốt. Tuy nhiên, đánh giá kết luận **FAIL** do hai lỗi nghiêm trọng cần khắc phục:
1. Metric đối tượng người xem của S2 (`female_pct`, `age_18_24_pct`, `age_25_34_pct`) bị nuốt hoàn toàn, không bao giờ được ghi vào DB do dùng nhầm cú pháp generator chưa duyệt trong list (`pipeline.py:319, 322`), vi phạm C3.
2. Khi rerun lượt chạy thực tế (có token ban đầu > 0), `_cached_call` giữ nguyên số token của lần gọi trước thay vì đặt về 0 (`pipeline.py:138-142`), vi phạm C6.

---

## Phát hiện theo mức độ nghiêm trọng

### 1. P1 — Metric đối tượng khán giả S2 không bao giờ được lưu vào cơ sở dữ liệu
- **Vị trí**: `src/koc/pipeline.py:319` và `src/koc/pipeline.py:322`
```python
319: write = lambda c: ([(db.upsert_metric(c, creator_id, n, v, source) for n, v in metrics.items())], db.upsert_score(c, run_id, creator_id, "S2", audience_score(metrics), metrics))
322: write = lambda c: ([(db.upsert_metric(c, creator_id, n, v, source) for n, v in metrics.items())], db.upsert_score(c, run_id, creator_id, "S2", audience_score(metrics), metrics))
```
- **Hiện tượng & Bằng chứng**:
  Cú pháp `[(db.upsert_metric(...) for n, v in metrics.items())]` tạo ra một danh sách chứa một đối tượng generator chưa được duyệt: `[<generator object <genexpr> at 0x...>]`.
  Hàm `db.upsert_metric` không bao giờ được thực thi.
  Thực nghiệm chạy pipeline mock: bảng `metrics` chỉ có các metric của S1 (`video_gpm`, `video_vs_live_share`, `revenue_trend_slope`, `follower_band_fit`, `engagement_per_view`, `skincare_revenue_share`), hoàn toàn không có `female_pct`, `age_18_24_pct`, hay `age_25_34_pct`.
- **Hệ quả**:
  - `summary.metrics` và `metric_evidence_ids` trong S4 không có dữ liệu đối tượng, khiến LLM không thể trích dẫn ID bằng chứng khán giả (`metric:<creator_id>:female_pct`), vi phạm C3.
  - Giao diện chi tiết creator (`queries.creator_detail`) không hiển thị được phân tích khán giả.
- **Cách sửa**:
  Chuyển sang hàm ghi tường minh hoặc list comprehension thực:
```python
def make_s2_write(metrics, source):
    def write(c):
        for n, v in metrics.items():
            db.upsert_metric(c, creator_id, n, v, source)
        db.upsert_score(c, run_id, creator_id, "S2", audience_score(metrics), metrics)
    return write
```

### 2. P1 — Cache hit của LLM trong lượt chạy thật không đặt token về 0 (vi phạm C6)
- **Vị trí**: `src/koc/pipeline.py:138-142`
```python
138: if cached:
139:     output, usage_data = cached
140:     usage_data["cache_hit"] = True
141:     usage_data["cost_usd"] = 0.0
142:     usage = Usage.model_validate(usage_data)
143:     db.add_llm_call(conn, run_id, kind, key, usage, True)
```
- **Hiện tượng & Bằng chứng**:
  Khi gặp cache hit trong `_cached_call`, mã nguồn chỉ gán `usage_data["cost_usd"] = 0.0` mà không gán `input_tokens = 0` và `output_tokens = 0`.
  Trong lượt chạy mock, lỗi này bị che khuất vì `_fake_analysis` vốn có token = 0. Nhưng trong lượt chạy live, `usage_data` lưu token thật (ví dụ: 1.500 token vào, 300 token ra). Khi chạy lại (rerun), `db.add_llm_call` chèn số token cũ này vào bảng `llm_calls` của `run_id` mới.
  Probe xác nhận: `SELECT input_tokens, output_tokens, cost_usd FROM llm_calls` ghi nhận 1.500 input tokens và 300 output tokens dù `cache_hit = 1`, làm `queries.run_costs` và `report.benchmark` báo cáo token tiêu thụ > 0 khi rerun, vi phạm SPEC C6 ("Rerun finished run: 0 credits, 0 LLM tokens (cache)").
- **Cách sửa**:
  Đặt rõ ràng `input_tokens = 0`, `output_tokens = 0` (và các token đa phương thức nếu có) khi cache hit:
```python
    if cached:
        output, usage_data = cached
        usage_data["cache_hit"] = True
        usage_data["cost_usd"] = 0.0
        usage_data["input_tokens"] = 0
        usage_data["output_tokens"] = 0
        if "audio_tokens" in usage_data:
            usage_data["audio_tokens"] = 0
        if "image_tokens" in usage_data:
            usage_data["image_tokens"] = 0
        usage = Usage.model_validate(usage_data)
        db.add_llm_call(conn, run_id, kind, key, usage, True)
```

### 3. P2 — Tham chiếu hàm chưa định nghĩa `_audience_tasks` gây crash `NameError`
- **Vị trí**: `src/koc/pipeline.py:269-272`
```python
269: if done("S1b") and "S2" not in states:
270:     if page is not None:
271:         _audience_tasks(conn, run_id, page)
272:     else:
273:         for creator_id in s1_shortlist(conn, run_id, config["s1_limit"]): db.add_task(conn, run_id, "S2", creator_id)
```
- **Hiện tượng & Bằng chứng**:
  Hàm `_audience_tasks` hoàn toàn không tồn tại trong mã nguồn.
  Nếu `execute` được gọi với `page` không phải `None` (ví dụ từ CLI hoặc kịch bản tự động mở sẵn browser page), pipeline văng lỗi ngay lập tức: `NameError: name '_audience_tasks' is not defined`.
- **Cách sửa**:
  Loại bỏ nhánh `_audience_tasks`, tạo task đồng nhất từ `s1_shortlist`:
```python
    if done("S1b") and "S2" not in states:
        for creator_id in s1_shortlist(conn, run_id, config["s1_limit"]):
            db.add_task(conn, run_id, "S2", creator_id)
```

### 4. P2 — Dự phóng chi phí cho 500 ứng viên bị phóng đại sai lệch do nhân tuyến tính phễu
- **Vị trí**: `src/koc/report.py:80-84`
```python
80: candidate_count = stages["S0"]["candidates_in"] or 1
81: projection = {"candidates": 500, "credits": round(total_credits * 500 / candidate_count, 4), "tokens_in": round(total_tokens_in * 500 / candidate_count),
82:               "tokens_out": round(total_tokens_out * 500 / candidate_count), "usd": round(total_usd * 500 / candidate_count, 6)}
```
- **Hiện tượng**:
  Pipeline được thiết kế dạng phễu (funnel): S1b chặn tối đa 60 ứng viên, S2 chặn 40, S3 chặn 15, S4 chọn 5. Khi mở rộng đầu vào lên 500 ứng viên, chỉ có S0 tăng số trang gọi `creator/rank` (5 trang = 0.5 credit) và S1a chạy tính điểm ngoại tuyến tại chỗ. Các giai đoạn tốn credit/token nặng nhất (S1b detail/videos, S3 video download + Gemini content, S4 reasons) giữ nguyên số lượng xử lý (60, 15, 5).
  Việc nhân thẳng `500 / candidate_count` (gấp 25 lần nếu đầu vào là 20 ứng viên) khiến `projection_500` dự báo sai lệch gấp hàng chục lần chi phí token và USD thực tế.
- **Cách sửa**:
  Dự phóng chi phí riêng từng tầng: S0 tăng theo số trang (`ceil(500/100) * 0.1`), các tầng S1b-S4 giữ nguyên giá trị đã đạt trần cấu hình.

### 5. P3 — Thông báo ngoại lệ tiếng Anh tại `src/koc/kalodata.py`
- **Vị trí**: `src/koc/kalodata.py:139, 145, 148`
```python
139: raise RuntimeError(f"Kalodata authentication failed ({status}).")
145: raise RuntimeError(f"Kalodata request failed ({status}).")
148: raise RuntimeError(f"Kalodata request failed ({status}).")
```
- **Hiện tượng**:
  SPEC yêu cầu toàn bộ văn bản người dùng thấy phải bằng tiếng Việt. Khi CLI gặp lỗi xác thực hoặc lỗi mạng từ Kalodata, thông báo hiển thị ra terminal là tiếng Anh.
- **Cách sửa**:
  Đổi sang tiếng Việt tương tự các thông báo lỗi khác:
```python
139: raise RuntimeError(f"Xác thực Kalodata thất bại ({status}).")
145: raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")
148: raise RuntimeError(f"Yêu cầu Kalodata thất bại ({status}).")
```

### 6. P3 — Đường dẫn tuyệt đối hardcoded trong `scripts/kill_resume_test.sh`
- **Vị trí**: `scripts/kill_resume_test.sh:4`
```bash
PYTHON="${PYTHON:-/home/lystiger/Projects/KOC-Discovery/.venv/bin/python}"
```
- **Hiện tượng**:
  Mặc dù cho phép override qua biến môi trường, giá trị fallback chứa đường dẫn tuyệt đối gắn liền với máy cụ thể thay vì dùng đường dẫn tương đối theo thư mục gốc của repository.
- **Cách sửa**:
```bash
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
```

### 7. P3 — Lỗ hổng trong bộ test: Bỏ sót kiểm tra ghi metric S2 và token cache hit
- **Vị trí**: `tests/core/test_d2_pipeline.py`
- **Hiện tượng**:
  Bộ test `test_d2_pipeline.py` chạy qua nhưng không phát hiện ra bug P1 (mất metric S2) vì không assert nội dung bảng `metrics` sau khi chạy, và không phát hiện ra bug P1 (token cache hit) vì fixture mock khởi tạo sẵn token = 0.
- **Cách sửa**:
  Bổ sung vào `test_d2_pipeline.py`:
  1. Kiểm tra sự tồn tại của các bản ghi `female_pct`, `age_18_24_pct` trong bảng `metrics`.
  2. Kiểm tra cache hit với một mock usage có token > 0 và xác nhận lượt chạy sau ghi nhận đúng 0 token.

---

## Phán quyết từng mục kiểm tra

| STT | Mục kiểm tra | Phán quyết | Bằng chứng và phân tích chi tiết |
|:---|:---|:---:|:---|
| 1 | Credit cap refuses before exceeding (C7) | **PASS** | `src/koc/kalodata.py:37–49`: `CreditCounter.reserve` gọi `conn.execute("BEGIN IMMEDIATE")` và kiểm tra `credits_used + credits > self.cap` trước khi ghi nhận call và trước khi gửi request mạng. `BudgetGuard.check` (`budget_guard.py:17–19`) kiểm tra `spent + estimated_usd > cap_usd` trước khi gọi Gemini. Đã xác minh qua `test_credit_counter_refuses_before_transport` và `test_llm_budget_uses_logged_cumulative_cost_and_cache_key`. |
| 2 | Cache keys canonical | **PASS** | `db.py:179–181`: `cache_key` dùng `json.dumps({"endpoint": endpoint, "body": body}, sort_keys=True, separators=(",", ":"))` và băm SHA-256. `budget_guard.py:42–44`: `llm_cache_key` dùng `json.dumps({"media_sha256": ..., "prompt_version": ..., "model": ..., "brief": ...}, sort_keys=True, separators=(",", ":"))`. Đảm bảo tính chuẩn hóa (canonical), không phụ thuộc thứ tự key hay khoảng trắng. |
| 3 | Rerun = 0 credits / 0 tokens (C6) | **FAIL** | Với Kalodata: `kalodata.py:113` ghi nhận `credits = 0` trên cache hit (PASS). Với LLM: `pipeline.py:138–142` chỉ gán `cost_usd = 0.0` mà không reset `input_tokens = 0` và `output_tokens = 0`. Khi chạy lại một lượt chạy live đã hoàn tất, `llm_calls` của lượt mới bị ghi nhận token > 0 từ cache, vi phạm trực tiếp SPEC C6. (Xem Phát hiện 2). |
| 4 | Task checkpoint in same transaction (CONTRACTS §3) | **FAIL** | Về cơ chế: `db.complete_task` (`db.py:70–78`) bọc `write_result(conn)` và `UPDATE tasks SET status='done'` trong cùng khối `BEGIN ... COMMIT` rất chuẩn mực. Tuy nhiên, nội dung `write_result` của giai đoạn S2 (`pipeline.py:319, 322`) chứa lỗi cú pháp logic `[(db.upsert_metric(...) for ...)]` khiến các lệnh ghi metric của task không được thực thi. Task bị đánh dấu hoàn thành trong khi dữ liệu metric bị bỏ rơi. (Xem Phát hiện 1). |
| 5 | Resume correctness (C5) | **PASS** | `pipeline.py:289` gọi `db.reset_running(conn, run_id)` đưa task đang chạy dở về `pending`. Khi có lỗi gián đoạn hoặc bị kill giữa chừng, `resume` tiếp tục xử lý các task chưa xong, không trùng lặp dòng hay gọi lại API tính phí. Script `scripts/kill_resume_test.sh` kiểm tra SIGKILL tại S1b và S3 chạy thành công 100%. (Lưu ý cần sửa lỗi `_audience_tasks` tại phát hiện 3 để tránh lỗi khi truyền `page`). |
| 6 | Creator contact fields never stored (C11) | **PASS** | `kalodata.py:17–23` và `db.py:171–176`: Hàm `strip_contacts` đệ quy loại bỏ tất cả các khóa bắt đầu bằng `creator_contact_` hoặc nằm trong danh mục cấm trước khi lưu vào `http_cache` và `creators`. Được kiểm chứng chặt chẽ bởi `test_strip_contacts_recurses` và `test_schema_tables_and_upserts_are_idempotent`. |
| 7 | S1a/S1b scoring math vs SPEC weights | **PASS** | `config/scoring.yaml` và `stages.py:24–64`: Trọng số chuẩn xác tuyệt đối (video_gpm 35, skincare 25, trend slope 15, video_vs_live 15, follower_band 10; tổng 100). Chuẩn hóa GPM theo mốc 100k, trend slope theo OLS chuẩn hóa. `s1_shortlist` dùng engagement per view từ `video/rank` làm tie-break đúng SPEC. `score_creator_rank` tính S1a rẻ từ bảng rank. Đã kiểm chứng qua `test_s1_score_uses_fixture_creator_values`. |
| 8 | S4 optimizer correctness (best 5/15 under 30M, MCN rule) | **PASS** | `pipeline.py:208–226`: Lấy 15 ứng viên từ S2, tính giá theo rate card (3 video/KOC), tính điểm tổng hợp (.45 S1 + .20 S2 + .35 S3). Duyệt tổ hợp 5 người, lọc cứng `total <= 30_000_000` và `len(mcn) == len(set(mcn))` (loại trừ KOC cùng MCN đã biết), chọn tổ hợp có tổng điểm cao nhất và sắp xếp giảm dần theo điểm. Đã kiểm chứng qua probe độc lập và `test_mock_run_is_resumable_cached_and_writes_five_recommendations`. |
| 9 | Audience capture pacing >=5 s and stop on limit text | **PASS** | `pipeline.py:89–100`: Hàm `capture_audience` tính thời gian trôi qua từ lần tải trước và gọi `sleep(5 - elapsed)` nếu dưới 5s, kèm `wait_for_timeout(5000)`. Khi gặp chuỗi giới hạn tài khoản dùng thử/truy cập, ném `PermissionError`. Vòng lặp `execute` bắt lỗi này, đánh dấu task hiện tại và toàn bộ task S2 còn lại là `blocked: giới hạn truy cập`, kết thúc lượt chạy với trạng thái `blocked`. Đã kiểm chứng qua `test_supervised_capture_waits_and_rejects_access_limit`. |
| 10 | Spearman calc | **PASS** | `report.py:5–25`: `spearman` triển khai thuật toán xếp hạng fractional ranking cho các giá trị trùng lặp (ties) và tính tương quan Pearson trên thứ hạng. Trả về `None` khi mẫu < 2 hoặc phương sai bằng 0 (tránh `ZeroDivisionError`). Đã kiểm chứng qua probe với vector cùng chiều (1.0), ngược chiều (-1.0), ties (0.948683) và vector bất biến (`None`). |
| 11 | Dry-run truly offline (C2) | **PASS** | `cli.py:30–44`: Khi có cờ `--dry-run`, hàm tính toán lý thuyết và in kế hoạch dự kiến số credit/token rồi `return` ngay. Hoàn toàn không khởi tạo SQLite (`db.connect`), không tạo file, không gọi socket/mạng. Được kiểm chứng bởi `test_dry_run_does_not_open_database_or_network` (chặn socket connect). |
| 12 | Vietnamese user-facing text | **PASS** | Toàn bộ thông điệp CLI, tài liệu chuẩn đo (`docs/BENCHMARK.md`), báo cáo benchmark, nhãn bảng giá (`rate_card.yaml`) đều bằng tiếng Việt đúng chuẩn SPEC. (Có 3 chuỗi ngoại lệ Kalodata cần việt hóa như đã nêu ở P3). |
| 13 | Tests meaningful | **PASS** | 19 bài kiểm tra trong `tests/core/` đều kiểm tra hành vi thật: kiểm tra tính nguyên vẹn của schema DB, giả lập crash process thật bằng `subprocess` và `os._exit`, kiểm tra rollback transaction, kiểm tra retry 503/500 có backoff, kiểm tra trừ credit và tie-break. Không phải mock rỗng. Tuy nhiên còn 2 lỗ hổng kiểm thử đã nêu ở Phát hiện 7. |

---

## Thực nghiệm offline

### 1. Kiểm thử đơn vị theo yêu cầu
```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/core
...................                                                      [100%]
19 passed in 1.05s
```

### 2. Kiểm thử ngắt đột ngột (SIGKILL) và khôi phục
```bash
bash scripts/kill_resume_test.sh
```
Kết quả:
```text
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã tiếp tục lượt chạy 1099734cf8f84df3ada856dcf881e9cf.
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã hoàn tất lượt chạy fa80edb2aa5e4a0b855167b1a5d54b7e.
Đã tiếp tục lượt chạy fa80edb2aa5e4a0b855167b1a5d54b7e.
SIGKILL + resume: S1b PASS
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã tiếp tục lượt chạy a426ac5ac09c4dd591926d12b422edd7.
Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa 'kem chống nắng' cho creator/rank.
Đã hoàn tất lượt chạy 0acb5e6bcbd8459784e88399723dc4d3.
Đã tiếp tục lượt chạy 0acb5e6bcbd8459784e88399723dc4d3.
SIGKILL + resume: S3 PASS
```

### 3. Probe kiểm tra lỗi mất metric S2 (Phát hiện 1)
```python
from koc import db
from koc.pipeline import start
conn = db.connect(':memory:')
db.init_db(conn)
start(conn, limit=5, mock=True)
s2_metrics = conn.execute("SELECT name, value FROM metrics WHERE name IN ('female_pct', 'age_18_24_pct', 'age_25_34_pct')").fetchall()
all_metrics = conn.execute("SELECT DISTINCT name FROM metrics").fetchall()
print('S2 metrics:', s2_metrics)
print('All metrics:', [r[0] for r in all_metrics])
```
Kết quả:
```text
S2 metrics: []
All metrics: ['engagement_per_view', 'follower_band_fit', 'revenue_trend_slope', 'skincare_revenue_share', 'video_gpm', 'video_vs_live_share']
```
*Kết luận: Toàn bộ metric của S2 không được ghi vào DB.*

### 4. Probe kiểm tra tồn đọng token trên cache hit (Phát hiện 2)
```python
from koc import db
from koc.pipeline import _cached_call
from koc.types import BrandBrief, ContentAnalysis, RubricScore, Usage
from koc.budget_guard import put_cached, llm_cache_key

conn = db.connect(':memory:')
db.init_db(conn)

brief = BrandBrief(product_vi='kem chống nắng', audience_vi='Nữ', budget_vnd=30000000)
key = llm_cache_key('media-hash-x', 'content_v1', 'gemini-3.8-flash', brief.model_dump())
usage = Usage(provider='gemini', model='gemini-3.8-flash', prompt_version='content_v1',
              input_tokens=1500, output_tokens=300, latency_ms=500, cost_usd=0.00225, cache_hit=False)
rubric = [RubricScore(criterion=n, score=3, rationale_vi='ok', evidence_ids=[])
          for n in ('hook', 'product_clarity', 'demonstration', 'claim_quality', 'cta', 'brand_fit', 'production_quality')]
analysis = ContentAnalysis(video_id='v1', transcript_vi=None, rubric=rubric, risks_vi=[], evidence=[], usage=usage)
put_cached(conn, key, analysis.model_dump(mode='json'), usage.model_dump(mode='json'))

_cached_call(conn, 'run-1', 'content', 'media-hash-x', 'content_v1', 'gemini-3.8-flash', brief, lambda *a, **kw: None)

row = conn.execute('SELECT input_tokens, output_tokens, cost_usd, cache_hit FROM llm_calls WHERE run_id="run-1"').fetchone()
print(dict(row))
```
Kết quả:
```text
{'input_tokens': 1500, 'output_tokens': 300, 'cost_usd': 0.0, 'cache_hit': 1}
```
*Kết luận: Token không được reset về 0 trên cache hit khi rerun.*

### 5. Probe kiểm tra `_audience_tasks` NameError (Phát hiện 3)
```python
from koc import db
from koc.pipeline import _advance
conn = db.connect(':memory:')
db.init_db(conn)
conn.execute("INSERT INTO tasks VALUES ('r1:S1b:c1', 'r1', 'S1b', 'c1', 'done', 0, NULL, '2026-01-01')")
_advance(conn, 'r1', None, 50, page=object(), mock=False, media_dir=None)
```
Kết quả:
```text
NameError: name '_audience_tasks' is not defined
```
*Kết luận: Gọi `_advance` khi `page is not None` lập tức gây crash.*

### 6. Probe kiểm tra tính đúng của bộ tối ưu hóa S4 (Mục 8)
Kiểm tra với 15 ứng viên có chi phí khác nhau và ràng buộc MCN (2 ứng viên MCN_A, 2 ứng viên MCN_B):
Kết quả: Chọn chính xác 5 ứng viên, tổng chi phí 24.000.000 VND (<= 30.000.000 VND), mỗi MCN chỉ chọn đúng 1 ứng viên có điểm cao nhất.
