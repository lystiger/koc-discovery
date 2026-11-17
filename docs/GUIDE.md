# KOC Discovery

> Hướng dẫn chi tiết từ bản v1.0 (kiến trúc, lệnh CLI, cấu hình). Tính năng và số liệu hiện tại của v2.0 xem [README](../README.md), [CHANGELOG](../CHANGELOG.md) và [RETROSPECTIVE](RETROSPECTIVE.md).

KOC Discovery lọc creator TikTok Việt Nam qua năm giai đoạn (S0 đến S4), chấm điểm thương mại, khán giả và nội dung video, rồi chọn số KOC theo brief (mặc định 5 KOC, tổng phí ước tính không quá 30.000.000 VND). Số liệu thương mại lấy từ Kalodata API, khán giả lấy từ trang creator trên Kalodata qua Chromium, video được phân tích bằng `ffmpeg` và OpenRouter với model `google/gemini-3.8-flash`. Mọi tác vụ, cache và chi phí nằm trong một file SQLite. Thiết kế chi tiết ở [docs/ARCHITECTURE.md](ARCHITECTURE.md). [src/koc/pipeline.py](../src/koc/pipeline.py) [src/koc/db.py](../src/koc/db.py) [config/llm_prices.yaml](../config/llm_prices.yaml)

## Cài đặt

Cần Python 3.12 trở lên, `ffmpeg` và Chromium. [pyproject.toml](../pyproject.toml) [src/koc/llm/media.py](../src/koc/llm/media.py)

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m playwright install chromium
```

`pyproject.toml` khai báo cả `fastapi`, `uvicorn`, `jinja2` cho web app và `google-genai`. `src/koc/llm/gemini.py` import `google.genai` ngay khi nạp module, nên gói này cần có cả khi dùng OpenRouter. Giao diện React cần Node 20 trở lên. Cài `ffmpeg` bằng trình quản lý gói của hệ điều hành. [pyproject.toml](../pyproject.toml) [src/koc/web/app.py](../src/koc/web/app.py) [src/koc/llm/gemini.py](../src/koc/llm/gemini.py) [src/koc/llm/factory.py](../src/koc/llm/factory.py)

## Khóa API

Khóa chỉ được đọc từ biến môi trường. Nhập khóa bằng `read -s` để khóa không hiện trên màn hình và không vào lịch sử shell. Không ghi khóa vào file hay Git. [src/koc/kalodata.py](../src/koc/kalodata.py) [src/koc/llm/openrouter.py](../src/koc/llm/openrouter.py)

```bash
read -rs KALODATA_API_KEY && export KALODATA_API_KEY
read -rs OPENROUTER_API_KEY && export OPENROUTER_API_KEY
```

Provider mặc định là `openrouter` (`provider:` trong `config/llm_prices.yaml`). Đổi sang `gemini` thì cần `GEMINI_API_KEY`. [config/llm_prices.yaml](../config/llm_prices.yaml) [src/koc/llm/gemini.py](../src/koc/llm/gemini.py)

## Phiên Chromium cho S2

S2 đọc tỷ lệ giới tính và độ tuổi khán giả từ trang creator trên Kalodata. Trước khi chạy tới S2, mở Chromium với cổng CDP `9333`, đăng nhập Kalodata bằng tay và giữ cửa sổ mở. Pipeline kết nối tới `http://127.0.0.1:9333` và chỉ mở kết nối khi S2 bắt đầu. Chương trình không đọc cookie hay header. [src/koc/pipeline.py](../src/koc/pipeline.py) [docs/research/FACTS.md](research/FACTS.md)

```bash
chromium --remote-debugging-port=9333 --user-data-dir=/tmp/koc-chromium
```

## Lệnh

```bash
.venv/bin/koc run --dry-run          # in kế hoạch và ước tính tín dụng, USD, token, phút (khoảng, nhãn "ước tính"); không gọi mạng, không ghi DB
.venv/bin/koc run                    # lượt chạy mới, mặc định --limit 200
.venv/bin/koc resume                 # chạy tiếp lượt mới nhất (tác vụ pending, failed, blocked)
.venv/bin/koc resume --retry-failed  # lượt đã xong: thử lại creator S3 bị loại, chọn lại S4 (tốn phí)
.venv/bin/koc run --cache-only       # chỉ dùng dữ liệu đã cache; cache miss thì chặn tác vụ, không gọi mạng
.venv/bin/koc status                 # trạng thái từng lượt và số tác vụ theo trạng thái
.venv/bin/koc benchmark --run <run_id>   # ghi reports/benchmark.json và docs/BENCHMARK.md, chỉ đọc DB
.venv/bin/koc report --run <run_id>      # bộ sinh báo cáo cũ (src/koc/report.py), cũng ghi docs/BENCHMARK.md
```

`run` còn nhận `--mock` để chạy bằng dữ liệu giả, không tốn credit hay token. `koc categories --keyword <từ-khóa>` tìm danh mục Kalodata và ghi ID khớp vào `config/scoring.yaml`. Biến `KOC_DB` đổi đường dẫn database (mặc định `data/koc.db`). `docs/BENCHMARK.md` hiện tại do `koc benchmark` tạo; đừng sửa tay file này. [src/koc/cli.py](../src/koc/cli.py) [src/koc/benchmark.py](../src/koc/benchmark.py) [src/koc/benchmark_render.py](../src/koc/benchmark_render.py)

### Brief của lượt chạy

Mỗi lượt chạy ứng với một sản phẩm. Brief nhập qua tham số của `koc run` và lưu trong `runs.params_json` (khóa `brief`). Không truyền gì thì brief giống các giá trị cũ.

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--product` | `kem chống nắng` | Sản phẩm; cũng là từ khóa tìm creator khi không có danh mục |
| `--product-type` | không có | Một trong sáu loại của web: `Chống nắng`, `Dưỡng ẩm`, `Serum`, `Làm sạch`, `Trang điểm`, `Khác`. Điền `--category-ids` từ [config/product_categories.yaml](../config/product_categories.yaml); `--product` mặc định là tên loại viết thường |
| `--category-ids "id1,id2"` | `s0.category_ids` trong `config/scoring.yaml` | Danh mục Kalodata cho S0 và S1 |
| `--gender` | `nu` | `nu`, `nam` hoặc `tat-ca`; S2 chấm tỷ lệ giới này |
| `--age-min` / `--age-max` | 18 / 30 | Từ 18 đến 99 (nhóm 55+ của web là 55-99). S2 chỉ có hai dải Kalodata đã lưu (18-24, 25-34) và cộng các dải giao với khoảng này. Khoảng không giao dải nào (ví dụ 35-44) thì điểm khán giả để trống và điểm cuối bỏ phần khán giả, như với số liệu mẫu |
| `--budget` | 30000000 | Ngân sách VND |
| `--count` | 5 | Số KOC cần chọn |

Ví dụ cho sản phẩm khác. Tìm ID danh mục trước, rồi chạy thử. Lưu ý `koc categories` ghi ID khớp vào `s0.category_ids` trong `config/scoring.yaml`, tức đổi mặc định của `--category-ids`:

```bash
.venv/bin/koc categories --keyword "Tóc"
.venv/bin/koc run --dry-run --product "dầu gội" --category-ids 601700,601701 --gender tat-ca --age-min 25 --age-max 34 --budget 12000000 --count 3
.venv/bin/koc run --dry-run --product-type "Serum" --age-min 35 --age-max 44
```

`config/product_categories.yaml` ghi ID đã khớp cho từng loại và cách khớp (tên danh mục trong cache `category/rank`). `Chống nắng` giữ ID hiện tại; `Khác` để trống, nên cần `--category-ids`. `--category-ids` luôn thắng bản đồ này.

`koc resume` dùng brief đã lưu và từ chối nếu bạn truyền giá trị khác. Muốn đổi brief thì chạy lượt mới. `koc status` hiện brief của từng lượt.

Từ chối trước khi gọi mạng, trong `run` và `--dry-run`, thoát với mã 1:

- `--product-type` có danh mục rỗng (như `Khác`) mà không có `--category-ids`, hoặc không phải một trong sáu loại.
- `--count` lớn hơn `s2_limit` (tài khoản dùng thử chỉ phân tích tối đa 10 creator mỗi lượt).
- `--budget` nhỏ hơn `--count` nhân phí rẻ nhất (3.000.000 VND mỗi KOC). Thông báo nêu số KOC tối đa vừa ngân sách, ngân sách tối thiểu cho `--count` đã chọn, và nhóm follower rẻ nhất (10k-50k).

Nếu S4 không tìm được nhóm `--count` KOC trong ngân sách, hoặc có ít creator có điểm nội dung hơn `--count`, lượt chạy dừng ở `blocked` với ba lựa chọn (lựa chọn không thực hiện được ghi "không có") tính từ các creator đã chấm: số KOC lớn nhất còn vừa và chi phí, ngân sách tối thiểu cho nhóm rẻ nhất, nhóm follower của các creator rẻ nhất. Code không tự giảm số KOC và không chọn vượt ngân sách. Phí mỗi KOC ở S4, ở bước kiểm tra trước và trên web đều tính bằng [src/koc/pricing.py](../src/koc/pricing.py): đơn giá theo bậc follower nhân 3 video; follower nằm ngoài bảng giá thì lấy bậc gần nhất, nên phí không bao giờ bằng 0. Trên web, form trả `status` là `ok`, `refused` (kèm ba lựa chọn) hoặc `needs_run`. `needs_run` nghĩa là chưa có lượt chạy nào đã chấm cho loại sản phẩm này; web đưa đúng lệnh `koc run --dry-run ...` dựng từ form và không tự chạy lượt trả phí. Một KOC chỉ được xét ở S4 và trong nhóm ứng viên của web nếu ít nhất một video đã phân tích của lượt chạy có điểm rubric `brand_fit` từ 3 trở lên (`s4.min_brand_fit` trong `config/scoring.yaml`); KOC bị loại hiện kèm lý do ở `koc status`, báo cáo và trang đề xuất, và không bao giờ nằm trong nhóm chọn hay ba lựa chọn. Khi chọn được, phần ngân sách dư giữ nguyên, không dùng; `koc run` và `koc status` in số dư, và `runs.params_json` lưu khóa `s4` (`total_vnd`, `budget_vnd`, `leftover_vnd`). [src/koc/brief.py](../src/koc/brief.py) [src/koc/pipeline.py](../src/koc/pipeline.py) [src/koc/cli.py](../src/koc/cli.py)

CLI không có lệnh `koc serve`. Build giao diện React một lần, rồi chạy web app:

```bash
cd web && npm ci && npm run build && cd ..
.venv/bin/python -m koc.web --db data/koc.db --media-dir data/media --port 8765
```

`web/dist` và `web/node_modules` không nằm trong Git. Nếu chưa build, `/` quay về danh sách lượt chạy Jinja cũ và các trang React trả 404.

Máy chủ nghe tại `http://127.0.0.1:8765`. Web app có danh sách lượt chạy, trang top 5 (đóng góp điểm theo trọng số, chi phí so với điểm), hồ sơ creator (khán giả, rubric từng video) và dashboard vận hành (funnel S0 đến S4, credits và USD so với hạn mức). [src/koc/web/__main__.py](../src/koc/web/__main__.py) [src/koc/web/app.py](../src/koc/web/app.py) [src/koc/web/charts.py](../src/koc/web/charts.py)

Giao diện React (trang landing, trang đề xuất `/de-xuat/<run_id>`, hồ sơ KOC `/de-xuat/<run_id>/koc/<creator_id>`) đã được gộp vào nhánh này; trang Jinja `/runs/<run_id>` vẫn giữ làm màn hình vận hành. Kết quả audit tích hợp: [docs/process/build/VERDICT_integration.md](process/build/VERDICT_integration.md). Deck thuyết trình 14 slide (bản v1.0) nằm ở [docs/pitch/](pitch/README.md).

## Kết quả lượt chạy thật (v1.0)

Lượt `7372009b22764b339fbcf0f3efb4bc4e` chạy live với `--limit 200` và kết thúc ở trạng thái `done`. Ngày 16/11/2026 có hai lần chạy lại trên lượt này. Lần đầu chấm lại 6 KOC bằng `content_v3` và viết lại lý do bằng `reasons_v4` (0 tín dụng, 0,3249 USD). Lần sau bật cổng brand_fit rồi chạy lại S4: 2 lượt gọi LLM trả phí, 0,0109 USD (truy vấn `llm_calls` trên bản sao DB). [src/koc/pipeline.py](../src/koc/pipeline.py)

Cổng brand_fit loại 4 trong 9 KOC có điểm nội dung, vì không video nào đã phân tích của họ đạt `brand_fit` 3/5. Hai KOC trong số đó từng nằm trong top 5. `@rio100806` (hạng 4 cũ) có video quảng cáo dầu gội trị gàu cho nam, `brand_fit` 2, 0, 2. `@ducvietbe__` (hạng 2 cũ) có video kem tay và phấn phủ, `brand_fit` 2, 0, 1. Hai KOC còn lại là `@dunghana2882` và `@gaixinhh114`. Danh sách lấy từ `koc.stages.excluded_brand_fit` trên bản sao DB. [src/koc/stages.py](../src/koc/stages.py)

Top 5 hiện tại, tổng phí ước tính 28.500.000 VND, dư 1.500.000 VND (`runs.params_json.s4`):

| Hạng | KOC | Follower | Điểm cuối | Phí ước tính (VND) |
|---:|---|---:|---:|---:|
| 1 | `@meixiuriviu` (7485602050560148487) | 12.200 | 78,6 | 3.000.000 |
| 2 | `@teetamofficial` (7594293671543079957) | 74.900 | 75,7 | 7.500.000 |
| 3 | `@emduyencantho` (6730533371858437121) | 56.900 | 73,4 | 7.500.000 |
| 4 | `@dieuduong_quynhhoa` (7164572563820250139) | 33.500 | 73,2 | 3.000.000 |
| 5 | `@k_dung26` (6872721641991209985) | 86.300 | 65,7 | 7.500.000 |

Sau cổng chỉ còn đúng 5 KOC đủ điều kiện, nên S4 không còn tổ hợp nào khác để so. Số liệu chi phí dưới đây lấy từ [docs/BENCHMARK.md](BENCHMARK.md), file sinh tự động từ DB.

| Chỉ số | Đường thành công | Tổng thực chi |
|---|---:|---:|
| Credits Kalodata | 26.00 | 27.60 |
| Token LLM vào / ra | 355.351 / 44.568 | 1.016.946 / 149.736 |
| USD LLM | 0,4336 | 1,3242 |
| Lượt gọi không qua cache (gồm cả lượt 0 đồng) | 195 | 307 |

"Đường thành công" chỉ tính lượt gọi tạo ra kết quả được giữ lại. "Tổng thực chi" gồm cả lần thất bại, lượt sửa lỗi `_repair` và kết quả bị thay bằng phiên bản prompt sau. Lượt này chạy trước khi có bảng `run_results`, nên phần thành công của S3 là ước tính theo khóa yêu cầu và phiên bản prompt. Tổng thời gian ghi nhận là 2.598 giây, gồm các lần resume và thời gian chờ. Phễu đi từ 200 ứng viên xuống 60, 40, 10, 9 rồi 5. Dự báo cho 50, 200 và 500 ứng viên nằm ở mục 5 của BENCHMARK. [docs/BENCHMARK.md](BENCHMARK.md)

Spearman giữa điểm nội dung S3 và lượt xem trên follower là +0,494; với GPM video là -0,259 (n = 9). Mẫu quá nhỏ để kết luận về độ tin cậy của điểm nội dung. [docs/BENCHMARK.md](BENCHMARK.md)

## Giới hạn hiện tại

- Dữ liệu khán giả là số mẫu. Gói Kalodata đang dùng hiển thị cùng một bộ số cho mọi creator (nữ 60%, 18-24 tuổi 30,5%, 25-34 tuổi 39,5%). Cả 10 KOC qua S2 trong lượt live đều bị nhận là placeholder. Với các KOC này, điểm khán giả bị bỏ khỏi điểm cuối và đề xuất có lưu ý "chưa xác minh". [src/koc/stages.py](../src/koc/stages.py) [docs/BENCHMARK.md](BENCHMARK.md)
- Điểm S1 bão hòa. Code truyền tổng `detail.revenue` vào thành phần `skincare_revenue_share`, nên thành phần này chưa đo riêng doanh thu skincare; nay trọng số của nó là 0 (proxy, không tính điểm) và các trọng số còn lại được chia lại, xem [docs/LIMITATIONS.md](LIMITATIONS.md). Trong lượt live, 53 trên 60 creator ở S1 đạt mức tối đa 100 ở `video_gpm`, và 53 trên 60 đạt 100 ở `skincare_revenue_share` (truy vấn chỉ đọc trên bản sao `data/koc.db`). S1 vì vậy phân biệt creator kém. [src/koc/pipeline.py](../src/koc/pipeline.py) [src/koc/stages.py](../src/koc/stages.py) [config/scoring.yaml](../config/scoring.yaml)
- S3 lấy 3 video doanh thu cao nhất, không xét video có đúng sản phẩm của brief hay không. Cổng brand_fit chỉ loại KOC sau khi đã trả tiền phân tích video. Trong lượt live, 4 trên 9 KOC đã phân tích bị loại theo cách này. [src/koc/pipeline.py](../src/koc/pipeline.py) [src/koc/stages.py](../src/koc/stages.py)
- `koc run --dry-run` in khoảng ước tính tín dụng, USD, token LLM và số phút, có nhãn "ước tính", tính từ đơn vị mỗi creator trong `reports/benchmark.json` nhân số creator mỗi giai đoạn xử lý theo giới hạn cấu hình (`s1a_limit`, `s1_limit`, `s2_limit`). Khoảng phút là giá trị đo ±25%, chưa hiệu chỉnh vì chỉ có một lượt chạy live. Dòng kế hoạch lấy các giới hạn từ cấu hình (S2 còn 10). [src/koc/estimate.py](../src/koc/estimate.py) [src/koc/cli.py](../src/koc/cli.py)
- Chạy lại với cùng brief trả lại đúng 5 KOC cũ, vì mọi request trùng khóa đều lấy từ cache. Cache Kalodata của `creator/rank`, `creator/detail` và `video/rank` hết hạn sau `cache_ttl_days` = 7 ngày (`config/pipeline.yaml`); phân tích video, cache LLM và `video/url` không hết hạn. Lưu ý vận hành: chạy lại thường một lượt cũ hơn 7 ngày sẽ gọi lại Kalodata và tốn credit; muốn chạy lại với 0 credit, 0 token, dùng `koc run --cache-only`. [src/koc/db.py](../src/koc/db.py)
- Giao diện web chưa có liên kết TikTok cho từng KOC và chưa hiện danh sách KOC bị cổng brand_fit loại, dù `POST /api/campaigns` đã trả trường `brand_fit_excluded`. [src/koc/web/matching_api.py](../src/koc/web/matching_api.py) [src/koc/web/api.py](../src/koc/web/api.py)
- Phí booking là ước tính theo bậc follower, nhân 3 video: 1.000.000, 2.500.000 hoặc 5.000.000 VND mỗi video. Cần xác nhận giá với creator hoặc MCN trước khi đặt. [config/rate_card.yaml](../config/rate_card.yaml) [src/koc/pricing.py](../src/koc/pricing.py)
- Tài khoản trial chỉ được mở 10 trang chi tiết mỗi ngày. `s2_limit` và `daily_ui_limit` đều là 10, nên mỗi lượt lấy khán giả cho tối đa 10 creator. Chưa xác minh hạn mức của gói trả phí. [docs/research/FACTS.md](research/FACTS.md) [config/pipeline.yaml](../config/pipeline.yaml)
- Chưa có benchmark độ chính xác transcript tiếng Việt. Transcript là ghép các câu trích lời nói mà model trả về, không phải đầu ra của ASR. [src/koc/llm/content.py](../src/koc/llm/content.py)

## Hướng mở rộng

Bản v2.0, hạn cuối ngày 17/11/2026, theo kế hoạch phát hành của Lystiger:

- Khi chạy lại, loại các KOC đã đề xuất ở lượt trước.
- Web hiện liên kết TikTok của từng KOC và ghi chú số KOC bị loại vì không hợp sản phẩm.
- Nếu kịp: S3 chọn video đúng sản phẩm của brief; đo riêng doanh thu skincare và đổi mốc chuẩn hóa GPM để S1 không bão hòa. [config/scoring.yaml](../config/scoring.yaml)

Sau v2.0:

- Tăng `--limit` để lấy thêm ứng viên S0. Các mức `s1a_limit`, `s1_limit`, `s2_limit` trong `config/pipeline.yaml` điều khiển phễu. Theo công thức trong BENCHMARK, chi phí gần như không đổi khi N ≥ 60, vì chỉ S0 và S1a tăng theo N. Muốn đánh giá nhiều creator hơn thì phải nâng các mức này, và S2 sẽ cần nhiều ngày trên tài khoản trial. [config/pipeline.yaml](../config/pipeline.yaml) [docs/BENCHMARK.md](BENCHMARK.md)
- `video_count: 3` trong config chưa có tác dụng: S3 cắt danh sách video bằng hằng số `[:3]`. Nối giá trị này vào code trước khi đổi. [src/koc/pipeline.py](../src/koc/pipeline.py)
- Lấy dữ liệu khán giả thật từ gói Kalodata có dữ liệu này hoặc từ ảnh chụp TikTok Analytics do creator gửi.
- Whisper ngoại tuyến: **chưa triển khai**. Có thể chạy `openai-whisper` cục bộ để lấy transcript tiếng Việt, với file weights tải từ `openaipublic.azureedge.net`. Code hiện không gọi Whisper; S3 gửi âm thanh cho provider LLM. Cách tải và chất lượng tiếng Việt chưa được kiểm chứng trong repo. [src/koc/llm/content.py](../src/koc/llm/content.py) [docs/process/build/SPEC.md](process/build/SPEC.md)

## Kiểm chứng

- Bộ test: `PYTHONPATH=src .venv/bin/python -m pytest -q tests` cho kết quả `429 passed, 1 skipped` (chạy ngày 16/11/2026 trên commit `8371032`).
- C5, dừng giữa chừng rồi chạy tiếp: [scripts/kill_resume_test.sh](../scripts/kill_resume_test.sh) chạy `koc run --mock --limit 50`, gửi SIGKILL sau lượt gọi API ở S1b và sau lượt gọi LLM ở S3, rồi chạy `koc resume --mock`. Script kiểm tra không có dòng trùng, không có lượt gọi trả phí lặp lại, và lần resume sau khi xong tốn 0 credit, 0 token. Lần chạy ngày 16/11/2026 (ngoại tuyến, trong network namespace, chế độ mock) in `SIGKILL + resume: S1b PASS` và `SIGKILL + resume: S3 PASS`. Log: [docs/process/logs/c5_kill_resume_2026-11-16.log](process/logs/c5_kill_resume_2026-11-16.log).
- C6, chạy lại lượt đã xong bằng cache: đạt trên bản sao DB, chạy lại ngày 16/11/2026 sau cổng brand_fit và lần chạy lại S4 (lượt kiểm tra `33f1fb5652fe48ea9a0921dffdabf75b`). `koc run --cache-only` ngoại tuyến (network namespace) cho 142 cache hit Kalodata, 0 tín dụng, 32 cache hit LLM, 0 token, và cùng top 5. Cần một bước tay: lượt live đã bỏ qua creator thứ 10 ở S3 để tiết kiệm chi phí (task `skipped`), nên bản chạy lại cũng phải bỏ qua creator này; nếu không, S3 không có cache cho creator đó và lượt chạy dừng ở trạng thái `blocked`. Chưa chạy lại C6 sau cổng brand_fit. [src/koc/pipeline.py](../src/koc/pipeline.py)
- Review độc lập (Codex/OpenAI): 27 file `docs/process/build/REVIEW_*.md`, 26 file có kết luận chung, 18 FAIL và 8 PASS. Các bản sửa sau lượt live qua 8 vòng, từ [REVIEW_live_fixes.md](process/build/REVIEW_live_fixes.md) tới [REVIEW_live_fixes_r8.md](process/build/REVIEW_live_fixes_r8.md) (PASS). Ba phần mới ngày 16/11 đều FAIL ở vòng 1 và PASS ở vòng 2: brief CLI ([REVIEW_brief_input_r2.md](process/build/REVIEW_brief_input_r2.md)), từ chối ngân sách trên web ([REVIEW_web_refusal_r2.md](process/build/REVIEW_web_refusal_r2.md)), cổng brand_fit ([REVIEW_brand_fit_gate_r2.md](process/build/REVIEW_brand_fit_gate_r2.md)). Còn một lỗi P3 mở: fixture autouse trong `tests/conftest.py` làm yếu độ cô lập test của cổng (F5 trong review cổng vòng 2).

## Bảo mật

Chương trình xóa các trường `creator_contact_*` trước khi ghi phản hồi Kalodata vào cache và SQLite. Bản text thô của trang S2 cũng bị lọc dòng liên hệ trước khi ghi. Khóa API chỉ lấy từ biến môi trường. [src/koc/kalodata.py](../src/koc/kalodata.py) [src/koc/db.py](../src/koc/db.py) [src/koc/pipeline.py](../src/koc/pipeline.py)

- Web chỉ chạy cục bộ và KHÔNG có đăng nhập. Mặc định bind `127.0.0.1`; nếu `--host` khác (ví dụ `0.0.0.0`) chương trình in cảnh báo tiếng Việt. Không mở cổng ra mạng ngoài, không đưa lên máy chủ công cộng. [src/koc/web/__main__.py](../src/koc/web/__main__.py)
- Khóa (`KALODATA_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) chỉ đặt qua biến môi trường; `.env` đã nằm trong `.gitignore`. Lịch sử git đã quét, không có khóa thật.
- Chống prompt injection, phần mã đảm bảo: tiêu đề và trích dẫn do bên thứ ba tạo ra được làm sạch, bọc trong khung dữ liệu và prompt nói rõ đó là dữ liệu; mã bằng chứng ngoài danh sách hợp lệ bị từ chối; điểm rubric bị chặn 0-5 bởi schema; thứ hạng tính trong mã từ số liệu, không từ văn bản của mô hình; văn bản giống chỉ thị (tiêu đề, trích dẫn, giải trình) bị gắn "Cảnh báo bảo mật" vào `risks_vi`. Phần phụ thuộc mô hình: mô hình có làm theo chỉ thị chèn hay không. Nếu làm theo, điểm video đó vẫn có thể bị đẩy lên, mã chỉ phát hiện và cảnh báo để kiểm tra thủ công. [src/koc/llm/guard.py](../src/koc/llm/guard.py) [tests/llm/test_injection.py](../tests/llm/test_injection.py)
