# Bằng Chứng Hoàn Thành Giao Diện Web (Deliverable D2)

**Ngày**: 2026-11-15  
**Người thực hiện**: Agy (Gemini 3.8 Flash high)  
**Nhánh**: `feat/koc-web`  
**Thư mục làm việc**: `~/Projects/KOC-Discovery-web`  
**Tiêu chí nghiệm thu**: SPEC C9 (FastAPI + Jinja2, tiếng Việt, 3 view chính, ảnh chụp màn hình 375px & 1440px)

---

## 1. Nội dung công việc đã hoàn thành

### A. Thiết kế hệ thống (Design System - Step 0)
- Đọc và áp dụng quy chuẩn từ `~/.claude/skills/ui-ux-pro-max/SKILL.md`.
- Chạy tra cứu `--design-system` cho ngành mỹ phẩm & skincare Việt Nam:
  `python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "KOC influencer discovery analytics dashboard beauty skincare Vietnam" --design-system`.
- Ghi nhận tài liệu thiết kế chi tiết tại `docs/build/DESIGN.md`:
  - Phong cách: **Soft UI Evolution** (mật độ dữ liệu cao nhưng dịu mắt, tương phản WCAG AA, số liệu tabular-nums).
  - Bảng màu: Sáng (#F8FAFC, #FFFFFF, Rose #BE185D) và Tối (#0B0F19, #131B2E, Pink #F472B6) kèm thanh màu phân rã (Teal thương mại 45%, Indigo khán giả 20%, Amber nội dung 35%).
  - Hỗ trợ chuyển đổi Theme (Light / Dark) trực tiếp trên thanh điều hướng và tham số URL `?theme=dark`.

### B. Kiến trúc ứng dụng FastAPI + Jinja2 (`src/koc/web/`)
1. **`src/koc/web/adapter.py`**:
   - Tích hợp chuẩn với `koc.queries` (`list_runs`, `get_run`, `top5`, `creator_detail`, `run_costs`).
   - Cung cấp các hàm tổng hợp dữ liệu read-only theo CONTRACTS §3, tài liệu hóa tại `docs/build/CHANGE_REQUEST_web.md`:
     - `get_top5_with_details`: thẻ KOC xếp hạng, điểm phân rã, chi phí ước tính, ngân sách tổng vs 30.000.000 ₫, 2 dòng lý do.
     - `get_creator_full_detail`: bảng metrics (kèm evidence ID, nguồn, chu kỳ), cơ cấu khán giả (nữ %, độ tuổi), 3 video (khung hình, timestamps, trích dẫn giọng nói, rubric 7 tiêu chí, rủi ro), lý do & lưu ý có liên kết neo bằng chứng.
     - `get_dashboard_data`: phễu lọc 5 giai đoạn (candidates in/out), trạng thái tasks, tín dụng Kalodata vs hạn mức 100, tokens/USD LLM vs hạn mức $5, thời gian từng stage, cache hits, hệ số Spearman ($\rho$).
2. **`src/koc/web/app.py`**:
   - Khởi tạo FastAPI app và cấu hình Jinja2 templates.
   - Các bộ lọc định dạng tiếng Việt: `format_vnd`, `format_number`, `format_percent`, `format_score`.
   - 4 Route HTML nghiệp vụ:
     - `GET /`: Danh sách đợt chạy (Run list).
     - `GET /runs/{run_id}`: Top 5 KOC đề xuất kèm phân rã điểm và tiến độ ngân sách.
     - `GET /runs/{run_id}/creators/{creator_id}`: Hồ sơ chi tiết KOC và bằng chứng video.
     - `GET /runs/{run_id}/dashboard`: Bảng điều khiển vận hành & hiệu năng.
   - Route phương tiện bảo mật:
     - `GET /media/{filepath:path}`: Phục vụ ảnh khung hình trích xuất từ `data/media/`.
     - Cơ chế phòng thủ nghiêm ngặt chặn tấn công **Path Traversal** (kiểm tra `..`, đường dẫn tuyệt đối, và `target_file.relative_to(base_dir)`).
3. **`src/koc/web/__main__.py`**:
   - Cho phép khởi chạy máy chủ độc lập qua lệnh `python -m koc.web [--db PATH] [--port 8765] [--media-dir PATH]`.
   - Không can thiệp hoặc chỉnh sửa `src/koc/cli.py`.
4. **Hệ thống Template Jinja2 (`src/koc/web/templates/`)**:
   - `base.html`: Khung sườn, thanh điều hướng, nút chuyển Dark/Light, cảnh báo dữ liệu giả lập (Mock Alert Banner), hiệu ứng cuộn mượt và highlight bằng chứng khi nhấp mã evidence.
   - `runs_list.html`: Bảng danh sách các đợt chạy.
   - `top5.html`: Thẻ xếp hạng 5 KOC, thanh phân rã điểm, tổng ngân sách so với 30.000.000 ₫.
   - `creator.html`: Chi tiết số liệu, cơ cấu độ tuổi/giới tính, phân tích 3 video kèm 7 rubric và rủi ro.
   - `dashboard.html`: Phễu lọc 5 giai đoạn, tasks theo stage, đồng hồ hạn mức credits/USD, tỷ lệ cache hit, hệ số hiệu chuẩn Spearman.

### C. Fixture DB và Bộ Kiểm Thử (`tests/web/`)
- `tests/web/fixtures/seed.py`: Nạp cơ sở dữ liệu mẫu thực tế ngành mỹ phẩm chăm sóc da tại Việt Nam (`data/fixture.db`), có cả run giả lập (`mock: true`) và run thật (`mock: false`), tự động tạo các ảnh khung hình JPEG hợp lệ tại `data/media/`.
- `tests/web/test_app.py`: Bộ kiểm thử tự động gồm 6 bài test đạt 100%:
  - Kiểm tra mã trạng thái HTTP 200 cho toàn bộ các route trên Fixture DB.
  - Kiểm tra sự hiện diện của nhãn tiếng Việt chuẩn marketing và SPEC ("ƯỚC TÍNH", "Thương mại", "Khán giả", "Nội dung", "30.000.000", v.v.).
  - Kiểm tra mọi liên kết bằng chứng (`href="#..."`) đều phân giải chính xác tới phần tử DOM có `id` tương ứng.
  - Kiểm tra hiển thị banner giả lập (Mock Banner) khi `mock: true` và ẩn hoàn toàn khi `mock: false`.
  - Kiểm tra chặn triệt để tấn công Path Traversal trên route `/media/`.
  - Kiểm tra mã lỗi 404 cho các tài nguyên không tồn tại.

---

## 2. Kết Quả Chạy Kiểm Thử (Pytest Output)

Lệnh thực thi:
```bash
PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -v
```

Kết quả: **59 passed in 7.16s** (bao gồm 6 bài test web mới và 53 bài test core/llm có sẵn).

```text
============================= test session starts ==============================
platform linux -- Python 3.14.8, pytest-9.2.0, pluggy-1.7.0 -- /home/lystiger/Projects/KOC-Discovery/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/lystiger/Projects/KOC-Discovery-web
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 59 items

tests/core/test_budget_guard.py::test_llm_budget_uses_logged_cumulative_cost_and_cache_key PASSED [  1%]
tests/core/test_cli.py::test_dry_run_does_not_open_database_or_network PASSED [  3%]
tests/core/test_config.py::test_config_has_required_cost_and_score_values PASSED [  5%]
tests/core/test_db.py::test_schema_tables_and_upserts_are_idempotent PASSED [  6%]
tests/core/test_db.py::test_task_result_write_rolls_back_and_resume_resets_running PASSED [  8%]
tests/core/test_db.py::test_process_crash_leaves_work_resumable PASSED   [ 10%]
tests/core/test_db.py::test_paid_response_is_cached_before_process_crash PASSED [ 11%]
tests/core/test_kalodata.py::test_cache_hit_costs_zero_credits_and_strips_contact PASSED [ 13%]
tests/core/test_kalodata.py::test_credit_counter_refuses_before_transport PASSED [ 15%]
tests/core/test_kalodata.py::test_strip_contacts_recurses PASSED         [ 16%]
tests/core/test_kalodata.py::test_retries_server_errors_three_times_then_logs_success PASSED [ 18%]
tests/core/test_scoring.py::test_s1_score_uses_fixture_creator_values PASSED [ 20%]
tests/core/test_scoring.py::test_s1_engagement_breaks_score_ties PASSED  [ 22%]
tests/llm/test_content.py::test_analyze_video_success PASSED             [ 23%]
tests/llm/test_content.py::test_analyze_video_budget_guard_blocks PASSED [ 25%]
tests/llm/test_content.py::test_analyze_video_repair_on_unresolved_evidence_id PASSED [ 27%]
tests/llm/test_content.py::test_analyze_video_fails_when_repair_also_invalid PASSED [ 28%]
tests/llm/test_gemini.py::test_gemini_client_generate_json_success PASSED [ 30%]
tests/llm/test_gemini.py::test_gemini_client_multimodal_tokens PASSED    [ 32%]
tests/llm/test_gemini.py::test_gemini_client_retry_on_transient_error PASSED [ 33%]
tests/llm/test_gemini.py::test_gemini_client_fails_after_one_retry PASSED [ 35%]
tests/llm/test_media.py::test_preprocess_video_real_file PASSED          [ 37%]
tests/llm/test_media.py::test_preprocess_video_missing_file PASSED       [ 38%]
tests/llm/test_pricing.py::test_load_pricing_config PASSED               [ 40%]
tests/llm/test_pricing.py::test_calculate_cost_usd PASSED                [ 42%]
tests/llm/test_pricing.py::test_estimate_usd PASSED                      [ 44%]
tests/llm/test_pricing.py::test_estimate_usd_zero PASSED                 [ 45%]
tests/llm/test_reasons.py::test_write_reasons_success PASSED             [ 47%]
tests/llm/test_reasons.py::test_write_reasons_budget_guard_blocks PASSED [ 49%]
tests/llm/test_reasons.py::test_write_reasons_repair_retry_on_invalid_evidence_id PASSED [ 50%]
tests/llm/test_reasons.py::test_write_reasons_fails_after_retry PASSED   [ 52%]
tests/test_cli.py::test_collect_dry_run_writes_no_db PASSED              [ 54%]
tests/test_db.py::test_upsert_creator_writes_one_evidence_row_per_field PASSED [ 55%]
tests/test_db.py::test_duplicate_upsert_keeps_one_row_and_updates PASSED [ 57%]
tests/test_db.py::test_add_task_is_idempotent PASSED                     [ 59%]
tests/test_db.py::test_checkpoint_rolls_back_when_write_fails PASSED     [ 61%]
tests/test_db.py::test_interrupted_run_recovers_on_resume PASSED         [ 62%]
tests/test_db.py::test_field_sources_override_reaches_source_evidence PASSED [ 64%]
tests/test_mapping.py::test_parse_number[1.2M-1200000] PASSED            [ 66%]
tests/test_mapping.py::test_parse_number[\u20ab1.5B-1500000000] PASSED   [ 67%]
tests/test_mapping.py::test_parse_number[45%-45] PASSED                  [ 69%]
tests/test_mapping.py::test_parse_number[12.3K-12300] PASSED             [ 71%]
tests/test_mapping.py::test_parse_number[1,234-1234] PASSED              [ 72%]
tests/test_mapping.py::test_parse_number_unparseable_returns_none PASSED [ 74%]
tests/test_mapping.py::test_normalize_creator_observed_and_missing PASSED [ 76%]
tests/test_mapping.py::test_cover_is_derived_not_observed PASSED         [ 77%]
tests/test_mapping.py::test_field_sources_override_record_source PASSED  [ 79%]
tests/test_mapping.py::test_collected_at_preserved_from_raw PASSED       [ 81%]
tests/test_schemas.py::test_missing_with_value_rejected PASSED           [ 83%]
tests/test_schemas.py::test_observed_without_value_rejected PASSED       [ 84%]
tests/test_schemas.py::test_missing_helper_is_valid PASSED               [ 86%]
tests/test_schemas.py::test_media_analysis_rejects_extra_field PASSED    [ 88%]
tests/test_schemas.py::test_media_analysis_valid_passes PASSED           [ 89%]
tests/web/test_app.py::test_routes_200_on_fixture_db PASSED              [ 91%]
tests/web/test_app.py::test_vietnamese_labels_present PASSED             [ 93%]
tests/web/test_app.py::test_evidence_anchors_resolve PASSED              [ 94%]
tests/web/test_app.py::test_mock_banner_display PASSED                   [ 96%]
tests/web/test_app.py::test_path_traversal_blocked PASSED                [ 98%]
tests/web/test_app.py::test_404_error_handling PASSED                    [100%]

============================== 59 passed in 7.16s ==============================
```

---

## 3. Ảnh Chụp Màn Hình Kiểm Thử (Screenshots)

Toàn bộ ảnh chụp thực tế bằng `chromium --headless=new` đã lưu tại `docs/build/shots/`:

| View | Độ phân giải | Đường dẫn tệp ảnh | Tình trạng kiểm tra |
|---|---|---|---|
| **Top 5 Ranked Cards** | 375 px (Mobile) | [top5_375.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/top5_375.png) | PASS: 1 cột cuộn dọc, 0 cuộn ngang, thanh breakdown rõ |
| **Top 5 Ranked Cards** | 1440 px (Desktop) | [top5_1440.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/top5_1440.png) | PASS: Bố cục lưới thoáng, thanh phân rã điểm cân đối |
| **Top 5 (Chế độ Tối)** | 1440 px (Dark Mode) | [top5_1440_dark.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/top5_1440_dark.png) | PASS: Nền navy êm dịu, tương phản cao, badge hồng nổi bật |
| **Creator Detail** | 375 px (Mobile) | [creator_375.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/creator_375.png) | PASS: Bảng metrics chuyển sang dạng thẻ, không tràn mép |
| **Creator Detail** | 1440 px (Desktop) | [creator_1440.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/creator_1440.png) | PASS: Đầy đủ 3 video, khung hình, timestamps, 7 rubric |
| **Run Dashboard** | 375 px (Mobile) | [dashboard_375.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/dashboard_375.png) | PASS: Phễu dọc mượt, bảng task co giãn hoàn hảo |
| **Run Dashboard** | 1440 px (Desktop) | [dashboard_1440.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/dashboard_1440.png) | PASS: Phễu 5 giai đoạn, đồng hồ hạn mức, Spearman |
| **Run List** | 375 px (Mobile) | [runs_list_375.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/runs_list_375.png) | PASS: Danh sách đợt chạy rõ ràng |
| **Run List** | 1440 px (Desktop) | [runs_list_1440.png](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/shots/runs_list_1440.png) | PASS: Bảng hiển thị thông số chiến dịch và nút thao tác |

---

## 4. Vấn Đề Mở & Khuyến Nghị (Open Issues)

1. **Nâng cấp `src/koc/queries.py` (Core)**:
   - Các hàm truy vấn hiện tại của module core chưa trả về thông tin kết hợp giữa `recommendations`, `creators`, `scores`, `videos`, `analyses` và thống kê phễu/tasks.
   - Web UI đã tài liệu hóa cụ thể đề xuất bổ sung tại [CHANGE_REQUEST_web.md](file:///home/lystiger/Projects/KOC-Discovery-web/docs/build/CHANGE_REQUEST_web.md). Khi Core hợp nhất, `src/koc/web/adapter.py` sẽ chuyển tiếp sang gọi trực tiếp các hàm này mà không thay đổi giao diện.
2. **Trình phát video trực tiếp (Video Player)**:
   - Bản MVP hiện hiển thị ảnh trích xuất khung hình tĩnh (`frame thumbnails`) kèm mốc thời gian và trích đoạn phụ đề. Trong các phiên bản sau, có thể nhúng trình phát HTML5 video player có đánh dấu mốc cue time trực tiếp trên thanh timeline.
3. **Phát hiện trùng lặp MCN (MCN Collision Alert)**:
   - Thuật toán tối ưu hóa S4 đã tuân thủ điều kiện không chọn 2 KOC cùng MCN. Giao diện hiện tại hiển thị huy hiệu MCN rõ ràng; có thể bổ sung cảnh báo trực quan nếu người dùng cố tình can thiệp thủ công chọn KOC cùng mạng lưới.
