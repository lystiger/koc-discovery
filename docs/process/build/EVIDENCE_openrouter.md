# Bằng Chứng Thực Hiện Hợp Đồng A2: Tích Hợp OpenRouter Provider Cho LLM Module & Khắc Phục Sau Đánh Giá Độc Lập

**Dự án:** KOC Discovery  
**Nhánh git:** `feat/koc-orfix`  
**Chủ sở hữu module:** LLM Module Owner (Agy)  
**Ngày thực hiện:** 2026-11-15  
**Căn cứ kỹ thuật:** Hợp đồng `docs/process/build/CONTRACTS.md` — Phụ lục A2 (Amendment A2) và Báo cáo Đánh giá Độc lập `docs/process/build/REVIEW_openrouter_kalodata.md`.

---

## 1. Tổng quan triển khai & Các điểm khắc phục sau Review

Đã triển khai và hoàn thiện toàn bộ các yêu cầu của Phụ lục hợp đồng A2 cùng 4 điểm sửa chữa sau phiên đánh giá độc lập:

1. **Kiểm soát cổng ngân sách cho transport retries (Budget Gate on Transport Retries — Điểm 1)**:
   - Trước đây: vòng lặp retry HTTP 503/429 bên trong `OpenRouterClient.generate_json` gửi thêm request mà không thông qua cổng `budget_guard.check`.
   - Khắc phục: mọi lần gửi HTTP outbound (kể cả lần đầu và các lần retry do lỗi mạng, HTTP 429 hoặc HTTP 5xx) đều phải được kiểm tra trước bởi `budget_guard.check(upper_bound)`.
   - Tái cấu trúc đường dẫn kiểm tra: `content.py` và `reasons.py` chuyển `budget_guard` và cận trên `upper_bound_usd` vào `generate_json`; các lần retry đều thực thi `active_guard.check(bound_usd)` trước khi gọi `http_client.post`.
   - Kiểm thử tự động với chuỗi phản hồi HTTP 503, 503, 200 xác nhận tuyệt đối thứ tự sự kiện: `['check', 'http', 'check', 'http', 'check', 'http', 'record']`.

2. **Định mức đa phương thức bảo thủ và biên an toàn 1.5 (Multimodal Conservative Estimate — Điểm 2)**:
   - Dừng gọi cận trên đa phương thức là "provable" (chứng minh được) trong docstrings và tài liệu bằng chứng.
   - Mô tả chính xác là **ước tính bảo thủ (`conservative estimate`)** do định mức token cho ảnh và âm thanh của OpenRouter (`google/gemini-3.8-flash`) là **UNVERIFIED** (OpenRouter tổng hợp định tuyến không công bố bảng token tile/second riêng lẻ).
   - Áp dụng hệ số an toàn **1.5** lên các số hạng token ảnh và âm thanh (`multimodal_safety_factor: 1.5` trong [config/llm_prices.yaml](file:///home/lystiger/Projects/KOC-Discovery-orfix/config/llm_prices.yaml)).
   - Sau mỗi cuộc gọi thực tế thành công, nếu usage thực tế trả về từ OpenRouter vượt mức ước tính (về chi phí USD hoặc số lượng token đầu vào), hệ thống tự động ghi log cảnh báo tiếng Việt kèm cả hai con số thực tế và ước tính.

3. **Bóc tách chi tiết lỗi non-200, khử sạch key và giới hạn 300 ký tự (Detailed Error Reporting — Điểm 3)**:
   - Khi OpenRouter trả về mã lỗi HTTP không phải 200 (ví dụ HTTP 400 Bad Request, 402, 429, 5xx): `RuntimeError` bóc tách và thể hiện đầy đủ nội dung từ `error.message` và `error.metadata.raw` (nếu có từ upstream provider).
   - Chuỗi chi tiết lỗi được giới hạn tối đa 300 ký tự.
   - Khử sạch mọi dấu vết của API key (`OPENROUTER_API_KEY`, các tiền tố Bearer hoặc mẫu regex token) thành `[REDACTED]`.

4. **Cấu hình trường reasoning và xử lý finish_reason 'length' (Reasoning Config & Finish Reason — Điểm 4)**:
   - Trường `reasoning` được cấu hình linh hoạt trong [config/llm_prices.yaml](file:///home/lystiger/Projects/KOC-Discovery-orfix/config/llm_prices.yaml) dưới mục `openrouter.reasoning`. Mặc định: bỏ qua hoàn toàn trường `reasoning` trong payload thay vì hardcode `{"effort": "none"}` (tránh lỗi HTTP 400 với các provider không hỗ trợ tham số này).
   - Nếu phản hồi trả về có `finish_reason == "length"` và nội dung `content` rỗng, hệ thống ném ngoại lệ tiếng Việt rõ ràng: `"Phản hồi OpenRouter bị cắt ngắn do hết giới hạn max_tokens mà chưa có nội dung (finish_reason='length')"`.

5. **Trừu tượng hóa Provider & Giữ nguyên Model Pinning**:
   - `get_llm_client()` tại [src/koc/llm/factory.py](file:///home/lystiger/Projects/KOC-Discovery-orfix/src/koc/llm/factory.py) tự động chọn provider từ cấu hình (`openrouter` mặc định, `gemini` tùy chọn).
   - Chỉ cho phép các model đã được định nghĩa giá rõ ràng trong file cấu hình (`get_model_pricing`). Mọi model chưa định giá đều bị từ chối trước khi gọi API.

---

## 2. Bằng chứng chạy kiểm thử (Test Execution Evidence)

Lệnh thực thi kiểm thử:
```bash
PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/llm tests/core
```

Kết quả:
```text
........................................................................ [ 62%]
...........................................                              [100%]
115 passed in 22.26s
```

Toàn bộ 115 bài test đạt kết quả **PASS** 100%:
- 21 bài test OpenRouter client (`tests/llm/test_openrouter.py`), bao gồm:
  - Kiểm tra thứ tự sự kiện `check, http, check, http, check, http, record` với chuỗi 503, 503, 200.
  - Kiểm tra chặn retry nếu `budget_guard.check` phát hiện vượt ngân sách.
  - Kiểm tra cảnh báo tiếng Việt với cả hai con số khi actual usage vượt estimate.
  - Kiểm tra bóc tách HTTP 400 gồm `error.message` và `error.metadata.raw`, khử sạch key và cắt ngắn 300 ký tự.
  - Kiểm tra trường `reasoning` được bỏ qua mặc định và nhận cấu hình khi thiết lập.
  - Kiểm tra lỗi tiếng Việt khi `finish_reason == 'length'` với content rỗng.
- 22 bài test pricing (`tests/llm/test_pricing.py`) cập nhật hệ số an toàn 1.5 cho ảnh và âm thanh.
- Toàn bộ các bài test core pipeline, media, content và reasons tiếp tục pass 100%.

---

## 3. Bằng chứng kiểm tra kịch bản `scripts/llm_check.py`

### 3.1. Chạy khi thiếu biến môi trường `OPENROUTER_API_KEY`:
```bash
$ PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python scripts/llm_check.py
FAIL: Biến môi trường OPENROUTER_API_KEY không được để trống
Exit code: 1
```

### 3.2. Chạy với MockTransport trong test suite (`tests/llm/test_openrouter.py::test_scripts_llm_check`):
```text
OK
Provider: openrouter
Model: google/gemini-3.8-flash
Tokens: in=45, out=12, total=57
Cost: $0.000087
```

---

## 4. Danh mục file thay đổi & Tính nguyên vẹn ranh giới sở hữu

| File | Thay đổi | Tuân thủ ranh giới sở hữu |
|---|---|---|
| `config/llm_prices.yaml` | Thêm `multimodal_safety_factor: 1.5`, cấu hình `openrouter.reasoning: null`, cập nhật doc/comment | Thuộc sở hữu LLM |
| `src/koc/llm/pricing.py` | Áp dụng hệ số an toàn 1.5 vào token ảnh/audio; cập nhật docstring mô tả ước tính bảo thủ UNVERIFIED; bổ sung `estimate_tokens_and_usd` | Thuộc sở hữu LLM |
| `src/koc/llm/openrouter.py` | Kiểm tra budget gate trước mọi HTTP attempt (kể cả transport retries); cảnh báo usage vượt ước tính; bóc tách `error.message` + `metadata.raw` giới hạn 300 ký tự khử key; cấu hình `reasoning`; kiểm tra `finish_reason == 'length'` | Thuộc sở hữu LLM |
| `src/koc/llm/gemini.py` | Hỗ trợ `**kwargs` trong `generate_json` tương thích giao thức chung | Thuộc sở hữu LLM |
| `src/koc/llm/content.py` | Chuyển `budget_guard` và cận trên vào `generate_json`; cập nhật comment | Thuộc sở hữu LLM |
| `src/koc/llm/reasons.py` | Chuyển `budget_guard` và cận trên vào `generate_json`; cập nhật comment | Thuộc sở hữu LLM |
| `src/koc/llm/__init__.py` | Export `estimate_tokens_and_usd` | Thuộc sở hữu LLM |
| `tests/llm/test_openrouter.py` | Thêm các bài test cho retry budget order (503, 503, 200), retry budget block, usage warning, HTTP 400 error reporting, reasoning config, finish_reason | Thuộc sở hữu LLM |
| `tests/llm/test_pricing.py` | Cập nhật giá trị kiểm thử phù hợp hệ số an toàn 1.5 trên token ảnh và audio | Thuộc sở hữu LLM |
| `docs/process/build/EVIDENCE_openrouter.md` | Tài liệu hóa toàn diện các cải tiến và kết quả kiểm thử | Thuộc sở hữu LLM |

Tất cả các thay đổi đều nằm trong phạm vi module LLM được phân công. Không can thiệp mã ngoài phạm vi. Nhánh không merge vào main.
