# Independent LLM review — round 3

Date: 2026-11-15. Reviewer: Codex / OpenAI. Author: Agy.
Reviewed HEAD: `ba5cacd`; fix: `4d2db73`. No differences between these commits in `src/koc/llm/`, `tests/llm/`, or pricing config.

**Overall: FAIL. R2-1 remains open (P1). R2-2 and R2-3 PASS.**

Offline review of all six files under `src/koc/llm/`, round 2 report, author’s “Round 2 Fixes” evidence, prompts, pricing config, BudgetGuard, and relevant tests. No network or real Gemini calls. Author evidence was not treated as independent verification. Only this report was created.

| Finding | Verdict | Independent evidence |
|---|---|---|
| R2-1 — P1 budget bound | **FAIL** | Original near-cap probe now blocks before generation: spent `4.9955`, estimate `0.005279`, calls `0`. Full-request bound and model/price binding remain unresolved; details below. |
| R2-2 — P2 evidence time integrity | **PASS** | Public `analyze_video` probes on a real three-second audio/video fixture rejected repeated `@999`/`start_s=0.5`, `start_s=end_s=3.4`, NaN start, and infinite end. Each made exactly two calls, then raised `ValueError`. Suite also confirms mismatched ID can repair successfully. Validation: `src/koc/llm/content.py:108`–`140`. |
| R2-3 — P2 video without audio | **PASS** | Real ffmpeg-generated silent MP4: preprocessing returned eight frames and `audio_path=None`. Public analysis completed after one mock generation; inspecting actual `Part.inline_data.mime_type` found eight `image/jpeg` parts and no audio. Returned transcript was `None`, missing-audio risk was appended, and all evidence frame files existed. Suite verifies zero-audio estimate. Implementation: `src/koc/llm/media.py:153`, `src/koc/llm/content.py:213`. |

## R2-1 — P1 remains open: the claimed bound excludes request schema and permits unpriced models

`src/koc/llm/pricing.py:144`–`153` counts only supplied text parts plus media and output allowance. Callers supply strings from `contents` (`src/koc/llm/reasons.py:154`, `src/koc/llm/content.py:244`), while `src/koc/llm/gemini.py:85` separately sends `response_schema`. Schema overhead is absent from the claimed full-request bound. The UTF-8 argument covers text bytes only; it does not establish a bound for this additional request material or prove the configured media accounting.

Independent conditional counterexample, using test candidate/brief helpers, real SQLite BudgetGuard, and mock generation:

```text
prompt UTF-8 bytes: 3039
RecommendationPayload JSON-schema bytes: 513
checked estimate (3039 input + 800 output): 0.005279 USD
synthetic usage (3552 input + 800 output): 0.005664 USD
initial recorded spend: 4.9945285 USD
generation calls: 1
record: BudgetExceeded; logged spend stays 4.9945285 USD
initial spend + synthetic call: 5.0001925 USD
```

This is a conditional accounting probe, not a measured Gemini token count. JSON-schema byte length is a reproducible synthetic usage increment, not proof of actual schema tokenization. It demonstrates that an underestimated response is still rejected only after generation and then omitted from the ledger (`src/koc/budget_guard.py:21`). Actual tokenization, schema overhead, and media bounds remain **UNPROVEN** offline; the original counterexample passing does not prove the general invariant.

Separately, `src/koc/llm/gemini.py:59` still accepts arbitrary model overrides while `generate_json` prices usage with the unchanged config (`gemini.py:139`). An injected SDK probe accepted `arbitrary-unpriced-model`, sent that model to generation, and charged `0.75 USD` for one million input tokens using the default table. No model-to-price/accounting validation exists. This was already part of R2-1, not a new finding.

Required closure: bind the allowed model to its verified prices/accounting; count or conservatively bound the complete request, including schema; retain usage for completed calls even when an estimate is exceeded. Do not label the current partial estimate a proven universal bound.

## Tests and short sweep

Requested command, with bytecode writes disabled:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q tests/llm tests/core
68 passed in 10.97s
```

Skipped `tests/web` as requested. Independent probes ran through Python stdin with `PYTHONPATH=src:tests/llm`; generated media lived in `TemporaryDirectory`. Budget probes used `test_reasons` sample helpers; time probes used `test_content` payload helpers, repeating each invalid response twice through the public API. No project source or tests were changed.

Short sweep covered validation/repair, citation resolution, frame mapping, media extraction, SDK request/usage handling, and pricing. No additional independently confirmed P1/P2 defect found. Live service behavior, prices, tokenizer/media accounting, and model quality remain **UNPROVEN** under the no-network constraint.
