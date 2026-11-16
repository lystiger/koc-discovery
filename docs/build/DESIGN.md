# Hệ thiết kế KOC Discovery

## Hướng giao diện

- **Chế độ:** Operate. UI phục vụ marketer và agency rà creator, điểm, bằng chứng, chi phí và tiến độ.
- **Phong cách:** Data-Dense Dashboard. Dùng KPI, biểu đồ, bảng dữ liệu, lưới gọn và nền sáng.
- **Tham chiếu bố cục:** Kalodata và FastMoss chỉ dùng làm tham chiếu cho cách tổ chức dashboard thương mại điện tử. Không dùng logo, tên, màu thương hiệu hoặc tài sản của họ.
- **Thiết kế:** Một giao diện dùng chung cho mọi trang. Không có bộ chọn giao diện, cookie giao diện hoặc `?theme`.
- **Thiết bị:** Sidebar trái trên màn hình rộng. Sidebar chuyển thành thanh điều hướng trên đầu trang dưới 768 px. Nội dung biểu đồ co theo khung; bảng dùng vùng cuộn ngang khi cần.

## Token

| Vai trò | Giá trị |
|---|---|
| Primary | `#1E40AF` |
| Secondary | `#3B82F6` |
| Accent | `#D97706` |
| Background | `#F8FAFC` |
| Card | `#FFFFFF` |
| Foreground | `#1E3A8A` |
| Muted foreground | `#475569` |
| Muted | `#E9EEF6` |
| Border | `#DBEAFE` |
| Destructive | `#B91C1C` |
| Thành công | `#166534` |
| UI | system sans: `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif |
| Số liệu | `ui-monospace`, `SFMono-Regular`, `Consolas`, monospace; bật `tabular-nums` |
| Bo góc | 4–7 px |
| Khoảng đệm | 8–16 px cho thẻ và bảng; 12–32 px cho khung trang |

Giao diện luôn sáng. Không tải font, JavaScript, biểu đồ hoặc ảnh đại diện từ mạng. Avatar dùng chữ cái đầu tên creator.

## Bố cục

- Điều hướng trái: **Đợt chạy**, **Đề xuất**, **Vận hành**. Trên màn hẹp, các liên kết nằm trên đầu trang.
- Thanh đầu trang: bộ chọn đợt chạy và mô tả chiến dịch.
- Trang đề xuất: KPI, biểu đồ đóng góp điểm, biểu đồ chi phí và điểm, bảng 5 creator, bảng vòng cuối.
- Trang vận hành: KPI, phễu S0–S4, mức dùng hạn mức, tác vụ, thời gian và đối chiếu điểm.
- Trang creator: hồ sơ, điểm, lý do có liên kết bằng chứng, chỉ số, nhân khẩu học, video và rubric.
- Bảng giữ hàng gọn, tiêu đề gợi ý khả năng sắp xếp. Trên 375 px, bảng có thể cuộn trong khung mà không làm tràn trang.

## Biểu đồ

Biểu đồ được dựng phía máy chủ bằng HTML/CSS và SVG. Không dùng thư viện biểu đồ JavaScript.

1. Phễu thể hiện số ứng viên sau từng bước S0–S4.
2. Thanh bullet so sánh credit Kalodata với hạn mức 100 và chi phí Gemini với hạn mức 5 USD.
3. Thanh ngang xếp chồng thể hiện điểm đóng góp: thương mại 45, khán giả 20, nội dung 35.
4. Scatter thể hiện chi phí ước tính và điểm cuối của tối đa 15 ứng viên. Năm creator được chọn dùng màu amber. Ngân sách 30.000.000 ₫ hiện cạnh biểu đồ.
5. Hồ sơ creator thể hiện tỷ lệ giới tính, nhóm tuổi và 7 tiêu chí rubric của từng video.

Biểu đồ thanh dùng HTML/CSS để giữ cỡ chữ theo CSS pixel ở mọi khung rộng. Scatter dùng SVG 720 × 265 px trong vùng cuộn ngang, có nhãn trục theo đơn vị và domain sát dữ liệu. Biểu đồ có tên và mô tả hỗ trợ truy cập; giá trị luôn hiện bằng chữ. Nội dung quan trọng không phụ thuộc vào màu.

Trên màn hình dưới 768 px, thứ hạng KOC dùng thẻ dọc để lý do và lưu ý tự xuống dòng. Bảng vòng cuối vẫn cuộn ngang để giữ đủ cột dữ liệu.

## Ngôn ngữ và dữ liệu

- Mọi nội dung giao diện dùng tiếng Việt, viết câu ngắn, sentence case, không emoji và không lời đệm.
- Chi phí luôn ghi **ước tính**.
- Run mô phỏng luôn hiện banner **GIẢ LẬP**.
- Marker bằng chứng `[n]` trỏ tới hàng chỉ số hoặc khung hình có `id` tương ứng.
- Điểm là mức phù hợp, không phải xác suất thành công.

## Nguồn thiết kế

- Lystiger cung cấp yêu cầu Data-Dense Dashboard, token màu, bố cục, biểu đồ và các ràng buộc ở yêu cầu web5.
- UI UX Pro Max `search.py "KOC creator analytics SaaS dashboard" --design-system` trả về phong cách Data-Dense Dashboard. Giữ system sans theo yêu cầu không tải tài nguyên mạng.
- Impeccable Operate và craft floor được đọc. Engine 0.1.22 không chạy do thiếu quyền mạng và ghi cache; phần tự động của Impeccable là **UNPROVEN**.

## React brand platform direction (B12)

The selected style is the editorial proposal direction in `design/taste/a-ban-de-xuat.html`.
It overrides the legacy D2 palette and typography below for the React brand platform.

| Token | Color | Use |
|---|---|---|
| Ground | `#F6F3EE` | Page background |
| Paper | `#FFFDF9` | Content surfaces |
| Ink | `#1F2A24` | Main text |
| Secondary ink | `#55605A` | Supporting text |
| Line | `#E3DDD3` | Borders |
| Green | `#2F5D50` | Primary actions and spent budget |
| Soft green | `#DCE8E2` | Calm emphasis |
| Clay | `#B5643C` | Remaining budget |
| Soft clay | `#F3E3D8` | Remaining-budget hatch |
| Amber | `#8A5A00` | Caution |
| Soft amber | `#FBEFD6` | Caution surface |

Headings use **Newsreader**. Body copy uses **Be Vietnam Pro**. Numbers use tabular figures.

## Coherence round (B21, 2026-11-16)

Keep the approved landing direction across every route: editorial paper surfaces, deep green actions,
Newsreader 600 titles with green italic emphasis, Be Vietnam Pro body text, pill primary actions,
text-link secondary actions, and the three illustrated steps. The required ui-ux-pro-max search
(`creator discovery campaign platform SaaS editorial --design-system`) returned an OLED dark theme
and Inter pairing, which conflict with B21; that result is unusable. B21 remains the design source.

Tài liệu thiết kế giao diện cho KOC Discovery MVP (Deliverable D2).  
Cơ sở tham chiếu: `~/.claude/skills/ui-ux-pro-max/SKILL.md` và kết quả tìm kiếm `--design-system` ngày 2026-11-15.
