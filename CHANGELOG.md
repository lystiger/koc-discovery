# Changelog

## 2.0.5 (2026-11-17): Docker

### Thêm
- `Dockerfile` hai tầng (Node 20 build web, Python 3.12 slim) và `scripts/docker-entrypoint.sh`: `web` mở lượt demo, `test` chạy kiểm thử, lệnh khác chạy trực tiếp (`koc run --mock`). Không cần khóa API; kiểm thử chạy được với `--network none`.
- README: Docker là cách nhanh nhất trong mục "Cho người chấm".
- Slide 17 "Có cần AI xem video không?": so A, B, C, C' và độ khớp người chấm của từng tín hiệu.

### Sửa (sau 3 vòng review độc lập)
- `data/demo.db` chỉ giữ 30 video và 30 phân tích của lượt, chỉ các trường web dùng; không còn đường dẫn khung hình; script dừng khi thấy số điện thoại hoặc đường dẫn máy.
- Kiểm tra xuất bản đọc toàn bộ bản dump của `demo.db` trước khi tìm dữ liệu riêng tư.
- Cách C chỉ được báo khi chấm chân dung đủ mọi video; C và C' giữ luật loại KOC cũ và không trùng MCN như B.
- Chi phí chân dung tính theo nhãn `persona:<lượt>:<video>` trên từng lượt gọi; lượt gọi cũ chưa có nhãn được báo là cận trên.

## 2.0.4 (2026-11-17): hiệu quả chi phí

### Thêm
- `docs/eval/COST_EFFICIENCY.md` và `scripts/compare_approaches.py`: so cách A (chỉ số liệu thương mại, không mô hình), B (pipeline hiện tại), C (persona-fit, chưa chạy) trên cùng 10 KOC đã chấm. Precision@5 chấm mù: A 2/5, B 1/5; A tốn 11,5 credit và 0 USD, B 26,0 credit và 0,43 USD.
- Cách C: `koc persona --run <id>` chấm độ hợp chân dung (`audience_persona_fit`, prompt `persona_v1`) cho từng video đã phân tích, lưu bảng `persona_fit`. Điểm chân dung khớp người chấm nhất (Spearman 0,65 chấm mù; điểm cuối B 0,48), nhưng C giữ cổng không hơn B; C' cổng mềm bằng A. 30 video, 0,28 USD.
- Ghi rõ đánh đổi recall của dự báo 500 ứng viên, và công thức chi phí chiến dịch (dữ liệu + mô hình + máy + người duyệt).

## 2.0.3 (2026-11-17): chạy được không cần khóa

### Thêm
- `data/demo.db`: lượt chạy `0e555cac` cho người chấm xem trong web, không cần khóa API. Tạo bằng `scripts/make_demo_db.py`: bỏ cache Kalodata và LLM, tiểu sử creator, đường dẫn video trên máy, lỗi task; dừng nếu thấy email, khóa hoặc đường dẫn máy.
- README mục "Cho người chấm": xem kết quả, chạy kiểm thử, chạy giả lập, chạy thật.

### Sửa
- Chế độ `--mock` gán tên giả `koc1`, `koc2`... thay vì dùng handle và tên của một creator thật cho mọi KOC.
- Khung hình không có file thì không hiện ảnh hỏng.
- Liên kết tới log không công khai trong `docs/GUIDE.md`.

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
