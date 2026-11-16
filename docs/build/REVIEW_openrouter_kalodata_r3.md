# Independent review: OpenRouter and Kalodata, round 3

Date: 2026-11-15. HEAD: `dc26787` (`feat/koc-mvp`). **Overall: FAIL — one new P2 in S2 credit accounting.** The three round-2 P2 findings are closed.

No network. Probes and pytest ran with socket connections rejected through temporary `sitecustomize.py`. Only this report was created in the repository. Existing uncommitted `config/kalodata_prices.yaml` change (`credits_cap: 100` to `60`) was preserved; results below describe that working tree.

## Finding

**P2 — Successful S2 views erase their reserved credits, bypassing the cumulative cap.** `src/koc/pipeline.py:358` calls `db.finalize_api_call(..., "200", 0)`. That helper unconditionally sets `credits=0` at `src/koc/db.py:170`. Independent execution of two distinct S2 tasks with a real `CreditCounter(cap=1)` and configured view price `1.0` navigated twice, completed both tasks, and left `credits_used=0`. One successful view alone finalized as `("200", 0)` despite a committed `("pending", 1.0)` reservation before navigation. Preserve the reserved charge when finalizing successful UI views; verify the second distinct view blocks at the cap.

## Per-item verdicts

| Item | Verdict | Evidence |
| --- | --- | --- |
| R2: overly broad not-found handling | PASS | Replayed `AUTH_ERROR/AUTH: API key not found` twice on each of `video/rank`, `creator/detail`, `category/rank`: six raised errors, six transport calls, no cache. Endpoint/code/category restriction at `src/koc/kalodata.py:188`. |
| Genuine video-not-found caching | PASS | Regression replay: recognized video-missing response is cached as empty data, one transport call for two requests, zero credits. `tests/core/test_kalodata.py:198`. |
| R2: null engagement crashes shortlist | PASS | Real empty-video `_s1` write, then `s1_shortlist`, then `_advance`: creator shortlisted and S2 task created. Null decoded engagement handled at `src/koc/stages.py:110`. |
| R2: no-content creator selectable | PASS | Seeded S1/S2, ran empty-video S3 and mock S4: null S3 score, missing-content caveat, empty `_best_five`, zero recommendations. Patched media/content LLM calls to reject invocation; none occurred. Exclusion at `src/koc/pipeline.py:235`. |
| S2 reserves before page view | PASS | Real `execute`, `capture_audience`, and counter with fake page: `goto` observed committed `pending` reservation at configured price, outside a transaction. `src/koc/pipeline.py:354`, `:357`. |
| S2 cap refusal blocks task | PASS | Real counter with cap `0`: zero page navigation, zero reservation rows, task/run `blocked/blocked`. `src/koc/pipeline.py:355`, `:365`. |
| S2 retains successful charges / cumulative cap | FAIL | Two distinct views admitted at cap `1`, price `1.0`; final total credits `0`. Finding above. |
| Earlier retry, 429 blocking, retry-budget guards | PASS | Focused regression replay covers mixed HTTP/logical limits, exhausted HTTP 429 including run blocking, and OpenRouter budget checks before retry. |
| Zero-video scoring / CLI errors | PASS | Combined empty-video probe completes S1/S3 scoring; CLI regressions pass in full suite. |
| Mathematical multimodal budget bound | FAIL — UNPROVEN | Upstream image/audio rates remain explicitly unverified; safety factor is an estimate. `src/koc/llm/pricing.py:53`. No network verification. |
| Actual S2 credit price | FAIL — UNPROVEN | `config/kalodata_prices.yaml:5` explicitly marks `ui_creator_detail_view: 1.0` unverified. Ordering proof uses the configured price only. |
| Required core/LLM suite | FAIL | `125 passed, 1 failed in 30.45s`. `tests/core/test_config.py:18` expects cap `100`; existing working-tree cap is `60`. This failure is separate from the new P2. |

## Verification

Requested suite executed with an additional offline guard path and bytecode writes disabled:

```sh
PYTHONPATH=/tmp/koc-r3-offline:src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/core tests/llm
```

Independent probes used temporary SQLite databases, fake credentials, injected transports, and fake browser pages. S2 probes retained real reservation, capture, completion, and blocking logic; `_advance` alone was disabled to isolate S2. No product code or tests changed.

Focused regression replay: **14 passed, 48 deselected in 10.37s**, selecting `mixed_http`, `exhausted_http_429`, `budget_order`, `retry_blocked`, `not_found`, `without_videos`, `zero_videos`, and `runtime_error` across Kalodata, pipeline, CLI, and OpenRouter tests.
