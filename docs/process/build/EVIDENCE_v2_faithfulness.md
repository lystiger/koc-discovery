# EVIDENCE v2 item 5 (A7): độ trung thực của lý do S4

Nhánh `v2/faithfulness` (từ `feat/koc-mvp` @ 48a5fdd). Không gọi mạng, không gọi trả phí, không ghi `data/koc.db`.

## Thiết kế

- `src/koc/faithfulness.py`, prompt `prompts/faithfulness_v1.md`. Mỗi đề xuất = 1 lượt gọi: mô hình chấm nhận các câu `reasons_vi` (điểm mạnh) và `caveats_vi` (điểm yếu) và chỉ phần bằng chứng mà đề xuất trích dẫn (chỉ số `metric:<id>:<tên>`, trích dẫn/mô tả khung `<video>@<giây>`, điểm rubric gắn với mã đó). Trả JSON chặt (`verdicts[{index, verdict: supported|partly|unsupported, why}]`, đúng n phần tử, kiểm tra index, thử lại 1 lần).
- Điểm: supported 1, partly 0,5, unsupported 0; KOC = trung bình câu; lượt chạy = trung bình KOC.
- Đề xuất không có mã bằng chứng tra cứu được: mọi câu unsupported, 0 lượt gọi. Câu lưu ý bắt buộc "Chưa xác minh hồ sơ khán giả" (do code thêm) không bị chấm.
- Lưu: bảng mới `faithfulness` khóa (run, creator, model, prompt) + `request_hash` của (prompt, mô hình, câu, bằng chứng): cùng đầu vào chạy lại 0 lượt gọi; đổi chỉ số/câu/mô hình thì chấm lại.
- Chi phí: `BudgetGuard(kind="faithfulness")`, kiểm tra ước tính trước mỗi lượt, ghi `llm_calls`; `run_id` NULL có chủ ý để `report.py`/`benchmark.py` (gán mọi kind khác `content` vào S4) không bị lẫn. Hạn mức vẫn tính trên tổng toàn bảng.
- CLI `koc faithfulness --run <id> [--model] [--cache-only] [--dry-run]`; `--dry-run` chỉ đọc, không tạo bảng.
- Benchmark: `faithfulness` trong `reports/benchmark.json` và mục 10 trong `docs/BENCHMARK.md` chỉ khi đã chấm; `units_*` không đổi (test).
- `scripts/faithfulness_free_smoke.py`: sao chép DB, mô hình `:free`, chấm hai lần (lần hai phải 0 lượt gọi), thoát 3 nếu bất kỳ lượt nào báo chi phí > 0.

## Kiểm chứng

- `tests/core/test_faithfulness.py` (12 test, transport giả): schema, toán điểm, bằng chứng được giải quyết, thiếu bằng chứng, chạy lại = 0 lượt gọi, cache-only, thử lại index sai, chặn ngân sách trước khi gọi, ước tính, CLI, benchmark chỉ khi có, script smoke PASS và mã 3. Sửa `tests/core/test_db.py` (thêm bảng mới).
- Toàn bộ suite dưới `unshare -rn`, khóa giả: 524 passed, 1 skipped.
- `bash -n` cả hai khối trong `RUNBOOK_v2_faithfulness.md`: ok.
- `--dry-run` trên bản sao chỉ-đọc của `data/koc.db` (mô hình mặc định `google/gemini-3.8-flash`):
  - `0e555cac95fb4fb49168410e40ea92d5`: 5 lượt gọi, tối đa 31.542 token vào, tối đa 0,0492 USD.
  - `7372009b22764b339fbcf0f3efb4bc4e`: 5 lượt gọi, tối đa 29.572 token vào, tối đa 0,0476 USD.
  - Bảng `faithfulness` không bị tạo trong bản sao sau dry-run.

## UNPROVEN

- Chất lượng phán quyết của mô hình thật và việc mô hình `:free` đáp ứng schema (chỉ Lystiger chạy khối 1).
- Chi phí thật (chỉ là cận trên ước tính); mô hình chấm cùng họ với S4 nên có thể thiên vị tự chấm.
- Smoke script chưa chạy với mạng; bước `.backup` của nó dùng `data/koc.db` theo thư mục hiện tại.
- Thực thi trên `data/koc.db` thật (tạo bảng mới) chưa thử.

## Small fix: Ly do / Luu y split
- Headline score = "Ly do" (reasons_vi only); "Luu y" (caveats_vi) reported separately per KOC and per run (CLI, `stored_summary`, BENCHMARK section 10).
- Every audience-unverified caveat (any wording; normalised pattern: khan gia/nhan khau hoc + chua (duoc) xac minh / khong co du lieu) is neither graded nor scored. Rows graded earlier (exact-string exclusion) are re-scored from stored verdicts by dropping those verdicts: 0 calls.
- Live copy, `faithfulness --run 0e555cac... --cache-only`: run Ly do 0.875 (teetamofficial 1.00, meixiuriviu 0.875, rio100806 / emduyencantho / dieuduong_quynhhoa 0.833); run Luu y 0.10 excluding audience caveats; calls 0, USD 0.
- Tests: new cases in tests/core/test_faithfulness.py; old 0.625 / 0.31 assertions updated to Ly do only.
