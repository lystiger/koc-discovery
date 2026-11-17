# Deck KOC Discovery 2.0

Mở `index.html` trong trình duyệt. Phím mũi tên, PageUp, PageDown hoặc Space chuyển slide. In ra PDF: mỗi slide một trang 1280 x 720.

Thiết kế:
- Bảng màu và font theo `design/system/koc-discovery/MASTER.md` (hướng A "Bản đề xuất"): giấy `#f6f3ee`, mực `#24312b`, xanh `#315f53`, xanh nhạt `#dce8e1`; Newsreader cho tiêu đề, Be Vietnam Pro cho chữ.
- `ui-ux-pro-max` (truy vấn "pitch deck creator marketing editorial") gợi ý mẫu "Scroll-Triggered Storytelling" và kiểu Brutalism. Giữ mẫu kể chuyện theo cuộn; bỏ Brutalism vì trái với hướng đã duyệt.
- Mỗi slide một hình lớn hoặc một con số lớn, tối đa khoảng 20 chữ.

Hình: ảnh chụp E2E trong `assets/e2e/` (cắt ở `assets/e2e/crops/`), linh vật `assets/b-hero.webp` và `assets/mascot.webp`. Không dùng khung hình video có mặt người.

Xuất PDF:

```bash
chromium --headless=new --disable-gpu --virtual-time-budget=5000 --no-pdf-header-footer \
  --print-to-pdf=koc-discovery.pdf "file://$PWD/docs/pitch/index.html"
```

Deck v1.0 (14 slide, có khối số liệu `DECK_DATA`) vẫn xem được ở tag `v1.0`.
