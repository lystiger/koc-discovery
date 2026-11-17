# Independent review: live fixes

Date: 2026-11-16, Asia/Ho_Chi_Minh. Branch: `feat/koc-mvp`. Range: `aa47285..2933bd25a9c661b7fb9d5103bbbfd74963ef98bd`, all 28 commits, including merges.

**Overall: FAIL. One P1, four P2 findings, and one P3 finding remain. The previous r3 P2 on S2 credit finalisation is closed.**

Reviewed the changed production code, configuration, prompts, tests, web presentation, and smoke script against the external `SPEC.md` and `docs/process/build/CONTRACTS.md`, including amendment A2. Findings distinguish new regressions from residual defects in the reviewed paths.

No network requests were allowed. Python ran with a temporary `sitecustomize.py` that rejects socket connections and DNS resolution. An additional guard rejects connections to the live database. I did not open, copy, or modify `data/koc.db`. All executed database paths used synthetic SQLite databases. Source files were not modified. Temporary scripts, generated media, raw captures, and logs are under `/tmp/koc-live-review/`. This report is the only repository file written by the reviewer. An unrelated untracked `.claude/` worktree appeared during review and was left untouched.

Reviewer is Codex/OpenAI. Provider separation from every actual builder is **UNPROVEN**: the specification assigns core work to Codex and LLM work to Gemini. This report establishes independently executed evidence, not proof of the requested provider separation.

## Findings

### F1. P1: Empty truncated OpenRouter responses discard billable usage

Location: `src/koc/llm/openrouter.py:394`, with the caller at `src/koc/llm/content.py:374` and `src/koc/llm/content.py:384`.

An HTTP 200 response with `finish_reason="length"` and empty content raises before usage is parsed or returned. Consequently, `BudgetGuard.record()` never runs. The new truncation repair logic never receives this response either. A reasoning model can exhaust output tokens without emitting content, so this is a paid failure, not a free transport rejection. Subsequent calls check an understated cumulative total.

Reproduction: run the real `_cached_call`, `analyze_video`, `OpenRouterClient`, and `BudgetGuard` with a generated three-second video and `httpx.MockTransport`. Return this response on each request:

```json
{"choices":[{"message":{"content":""},"finish_reason":"length"}],"usage":{"prompt_tokens":1000,"completion_tokens":4096,"cost":0.02}}
```

Set the real guard's cumulative cap to `$0.05`. Invoke the same uncached content operation three times, catching its `RuntimeError` each time. Actual probe output:

```text
http_calls=3 provider_reported_usd=0.06 cap=0.05 logged_calls=0 logged_usd=0
```

Every request passed its budget check. Every response raised the empty-truncation error. No usage or result cache row survived. The unchanged early raise predates this range; it remains an open defect in the truncation path changed here. S3's new continue-on-failure behavior can now proceed to more creators after this unlogged spend.

Fix: account for successful HTTP responses before content-specific rejection. Return the empty text with its usage to the caller, or carry and record usage through a typed failure. Then perform a budget-checked repair or stop. Add a regression that checks the ledger and cumulative cap, not only the exception text.

### F2. P2: Resuming a completed run repeats paid S3 failures

Location: `src/koc/pipeline.py:469` and `src/koc/pipeline.py:507`, interacting with `src/koc/pipeline.py:556` and `src/koc/pipeline.py:557`.

The new continuation logic permits a run to finish `done` with failed or blocked S3 tasks when five other creators have content scores. `resume()` unconditionally resets those unsuccessful tasks. Failed LLM output has no successful result cache, so a finished run can spend again on every resume. This violates the finished-run zero-cost requirement.

Reproduction: seed six eligible creators in a temporary database. Five have completed S3 scores. Give the sixth one local media and run the real S3 operation with a fake analyzer that records `$0.001` through its supplied real guard, then raises `ValueError`. Use a fake reasons generator that records `$0.001` per recommendation. Keep real task advancement, result writes, LLM caching, S4 selection, and `resume()`.

```text
before resume: status=done failed_creator_calls=1 total_usd=0.006 recommendations=5
after resume:  status=done failed_creator_calls=2 total_usd=0.007 recommendations=5
```

No inputs, model, or configuration changed. S4 stayed completed while the failed content request repeated. The reset code predates the range; completed runs containing unsuccessful S3 tasks are newly reachable through this change.

Fix: make ordinary resume of a completed run a no-op. If explicit retries of excluded creators are supported, distinguish that operation and invalidate the downstream selection when its inputs change.

### F3. P2: Mixed HTTP errors and Kalodata 1054 abort the whole run

Location: `src/koc/kalodata.py:190`, `src/koc/kalodata.py:195`, and `src/koc/kalodata.py:216`.

The 1054 handler shares a four-iteration outer loop with HTTP retries. After an earlier HTTP failure, the loop can end immediately after a 1054 retry delay. The final fallback handles logical rate limits but not 1054. It raises generic `RuntimeError` instead of `KalodataNotReady`, bypassing the creator-specific continuation handler.

Reproduction: use a real `KalodataClient`, injected transport, and no-op sleep. For `video/url`, return HTTP 500 followed by three HTTP 200 responses containing `success=false`, `code="1054"`, and `message="Video being fetched"`.

```text
calls=4 credits=0 exception=RuntimeError
message="Yêu cầu Kalodata thất bại (200)."
```

Running that sequence through real `execute()` and `_s3_creator()` with a second queued creator produced:

```text
run=failed tasks=[("c1", "failed"), ("c2", "pending")]
```

The second creator was never processed. Pure 1054 sequences pass the existing regression; the mixed sequence does not.

Fix: classify the last logical response when the overall attempt budget expires, including 1054. Keep retry counts and delays consistent across mixed error sequences. Verify that the current creator becomes blocked and the next creator executes.

### F4. P2: One different audience capture re-enables known sample data

Location: `src/koc/stages.py:120`, propagated by `src/koc/pipeline.py:317` and `src/koc/pipeline.py:320`.

The detector disables audience evidence only when every captured tuple matches the known sample, or when all captures are identical. In a run containing historical sample captures and distinct captures, the known `(60, 30.5, 39.5)` sample is treated as verified. Metrics are cached across runs, so mixed historical captures are possible. The affected creator keeps its audience score and receives sample metric IDs in the reasons allowlist.

Reproduction: seed five affordable, scored creators with audience tuples `(60,30.5,39.5)`, `(71,20,30)`, `(72,20,30)`, `(73,20,30)`, and `(74,20,30)`. Execute the real `_s4()` summary construction and write callback, replacing only the LLM cache call with a spy that returns a recommendation citing the supplied female metric.

```text
run_audience_is_placeholder=False
c0.audience_score=65
c0.metrics={female_pct:60, age_18_24_pct:30.5, age_25_34_pct:39.5, video_gpm:1000}
stored citation="metric:c0:female_pct"
```

Fix: retain audience availability per creator or capture. A distinct valid capture must not make another creator's known placeholder trustworthy. Renormalise only the affected scores and exclude their audience evidence from S4.

### F5. P2: Missing-audience caveat is enforced only by the prompt

Location: `src/koc/llm/reasons.py:222` and `src/koc/llm/reasons.py:228`; the new rule is in `prompts/reasons_v2.md:41`.

When `audience_score` is `None`, the prompt requires an unverified-audience caveat and forbids demographic claims. Output validation receives only the creator ID and evidence allowlist. It accepts an empty caveat list and unsupported audience claims when the response cites an unrelated allowed metric. A required schema property permits an empty list; the citation enum proves membership, not support for the claim.

Reproduction: call real `write_reasons()` with `audience_score=None`, no female or age metrics, and a real `OpenRouterClient` backed by `MockTransport`. Return three reasons, including `"Khán giả nữ chiếm 60%."`, an allowed commercial metric citation, and `caveats_vi=[]`.

```text
calls=1
accepted reason="Khán giả nữ chiếm 60%."
accepted caveats=[]
accepted citation="metric:cr_456:skincare_revenue_share"
```

No repair occurred. This is a gap in the new missing-audience protection, independent of F4: the probe explicitly sets the audience unavailable before generation.

Fix: append the mandatory unavailable-audience caveat in code. Validate this state against the returned reasons, including the known placeholder claims, before accepting or caching the result. Do not treat an enum-valid commercial citation as verification of an audience claim.

### F6. P3: The S4 smoke script exits successfully after printing FAIL

Location: `scripts/s4_free_smoke.py:72`.

`ok` controls only the printed result. Missing recommendations, audience citations, or sample numbers can make the smoke check fail while the process still returns exit code zero.

Reproduction: run the unmodified script from a temporary directory containing a synthetic empty `data/koc.db` initialised with `db.init_db()` and a copy of `config/llm_prices.yaml`. Use a fake OpenRouter key and the socket guard. No candidates means no LLM request is attempted.

```text
stdout="RESULT FAIL: 0 recommendations, cost 0.0 USD, model baidu/ernie-5.5-flash-preview:free"
exit_code=0
stderr=""
```

Fix: exit nonzero when `ok` is false. Verify both the printed verdict and process status with invalid and valid synthetic results.

## Per-item verdicts

| Item | Verdict | Evidence |
| --- | --- | --- |
| R3 P2: S2 preserves successful charges | PASS | Independent `s2_billing` probe: `goto` observed committed `pending,1.0` outside a transaction; final credits `1.0`; second creator blocked at cap `1`; exactly one navigation. Real finalisation at `src/koc/db.py:168` and `src/koc/pipeline.py:447`. |
| S2 empty-capture stop | PASS | `test_empty_s2_capture_blocks_run_keeps_charge_and_stops_after_first_page`: one view, retained charge, blocked run, next task pending, no fabricated metrics or S2 score. |
| S2 pacing, runtime limit, and raw capture | PASS | Executed capture pacing, Vietnamese-label, raw-contact-line removal, and runtime-limit tests. Remaining queued S2 tasks become `skipped`; null-only captures are excluded from S3. |
| Database task migration | PASS | Existing task-table migration test preserves the task and accepts both `blocked` and new `skipped` status. Transaction rollback and recovery tests also pass. |
| Tests independent of changed live caps and output limits | PASS | All 191 non-web tests pass using the real checkout configuration and explicit stable fixtures where numeric expectations require them. Full diagnostic run passes all 206 tests. |
| Kalodata 1054, pure sequence | PASS | `test_video_url_not_ready_retries_without_billing_or_cache` exercises four attempts and 30/60/120-second injected delays, without charges or cached error data. |
| Kalodata 1054, mixed sequence and run status | FAIL | F3: HTTP 500 followed by 1054 exhausts the loop as generic HTTP-200 failure; run fails and later creator remains pending. |
| LLM output caps | PASS | Request tests and real mock-transport probes exercise explicit `max_tokens`; checkout defaults are 4096 for content and 2048 for reasons. Field limits are tested after parsing as well as in the request schema. |
| S3 continue after a creator's invalid LLM output | PASS | Existing continuation tests and independent six-creator probe finish S4 with five recommendations after one creator fails. Content failure records usage when the client returns usage normally. |
| Completed-run resume costs zero | FAIL | F2: a finished six-creator run repeats a paid failed content call; total rises from `$0.006` to `$0.007`. The all-success mock rerun test does not cover this state. |
| Content prompt and cache version | PASS | Production pipeline uses `content_v3`; executed version and cache tests pass. `content_v2.md` remains present, while production loads `content_v3.md`. |
| Nonempty truncated JSON repair | PASS | Mock-transport integration test charges both responses, retries with clean media context, omits broken output, and returns `content_v3_repair`. |
| Empty truncated response accounting and repair | FAIL | F1: three responses reporting `$0.06` total pass a `$0.05` guard with no ledger entries. |
| 90-second media window | PASS | Executed real ffmpeg/ffprobe tests on generated 100-second video: clipped audio, eight in-window frames, 0.5-second hook; 95-second evidence is rejected and the cost estimate uses 90 seconds. |
| Transcript construction and evidence dedupe | PASS | Executed chronological speech-join, 1200-character transcript cap, quote/rationale caps, evidence pruning, duplicate-ID, and real mock-transport dedupe tests. |
| ProviderAccountError stop and resume | PASS | Executed 401/402/403 transport tests for OpenRouter and Gemini, plus pipeline account-stop/resume test: account failure leaves current S3 pending with a blocking reason and prevents later video URL calls during that execution. |
| S4 infeasible budget | PASS | Executed budget test: six content scores, cheapest feasible combination costs 33M VND; task/run block, no recommendations or reasons calls. Adding affordable candidates and resuming produces five recommendations. |
| Reasons required properties and evidence enum | PASS | Actual captured request schema requires all four properties, 3-5 reasons, nonempty citations, and candidate-specific evidence IDs. Local validation rejects unknown or duplicate citations. This does not establish semantic support for every reason. |
| Uniform placeholder audience and renormalisation | PASS | Executed known-signature and identical-distribution tests. S4 excludes audience metric IDs, stores null audience breakdown, and computes `(.45*S1 + .35*S3)/.80`. Distinct real captures retain all weights. |
| Mixed placeholder audience | FAIL | F4: known sample tuple remains scored and available for citation when other tuples differ. |
| Missing-audience claims and mandatory caveat | FAIL | F5: real reasons path accepts a 60% female claim with no audience data and no caveat. |
| Web placeholder presentation and regressions | PASS | Changed adapter/templates execute in the full diagnostic suite; all web tests pass. This is functional evidence, not a new visual audit or live-data claim check. |
| S4 free smoke failure status | FAIL | F6: unmodified script prints FAIL for an empty synthetic database and returns zero. |
| Actual free-model price and real-data smoke result | UNPROVEN | No network or live database access. Synthetic offline execution verifies control flow, not live model availability, pricing, or recommendation quality. |
| Actual S2 UI credit price | UNPROVEN | Configuration now records zero with a balance-measurement comment. No independent account-balance measurement was possible offline; billing proof uses an injected nonzero price. |
| Universal USD upper bound | UNPROVEN | `src/koc/llm/pricing.py:53` still identifies upstream multimodal token rates as unverified. Local estimates and stop checks pass covered cases, but F1 also independently bypasses accounting. |
| Unmodified full-suite completion | UNPROVEN | First web TestClient request stalls after 191 passing tests. Minimal unrelated FastAPI app reproduces the same stall. All 206 pass with the temporary selector workaround described below. |
| Reviewer-provider separation | UNPROVEN | This reviewer is Codex/OpenAI; actual builder-provider separation is not established by this session. |

## Verification

Tests used this checkout's source, interpreter, and test files. The working directory was `/tmp/koc-live-review/work`, because several tests write S2 raw captures relative to the working directory. The repository root is included in `PYTHONPATH` for imports such as `tests.llm.test_openrouter`. Bytecode and pytest cache writes were disabled. The initial collection attempt lacked that root path and failed two test-module imports; the commands below include the correction.

Full requested test selection, with the offline guard and absolute paths:

```sh
PYTHONPATH=/tmp/koc-live-review/guard:/home/lystiger/Projects/KOC-Discovery/src:/home/lystiger/Projects/KOC-Discovery \
PYTHONDONTWRITEBYTECODE=1 \
/home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q -p no:cacheprovider \
/home/lystiger/Projects/KOC-Discovery/tests
```

This run stalled at `tests/web/test_app.py::test_routes_200_on_fixture_db`, after 191 passes. A verbose diagnostic run with `-o faulthandler_timeout=20` showed the main thread waiting in AnyIO's `run_sync_from_thread` while the portal thread waited in `selectors.select`. Both stalled runs were interrupted. A minimal unrelated FastAPI root route reproduced the stall, including with a guard that permits Unix-domain sockets while rejecting network sockets.

For a diagnostic full run, `/tmp/koc-live-review/guard-poll/sitecustomize.py` retained the same network and live-database guards and added only this selector workaround:

```python
import selectors
_select = selectors.EpollSelector.select
def polling_select(self, timeout=None):
	return _select(self, 0.05 if timeout is None else min(timeout, 0.05))
selectors.EpollSelector.select = polling_select
```

The minimal app then returned HTTP 200. The entire test command above, changing only the guard directory to `guard-poll`, completed:

```text
206 passed in 80.76s (0:01:20)
```

Separately, the original guard without selector changes and the same command with `--ignore=/home/lystiger/Projects/KOC-Discovery/tests/web` completed:

```text
191 passed in 39.51s
```

The diagnostic result is not an unqualified PASS for unmodified full-suite execution. No repository dependency or application code was changed to obtain it.

Independent executable reproductions are retained at `/tmp/koc-live-review/probes.py` and `/tmp/koc-live-review/extra_probes.py`. Run either with the original guarded `PYTHONPATH` above. Both exit zero after exercising their checks. Their outputs are in `probes.log` and `extra_probes.log`. The first script executes the billing, finished-run resume, empty truncation, mixed-audience, and mixed-1054 paths. The second executes the mixed-1054 run-status failure, missing-audience output acceptance, and the actual smoke script in a subprocess against synthetic data. Neither script calls a live service.

The findings establish local correctness failures with fakes. They do not claim that the synthetic costs were charged to a real account, that a live model necessarily emits these responses, or that the existing live recommendations were inspected.
