# Independent review: live fixes, round 5

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `4366c34c767dbf7b3b204dc76d7e3a9785e8473c`.
Review range: `acb3e09..4366c34`. Previous report: `docs/process/build/REVIEW_live_fixes_r4.md`.

**Overall: FAIL. Both original R4 findings are CLOSED. One new P2 accounting regression remains OPEN. No P1 finding reported.**

R4-F1 no longer promotes a failed repair when another run supplies the cache. R4-F2 now removes reason attribution atomically with recommendations, and the benchmark excludes stale result subjects. Both web reproductions pass. The existing-database migration preserves stored rows, but a later explicit retry loses known successful-call attribution for recommendations reused from the old cache. The benchmark reports the resulting zero successful spend as exact.

The full suite passes: **268 passed in 89.10s (0:01:29)**. The additional upgrade reproduction below fails the accounting requirement despite that result.

No source files changed. This report is the only repository file created. All project execution used an external socket-blocking `sitecustomize.py`. Synthetic databases, media, scripts, and logs are under `/tmp/koc-review-r5/`. I never opened or copied the repository's `data/koc.db`. No network request reached a service.

## Findings

### R5-F1. P2: Retrying an upgraded run erases successful spend for its own cached recommendations

Location: `src/koc/db.py:41` and `src/koc/db.py:43`, combined with `src/koc/pipeline.py:226` and `src/koc/pipeline.py:232`. Exact classification consumes the resulting null producers at `src/koc/benchmark.py:87`.

The migration adds `llm_cache.call_id` with null values for every existing entry. `_producing_call()` treats those unknown producers the same as confirmed cache reuse from another run. On explicit retry, the pipeline deletes the previous reason references and then writes null producers for the old cache hits. `_exact()` still accepts those rows as complete attribution. Successful calls, tokens, and USD disappear even when the same run paid for every retained recommendation and had valid producer references before retry.

Executed reproduction uses the exact `acb3e09` schema, DB helpers, cache writer, and pipeline loaded into isolated in-memory modules. It uses real S4 summary/key construction, `write_reasons()`, `OpenRouterClient`, validation, cache persistence, and ledger accounting. Only HTTP responses and the Kalodata client are substituted:

1. Create an on-disk database with five completed S3 creators and a sixth failed S3 task.
2. Execute S4 with `acb3e09`. Five valid provider responses cost USD 0.01 each. The run finishes with five recommendations and five known producer IDs, 1 through 5.
3. Close the database and copy this synthetic file into separate baseline and upgrade cases.
4. In the upgrade case, reopen it with current code and call `init_db()` twice. All 80 existing rows across 13 tables retain their original field values. The five old cache entries gain null `call_id` values. Existing `run_results` references remain correct before retry.
5. Call real `resume(retry_failed=True)`. The sixth creator returns no videos, so the original five remain selected. All five reasons come from the old cache, with no additional provider call.

```text
                                      acb3e09 baseline   4366c34 upgrade
run status                            done               done
retained recommendations              5                  5
recommendation content changed        false              false
new provider calls                    0                  0
S4 cache hits                         5                  5
S4 total paid calls / USD             5 / 0.05           5 / 0.05
S4 successful calls before retry      5                  5
S4 successful calls after retry       5                  0
S4 successful input/output tokens     250 / 250          0 / 0
S4 successful USD after retry         0.05               0.00
retained producer IDs                 1,2,3,4,5          null,null,null,null,null
success_estimated                     false              false
```

The baseline runs the same supported retry against an independent copy of the same old database. It retains all five successful producers. This isolates a regression in the new migration and producer-selection path. The upgraded run's total spend remains correct, but its successful-path totals and per-candidate costs are wrong.

Fix: preserve or migrate verifiable producer identities for existing cache entries before retry invalidation removes their known references. Distinguish unknown legacy provenance from confirmed cross-run reuse, and label any heuristic fallback as estimated. Do not restore the last-paid-row-by-hash inference that caused R4-F1.

Evidence: `/tmp/koc-review-r5/upgrade_accounting.py` and `upgrade_accounting.log`. The script asserts the observed regression; its exit code is not a product PASS verdict.

## Per-item verdicts

CLOSED means the reported reproduction passes. A separate upgraded-cache retry fails in R5-F1. No wording-level audience-regex bypass is treated as a P1 or P2 finding.

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| R4-F1 P2: failed repair becomes producer of another run's cached result | CLOSED | A records two invalid paid responses, then selects five valid recommendations from B's cache. A retains five null producers, zero successful calls/tokens/USD, and USD 0.02 total spend. Both failed calls classify false. `new_regressions.log`, `failed_call_promoted_by_other_run_cache`. The full-suite producer test also verifies B keeps its successful call. |
| R4-F2 P2: interrupted retry retains invalidated success costs | CLOSED | Real retry blocks in S3 with zero recommendations, zero S4 scores, and zero reason references. Successful S4 calls/tokens/USD are zero; total spend stays USD 0.05. `new_regressions.log`, `interrupted_retry_keeps_discarded_selection`. |
| Retry invalidation transaction | PASS | A SQLite trigger aborts the S4-score deletion after recommendation and reason-reference deletion. The transaction restores all original rows in recommendations, `run_results`, scores, tasks, runs, and the LLM ledger. `accounting_safety.log`, `retry_atomicity`. |
| Benchmark counts only retained result subjects | PASS | Four recommendations with five reason references count four successful calls. One retained video with two content references counts one successful call/USD 0.01, while total remains two calls/USD 0.02. `accounting_safety.log`, `retained_only_reasons` and `retained_only_content`. |
| R5-F1 P2: upgraded cache loses same-run producer attribution on retry | OPEN | Same five recommendations and zero new provider calls, but successful S4 USD falls from 0.05 to 0.00 with `success_estimated=false`. The baseline retains USD 0.05. `upgrade_accounting.log`. |
| Web dashboard `KeyError: 'skipped'` | CLOSED | HTTP 200 with all six allowed statuses. Raw SQL, adapter counters, and rendered table cells agree per stage and overall. Totals are pending 1, running 2, done 128, failed 4, blocked 6, skipped 7, total 148. `web_safety.log`, `dashboard`; full suite `tests/web/test_app_ui_fixes.py`. |
| Web frame URLs lose the video folder | CLOSED | Six rendered detail-image URLs retain `/media/frames/<video_id>/f_<t_ms>.jpg` and serve JPEGs with HTTP 200. All five top-5 adapter hook URLs also retain their video folder and serve successfully. Relative paths, absolute paths, and flat-layout compatibility pass the suite. `web_safety.log`, `frames`; `tests/web/test_app_ui_fixes.py`. |
| `/media` traversal and symlink containment | PASS for executed probes | Sixteen requests cover encoded parent components, encoded separators, double encoding, absolute paths, backslashes, sibling-prefix escape, external file/directory symlinks, missing files, and adapter-generated unsafe paths. Every request returns 403 or 404. No external canary content leaks. The route retains its resolved-path containment check at `src/koc/web/app.py:223`. `web_safety.log`, `media_safety`. |
| Existing-database migration preserves schema/data | PASS for preservation; accounting FAIL | Exact `acb3e09` database: 80 original rows across 13 tables compare equal after close/reopen and two initializations, excluding only the newly added nullable field. The earlier 12-table schema also preserves every original row and adds an empty `run_results`. `upgrade_accounting.log`, `migration_preservation`; `regressions.log`, `migration_existing`. Subsequent retry accounting fails separately in R5-F1. |
| R3-F1: brand-target false positive | CLOSED | Both original sentences pass fresh generation and current-version cache-only validation without provider calls on cache hits. `regressions.log`, `brand_target_fresh` and `brand_target_cached`. |
| R3-F2: unrelated uncertainty bypass | CLOSED for reported strings | Original qualitative and numeric variants reject after original plus repair. Direct cached validation rejects, and five unsafe current-version entries block S4 with zero recommendations and provider calls. `regressions.log`. |
| R3-F3: failed S3 task leaves selected attribution | CLOSED | Two paid calls total USD 0.02; the second video fails. Zero analyses, S3 scores, or selected references remain. Successful calls/USD are zero. `regressions.log`, `partial_S3_success`. |
| R3-F4: completed retry displaces finalist | CLOSED for original reproduction | Real retry replaces c4 with c5. Five retained reason producers count five successful calls/USD 0.05; total S4 USD is 0.06. `selection_regressions.log`, `supported_retry_stale_finalist`. The interrupted variant is CLOSED under R4-F2. |
| R3-F4 supplement: another run's cache replaces changed inputs | CLOSED | Five recommendations use another run's cache. All selected producers become null and successful USD falls from 0.05 to 0.00. `regressions.log`, `cached_replacement_producer`. |
| R3-F5: legacy resume loses content attribution | CLOSED for original reproduction | Earlier 12-table schema, close/reopen, migration, and resume retain five analyses. S3 successful and total USD both remain 0.05, calibration n remains 5, and S3 remains labelled estimated. The partial-tracking fixture retains successful USD 0.011 and total USD 0.03. `legacy_resume.log`, `selection_regressions.log`. |
| Previous round-1 reproductions | PASS | Completed-run resume adds no spend. Empty truncations bill USD 0.04 for two calls and enforce the cap. Placeholder audience metrics/citations remain excluded. HTTP 500 plus three 1054 responses stop after four calls with zero credits. S2 reserves and bills one credit before blocking the second task. `replay_r1.log`. |
| Previous transport/stage cache-only probes | PASS | All five public Kalodata methods miss without ledger rows. S0/S1b/S2/S3 misses block. Browser/provider traps remain untouched. Missing media prevents download. S4 cache-hit resume stores five recommendations with zero tokens/USD. Socket-attempt delta is zero. `cache_probes.log`. |
| Previous round-2 accounting, status, and provenance reproductions | PASS | Failed original/repair followed by valid retry classifies `[false,false,true]`. Different-model cross-run analysis does not change successful spend. API and CLI reject mock-mode changes on resume. Mixed-error execution reaches the second creator. Raw totals remain 1.5 credits, 3,350 input tokens, 335 output tokens, USD 0.0335, 14 non-cache calls, and two cache hits. `adversarial.log`, `cache_probes.log`, `mock_cli.log`. |
| Previous audience-cache, smoke, and placeholder reproductions | PASS for reported cases | Old `reasons_v2` and `reasons_v3` keys block. Unsafe current entries block. Safe current entries include mandatory caveats. Unchanged smoke script produces five recommendations at USD 0.0 on synthetic nonempty data and fails on empty data. Mixed placeholder output reports one of five affected creators. `regressions.log`, `adversarial.log`. |
| Checked-in JSON/Markdown consistency | PASS for internal consistency | Stage sums and projection formulas pass. Rendering `reports/benchmark.json` exactly matches `docs/BENCHMARK.md`. Scaling remains labelled mock. `adversarial.log`, `stored_artifact`. |
| Full suite at requested HEAD | PASS | `268 passed in 89.10s (0:01:29)` with external socket/database guard, guarded Python children, and the permitted selector workaround. `suite.log`. |
| Live figures match live DB; live service/model/billing validity | UNPROVEN | Network and live DB access were prohibited. Synthetic execution and checked-in artifact consistency do not establish these facts. |
| Complete semantic support of audience reasons | UNPROVEN, documented regex limitation | The original reported strings remain covered. Regex screening is a safety net, not proof of semantic support. Wording-only bypasses remain P3 under the requested grading. |
| Reviewer-provider separation from all builders | UNPROVEN | This reviewer is Codex/OpenAI. The session does not establish every builder's provider. |

## Verification

I inspected the changed source and tests, the previous report, and the round-4 reproduction scripts. Regression searches remained within the changed producer/cache, migration, retry, benchmark, dashboard, and media-URL behavior. No new feature or source fix was attempted.

Round-4 scripts were copied outside the repository. Their candidate data, audience strings, task transitions, and production operations remain intact. The two expected-defect assertions in `new_regressions.py` now expect zero successful calls and USD. Old-schema fixture writes explicitly name the four original cache columns. Migration comparisons preserve those original fields and separately check the new null field. These are fixture/schema adaptations, not product changes.

`upgrade_accounting.py` loads `acb3e09`'s pipeline, DB module, and cache writer into isolated modules. It creates the old database through those production functions before comparing independent baseline and upgraded copies. It asserts unchanged recommendation content apart from usage metadata, unchanged total spend, zero new provider calls, and the observed successful-spend regression.

`web_safety.py` uses an isolated fixture database and FastAPI's in-process `TestClient`, so no local server or TCP connection is needed. The fixture's mock flag is cleared only in that temporary database to exercise frame rendering. Dashboard assertions compare actual SQL counts with both adapter values and rendered cells. The top-5 template currently does not render hook images; its changed adapter URLs are checked directly. `accounting_safety.py` forces a transaction failure and checks retained-subject accounting independently for reasons and content.

All project execution used `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python` against this checkout. The external runner changes directory to `/tmp/koc-review-r5/work` and sets:

```sh
PYTHONPATH=/tmp/koc-review-r5/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

`/tmp/koc-review-r5/guard/sitecustomize.py` blocks socket connections, datagrams, and DNS calls. Its audit hook refuses repository `data/koc.db` file opens and SQLite connections. Its subprocess wrapper preserves the guard in Python child environments. The selector workaround caps `EpollSelector.select()` waits at 50 ms. The only logged socket attempt is the deliberate, blocked `example.invalid:80` self-test in `replay_r1.py`.

Commands, with corresponding logs under `/tmp/koc-review-r5/`:

```sh
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/replay_r1.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/adversarial.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/cache_probes.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/mock_cli.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/regressions.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/selection_regressions.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/legacy_resume.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/new_regressions.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/upgrade_accounting.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/web_safety.py
/tmp/koc-review-r5/run-python /tmp/koc-review-r5/accounting_safety.py
/tmp/koc-review-r5/run-python -m pytest -q -p no:cacheprovider --basetemp=/tmp/koc-review-r5/pytest /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

Every final reproduction run exited 0 with its observation assertions satisfied. The first parallel cache-probe run observed the other script's deliberate socket self-test in their shared guard log. Running the cache probe alone passed with a zero attempt delta. The first web probe incorrectly expected hook images in the top-5 template; inspection corrected that assertion to check the adapter output directly. Neither initial verification-script mismatch is a product finding.

No source edits, fixes, commits, merges, or deployments were performed.
