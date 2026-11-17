# Hiệu quả chi phí: ba cách chọn KOC, lượt `0e555cac95fb4fb49168410e40ea92d5`

Cùng brief (kem chống nắng, 30.000.000 đ, 5 KOC), cùng người chấm, cùng 10 KOC đã chấm ([2_koc.csv](2_koc.csv)). Cả 5 KOC mà A chọn đều nằm trong 10 KOC đã chấm, nên không cần chấm thêm.

- **A, chỉ số liệu thương mại**: 15 KOC điểm thương mại (S1) cao nhất, chọn 5 KOC có tổng điểm S1 lớn nhất trong ngân sách. Không gọi mô hình, không xem video.
- **B, pipeline hiện tại**: thêm khán giả (S2), phân tích 3 video mỗi KOC bằng mô hình đa phương thức (S3), cổng hợp thương hiệu, chọn theo điểm cuối.
- **C, B thêm độ hợp chân dung**: mỗi video B đã phân tích được chấm thêm `audience_persona_fit` 1–5 (tuổi ước chừng, phong cách, cách xưng hô so với khán giả mục tiêu; [prompt](../../prompts/persona_v1.md)). Điểm cuối = (45 thương mại + 20 chân dung + 35 nội dung) / 100; cổng hợp thương hiệu và cách chọn trong ngân sách giữ nguyên. Phân tích video của B dùng lại nguyên vẹn, nên C chỉ khác B ở trọng số chân dung.
- **C', C với cổng mềm hơn**: KOC có video tốt nhất 2/5 vẫn qua cổng nếu điểm chân dung ≥ 80 (trung bình ≥ 4/5). Luật này đặt ra sau khi biết người chấm chọn thế nào: chỉ là tham khảo, thiên vị về phía người chấm này.

## Chấm mù

| Cách | Precision@5 ("có") | Precision@5 ("có điều kiện" = 0,5) | nDCG@5 so với 10 KOC | Thời gian lượt đầy đủ | Credit Kalodata | Chi phí mô hình |
|---|---:|---:|---:|---:|---:|---:|
| A | 2/5 | 2/5 | 0,77 | 4 phút | 11,5 | 0,00 USD |
| B | 1/5 | 1,5/5 | 0,59 | 43 phút | 26,0 | 0,43 USD |
| C | 1/5 | 1,5/5 | 0,54 | ≤ 47 phút | 26,0 | ≤ 0,71 USD |
| C' (cổng mềm, tham khảo) | 2/5 | 2,5/5 | 0,73 | ≤ 47 phút | 26,0 | ≤ 0,71 USD |
| Chọn ngẫu nhiên 5 trong 10 KOC (kỳ vọng) | 1,5/5 | | | | | |

## Sau khi người chấm đổi @meixiuriviu

| Cách | Precision@5 ("có") | Precision@5 ("có điều kiện" = 0,5) | nDCG@5 so với 10 KOC | Thời gian lượt đầy đủ | Credit Kalodata | Chi phí mô hình |
|---|---:|---:|---:|---:|---:|---:|
| A | 3/5 | 3/5 | 0,80 | 4 phút | 11,5 | 0,00 USD |
| B | 2/5 | 2,5/5 | 0,77 | 43 phút | 26,0 | 0,43 USD |
| C | 2/5 | 2,5/5 | 0,73 | ≤ 47 phút | 26,0 | ≤ 0,71 USD |
| C' (cổng mềm, tham khảo) | 3/5 | 3,5/5 | 0,90 | ≤ 47 phút | 26,0 | ≤ 0,71 USD |
| Chọn ngẫu nhiên 5 trong 10 KOC (kỳ vọng) | 2/5 | | | | | |

## KOC mỗi cách chọn

| # | A | B | C | C' |
|---|---|---|---|---|
| 1 | @rio100806 | @meixiuriviu | @meixiuriviu | @meixiuriviu |
| 2 | @ducvietbe__ | @rio100806 | @rio100806 | @rio100806 |
| 3 | @cleanboy.tips | @dieuduong_quynhhoa | @dieuduong_quynhhoa | @ducvietbe__ |
| 4 | @meixiuriviu | @emduyencantho | @teetamofficial | @dieuduong_quynhhoa |
| 5 | @gaixinhh114 | @teetamofficial | @k_dung26 | @teetamofficial |

## Độ hợp chân dung so với người chấm

Mô hình `google/gemini-3.8-flash`. Chi phí là cận trên: 31 lượt gọi, 0,2797 USD, gồm 31 lượt gọi persona cùng mô hình ghi trước khi có nhãn lượt chạy, không chứng minh được thuộc lượt này. Điểm chân dung = trung bình 3 video × 20.

| KOC | Chân dung (0–100) | Người chấm (0–3, mù) | Qua cổng hợp thương hiệu |
|---|---:|---:|---|
| @dunghana2882 | 100 | 3 | không |
| @ducvietbe__ | 93 | 3 | không |
| @meixiuriviu | 93 | 1 | có |
| @rio100806 | 87 | 3 | có |
| @k_dung26 | 80 | 0 | có |
| @teetamofficial | 73 | 1,5 | có |
| @dieuduong_quynhhoa | 67 | 1 | có |
| @gaixinhh114 | 60 | 1 | không |
| @emduyencantho | 40 | 1 | có |
| @cleanboy.tips | 27 | 0 | không |

Tương quan hạng Spearman giữa điểm chân dung và người chấm trên 10 KOC: 0,65 (chấm mù), 0,80 (sau khi đổi). Gần 1 là chân dung dự đoán đúng thứ tự người chấm; gần 0 là không liên quan. 10 KOC là mẫu rất nhỏ.

| Tín hiệu | Spearman với người chấm (mù) | Sau khi đổi |
|---|---:|---:|
| Thương mại (S1) | 0,25 | 0,34 |
| Nội dung video (S3) | 0,42 | 0,65 |
| Điểm cuối của B | 0,48 | 0,70 |
| Chân dung | 0,65 | 0,80 |

Với cổng giữ nguyên, chỉ 6 KOC qua cổng và ngân sách buộc giữ 2 KOC giá 3 triệu, nên C chỉ đổi được 1 KOC so với B: C không thể có Precision@5 cao hơn B trên lượt này.

## Kết luận về C

- Điểm chân dung khớp người chấm tốt nhất trong mọi tín hiệu đã đo: 4 KOC chân dung cao nhất gồm cả 3 KOC người chấm chọn "có" khi chấm mù (@dunghana2882, @ducvietbe__, @rio100806) và @meixiuriviu ("có" sau khi đổi). Mô hình thấy được tuổi và phong cách từ khung hình và giọng nói.
- Nhưng C (giữ cổng) không tốt hơn B: 2 trong 3 KOC đó bị cổng hợp thương hiệu loại, và C chọn @k_dung26 (chân dung 80, người chấm 0: video thô) thay @emduyencantho. Chân dung đo người, không đo chất lượng video; cần cả hai.
- C' (cổng mềm) đạt bằng A về Precision@5 và nDCG cao nhất sau khi đổi (0,90), nhưng luật cổng mềm được đặt ra sau khi biết người chấm chọn thế nào. @dunghana2882 vẫn không vào vì phí 15 triệu.
- Chi phí thêm của chân dung: khoảng 0,009 USD mỗi video, 0,28 USD cho 30 video, cộng khoảng 4 phút khi chạy tuần tự.
- Việc tiếp theo: giữ chân dung như một thành phần điểm, đổi cổng từ "video phải nói về kem chống nắng" sang "KOC làm chăm sóc da và hợp chân dung", rồi kiểm lại bằng người chấm thứ hai trên một brief mới. Chưa làm: một người chấm, một brief không đủ để đổi luật mặc định.

Phí booking ước tính: A 19.500.000 đ, B 28.500.000 đ, C 28.500.000 đ, C' 24.000.000 đ (chi phí chiến dịch, không phải chi phí phần mềm).

## Cách đọc

- Trên người chấm này, B **không** tốt hơn A. A chọn đúng 2 KOC người chấm muốn (@rio100806, @ducvietbe__) mà không tốn mô hình; B chọn 1 (chấm mù). Lý do đã biết: người chấm chọn theo tuổi và phong cách Gen Z, mà B không đo; điểm nội dung của B kéo các KOC lớn tuổi lên.
- A cũng có lỗi B tránh được: A chọn @cleanboy.tips (kênh nam) và @gaixinhh114 (nhiều loại sản phẩm). Cổng hợp thương hiệu của B loại cả hai, và người chấm cũng loại cả hai.
- Cổng đó cũng loại @ducvietbe__ và @dunghana2882, hai KOC người chấm chọn "có" (video tốt nhất chỉ 2/5 vì ít nói về kem chống nắng). Đây là chỗ B thua A nhiều nhất: cổng đo video, người chấm đo người.
- Giá trị của B hiện nằm ở bằng chứng (26/29 trích dẫn đúng, 0 bịa), không ở thứ hạng. Kết quả của C ở mục "Kết luận về C".
- Mẫu nhỏ: 1 brief, 1 người chấm, 5 KOC, không có tính toán độ bất định. Các chênh lệch ở đây là quan sát trên một người chấm và một brief, không phải kết luận thống kê; hướng cải tiến là giả thuyết cần kiểm trên nhiều brief và người chấm.
- C được thiết kế sau khi biết người chấm chọn thế nào: chấm C bằng chính người chấm này sẽ thiên vị C. Cần người chấm thứ hai hoặc brief giữ kín.

## Chi phí

- Số của A và B lấy từ lượt chạy đầy đủ 200 ứng viên ([BENCHMARK](../BENCHMARK.md)), trên đường thành công. Tính cả lần thử lỗi, B là 27,6 credit và 1,32 USD.
- Chi phí B lấy từ lượt đầy đủ `7372009b`; 5 KOC của B lấy từ lượt `0e555cac` (cùng dữ liệu S0–S2 từ cache, S3 chọn video theo chủ đề). Lượt `0e555cac` chỉ tốn 6,5 credit và 0,28 USD cho S3–S4 nhờ cache.
- A dừng sau S1b: các stage S0–S1b của B chính là A. Phần B trả thêm là S2 (thời gian), S3 (credit tải video và chi phí mô hình) và S4.
- Giá tiền của một credit Kalodata chưa biết, nên chi phí dữ liệu ghi bằng credit.
- Phí booking KOC là chi phí chiến dịch, tách khỏi chi phí vận hành phần mềm.

## Dự báo 500 ứng viên và recall

Dự báo 29,7 credit cho 500 ứng viên rẻ vì chỉ 10 KOC được xem video. KOC tốt nằm ngoài 40 KOC thương mại cao nhất không bao giờ được xem. Tỷ lệ bỏ sót ở bước này chưa đo: cần chấm một mẫu KOC bị loại ở S1.

## Chi phí một chiến dịch khi bán thành sản phẩm

Nhãn hàng mua một danh sách KOC đã được nghiên cứu, không mua token. Chi phí một chiến dịch:

C_chiến dịch = C_dữ liệu (credit Kalodata) + C_mô hình (USD) + C_máy (giờ máy) + C_duyệt (giờ người duyệt bằng chứng)

C_duyệt có thể lớn hơn C_mô hình: kiểm một trích dẫn mất khoảng 30 giây, 46 trích dẫn khoảng 25 phút (ước tính trong [HOW_TO_JUDGE](HOW_TO_JUDGE.md), chưa đo), trong khi C_mô hình của B là 0,43 USD. Giá bán nên theo chiến dịch hoặc theo danh sách, không theo token.
