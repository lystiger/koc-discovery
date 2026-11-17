# Đánh giá độc lập mô-đun LLM — vòng 2

Ngày: 2026-11-15. Người đánh giá: Codex / OpenAI. Tác giả: Agy. HEAD được đọc: `e9e5d0c`.

**Kết luận chung: FAIL.** Sáu phát hiện vòng 1 đạt PASS; hai phát hiện còn FAIL (P1 ngân sách, P2 toàn vẹn thời gian bằng chứng). Quét bổ sung xác nhận một lỗi P2: video không có audio không thể phân tích. Không có kết luận PASS cho toàn bộ bộ kiểm thử.

Phạm vi: `src/koc/llm/`, `prompts/`, `tests/llm/`; đối chiếu `docs/process/build/REVIEW_llm_by_codex.md`, `docs/process/build/EVIDENCE_llm_fix1.md`, `docs/process/build/CONTRACTS.md` gồm A1 và `docs/process/build/SPEC.md`. Đã đọc cấu hình giá và phần tích hợp BudgetGuard để kiểm tra tác động. Không truy cập mạng, không gọi Gemini thật, không sửa mã hay kiểm thử. Chỉ tạo báo cáo này. Số liệu trong evidence của tác giả không được coi là kết quả chạy độc lập.

## Phán quyết cho tám phát hiện vòng 1

| # | Phán quyết | Bằng chứng độc lập |
|---|---|---|
| 1 — Giới hạn chi phí | **FAIL — P1 còn mở** | `content.py:155,183,224`, `reasons.py:93,130,171`, `gemini.py:87,90,123` đã đồng bộ trần đầu ra 1200/800 với request, tắt thinking và cộng thoughts vào usage. Kích thước ảnh thực được truyền tại `content.py:148,189`. Nhưng `pricing.py:70,85` vẫn dùng heuristic ký tự/3; chưa phải cận trên. Probe ngân sách thật cho phép gọi rồi mới từ chối record khi usage vượt dự trù. Chi tiết R2-1. |
| 2 — Citation, đối tượng và bằng chứng | **FAIL — P2 còn mở** | `content.py:55,74,79,88,93,113` đã chặn video sai, citation/evidence rỗng, ID trùng và citation không tồn tại. `reasons.py:48,61,65,197` đã chặn creator sai/citation rỗng, không ghi đè creator. Probe xác nhận các nhánh đó. Tuy nhiên ID `@999` vẫn hợp lệ với `start_s=0.5` trong video 3 giây; `start_s=3.4` và NaN cũng qua kiểm tra. Chi tiết R2-2. |
| 3 — Frame bền vững, A1 | **PASS** | A1 tại `docs/process/build/CONTRACTS.md:122` cho phép thư mục tạm khi không truyền `frames_dir`. `content.py:136` chọn `<frames_dir>/<video_id>`, `media.py:124` đặt tên `f_<t_ms>.jpg`, `content.py:249` ánh xạ frame bằng code tới mốc gần nhất. Probe ffmpeg thật + malformed JSON rồi repair trả các đường dẫn còn tồn tại sau khi hàm trả về. Test `test_analyze_video_success_order_and_amendment_a1` đạt. PASS theo A1, không tiếp tục yêu cầu đường dẫn production bền vững khi caller bỏ `frames_dir`. |
| 4 — Khóa chỉ từ env | **PASS** | `gemini.py:50` không còn tham số `api_key`; `gemini.py:64` từ chối khóa thiếu/rỗng trước khi tạo SDK. Probe chỉ đặt `GOOGLE_API_KEY` giả, xóa các env khác: ValueError, SDK constructor gọi 0 lần. Hai test env-only đạt. Không đọc hay in khóa thật. |
| 5 — JSON/schema hỏng cần sửa một lần | **PASS** | `content.py:196,230,235,240,268`, `reasons.py:142,177,182,187,206` ghi usage trước parse, xử lý rỗng/schema/nghiệp vụ trong tối đa hai lần. Probe reasons với `{bad`, `None`, sai creator, citation rỗng và sai số lý do: đều gọi hai lần rồi nhận phản hồi hợp lệ. Probe content với `{bad` cũng sửa thành công. Test hai phản hồi hỏng đều raise; test guard chặn repair đều đạt. |
| 6 — Repair giữ nguồn và ràng buộc | **PASS** | `content.py:202,212,214` giữ nguyên prompt, frame và audio gốc; thêm lệnh sửa tiếng Việt và dự trù lại. `reasons.py:149,161,162` giữ prompt gốc cùng số liệu và whitelist. Probe so sánh trực tiếp contents trước/sau: phần gốc không đổi ở cả hai hàm. `prompts/content_v1.md:20` và `prompts/reasons_v1.md:33` nêu tiếng Việt, cấm phỏng đoán lời nói/doanh số, bắt citation. PASS về cấu trúc request/prompt; chất lượng model thật vẫn UNPROVEN. |
| 7 — Test di động và có ý nghĩa | **PASS** | `tests/llm/test_content.py:12`, `tests/llm/test_media.py:10` sinh media bằng ffmpeg trong tmp_path; không còn phụ thuộc media đường dẫn tuyệt đối. `test_content.py:128,143`, `test_reasons.py:128,138` kiểm thứ tự check/call/record và trần token; test giá exact tại `test_pricing.py:41`. Các test malformed JSON, duplicate criterion, citation rỗng, sai đối tượng, repair bị chặn, A1 và env-only đều đạt trong 33 test LLM. Giới hạn: `test_content.py:138` chỉ kiểm estimate > 0; `test_reasons.py:141` không kiểm số tiền check. Bộ test chưa phát hiện R2-1/R2-2/R2-3; PASS này không khẳng định độ phủ đầy đủ hay cận giá đúng. |
| 8 — Hook video ngắn | **PASS** | `media.py:82` giữ hook 0.5 giây khi duration > 0.5; fallback chỉ cho video ngắn hơn. Probe 2 giây/8 frame: `[0.5, 0.69, 0.88, 1.06, 1.25, 1.44, 1.62, 1.81]`. `test_calculate_frame_timestamps_short_video_hook` đạt, gồm video 0.4 và 10 giây. |

Các tên `content.py`, `reasons.py`, `gemini.py`, `pricing.py`, `media.py` trong bảng chỉ tệp dưới `src/koc/llm/`.

## Các lỗi thực chất còn mở

### R2-1 — P1: dự trù đầu vào vẫn không bảo vệ trần cứng

Vị trí: `src/koc/llm/pricing.py:70`, `src/koc/llm/pricing.py:85`, `src/koc/llm/reasons.py:130`, `src/koc/llm/content.py:183`.

Trần đầu ra đã sửa nhưng đầu vào vẫn là `ceil(prompt_chars / 3)`. Không có bước đếm token chính xác hoặc cận trên đã chứng minh. Content còn không tính các chuỗi nhãn frame/audio trong `base_contents` (`content.py:174,179`) vào `prompt_chars`; kích thước schema gửi trong request cũng không được dự trù. Model override vẫn độc lập với bảng giá (`gemini.py:59`). Không có bằng chứng offline rằng mọi model được phép override dùng cùng giá/token accounting.

Probe dùng `write_reasons`, BudgetGuard thật và SQLite trong bộ nhớ, giả lập usage đầu vào cao hơn heuristic nhưng đầu ra vẫn đúng trần 800. Đã chi 4.9955 USD; prompt 2557 ký tự được dự trù 853 token. Chi phí dự trù là 0.003640 USD, nên lời gọi được phép. Phản hồi giả lập 2557 token đầu vào, 800 token đầu ra có giá 0.004918 USD theo chính config. Tổng chi thực theo usage giả lập là 5.000418 USD. `BudgetGuard.record` mới ném BudgetExceeded và không ghi khoản gọi vừa xảy ra (`src/koc/budget_guard.py:21`).

Đây là phản ví dụ có điều kiện bằng usage giả lập, không phải phép đo tokenizer Gemini hoặc hóa đơn thật. Nó chứng minh code không bảo đảm bất biến ngân sách khi heuristic thiếu token; không khẳng định prompt cụ thể này thực tế dùng 2557 token. Vòng 1 đã yêu cầu không coi heuristic là cận trên; fix evidence chưa giải quyết yêu cầu đó.

Sửa: dự trù toàn bộ request theo token count đáng tin cậy hoặc cận trên bảo thủ được chứng minh, cộng trần output; khóa model và bảng giá tương ứng. Bảo đảm usage của cuộc gọi đã thực hiện vẫn được lưu khi vượt dự trù; chỉ chặn sau gọi không thể hoàn tác chi phí.

### R2-2 — P2: bằng chứng có thời gian mâu thuẫn vẫn được trả về

Vị trí: `src/koc/llm/content.py:85`, `src/koc/llm/content.py:96`, `src/koc/llm/content.py:102`, `src/koc/llm/content.py:106`.

Regex chỉ kiểm hình dạng ID, không đối chiếu số sau `@` với `start_s` hoặc thời lượng. So sánh thời gian cho phép vượt video 0.5 giây và không từ chối NaN. Với payload hợp lệ từ test, đổi bằng chứng đầu thành `<video_id>@999`, giữ `start_s=0.5` và sửa citation tương ứng: validator trả `[]`. Probe qua hàm public `analyze_video` với video thật 3 giây trả ID `@999`, thời gian 0.5 và ảnh `f_500.jpg` sau đúng một lần gọi. Không kích hoạt repair.

Các probe riêng đặt `start_s=end_s=3.4` trong video 3 giây hoặc `start_s=NaN,end_s=None` cũng trả `[]`. Đây là lỗi định vị bằng chứng, không phải nhận xét chủ quan về chất lượng model. Downstream nhận citation có mốc khác nguồn ảnh/video, làm mất tính kiểm chứng.

Sửa: parse mốc trong ID và đối chiếu với `start_s` bằng sai số được quy định; yêu cầu thời gian hữu hạn, nằm trong video và end >= start. Thêm ca regression qua hàm public để chứng minh có repair rồi raise nếu vẫn sai.

### R2-3 — P2 mới phát hiện: video không có audio làm hỏng cả phân tích hình ảnh

Vị trí: `src/koc/llm/media.py:143`, `src/koc/llm/media.py:154`; caller `src/koc/llm/content.py:145`.

`preprocess_video` luôn chạy lệnh xuất MP3 và `check=True`, kể cả MP4 không có audio stream. MP4 im lặng là đầu vào hợp lệ; contract `VideoInput` và API không yêu cầu phải có audio. Probe tạo video màu 2 giây bằng ffmpeg, không audio: xuất frame thành công, sau đó `CalledProcessError` exit 234 ở bước MP3. `analyze_video` chưa đến budget check hay Gemini; không có kết quả rubric dù có hình ảnh hợp lệ. Nhánh bỏ qua audio không tồn tại tại `content.py:178` không thể xử lý vì preprocessing đã raise.

Sửa: phát hiện audio stream trước khi trích xuất; với video không audio, cho phép phân tích frame và biểu diễn trạng thái không có lời nói. Vẫn phải báo lỗi thật khi trích xuất một audio stream tồn tại bị hỏng. Thêm fixture không audio và kiểm tra hàm public hoàn tất.

## Thực nghiệm và cách tái hiện

Lệnh bắt buộc đã chạy với `PYTHONDONTWRITEBYTECODE=1` để hạn chế ghi bytecode:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q tests
........................................................................ [ 81%]
..........
```

Lệnh dừng tiến triển ở test web đầu tiên; đã ngắt, exit 130. Chạy lại với `timeout -s INT 30` và `-o faulthandler_timeout=15` cho cùng điểm dừng; sau đó phải ngắt phiên. Stack dump chỉ tới `tests/web/test_app.py:39`, `starlette/testclient.py:407`, `anyio/from_thread.py:347` đang chờ future, portal thread ở `selectors.select`. **Toàn bộ tests: UNPROVEN**, không ghi nhận là test assertion FAIL và không quy lỗi treo này cho mô-đun LLM. Không có bằng chứng xác định nguyên nhân gốc của tình trạng treo trong môi trường review.

Kiểm thử bổ sung:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests/llm
33 passed in 6.68s

PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests --ignore=tests/web
82 passed in 7.80s
```

Probe chạy bằng Python trong bộ nhớ, import helper với `PYTHONPATH=src:tests/llm`; media chỉ sinh trong `TemporaryDirectory`. Tóm tắt output:

```text
empty: 8 validation errors
wrong_video: Video ID không khớp
duplicate_evidence: Mã bằng chứng trùng lặp
ID_timestamp_mismatch []
past_end []
NaN []
public analyze_video accepted: 7705660238917143816@999 start_s=0.5 frame=f_500.jpg calls=1
reasons repair {bad / None / wrong creator / empty citations / wrong count:
  calls=2 events=['check','record','check','record'] base_retained=True
env-only rejected fallback; SDK calls 0
content repair calls=2 events=['check','record','check','record'] media retained=True cap=1200
persisted frame paths True
silent MP4 preprocessing fails 234
estimate(8,30,3000) = 0.007518
synthetic budget probe: chars=2557 estimated_input=853 synthetic_input=2557
  capped_output=800 cost=0.004918 calls=1 logged_total=4.9955
```

Tái hiện R2-2: lấy `_make_valid_analysis_payload()` từ `tests/llm/test_content.py`; đổi ID của `evidence[0]` thành `video_id + '@999'`, thay mọi citation cũ tới ID đó. Gọi `_validate_payload(ContentAnalysisPayload.model_validate(payload), video_id, 3.0)` hoặc trả JSON này qua mock client cho `analyze_video` trên `_create_test_video(..., duration_s=3)`. Giữ `start_s=0.5`. Hai biến thể thời gian dùng payload mới cho mỗi lần: `start_s=end_s=3.4`; `start_s=float('nan'), end_s=None`.

Tái hiện R2-1: dùng `_make_sample_candidate()` và `_make_sample_brief()` từ `test_reasons`, tạo `sqlite3.connect(':memory:')`, gọi `koc.db.init_db`, rồi `BudgetGuard(conn, cap_usd=5)`. Record Usage khởi đầu `cost_usd=4.9955`. Mock `generate_json` đọc `len(contents[0])`, trả payload recommendation hợp lệ và Usage với `input_tokens=len(contents[0])`, `output_tokens=800`, `cost_usd=calculate_cost_usd(input_tokens,800)`. Gọi `write_reasons`; kiểm tra mock đã gọi một lần, BudgetExceeded xuất hiện sau phản hồi và tổng DB vẫn 4.9955.

Tái hiện R2-3:

```bash
ffmpeg -v error -f lavfi -i color=size=360x640:duration=2:rate=10 -c:v libx264 /tmp/koc_r2_silent.mp4
```

Gọi `preprocess_video('/tmp/koc_r2_silent.mp4', '/tmp/koc_r2_silent_out')` trong Python. Probe thực tế dùng đường dẫn riêng trong thư mục tạm để tránh đè file.

Giá/model thật, hỗ trợ `thinking_budget=0`, thuật toán tile và chất lượng hiểu tiếng Việt/video của dịch vụ vẫn **UNPROVEN** trong review offline. Test lặp số config không chứng minh những thuộc tính đó. Không phát hiện thêm lỗi P1/P2 có bằng chứng trong prompts hoặc các nhánh còn lại đã đọc.
