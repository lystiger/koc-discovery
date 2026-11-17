# Cách chấm tay

Mục đích: kiểm tra xem 5 KOC hệ thống chọn có thật sự hợp không, và hệ thống có bỏ sót KOC tốt không. Bạn là người xây hệ thống, nên chấm **mù**: không mở web, `docs/RESULTS.md` hay điểm hệ thống cho đến khi xong bước 2.

Thời gian: khoảng 2 giờ. 30 video × 2–3 phút, 10 KOC × 2 phút, 46 bằng chứng × 30 giây.

## Trước khi bắt đầu

Viết ra 3 dòng, không sửa sau khi đã chấm:

1. Brief: kem chống nắng, khán giả nữ 18–30, 30 triệu cho 5 KOC.
2. "Phù hợp" với tôi nghĩa là: ...
3. Điều làm tôi loại một KOC ngay: ...

## Bước 1: chấm 30 video (`1_videos.csv`)

Thứ tự đã xáo trộn; video của KOC được chọn và không được chọn lẫn với nhau. Mở link, xem tối thiểu 30 giây đầu. Điền `your_score_1_5`:

| Điểm | Nghĩa |
|---|---|
| 1 | Không liên quan chống nắng hay chăm sóc da (đồ ăn, thời trang, dầu gội nam...) |
| 2 | Chăm sóc da nhưng không phải chống nắng, hoặc kem chống nắng chỉ thoáng qua |
| 3 | Có giới thiệu kem chống nắng, nhưng hời hợt: đọc quảng cáo, không thử, không giải thích |
| 4 | Review kem chống nắng rõ: thoa thử, nói kết cấu hoặc chỉ số SPF/PA, có lời kêu gọi mua |
| 5 | Như 4, thêm đáng tin: so sánh, test thật (giấy thấm dầu, trước/sau), người xem nữ trẻ rõ ràng |

Chấm theo độ hợp **thương hiệu kem chống nắng**, không phải video hay hay dở. Ghi chú 1 câu vào `note` khi điểm là 1, 2 hoặc 5.

## Bước 2: chấm 10 KOC (`2_koc.csv`)

Sau bước 1. Mở trang TikTok của KOC, lướt 10–15 video gần nhất, dùng thêm điểm video ở bước 1.

- `your_verdict_co_dieukien_khong`: `co`, `dieukien` hoặc `khong`. "Có điều kiện" là bạn sẽ chọn nếu thêm một điều kiện (kịch bản do nhãn hàng duyệt, giá dưới mức X...). Viết điều kiện vào `reason`.
- `your_grade_0_3`: 0 không hợp, 1 tạm, 2 tốt, 3 rất tốt. Dùng để tính thứ hạng (nDCG).
- Không đoán khán giả: TikTok không cho xem tuổi, giới tính người xem. Chỉ dùng điều bạn thấy (bình luận, cách nói, sản phẩm thường làm).

## Bước 3: kiểm bằng chứng (`3_evidence.csv`)

Làm sau cùng, vì file này lộ 5 KOC được chọn. Mỗi dòng là một điều hệ thống trích để biện minh.

- `speech` và `frame`: mở video ở mốc giây trong `where_to_check`. Câu nói hoặc khung hình đó có đúng như `claim` không?
- `metric`: mở trang Kalodata của KOC (cần đăng nhập). Bỏ qua nếu không mở được; để trống thì không tính.
- Điền `dung` (đúng ý và đúng chỗ, lệch vài giây vẫn tính), `motphan` (đúng ý nhưng sai chi tiết, hoặc diễn giải quá), `sai` (không có, hoặc sai nghĩa).

Lưu ý: `skincare_revenue_share = 1.0` đúng với dữ liệu nhưng dữ liệu là proxy. Chấm `dung` nếu khớp Kalodata và ghi "proxy" vào `note`.

## Bỏ sót (false negative)

Không cần làm thêm: 5 KOC không được chọn nằm sẵn trong bước 1 và 2. Script tính hai loại bỏ sót:

- **KOC bị bỏ sót**: bạn chấm `co` cho một KOC không được chọn.
- **Bỏ sót do cổng**: hệ thống loại KOC vì video tốt nhất dưới 3/5, nhưng bạn chấm một video của KOC đó từ 3 trở lên.

Mỗi trường hợp bỏ sót, ghi vào `reason` vì sao bạn thấy KOC đó hợp. Đây là dữ liệu để sửa cổng hoặc cách chọn video.

Giới hạn: chỉ đo được trong 10 KOC đã phân tích video. KOC bị loại ở bước thương mại (40 → 10) chưa được đo.

## Tính kết quả

```bash
PYTHONPATH=src .venv/bin/python scripts/eval_metrics.py --run 0e555cac95fb4fb49168410e40ea92d5
```

Ghi ra `docs/eval/METRICS.md`. Có thể chạy khi mới chấm một phần; mục chưa chấm hiện "chưa chấm".

## Cách đọc

| Chỉ số | Đạt khi | Nếu không đạt, nói gì |
|---|---|---|
| Precision@5 | ≥ 4/5 | KOC nào bạn không chọn và vì sao |
| nDCG@5 trong 5 KOC | ≥ 0,85 | Thứ hạng trong danh sách lệch |
| nDCG@5 so với 10 KOC | ≥ 0,85 | Có KOC không được chọn tốt hơn KOC được chọn |
| Độ đúng bằng chứng | ≥ 95% | Bằng chứng nào sai: lỗi đọc video hay mô hình bịa |
| Đồng thuận hợp thương hiệu | ≥ 80% | AI chấm cao hay thấp hơn bạn |
| Vi phạm yêu cầu cứng | 0 | Yêu cầu nào |
| Khán giả, giá thật | luôn "không xác minh được" | Cần dữ liệu khán giả và báo giá thật |

Một người chấm, 5 KOC, 30 video là mẫu nhỏ: báo cáo số đếm (4/5, 26/30), không chỉ phần trăm. Nếu có người thứ hai chấm 10 video, ghi độ lệch giữa hai người.
