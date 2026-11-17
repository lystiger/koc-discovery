# Independent review: OpenRouter and Kalodata, round 2

Date: 2026-11-15. HEAD: `d3ec835` (`feat/koc-mvp`). **Overall: FAIL — three P2 findings; no P1 findings.** Only this report created. No network; independent probes used fake keys, injected transports, temporary SQLite databases, patched sleeps, and a socket-connect rejection guard.

## Findings

- **P2 — Real errors become cached empty answers.** `src/koc/kalodata.py:185` matches any message containing `not found`, ignoring endpoint, code, and error category. Probe: HTTP 200 `{success:false, code:"AUTH_ERROR", errorCategory:"AUTH", message:"API key not found"}` on each of `video/rank`, `creator/detail`, and `category/rank` returns `{data:[], not_found:true}` twice with only one transport call. Authentication failure is suppressed and cached. Restrict normalization to the recognized video-missing response and relevant endpoints; preserve other logical failures.
- **P2 — Zero-video S1 crashes shortlist construction.** `src/koc/pipeline.py:69` persists `engagement_per_view=null` for empty videos; `src/koc/stages.py:109` decodes that JSON as `None`, then `:110` calls `float(None)`. Independent `_s1(...)(conn)` followed by `s1_shortlist` raises `TypeError: float() argument must be a string or a real number, not 'NoneType'`. This blocks advancement at `src/koc/pipeline.py:290`; existing zero-video test stops before shortlisting. Treat decoded null as missing engagement before sorting.
- **P2 — Empty S3 content remains eligible for final recommendations.** `src/koc/pipeline.py:209` correctly writes a null score and `:217` a missing-video caveat, but `:238` converts null content to zero and `:239` admits the creator to selection. `_s4` never propagates the S3 caveat (`:258`, `:275`). Independent probe seeds S1/S2, runs empty-video S3, and observes `_best_five=[('c1', None)]`; mock S4 persists a recommendation with `caveats_vi=[]` and “Video có bằng chứng sản phẩm rõ.” Exclude candidates without content evidence from final selection, or explicitly support incomplete recommendations with a mandatory missing-content caveat and no unsupported video claims. The demonstrated fabricated sentence is from mock mode; live LLM output is UNPROVEN.

## Per-item verdicts

| Item | Verdict | Evidence |
| --- | --- | --- |
| Round-1 P2: mixed HTTP/logical retries | PASS | Replayed 503, then three logical 2017 failures: raises `KalodataRateLimited`, delays `[1,15,60,180]`, four calls, no cache. `src/koc/kalodata.py:132`, `:199`. Global four-attempt cap remains; failure is no longer returned as data. |
| Round-1 P2: HTTP 429 blocks run | PASS | Replayed exhausted 429: typed exception, three calls, delays `[1,2]`, no cache; S0 execution yields run/task `blocked/blocked`. `src/koc/kalodata.py:162`; `src/koc/pipeline.py:356`. |
| Round-1 P2: budget check before every retry | PASS | Real `write_reasons` with mocked 503,503,200 yields `check,http,check,http,check,http,record`. Retry budget refusal sends only one HTTP call. `src/koc/llm/openrouter.py:319`; `src/koc/llm/reasons.py:169`. |
| Genuine video-not-found caching | PASS | Existing regression verifies two lookups use one transport call, cached empty data, zero credits. `src/koc/kalodata.py:186`; `tests/core/test_kalodata.py:198`. |
| Real-error cache isolation | FAIL | First P2 above. |
| Zero-video advancement and S4 selection | FAIL | Second and third P2 above. S3 itself performs no media or content LLM calls for an empty video list (`src/koc/pipeline.py:199`). |
| Scoring division by zero | PASS | Empty-video S1 and S3 probes complete scoring: engagement and S3 score are null. Guards at `src/koc/stages.py:34`, `:36`, `:50`; `src/koc/pipeline.py:209`. Separate shortlist null-conversion bug remains. |
| CLI error presentation | PASS | Runtime errors print and exit 1 for run, resume, categories; regression tests pass. `src/koc/cli.py:48`, `:64`, `:99`; `tests/core/test_cli.py:49`, `:67`, `:80`. |
| Mathematical multimodal budget bound | FAIL — UNPROVEN | Still explicitly unverified upstream rates; 1.5 factor is an estimate, not proof. `src/koc/llm/pricing.py:55`; `config/llm_prices.yaml:51`. No network verification attempted. This preserves round-1's limitation; not counted as an additional P2. |

## Verification

```text
PYTHONPATH=src .venv/bin/python -m pytest -q tests/core tests/llm
121 passed in 22.34s
```

Separately reran the round-1 counterexamples now encoded in `test_mixed_http_and_logical_retries_never_return_rate_limit_as_data`, `test_exhausted_http_429_raises_rate_limited`, `test_exhausted_http_429_blocks_run`, `test_openrouter_transport_retries_budget_order`, and `test_openrouter_transport_retry_blocked_by_budget`, under the socket rejection guard. All passed. Additional independent not-found/shortlist/S4 probes produced the failures above; green suite does not cover those paths together.
