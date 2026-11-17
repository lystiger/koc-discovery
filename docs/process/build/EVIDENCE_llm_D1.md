# Evidence Report: LLM/Media Module (Deliverable D1)

Date: 2026-11-15  
Owner: Agy (Gemini 3.8 Flash high)  
Branch: `feat/koc-llm`  
Repository Worktree: `/home/lystiger/Projects/KOC-Discovery-llm`

---

## 1. Work Completed

Per `SPEC.md` and `CONTRACTS.md` (§1-2), the LLM and media processing components for KOC Discovery MVP have been implemented:

1. **`src/koc/llm/media.py`**:
   - `preprocess_video(mp4_path, out_dir, n_frames=8) -> dict`:
     - Extracts 8 JPEG frames scaled to 360 px wide (frame 0 at 0.5 s for opening hook, remaining 7 evenly distributed).
     - Extracts 16 kHz mono audio in compressed MP3 format (32 kbps) for lightweight upload to Gemini.
     - Computes video duration and sha256 checksum.
     - Tested on real MP4 file `/home/lystiger/Projects/KOC-Discovery/data/raw/media/7705660238917143816.mp4`.

2. **`config/llm_prices.yaml` & `src/koc/llm/pricing.py`**:
   - Configured official rates for `gemini-3.8-flash` from Google documentation verified on 2026-11-15.
   - `estimate_usd(n_frames, audio_s, prompt_chars)` helper for pre-flight budget checks (`budget_guard.check`).
   - `calculate_cost_usd(input_tokens, output_tokens)` for post-call cost calculation.

3. **`src/koc/llm/gemini.py`**:
   - Thin client wrapping `google-genai` SDK (`genai.Client`).
   - Model defaulted from config (`gemini-3.8-flash`).
   - Enforces structured JSON output via `types.GenerateContentConfig(response_mime_type="application/json", response_schema=...)`.
   - Extracts `usage_metadata` (prompt tokens, candidate tokens, audio/image token breakdowns from `prompt_tokens_details`).
   - Measures wall latency in milliseconds and computes `cost_usd`.
   - Automatic single retry on transient errors (`ServerError`, HTTP 429 rate limit, network timeouts).

4. **`src/koc/llm/content.py` & `prompts/content_v1.md`**:
   - `analyze_video(video: VideoInput, brief: BrandBrief, *, budget_guard: BudgetGuard) -> ContentAnalysis`:
     - Single multimodal call: 8 frames + 16 kHz mono audio + video metadata + BrandBrief.
     - Prompted in Vietnamese: `transcript_vi` (exact speech, unclear words marked `[không rõ]`), 7 rubric criteria (0–5 with `rationale_vi` and `evidence_ids`), `risks_vi` (claims/brand-safety), and `evidence` list with timestamps.
     - Validation: exactly 7 criteria (`hook`, `product_clarity`, `demonstration`, `claim_quality`, `cta`, `brand_fit`, `production_quality`), all rubric `evidence_ids` verified against the `evidence` list.
     - Automatic repair retry with error explanation if validation fails; raises if second attempt fails.
     - Calls `budget_guard.check(estimate)` before every call and `budget_guard.record(usage)` after.

5. **`src/koc/llm/reasons.py` & `prompts/reasons_v1.md`**:
   - `write_reasons(c: CandidateSummary, brief: BrandBrief, *, budget_guard: BudgetGuard) -> Recommendation`:
     - Generates 3–5 Vietnamese recommendation reasons and caveats.
     - Validates that all `cited_evidence_ids` exist in the candidate summary metrics or video analyses.
     - Automatic repair retry if reason count or evidence IDs are invalid.
     - Enforces `budget_guard.check` before and `budget_guard.record` after.

6. **`tests/llm/`**:
   - 18 comprehensive unit and integration tests covering preprocessing on real media, pricing calculations, Gemini client retry on transient failures, budget guard enforcement, and repair retry loops.
   - All external API calls strictly mocked; 0 live network calls made.

---

## 2. Pytest Output

### A. LLM Suite (`tests/llm`)
```
============================= test session starts ==============================
platform linux -- Python 3.14.8, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/lystiger/Projects/KOC-Discovery-llm
configfile: pyproject.toml
plugins: anyio-4.16.0
collecting ... collected 18 items

tests/llm/test_content.py ....                                           [ 22%]
tests/llm/test_gemini.py ....                                            [ 44%]
tests/llm/test_media.py ..                                               [ 55%]
tests/llm/test_pricing.py ....                                           [ 77%]
tests/llm/test_reasons.py ....                                           [100%]

============================== 18 passed in 6.04s ==============================
```

### B. Full Test Suite (`pytest -q`)
```
........................................                                 [100%]
40 passed in 6.06s
```

---

## 3. Pricing Sources (Verified 2026-11-15)

| Item | Value | Source URL | Verification Date |
|---|---|---|---|
| **Model ID** | `gemini-3.8-flash` | `https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash` | 2026-11-15 |
| **Input Tokens (Standard Paid)** | $0.75 / 1M tokens | `https://ai.google.dev/pricing` | 2026-11-15 |
| **Output Tokens (Standard Paid)** | $3.75 / 1M tokens | `https://ai.google.dev/pricing` | 2026-11-15 |
| **Context Cache Read** | $0.075 / 1M tokens | `https://ai.google.dev/pricing` | 2026-11-15 |
| **Image Token Accounting** | 258 tokens / tile (<= 768x768) | `https://ai.google.dev/gemini-api/docs/tokens` | 2026-11-15 |
| **Audio Token Accounting** | 32 tokens / second | `https://ai.google.dev/gemini-api/docs/tokens` | 2026-11-15 |
| **Video Token Accounting** | 263 tokens / second | `https://ai.google.dev/gemini-api/docs/tokens` | 2026-11-15 |
| **JSON Mode & Response Schema** | `response_mime_type="application/json"`, `response_schema` | `https://ai.google.dev/gemini-api/docs/structured-output` | 2026-11-15 |
| **Usage Metadata Fields** | `prompt_token_count`, `candidates_token_count`, `prompt_tokens_details` | `google.genai.types.GenerateContentResponseUsageMetadata` | 2026-11-15 |

---

## 4. Estimated Tokens and USD per Video

For standard TikTok video analysis with **8 frames** + **30 seconds audio**:

### Input Breakdown
- **8 frames (360x640 JPEG)**: $8 \times 258\text{ tokens} = \mathbf{2,064\text{ tokens}}$
- **30 s audio (16 kHz mono MP3)**: $30 \times 32\text{ tokens/s} = \mathbf{960\text{ tokens}}$
- **Prompt text (Vietnamese instructions + video metadata)**: $\sim 3,000\text{ chars} \approx \mathbf{1,000\text{ tokens}}$
- **Total Input Tokens**: $\approx \mathbf{4,024\text{ tokens}}$
- **Input Cost**: $4,024 \times \frac{\$0.75}{1,000,000} = \mathbf{\$0.003018\text{ USD}}$

### Output Breakdown
- **Structured ContentAnalysis JSON (rubric, transcript, evidence, risks)**: $\sim \mathbf{1,200\text{ tokens}}$
- **Output Cost**: $1,200 \times \frac{\$3.75}{1,000,000} = \mathbf{\$0.004500\text{ USD}}$

### Total per Video
- **Total Cost per Video**: $\mathbf{\$0.007518\text{ USD}}$ ($\approx 190\text{ VND}$)

### Campaign Projection (45 Videos)
- 15 shortlisted candidates $\times$ 3 videos each = 45 video analyses.
- **Estimated S3 Content Analysis Total**: $45 \times \$0.007518 \approx \mathbf{\$0.338\text{ USD}}$.
- **Estimated S4 Reasons Generation Total (5 candidates)**: $5 \times \$0.00266 \approx \mathbf{\$0.013\text{ USD}}$.
- **Total Estimated LLM Spend**: $\mathbf{\$0.351\text{ USD}}$, consuming only **7.0%** of the **$5.00 USD hard cap**.

---

## 5. Open Questions & Integration Notes for Core

1. **Transient Retry Backoff**:
   - `GeminiClient` currently sleeps 0.5s before retrying once on transient errors (`ServerError` or 429).
2. **Core Runner Caching**:
   - Per CONTRACTS §2, caching by `sha256(media sha256 + prompt_version + model + brief)` is handled by core's `llm_cache` table. The LLM module remains completely stateless.
3. **No Contract Changes Needed**:
   - CONTRACTS §1-2 were strictly fulfilled without modifications. `CHANGE_REQUEST_llm.md` was not required.
