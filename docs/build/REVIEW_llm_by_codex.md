# Đánh giá độc lập mô-đun LLM

Ngày: 2026-11-15. Người đánh giá: Codex / OpenAI; tác giả được giao: Agy / Gemini (khác nhà cung cấp theo thông tin giao việc).

Phạm vi: `src/koc/llm/`, `prompts/`, `config/llm_prices.yaml`, `tests/llm/`; đối chiếu `docs/build/SPEC.md` và `docs/build/CONTRACTS.md` §1–2. Không truy cập mạng. Không sửa mã nguồn hoặc kiểm thử. Chỉ tạo báo cáo này.

**Kết luận chung: FAIL.** Bộ kiểm thử hiện có xanh nhưng chưa chứng minh giới hạn chi phí cứng, tính toàn vẹn bằng chứng và yêu cầu chỉ nhận khóa qua biến môi trường.

## Phát hiện theo mức độ nghiêm trọng

1. **P1 — Ước lượng không chặn được chi phí thực tế.** `src/koc/llm/pricing.py:52`, `src/koc/llm/reasons.py:102`, `src/koc/llm/gemini.py:80`: dự trù 1.200 token đầu ra cho phân tích và 600 cho lý do, nhưng không đặt `max_output_tokens`. Bóc băng đầy đủ có thể vượt xa dự trù; kiểm tra ngân sách trước gọi không bảo đảm trần 5 USD. Probe cho cùng 4.024 token đầu vào: dự trù 0,007518 USD, nhưng 10.000 token đầu ra tốn 0,040518 USD theo chính config. Tại mức đã chi 4,98 USD, dự trù lọt qua còn kết quả vượt trần. **Sửa:** áp giới hạn đầu ra phù hợp, dự trù theo giới hạn thực và mọi thành phần token tính phí; dùng cùng config/model giữa dự trù và client. Tính số tile theo kích thước ảnh thay vì mặc định một tile mỗi frame; chiều rộng 360 không giới hạn chiều cao. Không coi heuristic 3 ký tự/token là cận trên đã được chứng minh.

2. **P1 — Cho phép kết quả không có bằng chứng và bằng chứng sai video.** `src/koc/llm/content.py:47`, `src/koc/llm/reasons.py:40`: chỉ kiểm tra quan hệ tập hợp nên danh sách citation rỗng luôn hợp lệ. Không đối chiếu `payload.video_id`, `Evidence.video_id`, định dạng ID, ID trùng hoặc khoảng thời gian với video đầu vào. `src/koc/llm/reasons.py:143` còn ghi đè creator trả về bằng creator đầu vào, che phản hồi sai đối tượng. Probe xác nhận bảy rubric không có citation, evidence rỗng và video sai đều không có lỗi; recommendation có ba lý do, creator sai và citation rỗng vẫn được trả về. **Sửa:** kiểm tra ID đối tượng, ID bằng chứng duy nhất/đúng định dạng, thời gian hợp lệ và ít nhất một bằng chứng cho mỗi rubric; bắt recommendation có citation khi đề xuất dựa trên dữ liệu. Giữ đúng một lần sửa rồi báo lỗi nếu vẫn sai. Yêu cầu không rỗng phục vụ SPEC C3 và nguyên tắc prompt, ngoài kiểm tra membership tối thiểu của contract.

3. **P1 — Bằng chứng frame không có đường dẫn bền vững.** `src/koc/llm/content.py:118`, `src/koc/llm/content.py:164`, `src/koc/llm/content.py:172`: chỉ gửi bytes và timestamp; không gán `Evidence.frame_path` từ frame thực. Sau gọi mặc định, thư mục tạm bị xóa trước khi trả về. Model không biết đường dẫn cục bộ để tạo liên kết đúng; ngay cả đường dẫn đúng trong thư mục tạm cũng hết tồn tại. Đây là cản trở phần bằng chứng ảnh của SPEC C9. **Sửa:** lưu frame trong vùng artifact bền vững do core quản lý, ánh xạ evidence frame về timestamp/path đã tạo, kiểm tra file tồn tại sau khi hàm trả về. Không giao model tự đặt đường dẫn.

4. **P2 — Không tuân thủ `GEMINI_API_KEY` env only.** `src/koc/llm/gemini.py:52`, `src/koc/llm/gemini.py:64`: nhận khóa trực tiếp qua `api_key`; khi biến `GEMINI_API_KEY` thiếu, truyền `None` cho SDK và để SDK chọn nguồn khác. SDK cài tại `.venv/lib/python3.14/site-packages/google/genai/_api_client.py:163` có logic đọc `GOOGLE_API_KEY`. **Sửa:** bỏ tham số khóa ở giao diện production, yêu cầu `GEMINI_API_KEY` không rỗng trước tạo SDK; giữ injection client cho test. Không thấy khóa thật hoặc câu lệnh ghi khóa trong các tệp thuộc phạm vi; đây là sai nguồn cấp khóa, không phải bằng chứng rò rỉ khóa.

5. **P2 — JSON hỏng hoặc sai schema bỏ qua sửa một lần.** `src/koc/llm/content.py:136`, `src/koc/llm/reasons.py:113`: `model_validate_json` nằm trước nhánh sửa. JSON sai cú pháp, thiếu trường bắt buộc hoặc score ngoài 0–5 ném `ValidationError` ngay. Probe `{bad` cho reasons: một lần gọi, một lần record, không sửa. Hành vi từ chối là an toàn và vẫn ghi usage, nhưng không đạt lời hứa retry khi validation thất bại của mô-đun. **Sửa:** gộp lỗi parse/schema và lỗi nghiệp vụ vào vòng tối đa hai lần; ghi usage mỗi phản hồi trước parse, từ chối rõ ràng sau lần hai. Thêm trường hợp response.text rỗng/None.

6. **P2 — Lần sửa mất ngữ cảnh và ràng buộc chống bịa.** `src/koc/llm/content.py:151`, `src/koc/llm/reasons.py:129`: request sửa chỉ chứa lỗi và JSON trước, không có prompt gốc, brief hay media; nội dung sửa còn dùng tiếng Anh. Model có thể tự thêm evidence để hợp thức hóa rubric mà không xem lại media, hoặc đổi ngôn ngữ lý do. `prompts/reasons_v1.md:33` không cấm suy diễn doanh số từ hình/lời nói như prompt content. **Sửa:** gửi lại ngữ cảnh gốc và media cho sửa content, nguồn dữ liệu gốc cho sửa reasons, đồng thời giữ yêu cầu tiếng Việt và không bịa/suy diễn. Dự trù lại toàn bộ request sửa. Bổ sung lệnh rõ ràng trong cả hai prompt: chỉ xuất tiếng Việt, không suy đoán lời nói hoặc doanh số, trích dẫn đúng nguồn.

7. **P2 — Bộ test có giá trị nhưng chưa đủ và phụ thuộc máy tác giả.** `tests/llm/test_content.py:9`, `tests/llm/test_media.py:9`: dùng đường dẫn tuyệt đối tới media cục bộ. Test guard kiểm số lần gọi nhưng không chứng minh thứ tự check/call/record; test estimate tại `tests/llm/test_pricing.py:34` chấp nhận khoảng rất rộng. Thiếu test JSON hỏng, rubric trùng tiêu chí, citation rỗng, video sai, repair bị chặn ngân sách, frame còn tồn tại và env-only. **Sửa:** sinh video nhỏ trong tmp_path hoặc dùng fixture tương đối có trong repo; fake client/guard ghi chuỗi sự kiện, assert thứ tự và số tiền; thêm các ca phản ví dụ trên và assert kết quả estimate chính xác. Các test hiện có không hoàn toàn tautological: chạy ffmpeg thật, kiểm kích thước ảnh, tính giá bằng số cụ thể và kiểm retry/citation không hợp lệ là kiểm hành vi thực. Mock trả payload sẵn không chứng minh chất lượng tiếng Việt hoặc tính đúng của nội dung lý do.

8. **P3 — Hook sai mốc cho video ngắn hơn 4,5 giây.** `src/koc/llm/media.py:36`: dùng `duration_s / (n_frames + 1)` thay vì chỉ thay thế khi video quá ngắn cho mốc 0,5 giây. Probe video 2 giây, 8 frame trả hook 0,22 giây; contract yêu cầu 0,5 giây. **Sửa:** giữ hook 0,5 giây khi video chứa mốc này, chỉ chọn fallback khi cần; phân bố các frame còn lại sau hook, thêm test video ngắn.

## Phán quyết từng mục

| Mục kiểm tra | Phán quyết | Bằng chứng và giới hạn |
|---|---|---|
| Chữ ký và shared types | PASS | Hàm công khai nhận được đúng lời gọi contract, import model từ `koc.types`; tham số tùy chọn thêm không phá caller hiện có. Payload riêng không thay shared types. |
| `budget_guard.check` trước / `record` sau | PASS | `content.py:115,129,134,149,151,156`; `reasons.py:103,106,111,127,129,134`. Cả hai nhánh sửa đều kiểm tra trước và ghi sau phản hồi thành công. Retry lỗi transport trong `gemini.py:90` không có guard riêng; không có bằng chứng offline về token bị tính phí cho phản hồi lỗi transport. |
| Giới hạn chi phí cứng / độ an toàn dự trù | FAIL | Phát hiện 1; không có giới hạn đầu ra tương ứng dự trù. |
| Citation recommendation thuộc tập đầu vào, sửa đúng một lần rồi raise | PASS | `reasons.py:32,45,117,138`; test ID bịa và hai phản hồi sai đều chạy. PASS này chỉ nói membership của ID được khai báo, không chứng minh mọi lý do đều có bằng chứng. |
| Toàn vẹn bằng chứng và định danh | FAIL | Phát hiện 2–3; probe chấp nhận không có citation và sai video. |
| Đúng bảy tiêu chí rubric, mỗi tiêu chí một lần | PASS | `content.py:27,49,52`: len = 7 cộng đủ tập bảy Literal kéo theo không có tiêu chí trùng. Điểm được shared type giới hạn 0–5. |
| Phép tính USD so với config | PASS | `pricing.py:31`: input/1e6 × 0,75 + output/1e6 × 3,75; test 1M/1M = 4,50 USD, 10k/2k = 0,015 USD. Đây là phép tính cho các token được truyền vào, không chứng minh đủ mọi token tính phí. |
| Giá/model thực tế và toàn bộ usage tính phí | UNPROVEN | Config có URL/ngày nhưng review không dùng mạng, không có bản nguồn chính thức offline trong phạm vi để xác minh tuyên bố verified. `gemini.py:113` chỉ lấy prompt/candidate token; SDK có `thoughts_token_count` (`types.py:8700`) nhưng code bỏ qua. Cần chứng minh chính sách tính phí thinking của model rồi tính đủ hoặc tắt thinking hợp lệ. Không được suy ra giá thật từ test lặp số config. |
| Token estimate hợp lý để bảo vệ ngân sách | FAIL | Các đơn vị và ceil audio/text hợp lý về số học; output không bị chặn, tile bị coi cố định, reasons hardcode 600 thay vì config 800. Không phải cận chi phí đáng tin cậy. |
| Prompt content: tiếng Việt, không đoán lời nói/doanh số, quote evidence | PASS | `prompts/content_v1.md:20–22,35–38` nêu rõ các yêu cầu. Đây là kiểm nội dung prompt, không phải chất lượng phản hồi live. |
| Prompt reasons và prompt sửa giữ các ràng buộc trên | FAIL | Phát hiện 6; reasons có whitelist ID nhưng thiếu các cấm đoán rõ ràng, repair thiếu nguồn và ràng buộc gốc. |
| Xử lý JSON model hỏng | FAIL | Có fail-closed và record trước parse; thiếu retry sửa cho parse/schema failure như phát hiện 5. |
| Secrets: chỉ `GEMINI_API_KEY` env | FAIL | Phát hiện 4. Không thấy secret literal trong phạm vi đã đọc. |
| Test có ý nghĩa | PASS | Test tính giá, ffmpeg thật, budget block và citation retry kiểm hành vi thực; không chỉ assert mock trả chính nó. |
| Độ phủ test đủ cho yêu cầu review | FAIL | Phát hiện 7 và các probe phản ví dụ vẫn lọt qua bộ test xanh. |
| Lệnh pytest được yêu cầu | PASS | `18 passed in 6.16s`, exit code 0. |
| Media theo contract | FAIL | 360 px JPEG và audio 16 kHz mono có trong lệnh ffmpeg; hook video ngắn sai. |

## Thực nghiệm offline

Lệnh được yêu cầu:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q tests/llm
..................                                                       [100%]
18 passed in 6.16s
```

Probe Python chạy trong bộ nhớ, dùng fixture/helper của `tests/llm` và client mock; không ghi thêm test, không gọi SDK ra mạng:

```text
Empty citations accepted: [] ; wrong response creator accepted: cr_456
Malformed JSON: ValidationError calls= 1 records= 1
Wrong video + no evidence validation errors: []
2 second hook: 0.22
Estimate 8 frames/30s/3000 chars: 0.007518
Same input, 10000 output tokens: 0.040518
```

Cách tái hiện: dùng `_make_sample_candidate`, `_make_sample_brief` từ `test_reasons`, trả payload có `creator_id='wrong'`, ba lý do và `cited_evidence_ids=[]` qua mock client; gọi `write_reasons`. Sau đó trả chuỗi `{bad` và đếm số lần gọi/record. Với content, lấy `_make_valid_analysis_payload`, đổi video ID, xóa evidence và mọi rubric citation; gọi `_validate_payload(ContentAnalysisPayload.model_validate(payload))`. Với media gọi `_calculate_frame_timestamps(2, 8)`; với giá gọi `estimate_usd(8, 30, 3000)` và `calculate_cost_usd(4024, 10000)`.

Chưa chứng minh: chất lượng nhận dạng audio/video bằng model thật, khả năng tồn tại của model/giá công bố, và usage billable đầy đủ. Các mục này giữ UNPROVEN; không dùng mạng hoặc chạy live để lấp khoảng trống.
