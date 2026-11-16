# Independent review: live fixes, round 2

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `7c765817118f3ded0b78b12d58e38693c259f0db`.

**Overall: FAIL. Six P2 findings and one P3 finding remain. No P1 reproduced.**

Range A, `4976960..44b4be7`, fails benchmark success attribution and mock/live provenance. Its cache-only controls passed the executed network probes. Range B, `44b4be7..7c76581`, closes the original F1, F2, F3, F4, and F6 reproductions. F5 remains partially open. Its exact original fresh-response reproduction is rejected, but other unsupported audience claims and previously cached unsafe recommendations survive.

I inspected both diffs and executed the combined code at HEAD. No source files changed. This report is the only repository file created. Temporary scripts, synthetic databases, media, and logs are under `/tmp/koc-review-r2/`. I never opened or copied the repository's `data/koc.db`. All database execution used synthetic data. No network request reached a service.

Python used an external `sitecustomize.py` that rejects socket connections, datagrams, and DNS resolution. An audit hook rejects file and SQLite access to repository paths ending in `/data/koc.db`. The guard also propagates to Python subprocesses whose tests replace their environment. The permitted round-1 selector workaround bounds `EpollSelector.select()` waits to 50 ms. The full suite passed with these controls: **235 passed**.

## Findings

### R2-F1. P2: A later successful retry makes an earlier failed LLM call count as successful

Range A. Location: `src/koc/benchmark.py:54` and `src/koc/benchmark.py:59`.

The classifier matches the request hash, prompt version, and final subject. It does not identify the individual call that produced the retained result. A failed invocation and a later successful invocation share the same hash and original prompt version. Once the later result enters `llm_cache`, both original calls count toward the successful path. The wasted-cost total becomes too small.

Reproduction: run real `_cached_call()`, `write_reasons()`, `OpenRouterClient`, and `BudgetGuard` against `httpx.MockTransport`. The first invocation receives the wrong creator ID on its original and repair responses, so validation fails. Repeat the identical operation and return a valid recommendation on its original response. Store that final recommendation and aggregate the run. Each response reports 50 input tokens, 50 output tokens, and USD 0.000001.

```text
call 1: reasons_v2        invalid creator, classified successful
call 2: reasons_v2_repair invalid creator, classified unsuccessful
call 3: reasons_v2        retained result, classified successful

expected success: calls=1 tokens_in=50  tokens_out=50  usd=0.000001
actual success:   calls=2 tokens_in=100 tokens_out=100 usd=0.000002
actual total:    calls=3 tokens_in=150 tokens_out=150 usd=0.000003
```

Evidence: `adversarial.py`, output `benchmark_failed_retry` in `/tmp/koc-review-r2/adversarial.log`. The three requests, usage recording, failure, subsequent cache write, and aggregation all executed production code. Only the HTTP responses were synthetic.

Fix: retain the producing call ID with a successful cached result and classify that call. A matching prompt version does not establish that a particular attempt succeeded.

### R2-F2. P2: Another run's analysis changes an older run's successful-path accounting

Range A. Location: `src/koc/benchmark.py:31`, `src/koc/benchmark.py:59`, and `src/koc/benchmark.py:65`.

`_final_content()` selects every global analysis belonging to a creator with an S3 score in the requested run. The analysis has no association with that run, and the result identity omits the model. This also controls successful video-URL attribution and the videos used for calibration.

Reproduction: create run A with a scored creator and a USD 0.01 content ledger entry for video `v`, model `m`, prompt `content_v3`. Give that call a matching cache entry but no retained analysis. Aggregate A. Then create run B for that creator and insert an analysis for `v`, prompt `content_v3`, model `other-model`. Aggregate A again without changing any of A's ledger rows or scores.

```text
run A successful USD before run B analysis: 0.00
run A successful USD after run B analysis:  0.01
run A total USD before/after:               0.01 / 0.01
call model: m; inserted analysis model: other-model
```

Evidence: `adversarial.py`, output `benchmark_cross_run_success`. Raw ledger totals remain run-filtered. The failure concerns the definition of a retained successful result, not addition of another run's ledger charges.

Fix: retain run-scoped references to the selected analyses, including model and producing call identity. Use those references for success attribution and calibration.

### R2-F3. P2: A mock resume produces a benchmark labelled live

Range A. Location: `src/koc/benchmark.py:195`, with the mode override at `src/koc/pipeline.py:582`.

`resume --mock` can finish a run initially created with `mock=false`. It does not update that stored parameter. The new benchmark trusts only the initial parameter, so it labels generated creators, analyses, and recommendations as live. The primary mock warning is absent.

Reproduction: create a synthetic unfinished run with `{"mock":false,"limit":20}` and a pending S0 task. Invoke the actual Typer commands `resume --mock` and `benchmark --run <id> --out-dir <temporary-directory>` against that database. No pipeline or benchmark function is replaced.

```text
resume_exit=0 benchmark_exit=0
benchmark.mode="live"
distinct llm_calls.model=["mock"]
rendered_live=true mock_warning_present=false
```

Evidence: `/tmp/koc-review-r2/mock_cli.py` and `mock_cli.log`. The same state also reproduced through the pipeline API in `cache_probes.py`.

Fix: prevent mode changes within a run, or persist provenance for every execution and report mixed or mock results accordingly. Do not infer live provenance solely from the initial run parameter.

### R2-F4. P2: F5 still accepts unsupported audience claims without a percent symbol

Range B, residual F5. Location: `src/koc/llm/reasons.py:62` and `src/koc/llm/reasons.py:82`.

The new validator rejects a demographic claim only when one sentence contains both a demographic keyword and a numeric percentage ending in `%`. Spelled-out percentages and qualitative demographic claims pass even when the creator has no audience data. Appending the missing-audience caveat does not remove the unsupported reason.

Reproduction: repeat F5 with `audience_score=None`, no female or age metrics, and only an allowed commercial citation. Run real `write_reasons()` and `OpenRouterClient` with a mock HTTP response. Replace the original first reason with either string below and leave `caveats_vi=[]`.

```text
"Khán giả nữ chiếm 60 phần trăm."
"Phần lớn khán giả là nữ, trong độ tuổi 18–30."

both: accepted on call 1, no repair
both: mandatory unavailable-audience caveat appended
```

Evidence: `adversarial.py`, outputs `F5_words` and `F5_qualitative`. The exact original `"Khán giả nữ chiếm 60%."` response now fails after two attempts. A benign response with an empty caveat list receives the required caveat.

Fix: enforce the absence of unsupported audience assertions beyond the `%` pattern. Test spelled-out percentages and claims about predominant gender or age.

### R2-F5. P2: Cached F5 outputs bypass both new audience protections

Range B, residual F5. Location: `src/koc/pipeline.py:190`, `src/koc/pipeline.py:199`, and `src/koc/pipeline.py:342`.

The new checks and mandatory caveat run only inside `write_reasons()`. A cache hit returns after Pydantic shape validation. The reasons cache remains on `reasons_v2`, so an unsafe result cached before the fix remains valid under the unchanged key.

Reproduction: seed five scored creators with the uniform known placeholder signature. Use production `_s4()` summary and key construction to populate synthetic pre-fix `reasons_v2` cache entries. Each entry cites an allowed commercial metric, contains `"Khán giả nữ chiếm 60%."`, and has no caveats. Then execute real `_s4(cache_only=True)` and its write callback, with the provider replaced by a trap.

```text
production_s4_cached_recommendations=5
first_reasons=["Khán giả nữ chiếm 60%.", "Lý do hai.", "Lý do ba."]
first_caveats=[]
llm_tokens=0
```

All summaries had `audience_score=None` and excluded female metrics. The provider trap was never called. The unsafe text reached stored recommendations through the real cache path.

Evidence: `/tmp/koc-review-r2/cache_legacy.py` and `cache_legacy.log`.

Fix: invalidate old reasons caches with a version change, or validate and normalize cached recommendations against the current audience state. In cache-only mode, an invalid old entry must block rather than call a provider.

### R2-F6. P2: The S4 smoke script crashes whenever it has candidates

Range A regression, still present after the F6 fix in B. Location: `src/koc/pipeline.py:342`, interacting with `scripts/s4_free_smoke.py:52` and `scripts/s4_free_smoke.py:53`.

S4 now always supplies `cache_only=cache_only` to `_cached_call()`. The smoke script replaces that function with an adapter that forwards all keywords to `write_reasons()`, which has no `cache_only` parameter. Execution fails before any model request or final smoke verdict.

Reproduction: run the unmodified script as a subprocess from a temporary directory. Its synthetic `data/koc.db` contains five affordable creators, S1/S2/S3 scores, and audience metrics under the script's configured run ID. Copy only the price configuration and set a fake OpenRouter key. Keep the external socket guard active.

```text
exit_code=1
stdout=""
TypeError: write_reasons() got an unexpected keyword argument 'cache_only'
```

Evidence: `adversarial.py`, output `smoke_nonempty`. The traceback passes through `_s4()` and the script's `fake_cached_call()`. The new test at `tests/core/test_s4_smoke_script.py:11` uses an empty database, so it never reaches this call.

Fix: make the smoke adapter consume the cache-control keyword. Verify a nonempty synthetic success path as well as the empty failure path. The original F6 zero-exit-on-FAIL defect is closed, but a successful nonempty smoke execution remains broken.

### R2-F7. P3: Benchmark denies placeholder audience data in a mixed run

Range A reporting gap exposed by B's F4 correction. Location: `src/koc/benchmark.py:210` and `src/koc/benchmark_render.py:97`.

The pipeline now uses `placeholder_audience_creators()` per creator. The benchmark still calls the old run-wide detector. For a mixed run, it reports `audience_placeholder=false` and states that no placeholder data was detected, even while S4 excludes a known sample capture.

Reproduction: seed F4's five mixed signatures, build the benchmark, render its Markdown, and inspect the real S4 selection.

```text
known sample creator's S4 audience score=null
benchmark.audience_placeholder=false
rendered: "Không phát hiện dữ liệu khán giả mẫu (placeholder) trong lượt chạy này."
```

Evidence: `adversarial.py`, output `benchmark_mixed_audience`.

Fix: derive benchmark availability from the same per-creator result as S4. Report the affected creator count instead of denying placeholder data for the whole run.

## Per-item verdicts

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| B, F1 P1: empty truncated response billing | CLOSED | Original three-invocation scenario, generated video, real client and guard. Two HTTP responses report USD 0.04, and two ledger rows retain USD 0.04. Both later invocations hit the USD 0.05 budget check before another request. `src/koc/llm/openrouter.py:393`; `replay_r1.log`, `empty_truncation`. |
| B, F2 P2: ordinary completed-run resume repeats paid failure | CLOSED | Original six-creator scenario. Before and after resume: `done`, one paid failed-creator call, USD 0.006 total, five recommendations. `src/koc/pipeline.py:568`; `replay_r1.log`, `completed_resume`. Suite also tests explicit retries and S4 invalidation. |
| B, F3 P2: HTTP 500 followed by three 1054 responses | CLOSED | Four calls, zero credits, `KalodataNotReady`. Through real `execute()`, creator 1 blocks, creator 2 executes and finishes, then S4 blocks for insufficient scores. `src/koc/kalodata.py:196`; `replay_r1.log` and `adversarial.log`. |
| B, F4 P2: mixed sample audience enters S4 | CLOSED | Same five signatures. Sample creator receives `audience_score=None`, only `video_gpm` remains in its metrics, and its stored citation uses that commercial metric. Other creators retain their audience component. `src/koc/stages.py:142`; `replay_r1.log`, `mixed_placeholder`, plus mixed-audience suite tests. Benchmark presentation has separate R2-F7. |
| B, F5 P2: missing-audience caveat and claims | OPEN, partial fix | Exact original fresh `60%` claim now rejects after two calls. Benign output receives the caveat in code. R2-F4 accepts equivalent unsupported wording, and R2-F5 reuses the original unsafe claim with no caveat through the production S4 cache path. |
| B, F6 P3: smoke prints FAIL but exits zero | CLOSED | Unmodified script, empty synthetic database: `RESULT FAIL: 0 recommendations...`, exit 1. `scripts/s4_free_smoke.py:73`; `adversarial.log`, `F6_empty`. Nonempty script execution has separate R2-F6. |
| A: Kalodata cache misses never reach transport | PASS | All five public methods reject misses with `CacheOnlyMiss` and create no call rows. Suite also checks a cache hit has zero credits. `src/koc/kalodata.py:136`; `cache_probes.log`, `kalodata_all_methods`. |
| A: S0 and S1b cache misses block without network | PASS | Real client with a fake unused key. Both executions end with task/run `blocked` and zero connection attempts. `cache_probes.log`, `cache_stage`. |
| A: S2 never opens CDP or navigates on a miss | PASS | Browser creation trap remains untouched. A supplied page whose `goto()` attempts a socket connection is also untouched. Missing metrics and cached null metrics both block. `src/koc/pipeline.py:409` and `src/koc/pipeline.py:443`. |
| A: S3 cannot download from a cached URL when media is missing | PASS | Cache video/rank and video/url with an HTTPS URL, remove the MP4, execute real S3 cache-only. It blocks on the missing file before download. `src/koc/pipeline.py:238`; `cache_probes.log`. |
| A: content LLM miss with local media never calls provider | PASS | Supply local media and cached video/rank, leave LLM cache empty, install provider trap. Task/run block at `LLM content (content_v3)`. `src/koc/pipeline.py:200`; `cache_probes.log`. |
| A: S4 miss blocks; populated cache resumes without spend | PASS | Five eligible creators. Empty reasons cache blocks with zero LLM rows. Populate matching entries and resume the cache-only run. It finishes with five recommendations, five cache hits, zero tokens, and zero USD. `cache_probes.log`, `S4_miss` and `S4_hit_resume`. |
| A: cache-only persists through resume and supports mock rerun | PASS | Full suite checks stored cache-only parameters and a completed mock rerun with the same top five, zero credits, and zero LLM tokens. Independent real-mode S4 resume also passes. |
| A: benchmark total ledger sums and exclusion | PASS on synthetic ledgers | Independent raw SQL sums match 1.5 credits, 3,350 input tokens, 335 output tokens, USD 0.0335, 14 non-cache calls, and two cache hits. Excludes seven credits in two other/null-run API rows and 99,999 input/output tokens plus USD 9 from another run. `adversarial.log`, `benchmark_baseline`. |
| A: honest successful-versus-total split | FAIL | R2-F1 counts a failed original call as successful after a later retry succeeds. R2-F2 changes successful attribution when another run adds an analysis. |
| A: documented projection formula | PASS for arithmetic | Independently checked N=50, 200, 500, both successful and total units. Counts follow the documented caps. Credits, tokens, USD, and stage wall-time projections match multiplication and rounding. This does not validate the success classifier supplying the units. |
| A: stored JSON and Markdown consistency | PASS for internal consistency | Recomputed each stored stage sum and all six projection tables. `render_markdown(reports/benchmark.json)` matches `docs/BENCHMARK.md` exactly. No live database access. |
| A: stored 50-candidate scaling run clearly labelled mock | PASS for presentation | Stored scaling mode is `mock`. The document explicitly says `MÔ PHỎNG, không phải số liệu thật` and excludes these figures from live cost projections. |
| A: mock can never be presented as live | FAIL | Supported `resume --mock` followed by the actual benchmark command produces mode `live` and no primary mock warning. R2-F3. This does not prove that the checked-in primary artifact used mock data. |
| B: mixed-audience web adapter changes | PASS for existing functional tests | The complete web test selection passes. No new visual audit was performed. |
| Full suite at requested HEAD | PASS with permitted workaround | `235 passed in 86.53s (0:01:26)`, socket/database guards and bounded selector waits active, including guarded Python subprocesses. |
| Checked-in live figures equal actual live database rows | UNPROVEN | User prohibited opening `data/koc.db`. Synthetic reconciliation and artifact arithmetic do not prove the provenance or raw ledger sums of the checked-in primary run. |
| Live model availability, upstream billing, audience validity, and recommendation quality | UNPROVEN | No network or live database access. Ledger reservations and configured S2 prices are not an independent account-balance measurement. |
| Reviewer-provider separation | UNPROVEN | Reviewer is Codex/OpenAI. This session does not establish the provider identity of every builder. |

## Verification

The round-1 reproduction scripts were read from `/tmp/koc-live-review/`. Their inputs and real production operations were retained in `/tmp/koc-review-r2/replay_r1.py`. The checkout and work paths changed. Assertions now check the fixes. The F1 loop catches the new validation/budget failures so all three invocations execute. The F4 summary spy uses the remaining commercial citation after the fixed code removes the female citation. The actual smoke subprocess and original F5 response are exercised in `adversarial.py`.

All Python commands use `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python`, importing this worktree's source and tests. The working directory is `/tmp/koc-review-r2/work`. Bytecode and pytest cache writes are disabled. `/tmp/koc-review-r2/run-python` sets:

```sh
PYTHONPATH=/tmp/koc-review-r2/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

The external guard is `/tmp/koc-review-r2/guard/sitecustomize.py`. It replaces `socket.socket.connect`, `connect_ex`, `sendto`, `sendmsg`, `socket.create_connection`, and DNS entry points with rejecting functions. Its audit hook protects repository `data/koc.db` file opens and SQLite connections. The subprocess wrapper retains the guard when a test supplies a replacement environment. The selector workaround changes only the maximum wait duration.

Full suite command:

```sh
/tmp/koc-review-r2/run-python -m pytest -q -p no:cacheprovider \
  /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

Final output, retained in `/tmp/koc-review-r2/suite_guarded_children.log`:

```text
235 passed in 86.53s (0:01:26)
```

Independent probe commands, each completed with exit code zero:

```sh
/tmp/koc-review-r2/run-python /tmp/koc-review-r2/replay_r1.py
/tmp/koc-review-r2/run-python /tmp/koc-review-r2/adversarial.py
/tmp/koc-review-r2/run-python /tmp/koc-review-r2/cache_probes.py
/tmp/koc-review-r2/run-python /tmp/koc-review-r2/cache_legacy.py
/tmp/koc-review-r2/run-python /tmp/koc-review-r2/mock_cli.py
```

Each script has a corresponding `.log` in `/tmp/koc-review-r2/`. A zero script exit means its assertions reproduced the stated behavior, including the defects. It does not mean the application passed the review.

The deliberate guard self-test rejects `socket.create_connection(('example.invalid', 80))` before opening a connection. The cache-only probe records the attempt count before and after its cases and asserts a delta of zero. It also uses provider/browser traps, so a caught network error cannot masquerade as successful cache-only enforcement.

`git diff --check` passes. The final repository status contains only this new report. No merge, deployment, source edit, or live operation occurred.
