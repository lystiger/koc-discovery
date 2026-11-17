# Bằng chứng CORE D2

Ngày: 2026-11-15  
Nhánh: `feat/koc-core2`

## Đã làm

- S1a chấm mọi kết quả creator/rank từ các trường hàng xếp hạng, không gọi thêm API. Giới hạn 60 nằm trong `config/pipeline.yaml`.
- S1b gọi `creator/detail(need_extra)` và `video/rank(page_size=10)` cho nhóm đã lọc; tính lại điểm thương mại và lưu tương tác/view.
- Khi chưa có `category_ids`, S0 dùng từ khóa `kem chống nắng` và CLI cảnh báo bằng tiếng Việt. `koc categories --keyword` lấy category/rank qua cache, in ID/tên khớp và ghi ID vào cấu hình.
- S2 mở trang creator qua CDP, chờ tối thiểu 5 giây, bỏ glyph vùng private-use, lưu tỷ lệ giới tính/tuổi cùng URL nguồn. Chặn lượt chạy và giữ tác vụ còn lại ở trạng thái `failed` với dấu `blocked:` khi gặp trang giới hạn; `resume` mở lại chúng.
- S3 lấy tối đa ba video mỗi creator, tải MP4 theo luồng và bỏ qua tệp đã có. LLM dùng cache lõi theo hash media/prompt/model/brief; cache hit ghi usage với chi phí 0. Điểm nội dung là trung bình rubric nhân 20.
- S4 tính điểm cuối theo trọng số 0.45/0.20/0.35, chọn tổ hợp tối đa năm creator trong ngân sách 30 triệu VND và loại MCN trùng khi có `mcn_id`. Lưu lý do và khuyến nghị.
- `koc report --run` ghi `reports/benchmark.json` và `docs/BENCHMARK.md`, gồm thời gian stage, credits, tokens, USD, cache hit, funnel, dự phóng 500 ứng viên và Spearman.
- `scripts/kill_resume_test.sh` dùng API fixture và LLM giả; gửi SIGKILL sau response S1b đã cache và sau LLM S3 đã cache, trước khi ghi kết quả task. Sau đó tiếp tục chạy, kiểm tra khóa duy nhất, không gọi lặp và lượt chạy mới dùng cache.

## Kiểm tra

Lệnh:

```text
PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

Kết quả:

```text
...........................................................              [100%]
59 passed in 7.07s
```

`bash -n scripts/kill_resume_test.sh` thành công. `PYTHONPATH=src bash scripts/kill_resume_test.sh` cho kết quả:

```text
SIGKILL + resume: S1b PASS
SIGKILL + resume: S3 PASS
```

`koc run --limit 200 --dry-run` báo 12.2 credits cho S0+S1 (0.2 + 60 × 0.2), 24 credits dự kiến cho S3, tổng 36.2; không mở DB và không gọi mạng.

Benchmark đã tạo từ lượt fixture mock 50 ứng viên: 50 → 50 → 40 → 15 → 5. Credits/tokens/USD bằng 0 vì mock. Spearman trả `null` do dữ liệu mock không có biến thiên. Đây không phải kết quả chi phí hay hiệu chuẩn chạy thật.

## Câu hỏi mở và giới hạn bằng chứng

- `config/scoring.yaml` vẫn có `category_ids: []`. Chưa có lần gọi category/rank thật để xác minh tên danh mục và ID Skincare; điểm chia sẻ doanh thu Skincare chỉ hoạt động sau khi operator cấu hình ID.
- Chưa xác minh CDP với phiên Kalodata đăng nhập. Giao diện có thể đổi nhãn hoặc cấu trúc trang; parser được kiểm tra bằng fake page.
- Tài liệu Kalodata offline không nêu trường MCN; hiện chỉ áp dụng điều kiện loại trùng khi dữ liệu có `mcn_id` tường minh.
- Chưa tải MP4 thật, gọi Gemini thật hoặc đo credits/tokens/USD thật. Benchmark mock không chứng minh các khoản này.
- Dữ liệu mock tạo điểm bằng nhau nên Spearman là `null`; chất lượng hiệu chuẩn còn UNPROVEN.
- Chưa có đánh giá độc lập TEST/VERDICT. Không merge.
