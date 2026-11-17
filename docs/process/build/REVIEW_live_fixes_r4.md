# Independent review: live fixes, round 4

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `acb3e0975905dbe79e72588efb21c9dbf86bd21a`.
Review range: `21f48d4..acb3e09`. Previous report: `docs/process/build/REVIEW_live_fixes_r3.md`.

**Overall: FAIL. Two reproduced P2 findings remain open. No P1 or P3 finding reported.**

R3-F1, R3-F2, R3-F3, and R3-F5 are CLOSED. Both original R3-F4 cases now pass: a completed retry drops the displaced finalist's producer, and replacement from another run's cache drops the obsolete producer. R3-F4 remains OPEN for a retry interrupted before S4 commits. A new regression also assigns a failed paid repair to a result produced by another run.

The full suite passes: **261 passed in 83.61s (0:01:23)**. The additional executed accounting cases below fail despite that result.

No source files changed. This report is the only repository file created. All project execution used an external socket-blocking `sitecustomize.py`. All synthetic databases, media, scripts, and logs are under `/tmp/koc-review-r4/`. I never opened or copied the repository's `data/koc.db`. No network request reached a service.

## Findings

### R4-F1. P2: A cache hit can promote this run's failed repair to the producing call

Location: `src/koc/pipeline.py:224`, recorded at `src/koc/pipeline.py:229` and consumed at `src/koc/benchmark.py:96`.

The new `_producing_call()` selects the last non-cache ledger row with the same request hash. A matching hash does not establish that the call produced a valid result. Failed attempts also receive that hash in `_cached_call()`'s `finally` block. If another run later populates the cache, selecting its result can incorrectly attribute production to this run's failed call.

Executed reproduction uses real `execute()`, `resume()`, S4 summary/key construction, `write_reasons()`, `OpenRouterClient`, validation, cache persistence, and `BudgetGuard`. Only HTTP responses and the unused Kalodata client are substituted:

1. Seed two runs with the same five synthetic candidate summaries. Create run B first so run A remains the latest run for production `resume()`.
2. Execute A. Return a wrong creator ID in both the original response and repair, recording USD 0.01 for each. Both responses fail validation; no result is selected or cached.
3. Execute B with valid HTTP responses. B produces and caches the five recommendations.
4. Resume A with `cache_only=True`. All five recommendations come from B's cache; A makes no further provider call.

```text
A status=done; stored recommendations=5, all marked cache_hit=true
A paid ledger=[(1, reasons_v4), (2, reasons_v4_repair)]
A classified paid calls=[(1, false), (2, true)]
A selected producers=[(c0, 2), (c1, null), (c2, null), (c3, null), (c4, null)]
A actual S4 successful calls=1; successful tokens=50 input + 50 output; successful USD=0.01
A expected S4 successful calls=0; successful tokens=0; successful USD=0.00
A total paid calls=2; total USD=0.02; cache hits=5
success_estimated=false
```

The selected `c0` result was produced by B, while A's call 2 was an invalid repair. The benchmark presents the resulting attribution as exact.

A controlled comparison loads `21f48d4`'s pipeline and matching DB helper into isolated in-memory modules, retaining the current benchmark, synthetic inputs, and HTTP responses. The same flow classifies both failed calls as false and reports zero successful USD. This isolates a regression in the changed producer-selection path. The prior pipeline uses its original `reasons_v3` cache key consistently in that comparison; the real current reason generator still returns the same versioned responses.

Impact: failed spend and tokens enter successful-path totals and per-candidate projections even when every retained recommendation was produced outside the run.

Fix: persist the identity of the actual successful cache producer. Reuse an in-run call only when that call produced the selected cache value; otherwise record a null producer. Do not infer success from the last paid row with the same request hash.

Evidence: `/tmp/koc-review-r4/new_regressions.py`, `new_regressions.log`, `failed_call_promoted_by_other_run_cache`; comparison: `prior_comparison.log`.

### R4-F2. P2: An interrupted explicit retry still counts invalidated recommendations as successful

Residual R3-F4. Location: `src/koc/benchmark.py:58` and `src/koc/benchmark.py:86`; the changed cleanup only runs at `src/koc/pipeline.py:386`. Retry invalidation occurs at `src/koc/pipeline.py:621`.

The completed-reselection fix deletes old reason references inside S4's final write callback. An explicit retry deletes the recommendations earlier. If the retry stops in S3, the old references remain. `_exact()` accepts an empty retained set as covered, and `_classify_llm()` then counts every old tracked producer without intersecting it with retained recommendations.

Executed reproduction uses the same six-creator shape as R3-F4, real paid reason generation over mock HTTP responses, real task execution, and real `resume()`:

1. Seed five completed S3 creators and a sixth failed S3 task.
2. Complete S4 with five paid recommendations, USD 0.01 each, and finish the run.
3. Call `resume(retry_failed=True, cache_only=True)` with a synthetic `video_rank` cache miss for the sixth creator.
4. Inspect the blocked run and aggregate its benchmark without changing its rows.

```text
status=blocked
S3 sixth creator=blocked; S4 selection=pending
retained recommendations=0
retained S4 scores=0 (retry invalidation)
tracked reasons producers=5
actual S4 successful calls=5; successful tokens=250 input + 250 output; successful USD=0.05
expected S4 successful calls=0; successful tokens=0; successful USD=0.00
S4 total paid calls=5; total USD=0.05
success_estimated=false
```

There are no recommendations left in the run, but all five obsolete reason calls still count as successful. This is the same stale-selection defect as R3-F4 at the supported interrupted-retry boundary. The original completed-retry and cache-replacement reproductions both pass now. The controlled prior-pipeline comparison also reproduces this interrupted case; it is a residual defect, not a newly introduced regression.

Impact: a blocked run reports exact successful-path costs for results it explicitly discarded. Reaching S4's successful final commit is required to repair the attribution.

Fix: invalidate reason references in the same transaction that invalidates recommendations, and restrict benchmark producers to retained result subjects. Cleanup must hold when a resumed run blocks before S4 commits.

Evidence: `/tmp/koc-review-r4/new_regressions.py`, `new_regressions.log`, `interrupted_retry_keeps_discarded_selection`; comparison: `prior_comparison.log`. Passing completed-retry evidence: `selection_regressions.log`; passing replacement evidence: `regressions.log`.

## Per-item verdicts

CLOSED means the reported reproduction passes. It does not claim semantic completeness of the audience regex or correctness of every related accounting path. R3-F4's individual original reproductions are marked separately from its remaining interrupted-retry defect.

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| R3-F1 P2: brand-target false positive | CLOSED | Both original sentences pass real fresh generation in one HTTP response and pass current-version cache-only validation with zero provider calls. `regressions.log`, `brand_target_fresh` and `brand_target_cached`. |
| R3-F2 P2: unrelated uncertainty bypass | CLOSED | Both original qualitative and numeric conversion-uncertainty strings reject after original + repair. Direct cached qualitative validation rejects; five current-version numeric bypass cache entries block S4 with zero recommendations and zero provider calls. `regressions.log`, `unrelated_uncertainty_bypass`, `unrelated_uncertainty_cached`, `percent_uncertainty_bypass`, and `S4_cache_bypass_v4`. |
| R3-F3 P2: failed S3 task leaves selected attribution | CLOSED | Two paid calls total USD 0.02; second video fails; zero analyses, S3 scores, or `run_results` rows remain. Successful calls/USD are zero and `success_estimated=false`. `regressions.log`, `partial_S3_success`. Suite also checks attribution appears only with the successful analysis commit. |
| R3-F4 original: completed retry displaces finalist | CLOSED for original reproduction | Real `resume(retry_failed=True)` replaces c4 with c5. Exactly five reason producers remain; successful S4 calls/USD are 5/0.05, total USD remains 0.06. `selection_regressions.log`, `supported_retry_stale_finalist`. |
| R3-F4 supplement: another run's cache replaces changed inputs | CLOSED for original reproduction | Five retained recommendations are cache hits for changed S3 inputs. All five producing IDs become null; successful USD drops from 0.05 to 0.00, with five cache hits. `regressions.log`, `cached_replacement_producer`. |
| R3-F4 P2: stale selection across explicit retry | OPEN, partial fix | Retry invalidates all recommendations, then blocks in S3. Five obsolete paid producers still count as successful. R4-F2; `new_regressions.log`. |
| R3-F5 P2: upgraded legacy resume loses content attribution | CLOSED | Exact pre-change schema, close/reopen, real migration and `resume()`: five analyses remain, S3 successful USD stays 0.05, total USD stays 0.05, calibration n stays 5, estimate warning remains true for S3. `legacy_resume.log`. Fixture supplement keeps S3 successful USD 0.011, total USD 0.03, and calibration n=1. `selection_regressions.log`, `legacy_partial_tracking`. |
| R4-F1 P2: failed repair becomes producer of another run's cached result | OPEN | Two invalid paid responses followed by another run's valid cache population and five cache-only selections. Failed repair is counted as one successful call/USD 0.01. `new_regressions.log`. Prior pipeline reports zero. `prior_comparison.log`. |
| R4-F2 P2: interrupted retry retains invalidated success costs | OPEN | Zero retained recommendations, but five successful S4 calls/USD 0.05. `new_regressions.log`. |
| R2-F1: failed original call followed by successful retry | CLOSED for original reproduction | Three real HTTP responses classify `[false,false,true]`; successful calls/tokens/USD are 1/50+50/0.000001, total USD 0.000003. `adversarial.log`, `benchmark_failed_retry`. Different cross-run cache flow fails separately in R4-F1. |
| R2-F2: different-model analysis from another run changes accounting | CLOSED | Successful USD remains 0.00 before/after another model's global analysis; total remains 0.01. `adversarial.log`, `benchmark_cross_run_success`. |
| R2-F3: mock resume becomes labelled live | CLOSED | Actual CLI refuses mode change, exit 1; benchmark exits 0 and no LLM rows appear. API resume also refuses. Suite retains mixed-mode warning coverage. `mock_cli.log`, `cache_probes.log`, and full suite. |
| R2-F4: original unsupported audience formulations | CLOSED for reported strings | Original percentage, spelled-out percentage, and qualitative audience strings all reject after two responses. `adversarial.log`, `F5_original`, `F5_words`, `F5_qualitative`; R3 uncertainty variants reject as above. |
| R2-F5: cached recommendations bypass validation/caveat | CLOSED | Five old `reasons_v2` entries and five old `reasons_v3` entries each block production S4. Unsafe `reasons_v4` entries block. Safe current entries complete with mandatory caveats, five cache hits, zero tokens, and zero provider calls. `regressions.log`. |
| R2-F6: nonempty S4 smoke crashes on `cache_only` | CLOSED | Unchanged smoke script over five synthetic candidates, real generator/client, mock HTTP: `RESULT PASS: 5 recommendations`, USD 0.0, exit 0. Empty synthetic DB still exits 1 with `RESULT FAIL`. `adversarial.log`, `smoke_nonempty` and `F6_empty`. |
| R2-F7: mixed run hides known audience placeholder | CLOSED | Original mixed signatures produce placeholder flag true, affected count 1 of 5, rendered `1/5 KOC`, and null audience score for the affected creator. `adversarial.log`, `benchmark_mixed_audience`; full suite per-creator count checks. |
| Existing-database schema migration | PASS for schema/data preservation | Seed one row in each of the exact old schema's 12 tables; close/reopen and run `init_db()` twice. All 12 rows compare equal and new `run_results` is empty. `regressions.log`, `migration_existing`. |
| Current cache validation never calls provider in cache-only mode | PASS | Old-version miss, unsafe current hit, safe current hit, and both brand-target hits leave provider traps untouched. Zero tokens. `regressions.log`. |
| Previous round-1 reproductions | PASS | Ordinary completed-run resume adds no spend; empty truncations bill USD 0.04 for two calls and enforce cap; mixed placeholder metrics/citations stay excluded; HTTP 500 plus three 1054 responses stop after four calls, zero credits; S2 reserves/bills one credit before the second task blocks. `replay_r1.log`. |
| Previous transport/stage cache-only probes | PASS | Five public Kalodata methods miss without ledger rows; S0/S1b/S2/S3 misses block; browser/provider traps stay untouched; missing media prevents download; local media with missing LLM cache blocks. S4 cache-hit resume stores five recommendations with zero tokens/USD. Socket-attempt delta=0. `cache_probes.log`. |
| Other original round-2 reproductions | PASS | Mixed HTTP-error pipeline still executes the second creator. Raw totals remain 1.5 credits, 3,350 input tokens, 335 output tokens, USD 0.0335, 14 non-cache calls, and two cache hits. Projection formulas and cross-run exclusion pass. `adversarial.log`. |
| Checked-in JSON/Markdown consistency | PASS for internal consistency | All stage sums and projection formulas pass. Rendering `reports/benchmark.json` exactly matches `docs/BENCHMARK.md`; scaling remains labelled mock. `adversarial.log`, `stored_artifact`. |
| Full suite at requested HEAD | PASS | `261 passed in 83.61s (0:01:23)` with external socket/database guard, guarded Python subprocesses, and permitted selector workaround. `suite.log`. |
| Live figures match live DB; live service/model/billing validity | UNPROVEN | Network and live DB access were prohibited. Synthetic execution and checked-in artifact consistency do not establish these facts. |
| Complete semantic support of audience reasons | UNPROVEN, outside regex guarantee | `src/koc/llm/reasons.py:76` documents regex screening as a safety net. Review checks reported strings, clause controls, prompt version, and appended caveat; it does not treat those controls as proof of semantic support. No wording-only bypass is used to fail this review. |
| Reviewer-provider separation from all builders | UNPROVEN | This reviewer is Codex/OpenAI. The session does not establish every builder's provider. |

## Verification

I inspected the round-3 scripts before copying them to `/tmp/koc-review-r4/`. The copies preserve the original candidate data, audience strings, task transitions, migration schemas, and production operations. Expected-defect assertions were updated to expect fixes. Current cache probes now request `reasons_v4`, while separate production probes retain both obsolete `reasons_v2` and `reasons_v3` keys. Two fixture-only writes now call `_commit_selected()` with their manual result write, mirroring the new production commit boundary. The scripts that generated other scripts (`prepare_replays.py` and `extend_probes.py`) were inspected but not executed; their resulting reproductions were rerun directly.

All project execution used `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python` against this checkout. The external runner changes directory to `/tmp/koc-review-r4/work` and sets:

```sh
PYTHONPATH=/tmp/koc-review-r4/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

`/tmp/koc-review-r4/guard/sitecustomize.py` rejects socket connections, datagrams, and DNS calls. Its audit hook refuses file opens and SQLite connections to repository paths ending in `/data/koc.db`. Its subprocess wrapper preserves the guard when tests replace Python child environments. The permitted selector workaround caps `EpollSelector.select()` waits at 50 ms. The only logged socket attempt is the deliberate, blocked `example.invalid:80` guard self-test from the round-1 replay. The cache-only probes independently report a zero attempt delta.

Commands, with corresponding logs under `/tmp/koc-review-r4/`:

```sh
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/replay_r1.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/adversarial.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/cache_probes.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/mock_cli.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/regressions.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/selection_regressions.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/legacy_resume.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/new_regressions.py
/tmp/koc-review-r4/run-python /tmp/koc-review-r4/new_regressions.py --prior
/tmp/koc-review-r4/run-python -m pytest -q -p no:cacheprovider --basetemp=/tmp/koc-review-r4/pytest /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

Every final reproduction run exited 0 with its observation assertions satisfied. `new_regressions.py` intentionally asserts the observed defects; its exit code is not a product PASS verdict. An initial prior-pipeline comparison hit the changed DB helper signature; the final comparison loads the matching prior DB module as well. No product defect is inferred from that harness mismatch.

No fixes, source edits, commits, merges, or deployments were performed.
