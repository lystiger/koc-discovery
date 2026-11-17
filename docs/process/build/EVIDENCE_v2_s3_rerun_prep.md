# EVIDENCE v2 item 4: chuẩn bị chạy lại S3 trả phí (V2-7)

Nhánh `v2/s3-rerun-prep` từ `feat/koc-mvp` 8b47aa8. Không gọi mạng, không gọi trả phí. `data/koc.db` không bị ghi: mọi bước chạy trên bản sao `sqlite3 -readonly data/koc.db ".backup <copy>"`, trong `unshare -rn`, khóa giả, `PYTHONPATH=src`, `KOC_DB=<bản sao>`. Thư mục `data/media` của bản chạy thử là các symlink (chỉ đọc) tới tệp thật.

## Kết luận
- Cách rẻ và đúng nhất: một `koc run` mới, không cờ. Lượt live không lưu khóa `brief` (`params_json` chỉ có `limit`, `mock`, `s4`, `stage_wall_ms`), nên `run_brief` rơi về mặc định = brief đã chạy; dry-run in `kem chống nắng · Nữ, 18-30 tuổi · 5 KOC · ngân sách 30.000.000 VND`, danh mục `601602, 873864, 601627`.
- S0/S1: 0 tín dụng. Hàng cache cũ nhất `creator/rank` 2026-11-14T22:37:17Z, `creator/detail` 22:37:21Z, `video/rank` 22:37:23Z; hạn 7 ngày hết 2026-11-21 22:37Z, ngày 16-17/11 còn hạn.
- S2: dùng lại bảng `metrics`, 0 tín dụng, không cần đăng nhập Kalodata. NHƯNG `pipeline.execute` vẫn gọi `connect_over_cdp("http://127.0.0.1:9333")` khi S2 bắt đầu (pipeline.py:557-559), nên cần một trình duyệt lắng nghe ở cổng 9333 (Chromium headless profile tạm là đủ, đã chạy thử).
- S3: 13 video cần trả phí, không phải 10 (xem dưới). Tín dụng sàn 13 x 0,5 = 6,5; ước 6,5-7,7. USD ước 0,23-0,69.

## Diễn tập 1: `--dry-run`
```
Kế hoạch: S0 tối đa 200 nhà sáng tạo, S1a lọc còn 60, S1b chấm điểm còn 40, S2 còn 10, S3 phân tích, S4 chọn 5.
Brief: kem chống nắng · Nữ, 18-30 tuổi · 5 KOC · ngân sách 30.000.000 VND.
Danh mục: 601602, 873864, 601627.
Tín dụng S3 dự kiến: tối đa 16.0; tổng toàn pipeline: 28.2; token LLM: 0 trong chạy thử.
  Tín dụng Kalodata ước tính: 27.6–29.4 tín dụng.   Chi phí LLM ước tính: 0.48–1.46 USD.
  Token LLM ước tính: 441.769–1.286.591 token.      Thời gian ước tính: 35–58 phút.
Chạy thử: không gọi mạng, không ghi dữ liệu.
```
Đây là ước tính toàn pipeline, bỏ qua cache; không dùng cho lần này.

## Diễn tập 2: `koc run --cache-only` trên bản sao (offline)
Lệnh: `KOC_DB=<copy> koc run --cache-only`. Kết quả (lượt `0c973ac4...`, trạng thái `blocked`):
```
S0|done|1   S1a|done|200   S1b|done|60   S2|done|10   S2|skipped|30 (vượt s2_limit)
S3|blocked|1  error: blocked: Chế độ chỉ-cache: thiếu dữ liệu đã lưu cho tệp video 7695457484974099730; không gọi mạng nên dừng lượt chạy.
S3|pending|9
creator/detail 60 cache hit, creator/rank 2, ui/creator_detail 10, video/rank 61: tổng 0 tín dụng, 0 token
```
Dừng đúng ở S3 vì thiếu tệp video. Lệnh in "Đã hoàn tất lượt chạy" dù trạng thái là `blocked` (hành vi cũ, ghi trong runbook).

## Diễn tập 3: vượt từng chỗ dừng (bản sao, đánh dấu tác vụ `done` bằng tay chỉ trên bản sao, rồi `koc resume`)
Mỗi KOC dừng ở video thiếu đầu tiên của nó:
```
7450735628620760071 (@rio100806)  -> 7695457484974099730
7471573167103378440 (@cleanboy.tips) -> 7706841783648701714
7485602050560148487 (@meixiuriviu) -> 7702310286232931605
7164572563820250139 (@dieuduong_quynhhoa) -> 7707875062786870548
6730533371858437121 (@emduyencantho) -> 7700025929283718408
7594293671543079957 (@teetamofficial) -> 7700088062222535944
```
Sau đó `S3|done|10`; `video/rank` 70 cache hit; 0 tín dụng. Bốn KOC (`@k_dung26`, `@dunghana2882`, `@ducvietbe__`, `@gaixinhh114`: không có video khớp chủ đề) và phần đã phân tích đi qua bằng cache.

## Danh sách đầy đủ: `scripts/s3_pending_videos.py` (đường chọn video của production)
`*` = cần tải và phân tích trả phí.
```
6730533371858437121 @emduyencantho 7581276298509683976 7700025929283718408* 7686825228000906514*
7164572563820250139 @dieuduong_quynhhoa 7533211696635219208 7703531291328793877 7707875062786870548*
7450735628620760071 @rio100806 7695457484974099730* 7698027306689809671* 7701751823807466759*
7471573167103378440 @cleanboy.tips 7706841783648701714* 7707286014947052806* 7701519564823153938*
7485602050560148487 @meixiuriviu 7701594488619191573 7702310286232931605* 7703462921245822229*
7594293671543079957 @teetamofficial 7700088062222535944* 7694231815078432001* 7699877846918909202(off-topic)
(4 KOC không video chủ đề: 0 video trả phí)
videos picked: 30; needing paid analysis (*): 13; video/url cost 6.5 credits
```
Khác bản xem trước (`s3_rerank_preview.py`, 10 video):
1. +3 video của `@cleanboy.tips`: lượt live đã bỏ S3 của KOC này bằng tay (`tasks`: `skipped: tiết kiệm chi phí, đủ 9 KOC`); lượt mới chấm đủ 10 KOC của S2.
2. `@dieuduong_quynhhoa`: bản xem trước gộp mọi trang `video/rank` đã cache và chọn `7696151096959585557`; S3 thật đọc trang `page_size=100` của riêng nó và chọn `7707875062786870548`. Số video trả phí vẫn là 1. UNPROVEN: vì sao hai trang khác nhau (chưa điều tra, không ảnh hưởng chi phí).
Đối chiếu: 10 + 3 = 13; 17 + 13 = 30 = 10 KOC x 3 video.

Số dư trước: 37,9 tín dụng (`sum(api_calls.credits)`), 1,3242 USD (`sum(llm_calls.cost_usd)`). Mỗi `video/url` thật trước đây tính 0,5 (30 lệnh 200 = 15,0).

## Smoke `:free`
`scripts/s3_free_smoke.py` (mới) chạy đúng `koc.llm.content.analyze_video` với client OpenRouter `:free`; ba chế độ (đầy đủ, `--no-audio`, `--text-only`), tự tra danh mục công khai để chọn mô hình có đầu vào image/audio. Người soạn không có mạng nên **chưa biết** mô hình `:free` nào nhận khung hình + audio: UNPROVEN, Lystiger chạy bước 1 của runbook. Kiểm tra offline:
- `tests/core/test_s3_free_smoke_script.py` (5 test, transport giả + video ffmpeg 3 giây): chế độ đầy đủ gửi 8 `image_url` + 1 `input_audio` và PASS; `--no-audio` không gửi audio và in `NOT PROVEN ... audio input`; `--text-only` gửi mô tả khung hình đã lưu, không có ảnh, mở DB `mode=ro`; lọc danh mục chỉ lấy `:free` có đủ modality; mô hình trả phí bị từ chối bằng `assert`; không chữ "ngân sách"/"budget" trong prompt.
- Trên video thật `7701594488619191573` (offline): tiền xử lý ffmpeg và dựng yêu cầu chạy đến lúc gọi HTTP, rồi `FAIL: RuntimeError: Lỗi kết nối tới OpenRouter: ConnectError` (đúng vì mạng bị cắt).

## Bộ test
`PYTHONPATH=src ... unshare -rn .venv/bin/python -m pytest -q` -> `504 passed, 1 skipped in 92.50s`.

## Chưa chứng minh (UNPROVEN)
- Mô hình `:free` nào nhận khung hình + audio (cần mạng); kết quả smoke thật.
- Chạy trả phí thật: chi phí thực, `video/url` có thể trả 1054 "đang xử lý" rồi chờ; thứ hạng top 5 mới; S4 viết lại bao nhiêu lý do (tối đa 5).
- Khối lệnh trong runbook chưa chạy nguyên văn (cần khóa thật, thư mục repo chính): đã `bash -n` OK cả 4 khối; các lệnh con (`--dry-run`, `--cache-only` trên bản sao, `s3_pending_videos.py`, truy vấn SQL so sánh) đã chạy riêng. Truy vấn `video_selection` trả rỗng ở lượt live cũ (đúng: cột này chỉ có ở lượt mới).
- Hạn dùng cache: tính bằng ngày lịch, chưa chạy với đồng hồ giả ngày 17/11.

## r1 fixes (review REVIEW_v2_s3_rerun_prep r1)
- P2-1: `s3_free_smoke.py` prints `STOP: model reported cost ...` and exits 3 on cost > 0 (test `test_nonzero_cost_stops_with_exit_code_3`). Runbook step 1 captures `rc`, breaks on 0, exits the block on 3 with `STOP: a :free model reported a cost`, tries the next mode on other codes.
- P2-2: `s3_pending_videos.py` opens `--db` with `mode=ro`, backs it up into `:memory:` and runs everything on that copy (test `test_s3_pending_videos_script.py`: sha256 of the DB file unchanged).
- P2-3: both Chromium/TMP traps now kill and wait for `$CPID` before `rm -rf "$TMP"`; the optional benchmark goes to `/tmp/koc_bench_$NEW`, outside the repo.
- P3: time estimate says 6 KOC (6 of 10 creators have uncached videos).
- Checks: `bash -n` on all 4 runbook bash blocks OK; full suite offline (`unshare -rn`) result in the commit message.
