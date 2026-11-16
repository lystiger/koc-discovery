# Bằng chứng sửa UI web6

## Quyết định giao diện

- Phong cách: Data-Dense Dashboard, theo kết quả UI/UX Pro Max.
- Màu: giữ token hiện có: xanh chính #1E40AF, xanh phụ #3B82F6, hổ phách #D97706, nền #F8FAFC.
- Chữ: giữ system-ui và ui-monospace của ứng dụng.

## Ánh xạ phát hiện

| Phát hiện | Kết quả | Vị trí |
|---|---|---|
| P1.1 Thanh điểm và khán giả trên hồ sơ creator không có màu nền | Thêm background #1E40AF trực tiếp cho thanh rubric và nhân khẩu học. | src/koc/web/charts.py:137 |
| P1.2 Tiêu đề vòng cuối ghi 15 dù bảng chỉ có 6 hàng | Dùng finalists length cho tiêu đề; giá trị lấy từ danh sách dùng để render bảng. | src/koc/web/templates/top5.html:54 |
| P1.3 Bảng thời gian bị cắt trên màn hình nhỏ | Thêm gợi ý vuốt ngang; bảng nằm trong vùng cuộn. | src/koc/web/templates/dashboard.html:24; src/koc/web/templates/base.html:168 |
| P1.4 Thẻ video tràn ở 375 px | Cho cột video về minmax(0, 1fr) và đặt min-width: 0 cho cột con. | src/koc/web/templates/base.html:139,164 |
| P1.5 USD bị làm tròn thành 0,1 | Dùng tối đa 4 chữ số thập phân, tối thiểu 2; giá trị biểu đồ và KPI cùng định dạng $0,0756 / $5,00. | src/koc/web/app.py:67; src/koc/web/charts.py:19,60 |
| P2.6 Mũi tên sắp xếp không hoạt động | Gỡ quy tắc CSS và lớp sortable; test xác nhận không còn mũi tên. | src/koc/web/templates/base.html:86; tests/web/test_app.py:252 |
| P2.7 Chỉ dấu nguồn quá nhỏ | Đặt cỡ chữ .75rem. | src/koc/web/templates/base.html:118 |
| P2.8 Chữ nguồn, điểm thành phần, avatar dưới 11 px | Đặt nguồn .75rem, điểm .72rem, avatar .75rem; bỏ mức chữ nhỏ hơn ở breakpoint 420 px. | src/koc/web/templates/base.html:90,96,137,180 |
| P2.9 Nhãn trục cuối của biểu đồ phân tán bị cắt | Cho SVG co theo vùng chứa và thu plot để chừa khoảng cho nhãn cuối. | src/koc/web/templates/base.html:71; src/koc/web/charts.py:110 |
| P2.10 Tên trợ năng của biểu đồ nói 15 ứng viên | Dùng số hàng thực tế của biểu đồ trong SVG title. | src/koc/web/charts.py:125 |
| P2.11 Biểu đồ trọng số thiếu chú giải | Thêm chú giải ba màu, khớp với các thành phần điểm. | src/koc/web/templates/top5.html:18; src/koc/web/templates/base.html:75 |
| P2.12 Nhãn giai đoạn lặp mã S0–S4 | Bảng dùng trực tiếp nhãn name_vi. | src/koc/web/templates/dashboard.html:13 |
| P2.13 Điểm tương quan dùng dấu chấm | Định dạng theo dấu phẩy thập phân. | src/koc/web/templates/dashboard.html:26 |
| P2.14 Nội dung mẫu có tuyên bố an toàn và seeding không có căn cứ | Sửa bio, lời thoại mẫu và nhận xét rubric trong fixture web. | tests/web/fixtures/seed.py:107,407,455 |
| P3.15 Nhãn placeholder khung hình lặp | Hiển thị lời nhắc một lần mỗi video; bỏ câu lặp khỏi chú thích từng khung. | src/koc/web/templates/creator.html:58,65 |
| P3.16 Ảnh giả xám trông như ảnh hỏng | Với run giả lập, thay ảnh rỗng bằng nền sọc trung tính; nhãn hiện một lần mỗi video. Run thật vẫn dùng ảnh khung hình. | src/koc/web/templates/base.html:123; src/koc/web/templates/creator.html:16,64 |
| P3.17 Chú thích lặp lại số liệu | Bỏ chú thích phần trăm khán giả và chú thích điểm trọng số bị lặp. | src/koc/web/templates/creator.html:50; src/koc/web/templates/top5.html:18 |
| P3.18 Tên cột điểm không khớp trục | Đổi thành Điểm trên 5. | src/koc/web/templates/creator.html:74 |
| P3.20 Nhãn trợ năng chi phí dùng số thô | Định dạng số tiền và ký hiệu ₫. | src/koc/web/charts.py:116-117 |

P3.19 giữ thuật ngữ quen dùng trong giao diện.

## Kiểm chứng

- PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/web/test_app.py -k 'creator_has_demographic or finalists_heading or usd_format or dashboard_mobile': 5 passed.
- PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m compileall -q src/koc/web tests/web: pass.
- Toàn bộ tests/web: UNPROVEN. Bộ test dừng ở test_routes_200_on_fixture_db, chờ trong starlette.testclient.py:407; stack trace cho thấy AnyIO portal vẫn chờ. Đây là giới hạn môi trường test.
- Ảnh chụp trình duyệt 375/1440 chưa chạy theo yêu cầu; orchestrator sẽ chụp và kiểm tra sau.
