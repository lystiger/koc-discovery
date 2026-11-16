# Chuẩn đo KOC Discovery

Lượt chạy `7372009b22764b339fbcf0f3efb4bc4e` · trạng thái `done` · chế độ `chạy thật (live)` · yêu cầu 200 ứng viên.
Số liệu lấy trực tiếp từ bảng `api_calls`, `llm_calls`, `tasks` và `runs.params_json` của đúng lượt chạy này (lọc theo `run_id`); không ước lượng bằng tay.
Giai đoạn S3 chưa được theo dõi đầy đủ trong bảng `run_results` (lượt chạy cũ): cột "đường thành công" của LLM ở giai đoạn đó là ƯỚC TÍNH theo khóa yêu cầu và phiên bản prompt, không phải gán chính xác theo từng lượt gọi.

## 1. Tóm tắt

| Chỉ số | Đường thành công | Tổng thực chi (gồm lần thất bại và sửa lỗi) |
|---|---:|---:|
| Tín dụng Kalodata | 26.00 | 27.60 |
| Token LLM vào | 355,351 | 1,016,946 |
| Token LLM ra | 44,568 | 149,736 |
| USD LLM | 0.4336 | 1.3242 |
| Số lượt gọi không qua cache (gồm cả lượt 0 đồng) | 195 | 307 |

Chênh lệch do lần thử thất bại, sửa lỗi (`_repair`) và kết quả bị thay thế: 1.60 tín dụng, 661,595 token vào, 105,168 token ra, 0.8906 USD (52 lượt gọi Kalodata và 60 lượt gọi LLM không nằm trên đường thành công).
Thời gian chạy là thời gian thực ghi nhận của giai đoạn, gồm mọi lần thử, chờ giới hạn tốc độ và chờ video Kalodata, nên hai bảng dưới có cùng cột thời gian.

## 2. Đường thành công

Chỉ tính các lượt gọi tạo ra kết quả được giữ lại: lượt LLM sinh ra phân tích/đề xuất cuối cùng, video thuộc phân tích cuối cùng, lượt xem S2 của KOC đã hoàn tất.

| Giai đoạn | Thời gian (giây) | Tín dụng | Token vào | Token ra | USD | Số lượt gọi | Cache hit | Ứng viên vào → ra |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 2.8 | 0.20 | 0 | 0 | 0.0000 | 2 | 0 | 200 → 200 |
| S1a | 0.4 | 0.00 | 0 | 0 | 0.0000 | 0 | 0 | 200 → 60 |
| S1b | 225.0 | 11.30 | 0 | 0 | 0.0000 | 114 | 7 | 60 → 40 |
| S2 | 644.4 | 0.00 | 0 | 0 | 0.0000 | 10 | 0 | 40 → 10 |
| S3 | 1581.1 | 14.50 | 335,319 | 41,330 | 0.4065 | 64 | 22 | 10 → 9 |
| S4 | 144.7 | 0.00 | 20,032 | 3,238 | 0.0272 | 5 | 4 | 9 → 5 |
| **Tổng** | 2598.5 | 26.00 | 355,351 | 44,568 | 0.4336 | 195 | 33 | |

## 3. Tổng thực chi

Gồm tất cả lượt gọi của lượt chạy: lần thất bại (`api_error`, `pending`), lượt sửa lỗi (`prompt_version` kết thúc bằng `_repair`), kết quả bị thay thế bởi phiên bản prompt sau, video đã tải nhưng không vào phân tích cuối. Lượt `pending` giữ chỗ 0.1 tín dụng vẫn tính vào tổng để không ẩn chi phí.

| Giai đoạn | Thời gian (giây) | Tín dụng | Token vào | Token ra | USD | Số lượt gọi | Cache hit | Ứng viên vào → ra |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 2.8 | 0.20 | 0 | 0 | 0.0000 | 2 | 0 | 200 → 200 |
| S1a | 0.4 | 0.00 | 0 | 0 | 0.0000 | 0 | 0 | 200 → 60 |
| S1b | 225.0 | 11.40 | 0 | 0 | 0.0000 | 116 | 7 | 60 → 40 |
| S2 | 644.4 | 0.00 | 0 | 0 | 0.0000 | 48 | 0 | 40 → 10 |
| S3 | 1581.1 | 16.00 | 940,076 | 139,103 | 1.2267 | 123 | 22 | 10 → 9 |
| S4 | 144.7 | 0.00 | 76,870 | 10,633 | 0.0975 | 18 | 4 | 9 → 5 |
| **Tổng** | 2598.5 | 27.60 | 1,016,946 | 149,736 | 1.3242 | 307 | 33 | |

Loại khỏi phạm vi (không thuộc lượt chạy này): 259 lượt gọi Kalodata của lượt chạy khác (lượt chạy cũ, lượt mô phỏng) và các lượt thăm dò không gắn `run_id`, tổng 10.30 tín dụng.

## 4. Đơn giá theo ứng viên

Đơn giá = chi phí giai đoạn ÷ số ứng viên đã xử lý ở giai đoạn đó (S0 và S1a: số ứng viên xếp hạng; S1b: số KOC chấm xong; S2: số KOC đã lấy khán giả; S3: số KOC có điểm nội dung; S4: số KOC được đề xuất). Mẫu số 0 hiển thị đơn giá 0.

| Giai đoạn | Mẫu số | Tín dụng (thành công) | Tín dụng (tổng) | USD (thành công) | USD (tổng) | Token vào (tổng) | Token ra (tổng) | Giây (ghi nhận) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 200 | 0.0010 | 0.0010 | 0.00000 | 0.00000 | 0 | 0 | 0.01 |
| S1a | 200 | 0.0000 | 0.0000 | 0.00000 | 0.00000 | 0 | 0 | 0.00 |
| S1b | 60 | 0.1883 | 0.1900 | 0.00000 | 0.00000 | 0 | 0 | 3.75 |
| S2 | 10 | 0.0000 | 0.0000 | 0.00000 | 0.00000 | 0 | 0 | 64.44 |
| S3 | 9 | 1.6111 | 1.7778 | 0.04516 | 0.13630 | 104,453 | 15,456 | 175.68 |
| S4 | 5 | 0.0000 | 0.0000 | 0.00543 | 0.01951 | 15,374 | 2,127 | 28.94 |

## 5. Dự báo cho 50, 200 và 500 ứng viên

Công thức, với N là số ứng viên đầu vào và các giới hạn phễu lấy từ `config/pipeline.yaml` (`s1a_limit` = 60, `s1_limit` = 40, `s2_limit` = 10, `recommendation_count` = 5, `video_count` = 3):

```
n(S0) = n(S1a) = N
n(S1b) = min(N, 60)
n(S2)  = min(n(S1b), 40, 10)
n(S3)  = n(S2)
n(S4)  = min(n(S3), 5)
chi phí giai đoạn = n(giai đoạn) × đơn giá theo ứng viên của giai đoạn (mục 4)
```

Vì phễu bị chặn bởi các giới hạn cố định, chi phí gần như không đổi khi N ≥ 60; chỉ S0 và S1a tăng theo N. S3 tính trên 10 KOC trong khi lượt chạy thật chỉ có 9 KOC có điểm (1 KOC bị bỏ qua để tiết kiệm), nên cột 200 ứng viên cao hơn số thực đo một chút. S2 cần 1 ngày theo giới hạn `daily_ui_limit` = 10 lượt xem giao diện mỗi ngày. Thời gian dự báo dùng thời gian thực đã ghi nhận (gồm chờ giới hạn tốc độ và chờ video), không phải thời gian gọi API thuần.

### 50 ứng viên

Đường thành công: 25.58 tín dụng, 0.4788 USD. Tổng thực chi (giữ tỷ lệ thất bại và sửa lỗi như lượt chạy thật): 27.33 tín dụng, 1.4605 USD.

Bảng tổng thực chi:

| Giai đoạn | Ứng viên | Tín dụng | Token vào | Token ra | USD | Thời gian (giây) |
|---|---:|---:|---:|---:|---:|---:|
| S0 | 50 | 0.05 | 0 | 0 | 0.0000 | 1 |
| S1a | 50 | 0.00 | 0 | 0 | 0.0000 | 0 |
| S1b | 50 | 9.50 | 0 | 0 | 0.0000 | 188 |
| S2 | 10 | 0.00 | 0 | 0 | 0.0000 | 644 |
| S3 | 10 | 17.78 | 1,044,529 | 154,559 | 1.3630 | 1757 |
| S4 | 5 | 0.00 | 76,870 | 10,633 | 0.0975 | 145 |
| **Tổng** | | 27.33 | 1,121,399 | 165,192 | 1.4605 | 2734 |

### 200 ứng viên

Đường thành công: 27.61 tín dụng, 0.4788 USD. Tổng thực chi (giữ tỷ lệ thất bại và sửa lỗi như lượt chạy thật): 29.38 tín dụng, 1.4605 USD.

Bảng tổng thực chi:

| Giai đoạn | Ứng viên | Tín dụng | Token vào | Token ra | USD | Thời gian (giây) |
|---|---:|---:|---:|---:|---:|---:|
| S0 | 200 | 0.20 | 0 | 0 | 0.0000 | 3 |
| S1a | 200 | 0.00 | 0 | 0 | 0.0000 | 0 |
| S1b | 60 | 11.40 | 0 | 0 | 0.0000 | 225 |
| S2 | 10 | 0.00 | 0 | 0 | 0.0000 | 644 |
| S3 | 10 | 17.78 | 1,044,529 | 154,559 | 1.3630 | 1757 |
| S4 | 5 | 0.00 | 76,870 | 10,633 | 0.0975 | 145 |
| **Tổng** | | 29.38 | 1,121,399 | 165,192 | 1.4605 | 2774 |

### 500 ứng viên

Đường thành công: 27.91 tín dụng, 0.4788 USD. Tổng thực chi (giữ tỷ lệ thất bại và sửa lỗi như lượt chạy thật): 29.68 tín dụng, 1.4605 USD.

Bảng tổng thực chi:

| Giai đoạn | Ứng viên | Tín dụng | Token vào | Token ra | USD | Thời gian (giây) |
|---|---:|---:|---:|---:|---:|---:|
| S0 | 500 | 0.50 | 0 | 0 | 0.0000 | 7 |
| S1a | 500 | 0.00 | 0 | 0 | 0.0000 | 1 |
| S1b | 60 | 11.40 | 0 | 0 | 0.0000 | 225 |
| S2 | 10 | 0.00 | 0 | 0 | 0.0000 | 644 |
| S3 | 10 | 17.78 | 1,044,529 | 154,559 | 1.3630 | 1757 |
| S4 | 5 | 0.00 | 76,870 | 10,633 | 0.0975 | 145 |
| **Tổng** | | 29.68 | 1,121,399 | 165,192 | 1.4605 | 2779 |

## 6. Hiệu chuẩn Spearman

Hệ số Spearman giữa điểm nội dung S3 và hai chỉ số kết quả thật, tính trên các KOC có điểm S3 (finalist) có dữ liệu video đã phân tích:

- Điểm nội dung ↔ lượt xem/người theo dõi (tổng lượt xem các video đã phân tích ÷ người theo dõi): +0.494 (n = 9).
- Điểm nội dung ↔ GPM video (`video_gpm` từ S1): -0.259 (n = 9).

Mẫu rất nhỏ (vài KOC), nên chỉ mang tính tham khảo, không đủ để kết luận về độ tin cậy của điểm nội dung.

## 7. Dữ liệu khán giả S2

Dữ liệu khán giả S2 của 10/10 KOC trong lượt chạy này là dữ liệu mẫu (placeholder) của Kalodata (quy tắc theo từng KOC, giống S4). Với các KOC này điểm khán giả bị bỏ khỏi điểm cuối (trọng số được chia lại) và đề xuất ghi rõ lưu ý; KOC còn lại giữ điểm khán giả.

Chi phí xem trang S2: đo thực tế 0.00 tín dụng cho mọi lượt `ui/creator_detail` của lượt chạy; giá cấu hình `ui_creator_detail_view` = 0.0 (đã xác minh 2026-11-15: số dư tài khoản không đổi ngoài bộ đếm API).

## 8. Lượt chạy mở rộng 50 ứng viên (MÔ PHỎNG, không phải số liệu thật)

Lượt chạy `f5adab7df38f460ebea54ede55528760` · chế độ `mock` · `--limit 50` · trạng thái `done`. Chạy bằng `koc run --mock --limit 50` để kiểm tra cấu trúc và thời gian của phễu mà không tốn tín dụng. Tín dụng, token và USD đều bằng 0 vì dùng dữ liệu giả, không dùng để suy ra chi phí thật. Thời gian là thời gian máy chạy mô phỏng, không gồm độ trễ mạng hay LLM.

| Giai đoạn | Thời gian (giây) | Tín dụng | Token vào | Token ra | USD | Số lượt gọi | Cache hit | Ứng viên vào → ra |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S0 | 0.0 | 0.00 | 0 | 0 | 0.0000 | 1 | 0 | 50 → 50 |
| S1a | 0.0 | 0.00 | 0 | 0 | 0.0000 | 0 | 0 | 50 → 50 |
| S1b | 0.3 | 0.00 | 0 | 0 | 0.0000 | 100 | 0 | 50 → 40 |
| S2 | 0.0 | 0.00 | 0 | 0 | 0.0000 | 0 | 0 | 40 → 10 |
| S3 | 0.3 | 0.00 | 0 | 0 | 0.0000 | 70 | 0 | 10 → 10 |
| S4 | 0.1 | 0.00 | 0 | 0 | 0.0000 | 5 | 0 | 10 → 5 |
| **Tổng** | 0.6 | 0.00 | 0 | 0 | 0.0000 | 176 | 0 | |

## 9. Hạn chế

- Lượt chạy mới gán "thành công" chính xác theo từng lượt gọi LLM qua bảng `run_results` (id lượt gọi tạo ra kết quả, theo `run_id`, kèm mô hình). Lượt chạy cũ không có bảng này nên dùng ước lượng theo khóa yêu cầu (`request_hash`), phiên bản prompt và mô hình; ghi rõ ở đầu tài liệu.
- Thời gian giai đoạn là tổng thời gian ghi nhận của mọi lần thử và lần tiếp tục (`resume`), kể cả thời gian chờ; không tách riêng được thời gian của đường thành công.
- Lượt chạy thật được tiếp tục nhiều lần sau khi sửa lỗi nên có nhiều phiên bản prompt (`content_v1`, `v2`, `v3`).
