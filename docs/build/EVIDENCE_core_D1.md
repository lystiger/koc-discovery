# Bằng chứng CORE D1

Ngày: 2026-11-15  
Nhánh: `feat/koc-core`

## Đã làm

- Thêm bốn cấu hình: trọng số S1/final, bảng giá KOC theo follower, giá Kalodata và hạn mức LLM.
- Thêm loader YAML tại `src/koc/config.py`.
- Tạo đúng 12 bảng theo CONTRACTS §3. Upsert dùng khóa ổn định; ghi kết quả và đánh dấu task `done` trong cùng transaction. `resume` đặt task `running` về `pending`.
- Thêm client Kalodata với `secret-key`, cache SHA-256, hạn mức tín dụng có reservation trước request, log request, pacing, retry 429/5xx tối đa ba lần và dừng ở 401/403. Loại mọi trường `creator_contact_*` trước khi cache hoặc lưu creator.
- Thêm `BudgetGuard` theo tổng `llm_calls.cost_usd`, helper cache LLM theo media hash, prompt version, model và brief.
- Thêm S0 lấy creator rank và S1 tính điểm thương mại, metric evidence ID và tie-break engagement/view. S2/S3/S4 báo `NotImplementedError` có TODO.
- Thêm pipeline checkpoint/resume, CLI `koc run`, `koc resume`, `koc status`, hàm truy vấn read-only và script kill/resume.
- `koc run --dry-run` chỉ in kế hoạch và chi phí dự kiến; không mở DB hoặc tạo client mạng.

## Kiểm tra

Lệnh:

```text
PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/core tests/ -q
```

Kết quả:

```text
...................................                                      [100%]
```

35 test pass, gồm test Phase 0. Thêm kiểm tra dry-run:

```text
Kế hoạch D1: S0 tối đa 5 nhà sáng tạo, S1 chấm điểm, chưa chạy S2/S3/S4.
Danh mục Skincare: chưa cấu hình.
Tín dụng dự kiến: tối đa 1.1; token LLM: 0.
Chạy thử: không gọi mạng, không ghi dữ liệu.
```

`bash -n scripts/kill_resume_test.sh` và `git diff --check` đều thành công. Script kill/resume chưa chạy vì lệnh đó cần API key và gọi API tính phí.

## Chưa làm trong D1

- S2 audience, S3 phân tích video và S4 chọn 5 KOC/viết lý do còn là stub.
- Không có run Kalodata thật hoặc benchmark; không có bằng chứng end-to-end cho 5 KOC.
- Rate card dùng giá ước tính trong YAML. Cần xác nhận lại mức booking trước khi dùng để báo giá.

## Câu hỏi mở

- `docs/kalodata_api/category_rank.txt` và `category_detail.txt` chỉ có category ID ví dụ, không ánh xạ ID nào sang Skincare. `config/scoring.yaml` để `category_ids: []`; vì vậy S0 hiện chưa lọc Skincare và skincare revenue share chưa có dữ liệu. Cần taxonomy/ID đã xác minh để bật hai tín hiệu này.
- Mốc chuẩn GPM `100000` và xu hướng `25%` mỗi mẫu là cấu hình khởi đầu, chưa được hiệu chỉnh bằng holdout.
- Chưa cài entry point vào venv theo yêu cầu không pip install. `pyproject.toml` khai báo `koc = koc.cli:app`; CLI đã chạy qua `python -m koc.cli`.
