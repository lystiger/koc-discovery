# Báo Cáo Bằng Chứng Sửa Lỗi Mô-đun LLM (Fix 1)

Ngày: 2026-11-15  
Tác giả: Agy (Gemini 3.8 Flash high)  
Nhánh: `feat/koc-llm2`  
Worktree: `/home/lystiger/Projects/KOC-Discovery-llm2`  
Căn cứ: `docs/build/REVIEW_llm_by_codex.md` (8 phát hiện) và `docs/build/CONTRACTS.md` (Tu chính A1).

---

## 1. Bảng Đối Chiếu 8 Phát Hiện & Tu Chính A1 Sang Commit Và Kiểm Thử

| Mục | Mức độ | Tóm tắt lỗi | Giải pháp khắc phục | Commit | Kiểm thử chứng minh |
|---|---|---|---|---|---|
| **P1 — Phát hiện 1** | P1 | Ước lượng không chặn chi phí; thiếu `max_output_tokens`; ảnh bị coi cố định 1 tile; heuristic 3 ký tự/token; reasons hardcode 600. | Áp trần `max_output_tokens` (1200 cho content, 800 cho reasons); tính tile ảnh theo kích thước thực (`width x height`); tắt thinking qua `thinking_budget=0` và tính `thoughts_token_count` vào token tính phí; ước lượng đúng theo cấu hình và trần đầu ra. | `32923d7` | `tests/llm/test_pricing.py::test_estimate_usd_exact`<br>`tests/llm/test_pricing.py::test_calculate_image_tiles`<br>`tests/llm/test_pricing.py::test_estimate_usd_with_tall_frame_sizes`<br>`tests/llm/test_gemini.py::test_gemini_client_generate_json_success` |
| **P1 — Phát hiện 2** | P1 | Cho phép kết quả không có bằng chứng, citation rỗng, video/creator sai; `reasons.py` ghi đè creator đầu vào che lỗi model. | Kiểm tra bắt buộc: `payload.video_id == video.video_id`, `payload.creator_id == c.creator_id` (không ghi đè); bắt buộc mỗi tiêu chí rubric có ít nhất một bằng chứng; `cited_evidence_ids` không được rỗng; kiểm tra định dạng ID (`<vid>@<start_s>`, `<vid>:transcript:<n>`), tính duy nhất và mốc thời gian trong độ dài video. | `5544e98` | `tests/llm/test_content.py::test_analyze_video_repair_on_empty_citations`<br>`tests/llm/test_content.py::test_analyze_video_rejects_wrong_video_and_empty_evidence`<br>`tests/llm/test_reasons.py::test_write_reasons_rejects_wrong_creator_id`<br>`tests/llm/test_reasons.py::test_write_reasons_rejects_empty_citations` |
| **P1 — Phát hiện 3 & Tu chính A1** | P1 | Frame không có đường dẫn bền vững; model không biết path; thư mục tạm bị xóa trước khi trả về. | Triển khai Tu chính A1 (`frames_dir`): lưu khung hình bền vững tại `<frames_dir>/<video_id>/f_<t_ms>.jpg`; mã nguồn tự động gán `Evidence.frame_path` về frame trích xuất gần nhất; kiểm tra file tồn tại trên đĩa sau khi trả về; không để model tự đặt đường dẫn. | `7de4a18`<br>`5544e98` | `tests/llm/test_content.py::test_analyze_video_success_order_and_amendment_a1`<br>`tests/llm/test_media.py::test_preprocess_video_generated_file` |
| **P2 — Phát hiện 4** | P2 | Nhận khóa trực tiếp qua tham số `api_key`; khi thiếu truyền `None` để SDK tự tìm `GOOGLE_API_KEY`. | Xóa bỏ tham số `api_key` ở `GeminiClient.__init__`; yêu cầu biến môi trường `GEMINI_API_KEY` tồn tại và không rỗng khi khởi tạo production; giữ injection `client` cho test. | `32923d7` | `tests/llm/test_gemini.py::test_gemini_client_env_only_key_missing`<br>`tests/llm/test_gemini.py::test_gemini_client_env_only_key_present` |
| **P2 — Phát hiện 5** | P2 | JSON hỏng hoặc sai schema ném `ValidationError` ngay, bỏ qua vòng retry sửa một lần. | Hợp nhất lỗi parse JSON, schema Pydantic và lỗi nghiệp vụ vào vòng lặp tối đa 2 lần; ghi nhận `usage` vào `budget_guard` ngay sau mỗi phản hồi (kể cả phản hồi lỗi); từ chối sau lần 2. | `5544e98` | `tests/llm/test_content.py::test_analyze_video_repair_on_malformed_json`<br>`tests/llm/test_content.py::test_analyze_video_fails_when_both_attempts_malformed_json`<br>`tests/llm/test_reasons.py::test_write_reasons_repair_on_malformed_json`<br>`tests/llm/test_reasons.py::test_write_reasons_fails_when_both_attempts_malformed` |
| **P2 — Phát hiện 6** | P2 | Lần sửa mất ngữ cảnh gốc và media; nội dung sửa dùng tiếng Anh; thiếu ràng buộc chống suy diễn doanh số. | Gửi lại toàn bộ ngữ cảnh gốc (prompt + 8 frames + audio cho content; prompt + chỉ số cho reasons) kèm lệnh sửa bằng tiếng Việt; dự trù ngân sách cho toàn bộ yêu cầu sửa; cập nhật hai prompt `content_v1.md` và `reasons_v1.md` với ràng buộc tuyệt đối: chỉ xuất tiếng Việt, không suy đoán lời nói (`[không rõ]`), không suy diễn doanh số từ hình ảnh/âm thanh, trích dẫn đúng nguồn. | `5544e98` | `tests/llm/test_content.py::test_analyze_video_repair_on_malformed_json`<br>`tests/llm/test_reasons.py::test_write_reasons_repair_on_malformed_json` |
| **P2 — Phát hiện 7** | P2 | Test dùng đường dẫn tuyệt đối; test guard chưa chứng minh thứ tự check/call/record và số tiền; test estimate chấp nhận khoảng rộng; thiếu test ca phản ví dụ. | Loại bỏ toàn bộ đường dẫn tuyệt đối, sinh video thử nghiệm nhỏ bằng ffmpeg trong `tmp_path`; dùng `SpyGuard` kiểm tra đúng thứ tự sự kiện `check -> call -> record` và số tiền chính xác; thêm đầy đủ kiểm thử phản ví dụ; assert số tiền dự trù chính xác (`0.007518 USD`). | `7de4a18`<br>`32923d7`<br>`5544e98` | `tests/llm/test_content.py::test_analyze_video_success_order_and_amendment_a1`<br>`tests/llm/test_reasons.py::test_write_reasons_success_order_and_amounts`<br>`tests/llm/test_pricing.py::test_estimate_usd_exact`<br>`tests/llm/test_content.py::test_analyze_video_repair_blocked_by_budget_guard`<br>`tests/llm/test_reasons.py::test_write_reasons_repair_blocked_by_budget_guard` |
| **P3 — Phát hiện 8** | P3 | Hook sai mốc cho video ngắn hơn 4.5 giây (probe video 2 giây trả hook 0.22 giây thay vì 0.5 giây). | Sửa `_calculate_frame_timestamps`: giữ cố định hook tại mốc 0.5 giây cho mọi video dài hơn 0.5 giây; chỉ dùng fallback chia đôi khi video ngắn hơn hoặc bằng 0.5 giây; phân bố đều các frame còn lại sau hook. | `7de4a18` | `tests/llm/test_media.py::test_calculate_frame_timestamps_short_video_hook` |

---

## 2. Kết Quả Kiểm Thử (Pytest)

### A. Kiểm thử riêng mô-đun LLM (`tests/llm`)
```text
$ PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/llm
.................................                                        [100%]
33 passed in 6.63s
```
*(Tăng từ 18 tests lên 33 tests, 100% đạt, không có cảnh báo hay lỗi).*

### B. Kiểm thử toàn bộ hệ thống (`tests`)
```text
$ PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
........................................................................ [ 90%]
........                                                                 [100%]
80 passed in 8.12s
```
*(Tăng từ 65 tests lên 80 tests, toàn bộ xanh).*

---

## 3. Thực Nghiệm Đối Chứng Probe Của Đánh Giá Độc Lập

| Tình huống thực nghiệm | Kết quả trong Codex Review (Cũ - FAIL) | Kết quả sau khi sửa (Mới - PASS) | Chứng minh |
|---|---|---|---|
| **Mốc Hook video 2 giây** | `0.22s` | `0.5s` (chuỗi: `[0.5, 0.69, 0.88, 1.06, 1.25, 1.44, 1.62, 1.81]`) | Đúng contract hook 0.5s cho video ngắn. |
| **Ảnh kích thước lớn (chiều cao cao)** | Bị tính mặc định 1 tile | Tính chính xác theo tile: 360x640 = 1 tile; 360x1600 = 3 tiles | `calculate_image_tiles` bảo vệ trần chi phí. |
| **Dự trù chi phí chuẩn 8 frames/30s/3000 chars** | Test cũ kiểm tra khoảng `0.005 <= est <= 0.010` | Đúng chính xác con số giải tích `0.007518 USD` | Kiểm tra chính xác qua `pytest.approx(est, abs=1e-6) == 0.007518`. |
| **Phản hồi JSON hỏng `{bad`** | Gây `ValidationError` ngay, chỉ gọi 1 lần, ghi nhận 1 lần, không retry sửa | Gọi lần 1 -> ghi nhận -> retry với prompt tiếng Việt đầy đủ ngữ cảnh -> gọi lần 2 -> ghi nhận | Thử nghiệm `test_analyze_video_repair_on_malformed_json` đạt. |
| **Citation rỗng và sai video** | Bị bỏ lọt không báo lỗi (`validation errors: []`) | Bị từ chối ngay với 4 lỗi chi tiết: sai video ID, thiếu 7 tiêu chí, citation rỗng | Thử nghiệm `test_analyze_video_rejects_wrong_video_and_empty_evidence` đạt. |
| **Recommendation sai Creator ID** | Bị ghi đè âm thầm bằng creator đầu vào | Bị từ chối với lỗi: `Creator ID không khớp: mong đợi 'target_cr', nhận được 'wrong_cr'` | Thử nghiệm `test_write_reasons_rejects_wrong_creator_id` đạt. |
| **Khung hình bền vững** | Bị xóa sau khi gọi do dùng tempdir | Khung hình được lưu cố định tại `<frames_dir>/<video_id>/f_<t_ms>.jpg` và ánh xạ chính xác vào `Evidence.frame_path` | Thử nghiệm `test_analyze_video_success_order_and_amendment_a1` đạt. |

---

## 4. Cam Kết & Trạng Thái Nhánh

- Tất cả chuỗi hiển thị cho người dùng và thông báo kiểm tra nghiệp vụ đều bằng tiếng Việt.
- Không truy cập mạng, không gọi API Gemini thực tế trong kiểm thử.
- Nhánh hiện tại: `feat/koc-llm2`.
- Không thực hiện lệnh merge vào nhánh chính.

---

## 5. Bổ Sung Sửa Lỗi Vòng 2 (Round 2 Fixes)

Ngày: 2026-11-15  
Tác giả: Agy (Gemini 3.8 Flash high)  
Nhánh: `feat/koc-llm3`  
Worktree: `/home/lystiger/Projects/KOC-Discovery-llm3`  
Căn cứ: `docs/build/REVIEW_llm_by_codex_r2.md` (3 phát hiện: R2-1, R2-2, R2-3).

### 5.1. Bảng Đối Chiếu 3 Phát Hiện Vòng 2

| Mục | Mức độ | Vấn đề phát hiện | Giải pháp khắc phục đã triển khai | Kiểm thử chứng minh |
|---|---|---|---|---|
| **R2-1** | P1 | Dự trù đầu vào vẫn dùng heuristic ký tự/3, không phải cận trên; probe cận trần cho phép gọi rồi mới ném lỗi khi record. | Thiết lập cận trên toán học chứng minh được (**Provable Upper Bound**):<br>- Text tokens bound = Tổng độ dài UTF-8 bytes của toàn bộ text parts (prompt + metadata + nội dung repair). Với BPE/SentencePiece, mỗi token luôn $\ge 1$ byte nên số bytes là cận trên tuyệt đối.<br>- Image tokens: Tính chính xác theo tile math ($W \le 384 \land H \le 384 \to 1$ tile 258 tokens; lớn hơn thì $\lceil W/768 \rceil \times \lceil H/768 \rceil \times 258$).<br>- Audio tokens: $32 \text{ tokens/s} \times \lceil \text{duration} \rceil \times 1.10$ (biên độ an toàn cố định 10%); bằng 0 nếu video không có audio.<br>- Output tokens: Giữ cố định trần `max_output_tokens` và tắt thinking (`thinking_budget=0`).<br>- Gọi `budget_guard.check(upper_bound_usd)` trước **mọi** cuộc gọi (kể cả lần gọi sửa repair).<br>- Tài liệu hóa cận trên chi tiết trong docstring `pricing.py`. | `tests/llm/test_pricing.py::test_estimate_usd_provable_bound_exact`<br>`tests/llm/test_pricing.py::test_estimate_usd_text_parts_utf8_bound`<br>`tests/llm/test_reasons.py::test_budget_check_provable_upper_bound_refuses_before_call` |
| **R2-2** | P2 | ID `@999` với `start_s=0.5`, `start_s=3.4` trong video 3 giây, hoặc NaN không bị từ chối; không kích hoạt vòng repair. | Siết chặt toàn bộ kiểm tra thực thể Evidence trong `_validate_payload`:<br>- `start_s` và `end_s` bắt buộc là số thực hữu hạn (`math.isfinite`), từ chối triệt để `NaN` và `Inf`.<br>- Bắt buộc $0 \le \text{start\_s} \le \text{duration\_s}$ (bỏ dung sai $+0.5\text{s}$).<br>- `end_s` nếu có phải thỏa mãn $\text{start\_s} \le \text{end\_s} \le \text{duration\_s}$.<br>- Đối chiếu mốc thời gian trong ID: định dạng `<video_id>@<start_s>` bắt buộc phần số sau `@` phải bằng chính xác `start_s` (sai số $\le 10^{-3}\text{s}$); định dạng transcript là `<video_id>:transcript:<n>`.<br>- Khi vi phạm: kích hoạt vòng repair thông báo lỗi mốc thời gian cho model; nếu sau repair vẫn sai sẽ ném `ValueError`. | `tests/llm/test_content.py::test_analyze_video_rejects_evidence_timestamp_past_duration`<br>`tests/llm/test_content.py::test_analyze_video_rejects_nan_timestamp`<br>`tests/llm/test_content.py::test_analyze_video_rejects_evidence_id_timestamp_mismatch_at_999` |
| **R2-3** | P2 | Video không có audio stream gây lỗi ffmpeg exit code 234 ở bước trích xuất MP3, làm hỏng toàn bộ phân tích hình ảnh. | Xử lý video im lặng/không có audio stream:<br>- Dùng `ffprobe` phát hiện luồng audio trước khi trích xuất (`_has_audio_stream`).<br>- `preprocess_video` trả về `audio_path = None` khi video không có audio; vẫn ném lỗi thật nếu audio stream tồn tại nhưng bị hỏng.<br>- `analyze_video` chỉ gửi frames hình ảnh (không gửi Part audio), đặt `transcript_vi = None`, bổ sung ghi chú thiếu âm thanh vào `risks_vi`.<br>- Dự trù ngân sách với 0 token audio. | `tests/llm/test_media.py::test_preprocess_video_no_audio_stream`<br>`tests/llm/test_content.py::test_analyze_video_no_audio_stream`<br>`tests/llm/test_pricing.py::test_estimate_usd_no_audio_stream` |

### 5.2. Kết Quả Kiểm Thử Sau Vòng 2

```text
$ PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/llm
.........................................                                [100%]
41 passed in 10.07s

$ PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/llm tests/core
....................................................................     [100%]
68 passed in 11.14s
```
*(100% passed, toàn bộ 41/41 tests LLM và 68/68 tests kết hợp core + llm đều xanh).*

### 5.3. Thực Nghiệm Đối Chứng Probe Của Đánh Giá Độc Lập Vòng 2

1. **R2-1 Probe (Cận trần ngân sách)**:
   - Tình huống: Đã chi 4.9955 USD trên trần 5.00 USD. Prompt 2557 ký tự / 3039 UTF-8 bytes.
   - Heuristic cũ: Dự trù $2557/3 = 853$ tokens input + 800 tokens output = 0.003639 USD. $4.9955 + 0.003639 = 4.999139 \le 5.00$ USD $\to$ cho phép gọi, sau đó gọi thật ném BudgetExceeded ở bước record và không lưu cuộc gọi.
   - Provable Bound mới: Dự trù theo UTF-8 byte length = 3039 tokens input + 800 tokens output = 0.005279 USD. $4.9955 + 0.005279 = 5.000779 > 5.00$ USD $\to$ `budget_guard.check` từ chối ngay trước cuộc gọi. Số lần gọi SDK: **0**, chi phí DB giữ nguyên 4.9955 USD.
2. **R2-2 Probe (Thời gian bằng chứng)**:
   - Tình huống 1: Payload có `start_s = 3.4` trong video 3.0 giây $\to$ Bị từ chối với thông báo `Mốc thời gian start_s không hợp lệ: 3.4s (video dài 3.0s)`, kích hoạt repair loop.
   - Tình huống 2: Payload có `start_s = NaN` $\to$ Bị từ chối với thông báo `Mốc thời gian start_s không phải số hữu hạn: nan`, kích hoạt repair loop.
   - Tình huống 3: Payload có ID `<video_id>@999` với `start_s = 0.5` $\to$ Bị từ chối với thông báo `Mốc thời gian trong evidence_id ... (999.0s) không khớp với start_s (0.5s)`, kích hoạt repair loop.
3. **R2-3 Probe (Video không có luồng audio)**:
   - Tình huống: Video MP4 sinh bởi ffmpeg không có stream audio (`-an` hoặc chỉ có visual testsrc).
   - Trước sửa: ffmpeg exit 234 tại bước xuất MP3, `CalledProcessError`.
   - Sau sửa: `preprocess_video` hoàn tất với `audio_path = None`, 8 frames ảnh trích xuất bình thường. `analyze_video` chạy hoàn tất, chỉ gửi frames, tính 0 token audio trong dự trù ngân sách, trả `transcript_vi = None` và tự động ghi chú `Video không có luồng âm thanh (silent video).` vào `risks_vi`.

### 5.4. Trạng Thái Nhánh
- Nhánh: `feat/koc-llm3`.
- Không thực hiện lệnh merge vào nhánh chính.

---

## 6. Bổ Sung Sửa Lỗi Vòng 3 (Round 3 Fixes)

Ngày: 2026-11-15  
Tác giả: Agy (Gemini 3.8 Flash high)  
Nhánh: `feat/koc-llm4`  
Worktree: `/home/lystiger/Projects/KOC-Discovery-llm4`  
Căn cứ: `docs/build/REVIEW_llm_by_codex_r3.md` (Phần R2-1 — P1 budget bound & model pinning).

### 6.1. Bảng Đối Chiếu Yêu Cầu Vòng 3 Sang Giải Pháp Triển Khai

| Yêu cầu | Mô tả chi tiết | Giải pháp triển khai | Kiểm thử chứng minh |
|---|---|---|---|
| **1. Request Material Inclusive Bound** | Cận trên phải bao gồm TOÀN BỘ tài liệu request: prompt text, metadata, repair context VÀ `response_schema` đã serialize (UTF-8 bytes JSON) cộng hằng số overhead biên cố định 200 tokens; giữ nguyên media và output. | - Bổ sung `serialize_response_schema` tính độ dài UTF-8 bytes của JSON schema (`RecommendationPayload`: 513 bytes, `ContentAnalysisPayload`: 1776 bytes).<br>- Bổ sung hằng số `REQUEST_OVERHEAD_TOKENS = 200` vào `pricing.py` và cấu hình `config/llm_prices.yaml`.<br>- `estimate_usd` tính tổng: `image_tokens + audio_tokens + text_tokens + schema_tokens + overhead_tokens`.<br>- `analyze_video` và `write_reasons` truyền đầy đủ `response_schema` vào `estimate_usd`. | `tests/llm/test_pricing.py::test_serialize_response_schema`<br>`tests/llm/test_pricing.py::test_estimate_usd_schema_inclusive_bound`<br>`tests/llm/test_pricing.py::test_codex_r3_counterexample_blocked_before_call` |
| **2. Pin Models & Strict Price Binding** | Client chỉ chấp nhận model ID có trong `config/llm_prices.yaml` kèm giá; model khác phải raise trước khi gọi. Tính phí luôn dùng đúng cấu hình của model thực sự được gửi. | - Bổ sung `get_model_pricing(model, config_path)` kiểm tra model có định nghĩa giá hợp lệ (`input_usd`, `output_usd`).<br>- `GeminiClient.__init__` từ chối ngay model chưa định giá.<br>- `GeminiClient.generate_json` kiểm tra lại `get_model_pricing(self.model)` trước khi gọi `generate_content`.<br>- Tính phí qua `calculate_cost_usd(..., model=self.model)`. | `tests/llm/test_pricing.py::test_unpriced_model_refused`<br>`tests/llm/test_gemini.py::test_gemini_client_refuses_unpriced_model_at_init`<br>`tests/llm/test_gemini.py::test_gemini_client_refuses_unpriced_model_before_generate_json`<br>`tests/llm/test_gemini.py::test_gemini_client_pricing_uses_model_actually_sent` |
| **3. Helper `max_call_upper_bound_usd`** | Xuất helper `max_call_upper_bound_usd(kind)` tính worst-case cho 1 cuộc gọi content (8 frames + max audio seconds từ config) và 1 cuộc gọi reasons để core bảo lưu headroom. | - Xuất `max_call_upper_bound_usd` tại `pricing.py` và `koc.llm.__init__`.<br>- Content: 8 frames (2064 tok) + 180s audio (`max_audio_seconds`: 6336 tok) + 5000 text tok + Content schema (1776 tok) + 200 overhead + 1200 output = 15376 tok in / 1200 tok out = `0.016032 USD`.<br>- Reasons: 0 frames/audio + 4000 text tok + Reasons schema (513 tok) + 200 overhead + 800 output = 4713 tok in / 800 tok out = `0.006535 USD`. | `tests/llm/test_pricing.py::test_max_call_upper_bound_usd_values` |

### 6.2. Kết Quả Kiểm Thử Sau Vòng 3

```text
$ PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/llm tests/core
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 11.48s
```
*(100% passed, 49/49 tests LLM và 27/27 tests core đều xanh).*

### 6.3. Giải Quyết Phản Ví Dụ Độc Lập Vòng 3 Của Codex

- **Tình huống trong Báo cáo Codex R3**:
  - Đã chi trong DB: `4.9945285 USD` trên trần `5.00 USD`.
  - Prompt text: 3039 UTF-8 bytes.
  - JSON-schema RecommendationPayload: 513 bytes.
  - Dự trù cũ: 3039 input + 800 output = `0.005279 USD`. $4.9945285 + 0.005279 = 4.9998075 \le 5.00$ USD $\to$ vượt qua bước check, gọi SDK, rồi mới ném lỗi ở record và bỏ lọt usage.
- **Kết quả sau sửa Round 3**:
  - Dự trù mới: $3039 \text{ text} + 513 \text{ schema} + 200 \text{ overhead} = 3752 \text{ input tokens}$.
  - $3752 \times 0.75 / 10^6 + 800 \times 3.75 / 10^6 = 0.002814 + 0.003000 = \mathbf{0.005814\text{ USD}}$.
  - $4.9945285 + 0.005814 = \mathbf{5.0003425 > 5.000000\text{ USD}}$.
  - `budget_guard.check` từ chối NGAY LẬP TỨC trước khi gọi model.
  - Số cuộc gọi SDK thực tế: **0**.
  - Chi phí đã lưu trong DB giữ nguyên không bị thay đổi (`4.9945285 USD`).

### 6.4. Trạng Thái Nhánh
- Nhánh: `feat/koc-llm4`.
- Không chỉnh sửa `src/koc/budget_guard.py`.
- Không thực hiện lệnh merge vào nhánh chính.


