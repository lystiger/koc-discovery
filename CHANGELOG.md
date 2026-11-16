# Changelog

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
