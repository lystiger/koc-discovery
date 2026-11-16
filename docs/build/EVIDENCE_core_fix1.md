# Core fix 1 evidence

Date: 2026-11-15. Scope: core, `tests/core/`, and `scripts/kill_resume_test.sh`.
No network or live API calls used.

## Review findings

| Finding | Fix | Regression evidence |
|---|---|---|
| P1-1: S2 audience metrics were not written. | `src/koc/pipeline.py:106-111` writes each metric in a plain loop, then writes the score in the task transaction. Both mock and browser paths use it at `pipeline.py:331-338`. | `test_mock_run_writes_s2_metrics` and `test_page_path_creates_audience_tasks_and_writes_metrics` assert all three audience metric rows. Both failed before the fix. |
| P1-2: LLM cache hits kept original token counts. | `src/koc/pipeline.py:141-150` clears input, output, audio, and image token counts and cost while marking cache hits. Used for both regular and mock cache paths. | `test_cached_llm_call_logs_zero_tokens_and_cost` seeds 1,500 input and 300 output tokens, then asserts the cache-hit result and `llm_calls` row record zero tokens and cost. It failed before the fix. |
| P2-3: `_audience_tasks` caused `NameError` when a page was supplied. | `src/koc/pipeline.py:286-288` always creates S2 tasks from the S1 shortlist. | `test_page_path_creates_audience_tasks_and_writes_metrics` exercises `_advance` with a page and asserts the task exists. It failed before the fix. |
| P2-4: 500-candidate cost projection scaled the whole funnel linearly. | `src/koc/report.py:82-86` projects five S0 ranking pages at configured price and keeps observed downstream credits, tokens, and USD unchanged. | `test_projection_500_keeps_funnel_costs_and_scales_s0_pages` asserts projected credits are 0.5 S0 + observed downstream credits; tokens and USD stay at observed values. It failed before the fix. |
| P3-5: Kalodata exceptions were in English. | `src/koc/kalodata.py:137-148` now emits Vietnamese authentication and request errors. | `test_request_errors_are_in_vietnamese` checks authentication, client, and exhausted server-error responses. |
| P3-6: Resume script used a machine-specific Python path. | `scripts/kill_resume_test.sh:4-5` derives the default interpreter from repository root; `PYTHON` remains overridable. | `bash -n scripts/kill_resume_test.sh` passed. Resume gate passed with the requested Python supplied through `PYTHON` because this checkout has no `.venv`. |
| P3-7: tests missed S2 writes and cache-hit token accounting. | Added mock and fake-page metric assertions plus a nonzero-token cache-hit test. | The three targeted regression tests above failed on the old code and passed after the fixes. |

## Contract amendment A1

`docs/build/CONTRACTS.md:122-125` already contains A1. Core now passes
`frames_dir="data/media/frames"` by keyword at `src/koc/pipeline.py:206`.
`test_s3_passes_frames_directory_to_llm` uses a fake LLM with the amended
keyword signature and confirms the value.

The core-side keyword test passes. Live integration remains **UNPROVEN** in
this checkout: `src/koc/llm/content.py` is outside core ownership and its
current local signature has not yet adopted `frames_dir`. The parallel LLM
change must land before a live call can validate the combined API.

## Verification

- Before implementation: four added regressions failed on the intended defects (S2 rows, page-path `NameError`, cache tokens, and projection math).
- `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests/core`: **27 passed**.
- `PYTHON=/home/lystiger/Projects/KOC-Discovery/.venv/bin/python bash scripts/kill_resume_test.sh`: **S1b PASS; S3 PASS**.
- `bash -n scripts/kill_resume_test.sh`: **PASS**.
- `git diff --check`: **PASS**.
