# Bằng chứng rebuild giao diện web

## Thay đổi

- Thay giao diện mẫu thẻ nặng và màu hồng bằng ba giao diện có thể chọn qua `?theme=a|b|c`. Cookie `theme` lưu lựa chọn một năm. Mặc định là `a`.
- Thêm bộ token sáng/tối theo ba hướng, điều hướng đổi giao diện, bố cục gọn trên điện thoại và banner `GIẢ LẬP` nhỏ trên mọi trang run giả lập.
- Viết lại trang đề xuất, hồ sơ KOC, vận hành và danh sách đợt chạy. Hồ sơ dùng khung hình video hiện có. Mã bằng chứng trỏ tới đúng hàng hoặc khung hình.
- Đổi mọi run fixture sang `mock: true`; bỏ `prod` khỏi mã run. Thêm test cho tất cả run fixture và banner trên đề xuất, hồ sơ, vận hành.
- Viết lại `DESIGN.md` và tạo trang so sánh ba hướng tại `docs/process/build/shots/index.html`.

## Kiểm tra

- `py_compile` cho app, adapter, fixture và test: đạt.
- `git diff --check`: đạt.
- Kiểm tra render trực tiếp không qua socket: đạt. Có 2 run giả lập và 18 tổ hợp trang/giao diện. Mã liên kết bằng chứng đều tồn tại; cookie chọn giao diện `c`.
- `pytest -q tests/web`: chưa có kết quả. Lệnh dừng khi test đầu tiên gọi `TestClient`. Chạy lại với giới hạn 8 giây, pytest thu thập 7 test rồi dừng tại `test_routes_200_on_fixture_db`, mã thoát 124. Một app FastAPI tối giản cũng treo trong `starlette.testclient.py:407`, chờ phản hồi ASGI. Đây là giới hạn kiểm thử của môi trường, không phải kết quả xanh.
- Lệnh máy chủ tại cổng 8766 không bind được. Python báo `PermissionError: [Errno 1] Operation not permitted` khi bind localhost.
- Chromium không chụp được ảnh. Chromium dừng với `setsockopt: Operation not permitted (1)` ở socket crashpad. Đã thử `--headless=new` và `--headless=old`.
- Do đó ảnh render mới ở 375 px và 1440 px chưa được tạo hoặc xem. Các ảnh cũ trong thư mục vẫn là ảnh giao diện trước rebuild. 18 ảnh dưới đây đều **UNPROVEN**.

## Ảnh cần chụp

Mỗi trang cần ảnh 375 px và 1440 px bằng Chromium khi chạy trong môi trường cho phép localhost và crashpad.

| Hướng | Đề xuất | Hồ sơ KOC | Vận hành |
|---|---|---|---|
| a | `a_top5_375.png`, `a_top5_1440.png` · UNPROVEN | `a_creator_375.png`, `a_creator_1440.png` · UNPROVEN | `a_dashboard_375.png`, `a_dashboard_1440.png` · UNPROVEN |
| b | `b_top5_375.png`, `b_top5_1440.png` · UNPROVEN | `b_creator_375.png`, `b_creator_1440.png` · UNPROVEN | `b_dashboard_375.png`, `b_dashboard_1440.png` · UNPROVEN |
| c | `c_top5_375.png`, `c_top5_1440.png` · UNPROVEN | `c_creator_375.png`, `c_creator_1440.png` · UNPROVEN | `c_dashboard_375.png`, `c_dashboard_1440.png` · UNPROVEN |

## Tự đánh giá

- **a · Bảng tin tài chính:** Serif, số tabular và đường kẻ tạo nhịp báo cáo. Danh sách xếp hạng vẫn dễ quét. Rủi ro là độ tương phản giữa sắc ngà và chữ phụ cần đo trên ảnh thật.
- **b · Công cụ phân tích:** Bảng và số gọn giúp so sánh nhanh. Màu trạng thái có ý nghĩa. Rủi ro là lượng thông tin dày có thể chật ở 375 px; chưa xem ảnh để xác nhận.
- **c · Hồ sơ thương hiệu:** Ảnh khung hình lớn đặt cạnh hồ sơ, nền ấm và màu mận đất tạo cảm giác khác biệt. Ảnh fixture hiện là khung hình minh họa có chữ, không phải ảnh chân dung KOC. Cần xem render và thay bằng khung hình thật khi có dữ liệu thật.

## Commit

Chưa commit được. `git add` không tạo được `index.lock` trong gitdir dùng chung vì filesystem báo `Read-only file system`. Không có merge hoặc deploy.
