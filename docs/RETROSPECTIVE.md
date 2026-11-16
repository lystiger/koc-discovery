# Nhìn lại KOC Discovery (v1 đến v2.0)

## Dòng thời gian

| Ngày | Việc |
|---|---|
| 14/11/2026 | Bắt đầu lượt chạy thật đầu tiên: 200 KOC qua phễu S0 đến S4 (xong ngày 15/11). |
| 15/11/2026 | Chốt hướng giao diện "Bản đề xuất"; web React đầu tiên. |
| 16/11/2026 | Cổng hợp thương hiệu, phát hành v1.0. Chốt kế hoạch v2 (A1 đến A8). Chạy lại S3 với video đúng chủ đề. |
| 17/11/2026 | Điểm trung thực, chống prompt injection. Phát hành v2.0. |

## 1. Cách lên kế hoạch

- Hỏi kỹ từng quyết định (grill mode) đến khi Lystiger nói "đồng ý". Kết quả là kế hoạch v2 với 8 tiêu chí nghiệm thu A1 đến A8.
- Mỗi mục đi qua ba giai đoạn: PRETEST viết kịch bản kiểm thử trước, DEV làm trên nhánh riêng, TEST do một người duyệt độc lập (Codex hoặc Agy) chấm ĐẠT, KHÔNG ĐẠT hoặc CHƯA CHỨNG MINH.
- Chỉ gộp nhánh khi ĐẠT. Nhiều mục cần 2 đến 6 vòng duyệt.

## 2. Cách giải

Phễu lọc, bước rẻ chạy trước, bước đắt chạy trên ít KOC:

200 KOC quét, 60 qua chấm nhanh, 40 qua điểm thương mại, 10 qua điểm khán giả, phân tích 3 video mỗi KOC, chọn 5 KOC trong ngân sách.

Điểm cuối = 45% thương mại + 20% khán giả + 35% nội dung. KOC chỉ vào nhóm chọn khi có ít nhất một video hợp thương hiệu từ 3/5. Mô hình viết lý do, nhưng thứ hạng tính bằng mã từ số liệu.

## 3. Vấn đề và cách giải

| Vấn đề | Cách giải |
|---|---|
| Video lạc đề (dầu gội) được chấm cho kem chống nắng | S3 chọn 3 video gần brief nhất. @rio100806 từ bị loại thành hạng 2 với 3 video kem chống nắng. |
| Người duyệt hết lượt hoặc bị giới hạn | Đổi sang người duyệt khác, vẫn giữ cổng ĐẠT. |
| Dữ liệu cache cũ | Dữ liệu Kalodata hết hạn sau 7 ngày; phân tích video giữ nguyên. |
| Lưu ý (caveats) có điểm trung thực thấp | Tách điểm lý do (0,875) và điểm lưu ý (0,10) để thấy rõ chỗ yếu. |
| Tiêu đề hoặc lời nói chứa lệnh chèn | Bọc dữ liệu, chặn mã bằng chứng lạ, giới hạn điểm 0 đến 5, gắn "Cảnh báo bảo mật". |

## 4. Chỉ số thành công

| Chỉ số | Kết quả | Mục tiêu |
|---|---|---|
| Credit Kalodata, cả dự án | 44,4 | dưới 60 |
| Chi phí mô hình, cả dự án | 1,62 USD | dưới 5 USD |
| Chạy lại v2 | 6,5 credit, 0,28 USD | trong khoảng ước tính |
| Kiểm điểm trung thực | 0,017 USD | gần 0 |
| Lý do khớp bằng chứng | 0,875 (teetamofficial 1,00, meixiuriviu 0,875, còn lại 0,833) | cao |
| Lưu ý có trích dẫn | 0,10 | cần cải thiện |
| Báo động nhầm của bộ chống injection | 0 trên 941 tiêu đề và 405 trích dẫn thật | 0 |
| Bài kiểm thử | 556 đạt, 1 bỏ qua | tất cả đạt |
| Tiêu chí A1 đến A8 | 8 / 8 gộp sau khi người duyệt chấm ĐẠT | 8 / 8 |

Phần mã bảo đảm: bọc dữ liệu, danh sách mã bằng chứng, điểm 0 đến 5, thứ hạng từ số liệu. Phần không bảo đảm: mô hình có làm theo lệnh chèn hay không; cảnh báo chỉ giúp phát hiện.

## 5. Cải tiến tiếp

1. Lưu ý phải trích dẫn bằng chứng như lý do, để nâng điểm 0,10.
2. Thử lệnh chèn trên mô hình thật, không chỉ trong kiểm thử offline.
3. Tìm nguồn dữ liệu khán giả ổn định hơn trang Kalodata đọc bằng Chromium.
4. Thêm đăng nhập trước khi đưa web lên bất kỳ máy chủ nào.
5. Hashtag lẫn có dấu và không dấu: gộp khi tìm và khi chọn video.
