# EVIDENCE v2 item 4: chọn video S3 theo chủ đề (A4)

Nhánh `v2/video-rerank` (từ `feat/koc-mvp` 2f7578c). Không mạng, không gọi trả phí. Bản sao DB chỉ đọc: `sqlite3 -readonly data/koc.db ".backup <copy>"`.

## Thay đổi
- `src/koc/video_select.py` (mới): `fold_text` (NFD, bỏ dấu, đ->d, chữ thường), `select_videos`. Điểm = số cụm từ khớp (mọi từ của cụm có trong tiêu đề + tên sản phẩm kèm theo nếu có; cụm nhiều từ cũng khớp khi dính liền trong hashtag, ví dụ `#kemchongnang`). Sắp xếp: điểm giảm dần, rồi doanh thu giảm dần. Thiếu video đúng chủ đề thì lấp bằng video doanh thu cao nhất kế tiếp, đánh dấu `on_topic: false`.
- `config/video_topics.yaml` (mới) + `config.py`: cụm từ theo `product_type`; cụm từ luôn gồm tên sản phẩm của brief. Run cũ không có `product_type` (như run live) thì lấy loại có tên nằm trong tên sản phẩm (kem chống nắng -> Chống nắng).
- `pipeline._s3_creator`: dùng `select_videos`; `scores.breakdown_json` của S3 thêm `video_selection: [{video_id, on_topic, score, matched_terms}]` (giữ nguyên `video_ids`).
- `prompts/content_v3.md` + `llm/content.py`: bỏ dòng ngân sách và tham số `budget_vnd` khỏi prompt.
- `pipeline._cached_call` / khóa mock: khóa cache nội dung không còn `budget_vnd` (`_key_brief`). Phân tích lý do (reasons) vẫn dùng ngân sách như cũ.
- `tests/core/test_s4_smoke_script.py`: thêm `monkeypatch.setattr(pipeline, "_cached_call", pipeline._cached_call)` để test này không để lại `_cached_call` giả sau khi chạy script (lỗi có sẵn: làm hỏng test khác chạy sau; lộ ra khi thêm test cache mới).

## Phát hiện về dữ liệu
`video/rank` KHÔNG trả `product_id` hay tên sản phẩm (1752 dòng trong 258 hàng http_cache của bản sao, chỉ có 17 khóa: ad, ad_revenue_ratio, ad_view_ratio, ads_roas, ai_video, belonged_creator_handle, belonged_creator_id, comment_count, creator_debut, digg_count, publish_date, revenue, revenue_growth_rate, share_count, video_id, video_title, views). Vì vậy (a) bộ lọc `attached` có sẵn trong `_s3_creator` (theo `top3_product_ids`) không có tác dụng trên dữ liệu live, (b) chỉ khớp được theo tiêu đề; code vẫn đọc `product_name` nếu API sau này có. Nhiều tiêu đề chỉ là hashtag, nên khớp từ khóa theo tiêu đề không bắt được những KOC này.

## Cache nội dung cũ (yêu cầu 2)
Khóa cũ = sha256 của {media_sha256, prompt_version, model, brief.model_dump()} có `budget_vnd`. Khóa mới (r1) bỏ `budget_vnd` và thêm `video_id`, nên mọi hàng `llm_cache` nội dung hiện có KHÔNG khớp khóa mới. Để không phải trả lại tiền: khi miss khóa mới, `_adopt_legacy_content` thử khóa cũ với ngân sách của brief và mọi `budget_vnd` ở bất kỳ vị trí nào trong `runs.params_json` (r2: run live lưu ở `s4.budget_vnd`, không có `brief`); nếu thấy thì chỉ khi `video_id` trong bản phân tích của hàng đó khớp video được yêu cầu thì sao chép hàng sang khóa mới (giữ `call_id`) rồi dùng như cache hit (0 token, 0 USD).
Nhãn phiên bản giữ `content_v3` (bản phân tích cũ vẫn hợp lệ: tiêu chí chấm không đổi, chỉ bỏ dòng ngân sách khỏi prompt). Đổi nhãn sang `content_v4` sẽ vô hiệu mọi bản phân tích (bảng `analyses`, `run_analyses`, khóa cache) và buộc trả lại toàn bộ các lần gọi, nên KHÔNG làm.
Kiểm tra trên bản sao DB live (script tạm `legacy_check.py`, chỉ đọc):
```
brief budget 30000000 model gemini-3.8-flash
llm_cache rows: 68
analyses rows by prompt_version: [('content_v1', 3), ('content_v2', 12), ('content_v2_repair', 3), ('content_v3', 24), ('content_v3_repair', 3)]
run content videos: legacy key present in llm_cache=18, absent=0, media file missing=0
```
Cả 18 video của run live có hàng cache khóa cũ, nên chạy lại cùng video tốn 0 lần gọi. Hàng cũ tạo với một ngân sách không còn lưu trong bảng `runs` sẽ miss và trả phí một lần (UNPROVEN: không có trường hợp này trong DB live).

## A4, từng phần

### Test mới (13) và toàn bộ suite
Lệnh:
```
unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake .venv/bin/python -m pytest -q'
```
Kết quả: `480 passed, 1 skipped in 90.62s` (r1; bản đầu: 474 passed). Test mới đỏ trước khi viết `video_select.py`: `ModuleNotFoundError: No module named 'koc.video_select'`.

| Phần A4 | Test (tests/core/test_video_select.py) |
|---|---|
| Gập dấu | `test_fold_text_strips_diacritics_case_and_d_stroke`, `test_diacritic_free_title_matches_and_matched_terms_are_stored` |
| Xếp hạng theo chủ đề, hòa thì theo doanh thu | `test_on_topic_outranks_higher_revenue_off_topic`, `test_ties_break_by_revenue_and_hashtag_compound_matches` |
| Thiếu video đúng chủ đề: lấp và đánh dấu | `test_fewer_than_n_on_topic_fills_by_revenue_and_marks_off_topic`, `test_other_product_type_uses_brief_product_only`, `test_no_videos_returns_empty`, `test_attached_product_name_counts_when_present` |
| Ngân sách không còn trong prompt | `test_content_prompt_has_no_budget`, `test_analyze_video_sends_no_budget_in_prompt` |
| Ngân sách không còn trong khóa cache; hàng cũ vẫn dùng được | `test_real_cache_key_ignores_budget_and_legacy_rows_are_reused` |
| Đổi riêng ngân sách => 0 lần gọi LLM mới khi chạy lại | `test_budget_only_change_costs_zero_new_llm_calls` (lần 1: 2 lần gọi trả phí; lần 2 ngân sách khác: 0 lần mới, 2 cache hit) |
| Lý do chọn được lưu | `test_s3_breakdown_stores_selection_reason` |

### Xem trước trên run live 7372009b22764b339fbcf0f3efb4bc4e (không mạng, không LLM)
Lệnh:
```
sqlite3 -readonly data/koc.db ".backup $TMPDIR/copy.db"
unshare -rn sh -c "ip link set lo up; PYTHONPATH=src .venv/bin/python scripts/s3_rerank_preview.py --db $TMPDIR/copy.db"
```
"Top 3 cũ" = quy tắc cũ (doanh thu giảm dần) áp lên đúng các dòng `video/rank` đã cache; script sẽ in cảnh báo nếu khác `video_ids` đã ghi của run (không có cảnh báo nào). Tiêu đề cắt 70 ký tự.
Kết quả (bản r1, sau khi sửa; lệnh thêm `--media-dir <data/media của repo chính>`):
```
Run 7372009b22764b339fbcf0f3efb4bc4e
Brief: kem chống nắng (None); terms: kem chống nắng, chống nắng, xịt chống nắng, sunscreen, sunblock, sun cream, spf, uv, chống tia uv

== @emduyencantho (6730533371858437121); 100 cached candidate videos
   old top 3 (by revenue):
     7705359977145322770  score=0  Quần độn hong và độn mông #tiktok #suhuong #emduyencantho
     7686018507649142023  score=0  Trả lời @Cô 2 Bến Tre kem dưỡng ẩm sáng da làm mờ thâm nám#tiktok #xu…
     7581276298509683976  score=2  Trả lời @Tam Thanh # kem chống nắng dữơng trắng #tiktok #xuhuong #emd…
   new top 3 (on-topic first):
     7581276298509683976  score=2 on-topic  Trả lời @Tam Thanh # kem chống nắng dữơng trắng #tiktok #xuhuong #emd…
     7700025929283718408  score=2 on-topic  Trả lời @hồ cúc kem chống nắng dưỡng trắng #tiktok #suhuong #emduyenc…  [needs paid analysis]
     7686825228000906514  score=2 on-topic  Trả lời @Đặng Mỹ hạnh kem chống nắng dưỡng trắng#tiktok #xuhuong #emd…  [needs paid analysis]

== @k_dung26 (6872721641991209985); 18 cached candidate videos
   old top 3 (by revenue):
     7700828901895081236  score=0  Như một thói quen #kcnbeskin #kimdung26 @Kim Dung26 ✅
     7703164953263344916  score=0  Ly mới đón tháng mới 😊 #kimdung26 @Kim Dung
     7697097183732026641  score=0  Đâu cần nói #kimdung26
   new top 3 (on-topic first):
     7700828901895081236  score=0 OFF-TOPIC  Như một thói quen #kcnbeskin #kimdung26 @Kim Dung26 ✅
     7703164953263344916  score=0 OFF-TOPIC  Ly mới đón tháng mới 😊 #kimdung26 @Kim Dung
     7697097183732026641  score=0 OFF-TOPIC  Đâu cần nói #kimdung26

== @dunghana2882 (6976265099049305089); 100 cached candidate videos
   old top 3 (by revenue):
     7702567422238231828  score=0  #dunghana2882 #xuhuong1111
     7700630539698687240  score=0  #dunghana2882
     7676534167454092552  score=0  #dunghana2882 #depkhonggioihan #cộngtácvớimaybelline #camnanglamdep #…
   new top 3 (on-topic first):
     7702567422238231828  score=0 OFF-TOPIC  #dunghana2882 #xuhuong1111
     7700630539698687240  score=0 OFF-TOPIC  #dunghana2882
     7676534167454092552  score=0 OFF-TOPIC  #dunghana2882 #depkhonggioihan #cộngtácvớimaybelline #camnanglamdep #…

== @dieuduong_quynhhoa (7164572563820250139); 26 cached candidate videos
   old top 3 (by revenue):
     7533211696635219208  score=2  Mỗi lần ra ngoài chỉn chu tự tin với kem chống nắng dạng sữa của The …
     7704674181962550548  score=0  Nó cỡ này cơ mà#sanphamchinhhang #maytamnuoc #nhakhoa #dieuduongquynh…
     7703531291328793877  score=2  Trả lời @Trang thỏ 120687 sữa chống nắng dưỡng trắng sáng da trang đi…
   new top 3 (on-topic first):
     7533211696635219208  score=2 on-topic  Mỗi lần ra ngoài chỉn chu tự tin với kem chống nắng dạng sữa của The …
     7703531291328793877  score=2 on-topic  Trả lời @Trang thỏ 120687 sữa chống nắng dưỡng trắng sáng da trang đi…
     7696151096959585557  score=2 on-topic  Sữa chống nắng trang điểm nói thật là nền của nó xinh xỉu lung linh l…  [needs paid analysis]

== @ducvietbe__ (7234931025289217051); 100 cached candidate videos
   old top 3 (by revenue):
     7605826096197569813  score=0  Roopy có deal nè #ducvietbe
     7694339958831582485  score=0  Kato Kato có deal nè #ducvietbe #tiktokshop1010 #quangcao
     7700201671380520210  score=0  Charmix có deal nè #quangcao #ducvietbe
   new top 3 (on-topic first):
     7605826096197569813  score=0 OFF-TOPIC  Roopy có deal nè #ducvietbe
     7694339958831582485  score=0 OFF-TOPIC  Kato Kato có deal nè #ducvietbe #tiktokshop1010 #quangcao
     7700201671380520210  score=0 OFF-TOPIC  Charmix có deal nè #quangcao #ducvietbe

== @gaixinhh114 (7288941699803694098); 100 cached candidate videos
   old top 3 (by revenue):
     7706170815640767765  score=0  #TikTokShop1111 #SaleToVoDoi #Xuhuong1111 #TikTokShopFunFest #TuHaoHC…
     7688027815312493845  score=0  #SaleLuongVe #2425LuongVe #SaleVuiChinhHang #SamDealRuocDen #BrandFan…
     7706556087222291733  score=0  #TikTokShop1111 #SaleToVoDoi #Xuhuong1111 #TikTokShopFunFest #TuHaoHC…
   new top 3 (on-topic first):
     7706170815640767765  score=0 OFF-TOPIC  #TikTokShop1111 #SaleToVoDoi #Xuhuong1111 #TikTokShopFunFest #TuHaoHC…
     7688027815312493845  score=0 OFF-TOPIC  #SaleLuongVe #2425LuongVe #SaleVuiChinhHang #SamDealRuocDen #BrandFan…
     7706556087222291733  score=0 OFF-TOPIC  #TikTokShop1111 #SaleToVoDoi #Xuhuong1111 #TikTokShopFunFest #TuHaoHC…

== @rio100806 (7450735628620760071); 100 cached candidate videos
   old top 3 (by revenue):
     7654235452152515848  score=0  Trộm vía lắm luôn dầu gội này thấy dùng tốt này #xuhuong #daugoidau
     7591175255134162194  score=0  Trả lời @phương đơn côi dầu gội hỗ trợ ngừa gầu ở đây ạ#viral #daugoi…
     7591172804385590535  score=0  Trả lời @scubidu dầu gội hỗ trợ ngừa gầu ạ#viral #daugoi #daugoitriga…
   new top 3 (on-topic first):
     7695457484974099730  score=2 on-topic  Vừa là kem che khuyết điểm vừa là kem chống nắng #viral  [needs paid analysis]
     7698027306689809671  score=2 on-topic  Kem chống nắng dành cho da dầu mụn #viral #kemchongnang  [needs paid analysis]
     7701751823807466759  score=1 on-topic  Ra đường nhớ chống nắng cho em để da sáng đều màu lên mỗi ngày nhé #v…  [needs paid analysis]

== @meixiuriviu (7485602050560148487); 100 cached candidate videos
   old top 3 (by revenue):
     7701594488619191573  score=2  Kem chống nắng Bioré chân ái cho da dầu m.ụn #biore #kemchongnang #ho…
     7685681792774409493  score=0  Nên dùng B3 hay B5 của nhà Dr Ceutis #drceutics #serumdrceutics #xuhu…
     7691943395123563796  score=0  Tr oi son tint trend mới Mooekiss rẻ chưa nè mấy vợ 😍#mooekiss #mooek…
   new top 3 (on-topic first):
     7701594488619191573  score=2 on-topic  Kem chống nắng Bioré chân ái cho da dầu m.ụn #biore #kemchongnang #ho…
     7702310286232931605  score=2 on-topic  Trả lời @Nhi nhỏ nhắn săn lẹ tay nhoaaaa ✨🤩#Biore #HopTacCungBiore #k…  [needs paid analysis]
     7703462921245822229  score=2 on-topic  săn lẹ kẻo hết quà nhaa ✨😍#Biore #HopTacCungBiore #kemchongnang #xuhu…  [needs paid analysis]

== @teetamofficial (7594293671543079957); 100 cached candidate videos
   old top 3 (by revenue):
     7699877846918909202  score=0  Sale rẻ dễ sợ
     7682217024046533895  score=0  Phấn lười nhưng xịn quánh đẹp mà giá siêu hời
     7702286059987635463  score=0  Cô mà biết em này là cô mê cho coi
   new top 3 (on-topic first):
     7700088062222535944  score=2 on-topic  Kem chống nắng cô khen  [needs paid analysis]
     7694231815078432001  score=1 on-topic  chống nắng còn chống nóng và không chống lại thời trang nha  [needs paid analysis]
     7699877846918909202  score=0 OFF-TOPIC  Sale rẻ dễ sợ

== Summary
creators in S3: 9; with cached candidates: 9; selection changes: 5
old selection off-topic videos: 23; new selection off-topic videos: 13; creators with no on-topic video at all: 4
new paid analyses needed for a partial S3 rerun: 10 video(s) (production cache lookup misses: no current-key or valid legacy row)
estimate (benchmark S3 units per creator / 3 videos, x 10): credits 5.37-5.93, USD 0.151-0.454, tokens 139,500-399,696
Cache note: video/rank rows older than cache_ttl_days are refetched on a live rerun (0.1 credit per creator page).
```

### Ước tính chạy lại S3 một phần (chỉ Lystiger chạy)
Từ output trên: 10 video mới cần phân tích trả phí (chưa có bản phân tích `content_v3`), thuộc 5 KOC (emduyencantho 2, dieuduong_quynhhoa 1, rio100806 3, meixiuriviu 2, teetamofficial 2). Đơn giá = đơn vị S3 mỗi KOC trong `reports/benchmark.json` chia 3 video, nhân 10: 5,37-5,93 tín dụng Kalodata (chủ yếu `video/url` 0,5 mỗi video; thêm 0,1 mỗi KOC nếu trang `video/rank` cache quá hạn `cache_ttl_days`), 0,151-0,454 USD LLM (khoảng 139,5k-399,7k token). Cận trên khớp V2-7 (0,3-0,5 USD). Video đã phân tích dùng lại cache: 0 lần gọi.

## Chưa chứng minh (UNPROVEN)
- Holdout A4: @rio100806 chọn lại toàn video chống nắng, dầu gội bị loại (xem output). 7234931025289217051 (@ducvietbe__) có 100 video nhưng không tiêu đề nào khớp (dạng "<thương hiệu> có deal nè"), nên vẫn lấp bằng 3 video "deal" đánh dấu `on_topic: false`. Chưa chứng minh là ở đó "có video đúng chủ đề"; cần người thẩm định.
- 4/9 KOC (k_dung26, dunghana2882, ducvietbe__, gaixinhh114) không có video nào khớp theo tiêu đề (tiêu đề chỉ hashtag hoặc tên thương hiệu); kế hoạch "embeddings chỉ khi holdout rớt" có thể bị kích hoạt. Chưa thử embeddings (ngoài phạm vi).
- Hàng cache cũ tạo với ngân sách không còn lưu trong `runs` (nêu trên).
- Chưa hiển thị `video_selection` trong web/báo cáo (không đụng `web/`; dữ liệu đã được lưu sẵn).

## r1 (Codex FAIL, 4 P2 + 1 P3) và cách sửa
1. Khớp sai: `_matches` nay khớp cả cụm liền nhau theo ranh giới từ, không còn so từ rời. Tiêu đề có dấu so khớp giữ dấu ("nâng" khác "nắng"); chỉ tiêu đề không có dấu nào mới gập dấu; hashtag dính liền (#kemchongnang) vẫn khớp. Test: `test_scattered_words_and_accent_lookalikes_do_not_match` (ca của reviewer "Kem dưỡng chống lão hóa, nâng cơ" -> off-topic, xếp sau video chống nắng dù doanh thu cao hơn), `test_unaccented_title_is_matched_folded` ("kem chong nang spf50" -> on-topic), `test_hashtag_glued_term_still_matches_in_accented_title`.
2. Bộ lọc `attached` (top3_product_ids) đã bỏ khỏi `_s3_creator`; mọi video ứng viên được xếp theo độ liên quan. Test: `test_attached_product_prefilter_does_not_hide_on_topic_video`.
3. Danh tính video trong cache: khóa nội dung có `video_id`; hàng cũ chỉ được nhận khi `video_id` của bản phân tích khớp. Test của reviewer (cùng bytes, v1/v2): `test_identical_media_under_two_video_ids_never_shares_an_analysis` (v2 trả phí 1 lần rồi cache, v1 vẫn dùng lại hàng cũ).
4. Xem trước: `needs_payment` gọi cùng `content_analysis_cached` của production (khóa hiện tại, rồi hàng cũ hợp lệ), chỉ đọc; thiếu file mp4 thì tính là phải trả phí. Test: `test_preview_counts_unrelated_model_analysis_as_needing_payment`. Chạy lại trên bản sao DB mới (copy2): 9 KOC, 5 thay đổi, 10 video cần trả phí (không đổi so với bản đầu; các video đã phân tích đều có hàng cache khóa cũ khớp video), ước tính 5,37-5,93 tín dụng, 0,151-0,454 USD, 139.500-399.696 token.
5. Test prompt: có guard, yêu cầu đúng ngoại lệ `Stop`, khẳng định prompt đã được ghi lại, chứa "kem chống nắng" và không chứa ngân sách.

## r2 (Codex FAIL, 2 P2) và cách sửa
1. Khớp theo từng từ: một từ của tiêu đề khớp từ của cụm khi giống hệt (giữ dấu) hoặc khi chính từ đó không có dấu và bằng từ cụm đã gập dấu. Test `tests/core/test_video_select_r2.py`: "kem chong nang cho da dầu" -> on-topic và xếp trên video dầu gội doanh thu cao hơn; "kem dưỡng chống lão hóa, nâng cơ" và "chống nâng" -> off-topic.
2. Ngân sách lịch sử: DB live có đúng một run, ngân sách chỉ ở `s4.budget_vnd` = 30.000.000 (không có `brief`; kiểm tra trên bản sao: `.s4.budget_vnd 30000000` x1). `_legacy_content_row` nay gom mọi `budget_vnd` trong params của mọi run cộng ngân sách của brief. Test `test_legacy_row_keyed_with_budget_stored_only_under_s4_is_reused_at_a_different_budget`: hàng cũ khóa theo 30M chỉ có ở `s4`, chạy lại với 8M -> 0 lần gọi analyzer.
3. Bản sao DB chỉ đọc mới (copy3), cùng tra cứu production, 27 video được chọn:
```
run brief budget_vnd: 30000000 | selected videos: 27
budget 30000000: reusable (0 calls) = 17, needing payment = 10
budget 8000000: reusable (0 calls) = 17, needing payment = 10
budget 55000000: reusable (0 calls) = 17, needing payment = 10
```
Preview đầy đủ chạy lại: 9 KOC, 5 thay đổi, 10 video cần trả phí, 5,37-5,93 tín dụng, 0,151-0,454 USD (không đổi). Suite: xem dưới.
Suite r2: 482 passed, 1 skipped in 90.53s.

## r3 (Codex FAIL, 1 P2)
So sánh từ đối xứng: hai từ khớp khi giống hệt, hoặc khi một trong hai không dấu và bằng nhau sau khi gập dấu; hai từ đều có dấu so khớp chính xác. Test `tests/core/test_video_select_r3.py`: brief "sua tam" khớp "Sữa tắm hương hoa" và xếp trên dầu gội doanh thu cao hơn; "nâng cơ", "chống nâng" vẫn off-topic; "kem chong nang cho da dầu" vẫn on-topic. Preview chạy lại trên bản sao copy3: output giống hệt bản r2 (10 video cần trả phí). Suite: 484 passed, 1 skipped in 89.85s.

## r4 (Codex FAIL, 1 P2)
Quy tắc: cụm cấu hình (config/video_topics.yaml, có dấu) là chuẩn; khớp chính xác, hoặc gập dấu chỉ khi TỪ TRONG TIÊU ĐỀ không có dấu (quy tắc r2). Tên sản phẩm của brief chỉ được thêm làm cụm khi có dấu, hoặc khi loại sản phẩm không có cụm cấu hình; chỉ trong trường hợp dự phòng đó cụm không dấu mới được gập dấu đối xứng (`_Term.loose`). Trùng cụm sau khi gập dấu thì cách viết cấu hình thắng. Test `tests/core/test_video_select_r4.py`: loại Chống nắng + brief "chong nang" -> "chồng - Nàng" off-topic, video chống nắng thật on-topic; "rua mat" không khớp "rửa mát"; loại Khác / không có loại + "sua tam" -> "Sữa tắm hương hoa" on-topic; các ca cũ (nâng cơ, chống nâng, kem chong nang cho da dầu, hashtag) giữ nguyên. Preview chạy lại trên bản sao mới (copy4): chỉ khác thứ tự cụm từ trong dòng "terms"; mọi lựa chọn và con số giống hệt (10 video cần trả phí). Suite: 488 passed, 1 skipped in 87.00s.

## r5 (Codex FAIL, 1 P2)
Hashtag dính liền theo cùng quy tắc dấu: hashtag không dấu (#kemchongnang) so khớp gập dấu; hashtag có dấu phải chứa đúng cụm có dấu bỏ khoảng trắng (#kemchốngnắng); cụm dự phòng "loose" của brief vẫn gập dấu. Test `tests/core/test_video_select_r5.py`: #chồngnàng, #chốngnâng, #rửamát -> off-topic; #kemchongnang, #kemchốngnắng, #KemChốngNắng -> on-topic; 3 video on-topic dạng hashtag thắng 1 video hashtag không liên quan doanh thu 999; loose "sua tam" vẫn khớp #sữatắm. Preview chạy lại trên bản sao mới (copy5): giống hệt r4. Suite: 496 passed, 1 skipped in 90.58s.

## Paid S3 rerun (Lystiger, 2026-11-16 23:08-23:30 +07)

Runbook: `docs/build/RUNBOOK_v2_s3_rerun.md` (Agy r2 PASS). Free-model smoke ran first (backup `data/koc_backup_before_s3_smoke_20261116_225559.db`); paid run backup `data/koc_backup_before_s3_rerun_20261116_230827.db`.

- New run `0e555cac95fb4fb49168410e40ea92d5`: `done`; tasks S0 done 1, S1a done 200, S1b done 60, S2 done 10 / skipped 30, S3 done 10, S4 done 1.
- Spent: 6.5 Kalodata credits, 0.2793 USD (estimate 6.5-7.7 credits, 0.23-0.69 USD). Totals 44.4 / 60 credits, 1.6035 / 5 USD.

| # | v1 run 7372009b | final | v2 run 0e555cac | final |
|---|---|---|---|---|
| 1 | @meixiuriviu | 78.6 | @meixiuriviu | 79.0 |
| 2 | @teetamofficial | 75.7 | @rio100806 | 77.7 |
| 3 | @emduyencantho | 73.4 | @dieuduong_quynhhoa | 76.2 |
| 4 | @dieuduong_quynhhoa | 73.2 | @emduyencantho | 74.7 |
| 5 | @k_dung26 | 65.7 | @teetamofficial | 74.1 |

On-topic videos per S3 creator (of 3): meixiuriviu 3, dieuduong_quynhhoa 3, rio100806 3, emduyencantho 3, teetamofficial 2, cleanboy.tips 3, dunghana2882 0, ducvietbe__ 0, gaixinhh114 0, k_dung26 0.

Holdout A4: PASS. @rio100806's selection is 7695457484974099730, 7698027306689809671, 7701751823807466759, all `on_topic: true` (matched "kem chống nắng" / "chống nắng"); no shampoo video. 7234931025289217051 (@ducvietbe__): no on-topic title exists, clause not applicable; its 3 deal videos are marked `on_topic: false` and it is not in the top 5.
