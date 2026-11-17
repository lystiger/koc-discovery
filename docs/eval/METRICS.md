# Đánh giá thủ công, lượt `0e555cac95fb4fb49168410e40ea92d5`

Người chấm: người xây hệ thống (không độc lập). Chấm video và KOC trước khi xem điểm hệ thống.

| Chỉ số | Kết quả | Mục tiêu |
|---|---|---|
| Precision@5 (chỉ tính "có") | 2/5 | ≥ 4/5 |
| Precision@5 ("có điều kiện" = 0,5) | 2.5/5 | ≥ 4/5 |
| nDCG@5 trong 5 KOC được chọn | 0.99 | ≥ 0,85 |
| nDCG@5 so với cả 10 KOC đã phân tích | 0.77 | ≥ 0,85 |
| Độ đúng bằng chứng (29/46 mục đã kiểm) | 95% | ≥ 95% |
| Đồng thuận hợp thương hiệu, lệch ≤ 1 điểm (28 video) | 79% | ≥ 80% |
| Đồng thuận hợp thương hiệu, cùng phía ngưỡng 3 | 82% | ≥ 80% |
| Sai lệch trung bình người và AI | 1.18 điểm | |
| Vi phạm yêu cầu cứng (code) | 0/3 kiểm được | 0 |
| Vi phạm yêu cầu cứng (người chấm: KOC không có video nào ≥ 3) | 0/5 | 0 |
| Khán giả nữ 18–30 | không xác minh được (gói Kalodata không có dữ liệu khán giả) | xác minh |
| Ngân sách khả thi | không xác minh được (giá ước tính theo bậc follower, chưa hỏi KOC/MCN) | xác minh |
| Bỏ sót: KOC không được chọn nhưng người chấm thấy phù hợp | 2/5 | 0 |
| Bỏ sót do cổng hợp thương hiệu (người chấm có video ≥ 3) | 1/4 | 0 |
| Recall trong 10 KOC đã phân tích | 50% | |

## Kiểm tra bằng code

| Yêu cầu | Đạt | Chi tiết |
|---|---|---|
| Số KOC = brief | đạt | 5 / 5 |
| Tổng phí ≤ ngân sách | đạt | 28.500.000 / 30.000.000 đ |
| Không trùng MCN | không rõ | 0/5 KOC có mã MCN: không rõ, dữ liệu đã lưu không có mã MCN |
| Mỗi KOC có video AI chấm hợp thương hiệu ≥ 3 | đạt | cổng D-B7 |

## KOC bị bỏ sót

- @cleanboy.tips (bị cổng loại)
- @ducvietbe__
- @dunghana2882

Recall@10 trên toàn bộ 200 ứng viên chưa đo: cần gán nhãn cả nhóm ứng viên. Chỉ đo được trong các KOC đã phân tích video.

## Chấm mù và chấm sau khi biết kết quả

Người chấm đổi @meixiuriviu từ 1 (không) lên 3 (có) ở bước 3, sau khi đã biết KOC này được chọn. Bảng trên dùng điểm sau khi đổi. Điểm mù ban đầu cho:

| Chỉ số | Chấm mù | Sau khi đổi |
|---|---|---|
| Precision@5 (chỉ tính "có") | 1/5 | 2/5 |
| Precision@5 ("có điều kiện" = 0,5) | 1,5/5 | 2,5/5 |
| nDCG@5 trong 5 KOC được chọn | 0,84 | 0,99 |
| nDCG@5 so với cả 10 KOC | 0,59 | 0,77 |
| Recall trong 10 KOC đã phân tích | 1/3 | 2/4 |

## Bằng chứng

29 trích dẫn từ video (19 lời nói, 10 khung hình) được người mở đúng giây để kiểm: 26 đúng, 3 đúng một phần, 0 sai. Ba mục một phần: hai câu ghi "mấy bà" thay vì từ lóng "mấy vợ", một khung hình gọi giấy thấm dầu là "giấy ăn". Không có trích dẫn nào bịa. 17 số liệu Kalodata không được người kiểm (cần đăng nhập Kalodata); chúng được đọc thẳng từ phản hồi API đã lưu.
