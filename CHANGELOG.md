# Changelog

## 2.0.2 (2026-11-17): kiến trúc tương lai

### Thêm
- README mục "Kiến trúc tương lai (v2.0.2)": worker song song và hàng đợi chung, lượt chạy lạnh, bảo mật và thông tin cá nhân, bảo vệ tài khoản, vấn đề của agent. Là kế hoạch, chưa xây; thời gian là ước tính chưa đo.

## 2.0.1 (2026-11-17): đo lường mở rộng

### Thêm
- `docs/RESULTS.md`: 5 KOC kèm lý do, trích dẫn video có mốc giây, điểm, phí, chi phí và thời gian từng giai đoạn (`scripts/results_doc.py`).
- Đánh giá thủ công mù (`docs/eval/`): phiếu 30 video, 10 KOC, 46 trích dẫn; tiêu chí ghi trước; `scripts/eval_sheets.py` và `scripts/eval_metrics.py` tính Precision@5, nDCG@5, độ đúng bằng chứng, độ đồng thuận hợp thương hiệu, vi phạm yêu cầu cứng, KOC bị bỏ sót.
- Kết quả vòng đầu: trích dẫn 26/29 đúng, 0 bịa; đồng thuận video 23/28; Precision@5 1/5 (chấm mù); 2/5 KOC tốt bị bỏ sót.
- `docs/LIMITATIONS.md` và slide "Giới hạn", slide "Người chấm mù so với AI".
- README: kiến trúc, quyết định chính, giới hạn, hướng mở rộng, đánh giá chất lượng và cách dựng golden dataset, cấu trúc repo, bảng bàn giao.
- Ghi chú "điểm tính theo trọng số cũ" trên mọi trang hiện điểm của lượt chạy cũ.

### Đổi
- Trọng số tỷ trọng doanh thu ngành (proxy, gần như ai cũng 100%) về 0; các trọng số S1 còn lại chia lại. Thứ tự top 5 không đổi.
- Điểm độ trung thực tách "Lý do" (0,875) và "Lưu ý"; lưu ý chưa xác minh khán giả không tính.
- Cảnh báo chèn lệnh nhận cả văn bản không dấu, nhiều khoảng trắng, và chạy cả khi đọc từ cache.
- Sắp xếp lại repo: lịch sử xây dựng vào `docs/process/`, khảo sát vào `docs/research/`, hệ thống thiết kế vào `design/system/`.
- Nút "Quay lại" trên trang KOC cùng kiểu với "Về trang chủ".

## 2.0.0 (2026-11-17)

### Thêm
- Liên kết TikTok cho từng KOC và từng video.
- Ô điểm theo ba phần (thương mại, khán giả, nội dung) và mục "Cách chấm điểm".
- Ô "Không hợp thương hiệu": KOC bị cổng brand_fit (dưới 3/5) loại, kèm lý do.
- Thanh lọc và sắp xếp; trên điện thoại là ngăn kéo.
- Ô tìm KOC ở đầu trang, gõ không dấu vẫn tìm được.
- `koc run --dry-run` in ước tính credit, USD, token và thời gian.
- `--exclude-run`: loại KOC đã đề xuất ở lượt trước (CLI và web).
- Cache dữ liệu Kalodata hết hạn sau 7 ngày (`cache_ttl_days`).
- Điểm trung thực của lý do S4 (mô hình thứ hai kiểm từng lý do với bằng chứng).
- Chống prompt injection: bọc dữ liệu bên thứ ba, chặn mã bằng chứng lạ, gắn "Cảnh báo bảo mật".
- Cảnh báo khi web chạy với `--host` khác `127.0.0.1`.

### Đổi
- S3 chọn 3 video đúng chủ đề sản phẩm thay vì 3 video doanh thu cao nhất.
- Ngân sách không còn nằm trong prompt nội dung và khóa cache.
- Phiên bản gói: Python 2.0.0, web 2.0.0. Thêm giấy phép MIT.

## 1.0.0 (2026-11-16)
- Phễu S0 đến S4, web đề xuất và hồ sơ KOC, cổng brand_fit, benchmark.
