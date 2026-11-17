# Independent review: live fixes, round 3

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `21f48d405a058238e97677217bd7bcd58dfa214c`.
Review range: `7c76581..21f48d4`.

**Overall: FAIL. Five reproduced P2 findings. No P1 or P3 reproduced.**

Six round-2 findings are CLOSED. R2-F4 remains OPEN through a different unsupported-claim formulation. Both original R2-F4 strings now reject. The new code also rejects a legitimate brand-target statement, counts results discarded by failed stages or a new finalist selection, and loses legacy content attribution after an upgraded run resumes.

The full suite passes: **251 passed in 85.93s**. The additional executed reproductions below fail the review criteria despite that result.

No source files changed. This report is the only repository file created. All project execution used an external socket-blocking `sitecustomize.py`. All databases, media, scripts, and execution logs were synthetic and under `/tmp/koc-review-r3/`. I never opened or copied the repository's `data/koc.db`. No network request reached a service.

## Findings

### R3-F1. P2: The audience filter rejects a legitimate restatement of the brand target

Location: `src/koc/llm/reasons.py:91`. Cached recommendations use the same check at `src/koc/llm/reasons.py:305`.

The audience-subject rule rejects any sentence containing an audience word and a demographic word. It does not distinguish the brand's intended audience from a claim about the creator's audience. The brand-target exception only applies to the later age-phrase rule.

Reproduction: use the original candidate with `audience_score=None`, remove its demographic metrics and citations, and return this first reason with an allowed commercial citation:

```text
Nhãn hàng hướng đến khán giả nữ 18–30 tuổi.
```

This means the brand targets women aged 18–30. It states no fact about the creator's audience. Run the real `write_reasons()` and `OpenRouterClient` with `httpx.MockTransport` returning the same valid payload for both attempts. Then seed that recommendation under the current `reasons_v3` key and call real `_cached_call(..., cache_only=True)` with the candidate.

```text
fresh output: rejected after 2 HTTP responses
error: Recommendation validation failed after repair:
       Lý do nêu tỷ lệ giới tính/độ tuổi dù chưa có dữ liệu khán giả:
       'Nhãn hàng hướng đến khán giả nữ 18–30 tuổi.'
cached output: CacheOnlyMiss; provider calls=0
```

The control sentence `Tệp mục tiêu nữ 18-30 của nhãn hàng phù hợp với dòng kem chống nắng.` passes fresh and cached validation. Executing the previous revision's `_audience_claims()` against the rejected sentence returns no claim, confirming a regression.

Impact: valid model output consumes a repair attempt and can fail S4. A valid cached recommendation blocks cache-only execution.

Fix: distinguish a campaign-target statement from a creator-audience assertion. Preserve rejection of claims that the creator's audience matches that target.

Evidence: `/tmp/koc-review-r3/regressions.py`; `regressions.log`, `brand_target_fresh`, `brand_target_cached`, and `prior_code_comparison`.

### R3-F2. P2: Uncertainty about conversion exempts an unsupported audience claim

Residual R2-F4, with an additional regression for numeric claims. Location: `src/koc/llm/reasons.py:87`.

The new early return treats any occurrence of `chưa rõ`, `chưa xác minh`, or the other uncertainty phrases as permission to accept the whole sentence. It does not check what is uncertain.

Reproduction: retain the original missing-audience candidate and commercial citation. Run real `write_reasons()` and `OpenRouterClient` with either first reason below:

```text
Phần lớn khán giả là nữ 18–30 tuổi, nhưng chưa rõ tỷ lệ chuyển đổi.
Khán giả nữ chiếm 60%, nhưng chưa rõ tỷ lệ chuyển đổi.
```

Both assert a creator demographic while saying only that conversion rate is unknown. Both pass on the first response without repair. The mandatory caveat is appended, but the unsupported reason remains.

The current cache validator also accepts both strings. To exercise persistence, seed five current `reasons_v3` entries through the real S4 summary/key construction, using the second string and uniform placeholder captures. Execute real `execute(..., cache_only=True)` with a provider trap:

```text
run status=done
stored recommendations=5
provider calls=0
LLM cache-hit rows=5; tokens=0
unsupported 60% reason retained
```

The previous revision's `_audience_claims()` rejects the numeric sentence. The new uncertainty exception therefore weakens an existing protection, in addition to leaving the qualitative R2-F4 requirement incomplete.

Fix: scope uncertainty exceptions to the audience assertion itself. Uncertainty about conversion or another metric must not exempt a positive demographic claim.

Evidence: `/tmp/koc-review-r3/regressions.py`; `regressions.log`, `unrelated_uncertainty_bypass`, `percent_uncertainty_bypass`, `S4_cache_bypass_v3`, and `prior_code_comparison`.

### R3-F3. P2: A failed S3 task leaves an uncommitted analysis classified as successful

Location: `src/koc/pipeline.py:221`, consumed at `src/koc/benchmark.py:74`. The actual analysis write occurs later at `src/koc/pipeline.py:289`.

`_cached_call()` commits `run_results` as soon as one video returns. The enclosing S3 task writes its analyses and score only after every video succeeds. If a later video fails, the first result remains marked selected even though the task never commits any analysis.

Reproduction: create one S3 creator with two ranked videos and local synthetic media. Execute real `execute()`, `_s3_creator()`, `_cached_call()`, and `BudgetGuard`. Replace only the provider function: record USD 0.01 and return a valid analysis for `v0`; record USD 0.01 and raise a validation error for `v1`.

```text
tasks: S3=failed, S4=blocked
retained analyses=0; S3 scores=0
run_results=[("content", "v0", 1)]
actual successful LLM calls=1; successful USD=0.01
actual total LLM calls=2; total USD=0.02
success_estimated=false
expected successful LLM calls=0; successful USD=0.00
```

Running the previous revision's aggregator against this same synthetic state returns zero successful LLM calls.

Impact: the benchmark understates discarded spend and reports precise attribution for an analysis that did not enter the run's scored results.

Fix: commit selected-result attribution with the task's retained analysis and score, or restrict classification to results that reached that commit. Cache persistence can remain independent.

Evidence: `/tmp/koc-review-r3/regressions.py`; `regressions.log`, `partial_S3_success` and `prior_code_comparison`.

### R3-F4. P2: Explicit retry keeps a discarded finalist's recommendation in successful costs

Location: `src/koc/benchmark.py:66` and `src/koc/benchmark.py:75`, interacting with `src/koc/pipeline.py:610` and `src/koc/db.py:191`.

Explicit retry invalidates recommendations and reselects S4, but it does not invalidate or reconcile the corresponding `run_results` rows. The new classifier trusts every recorded producer without checking whether its recommendation remains selected.

Reproduction: seed six eligible creators. Five have completed S3 tasks; the sixth has a failed S3 task. Generate and commit the first five recommendations through real `_s4()` and `_cached_call()`, recording USD 0.01 each. Finish the run. Invoke real `resume(retry_failed=True)` with synthetic provider functions and a ranked local video for the sixth creator. Its new score displaces `c4` from the final five.

```text
run status=done
old finalists=[c0,c1,c2,c3,c4]
new finalists=[c0,c1,c2,c3,c5]
retained reason producers include c4's old call 5
actual S4 successful calls=6; successful USD=0.06
S4 total USD=0.06
expected S4 successful calls=5; successful USD=0.05
```

The old `c4` recommendation is absent from `recommendations`, but its paid call still counts as successful. Executing the previous revision's aggregator against the final state returns five successful S4 calls and USD 0.05.

A supplementary executed case also shows stale identity on cache replacement. After five paid recommendations, change their content-score inputs and populate the new S4 cache keys from another run. Reselect through production S4 in cache-only mode. All five stored recommendations are cache hits for the changed inputs, but `INSERT OR IGNORE` preserves all five earlier producing IDs and USD 0.05 of obsolete successful costs.

Fix: reconcile reason-result references with the committed final selection. Preserve a producer across a cache hit only when it produced that same selected request/result, and remove references to displaced finalists.

Evidence: `/tmp/koc-review-r3/selection_regressions.py`; `selection_regressions.log`, `supported_retry_stale_finalist` and `prior_code_retry_comparison`. Supplement: `regressions.log`, `cached_replacement_producer`.

### R3-F5. P2: Resuming an upgraded legacy run drops successful content costs and its estimate warning

Location: `src/koc/benchmark.py:37`, `src/koc/benchmark.py:47`, `src/koc/benchmark.py:66`, and `src/koc/benchmark.py:233`.

The benchmark treats any `run_results` row as complete tracking for the whole run. An existing run can already have completed S3 before that table existed. Its first newly tracked S4 result switches off the legacy fallback for all content results and clears `success_estimated`.

Reproduction: create an on-disk database using `7c76581`'s exact schema. Seed five valid retained analyses, matching paid content calls/cache entries, S1/S2/S3 scores, completed S3 tasks, and one pending S4 task. Aggregate before migration. Close and reopen the database, run real `db.init_db()`, and call real `resume()` with only `llm.write_reasons` replaced by a synthetic provider that records usage through the real guard.

```text
resume status=done; recommendations=5
retained analyses before/after=5 / 5
run_results kinds after resume=["reasons"]
S3 successful USD before/after=0.05 / 0.00
S3 total USD before/after=0.05 / 0.05
success_estimated before/after=true / false
content calibration sample count before/after=5 / 0
```

No content result or content ledger row changed. Partial tracking alone makes the retained content disappear from the successful path and calibration, while the report stops warning that attribution is incomplete.

The schema migration itself creates the table without losing rows; this finding concerns the mixed legacy/new attribution state after a supported resume.

Fix: track attribution coverage per result or stage. Preserve an explicitly estimated legacy path until all retained results have producing-call references, or backfill those references where identity is provable.

Evidence: `/tmp/koc-review-r3/legacy_resume.py` and `legacy_resume.log`. A separate fixture-based reproduction is in `selection_regressions.log`, `legacy_partial_tracking`.

## Per-item verdicts

Round-2 verdicts refer to each reported defect. New accounting failures have separate R3 identifiers rather than reopening an original reproduction that now passes.

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| R2-F1 P2: failed original call becomes successful after later retry | CLOSED | Original two failed responses followed by one valid response. Classification is `[false,false,true]`; success is one call, 50 input tokens, 50 output tokens, USD 0.000001. Total remains three calls and USD 0.000003. `adversarial.log`, `benchmark_failed_retry`. New selection-accounting failures are R3-F3 and R3-F4. |
| R2-F2 P2: another run's different-model analysis changes old accounting | CLOSED | Original model `m` call and later `other-model` analysis leave successful USD at 0.00 before and after. Total stays USD 0.01. Legacy attribution is explicitly estimated. `adversarial.log`, `benchmark_cross_run_success`. Partial legacy tracking has separate R3-F5. |
| R2-F3 P2: `resume --mock` generates a benchmark labelled live | CLOSED | Actual CLI exits 1 with the mode-change error; no LLM rows are generated. Benchmark command still succeeds on the untouched synthetic run. API resume also refuses the change. Suite verifies recorded mock calls in a stored-live run produce `mixed` and a warning. `mock_cli.log`, `cache_probes.log`, and `tests/core/test_r2_findings.py:119`. |
| R2-F4 P2: unsupported non-percent audience claims | OPEN, partial fix | Both original strings, `Khán giả nữ chiếm 60 phần trăm.` and `Phần lớn khán giả là nữ, trong độ tuổi 18–30.`, reject after two responses. Adding uncertainty about conversion still permits an unsupported qualitative claim. R3-F2; `adversarial.log`, `F5_words` and `F5_qualitative`, plus `regressions.log`. |
| R2-F5 P2: cached recommendations bypass validation and the caveat | CLOSED | Production S4 requests `reasons_v3`; five seeded old `reasons_v2` entries block without a provider call. Five unsafe current-version entries also block. Five benign current-version entries finish with mandatory caveats and zero tokens. Revalidation itself has the R3-F1 and R3-F2 semantic errors. `regressions.log`, `S4_cache_legacy_v2`, `S4_cache_unsafe_v3`, and `S4_cache_safe_v3`. |
| R2-F6 P2: nonempty S4 smoke crashes on `cache_only` | CLOSED | Unchanged smoke script, five synthetic candidates, real reason generator/client, mock HTTP responses. Prints `RESULT PASS: 5 recommendations`, cost 0.0 USD, exits 0. Empty synthetic database still prints FAIL and exits 1. `adversarial.log`, `smoke_nonempty` and `F6_empty`. |
| R2-F7 P3: mixed run denies known placeholder audience | CLOSED | Original mixed five-creator signatures now produce `audience_placeholder=true`, affected count 1, checked count 5, and rendered `1/5 KOC`. The sample creator's S4 audience score remains null. `adversarial.log`, `benchmark_mixed_audience`, and the suite's per-creator count test. |
| Existing-database schema migration | PASS for schema/data preservation | Build an on-disk DB from the exact pre-change schema. Seed one row in each of its 12 tables, close/reopen, call `init_db()` twice. All 12 original rows compare equal, and the new empty `run_results` table exists. `regressions.log`, `migration_existing`. Attribution after resume fails separately in R3-F5. |
| Cache revalidation never reaches a provider in cache-only mode | PASS | Old-version miss, invalid current-version hit, valid hit, and rejected brand-target hit all leave provider traps untouched. Invalid entries remain cached rather than triggering regeneration. All cache-only probes report zero tokens. `regressions.log` and `cache_probes.log`. |
| Legitimate reasons can restate the brand target | FAIL | One explicit target restatement passes; the equally legitimate audience-word formulation fails fresh and cached validation. R3-F1. |
| R3-F1: brand-target false positive | OPEN, P2 | Fresh rejection after two responses; current cache-only hit blocks without calling a provider. |
| R3-F2: unrelated uncertainty bypass | OPEN, P2 | Fresh claims pass on one response; unsafe current cache entries reach five stored recommendations. |
| R3-F3: failed stage leaves selected-result attribution | OPEN, P2 | Zero retained analyses and zero S3 scores, but USD 0.01 counts as successful. |
| R3-F4: stale selection after retry/cache replacement | OPEN, P2 | Supported retry retains six successful reason producers for five final recommendations. |
| R3-F5: partial tracking of an upgraded run | OPEN, P2 | Supported resume preserves five analyses but drops their USD 0.05 success attribution and estimate warning. |
| Previous round-1 reproductions | PASS | Completed-run ordinary resume adds no spend; empty truncated responses retain billing and enforce the cap; mixed placeholder metrics stay excluded; HTTP 500 followed by three 1054 responses blocks after four calls with zero credits; S2 reservation/billing probe passes. `replay_r1.log`. |
| Previous cache-only transport/stage probes | PASS | All five Kalodata method misses block with no ledger rows. S0/S1b/S2/S3 misses block. Browser/page and provider traps remain untouched. Missing media prevents download; local-media LLM miss blocks. S4 populated-cache resume stores five recommendations with five cache hits, zero tokens, and zero USD. Socket-attempt delta is zero. `cache_probes.log`. |
| Other original round-2 reproductions | PASS | Mixed HTTP-error pipeline still runs the second creator after blocking the first. Raw benchmark sums remain 1.5 credits, 3,350 input tokens, 335 output tokens, USD 0.0335, 14 non-cache calls, and two cache hits. Projection arithmetic and cross-run exclusion pass. `adversarial.log`. |
| Checked-in JSON/Markdown consistency | PASS for internal consistency | Stage sums and projection formulas pass. `render_markdown(reports/benchmark.json)` equals `docs/BENCHMARK.md`. Scaling figures remain labelled mock. `adversarial.log`, `stored_artifact`. |
| Full suite at requested HEAD | PASS | `251 passed in 85.93s (0:01:25)`; external socket/database guard and permitted selector workaround active, including Python subprocesses. `suite.log`. |
| Checked-in live figures match the live database; live service/model/billing validity | UNPROVEN | Live database access and network access were prohibited. Synthetic checks and artifact consistency do not establish those facts. |
| Reviewer-provider separation from all builders | UNPROVEN | This reviewer is Codex/OpenAI. This session does not establish every builder's provider. |

## Verification

The prior scripts under `/tmp/koc-review-r2/` were inspected before reuse. Copies under `/tmp/koc-review-r3/` retain the original synthetic inputs and production operations. Assertions were changed to expect the fixes; reason-cache calls use the current `reasons_v3` version. The nonempty smoke reproduction uses the unchanged script with synthetic HTTP responses instead of attempting a live request. The legacy-cache reproduction was reconstructed in `regressions.py` around production S4 summary/key construction and task execution.

All project execution used `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python` with this worktree's source/tests. The runner `/tmp/koc-review-r3/run-python` changes directory to `/tmp/koc-review-r3/work` and sets:

```sh
PYTHONPATH=/tmp/koc-review-r3/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

The external guard replaces socket connection, datagram, and DNS functions with rejecting functions. Its audit hook refuses file opens and SQLite connections to repository paths ending in `/data/koc.db`. Its subprocess wrapper preserves the guard in replacement Python environments. The permitted selector workaround caps `EpollSelector.select()` waits at 50 ms. The only recorded socket attempt was the deliberate blocked `example.invalid:80` guard self-test in the round-1 replay. The independently rerun cache-only probes recorded a zero attempt delta.

Commands, with logs of the corresponding names under `/tmp/koc-review-r3/`:

```sh
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/replay_r1.py
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/adversarial.py
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/cache_probes.py
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/mock_cli.py
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/regressions.py
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/selection_regressions.py
/tmp/koc-review-r3/run-python /tmp/koc-review-r3/legacy_resume.py
/tmp/koc-review-r3/run-python -m pytest -q -p no:cacheprovider --basetemp=/tmp/koc-review-r3/pytest /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

Each final reproduction run exited 0 with its observation assertions satisfied. The scripts intentionally assert the observed defects in the new regression cases; their exit status is not a product PASS verdict. An initial overlapping replay incremented the shared guard log during a cache-probe count assertion. The cache probes were rerun independently and passed with zero new attempts. Temporary legacy-fixture setup errors were corrected before the final successful reproduction runs; neither is reported as a product defect.

No fixes, source edits, commits, merges, or deployments were performed.
