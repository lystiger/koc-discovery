# Independent review: live fixes, round 7

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `c9c1231d13b156cf8f8ff070247d5c0fb26458fd`.
Review range: `b81bfca..c9c1231`. Previous report: `docs/build/REVIEW_live_fixes_r6.md`.

**Overall: FAIL. R6-F1 is CLOSED. One new P2 benchmark regression remains OPEN. No P1 finding reported.**

Per-result attribution preserves confirmed producers and known exclusions when another result has unknown provenance. The exact R6-F1 reproduction now reports zero successful spend for A, USD 0.02 total spend, and an estimated S4 split. However, the new `_exact()` implementation crashes read-only benchmark generation for older databases when a run has no retained content results. The previous benchmark reports the same run's paid calls correctly.

The full suite passes: **272 passed in 90.18s (0:01:30)**. The independent legacy-run reproduction exposes the regression despite that result.

No source files changed. This report is the only repository file created during this review. Scripts, synthetic databases, and logs are under `/tmp/koc-review-r7/`. The unchanged R6 script also recreates its original synthetic `/tmp/koc-review-r6/work/mixed.db`. All project execution used an external socket-blocking `sitecustomize.py`. I never opened or copied the repository's `data/koc.db`. The guard logged zero socket or DNS attempts.

## Findings

### R7-F1. P2: Read-only benchmarking crashes for legacy runs without retained content results

Location: `src/koc/benchmark.py:78`, through the new empty-set return at `src/koc/benchmark.py:68` and the existing dereference at `src/koc/benchmark.py:83`.

When `run_results` does not exist, `_selected()` returns `None`. Previously, `_exact()` returned false for that schema. Now `_attribution()` returns `(set(), set(), retained)`, and `_exact()` returns true when `retained` is empty. `_final_content()` then evaluates `_selected(conn, run_id)["content"]` and raises `TypeError: 'NoneType' object is not subscriptable`.

This state occurs in a legitimate legacy run whose paid S3 work fails before committing a result. The benchmark CLI opens existing databases without migration, so the missing table is part of its supported read-only path.

Executed reproduction:

1. Load the exact `7c76581` DB helpers and pipeline into isolated modules. Create an on-disk database through those old helpers, without `run_results`.
2. Create one S3 task and a local synthetic video. Execute the old production pipeline with a provider substitute that records USD 0.01 through the real budget guard, then raises a validation error.
3. Confirm that S3 failed, S4 is blocked, the run is blocked, and no analysis or S3 score exists. The ledger retains one paid call, 50 input tokens, 50 output tokens, and USD 0.01.
4. Close the database. Reopen it read-only and aggregate the same run with the `b81bfca` benchmark and the current benchmark.
5. Invoke the actual benchmark CLI with each benchmark module and separate temporary output directories.

```text
                                      b81bfca           c9c1231
stored run status                     blocked           blocked
run_results table                     absent            absent
retained content results              0                 0
raw ledger paid calls / USD           1 / 0.01          1 / 0.01
reported total paid calls / USD       1 / 0.01          no result: TypeError
reported successful calls / USD       0 / 0.00          no result: TypeError
benchmark CLI exit code               0                 1
JSON report written                   true              false
read-only aggregation DB changes      0                 0
```

The defect prevents reporting actual ledger spend for this run. It does not change the ledger or represent uncertainty in an estimated successful-path split. Therefore the requested exception for imperfect legacy estimates does not apply.

Fix: preserve the missing-table behavior in `_exact()`, or let `_final_content()` handle that schema without dereferencing `None`. A legacy run with zero retained results must still produce its ledger totals and zero successful result costs.

Evidence: `/tmp/koc-review-r7/legacy_empty_content.py` and `legacy_empty_content.log`. The script executes production pipeline, ledger, aggregation, and CLI code. Only the video-list response and provider behavior are synthetic. Its assertions confirm the baseline result, current exception, CLI failure, and zero changes during read-only aggregation. An empty run with the current schema aggregates successfully in `attribution_matrix.log`, which isolates the missing-table condition.

## Per-item verdicts

CLOSED applies to the executed reproduction and supported tracked-result behavior. Imperfect attribution for untracked legacy rows remains P3 when the report labels it estimated. Such estimates do not count as open P1 or P2 findings.

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| R6-F1 P2: unknown provenance overrides a known cross-run exclusion | CLOSED | The unchanged original script now classifies both failed A calls false. A retains four `reused` rows and one `unknown` row, zero successful calls or USD, five cache hits, and USD 0.02 total spend. S4 remains estimated. Resume adds zero provider calls. `mixed_provenance_original.log`, `mixed_provenance.log`. |
| R6-F1 control: stale unknown reference broadens attribution | CLOSED | Removing only c4's recommendation leaves four retained reused results. Successful spend remains zero and `success_estimated=false`. `mixed_provenance.log`. |
| R2-F1: failed original call counted after a later successful retry, with committed attribution | CLOSED | The surviving R4 and R5 versions record the selected producer. Classification is `[false,false,true]`, with one successful call, 50 input tokens, USD 0.000001 successful spend, and USD 0.000003 total spend. The split is exact. `original_benchmark_sections.log`, `adversarial.log`. |
| R2-F1 legacy variant: original R2 and R3 scripts omit the result-commit callback | OPEN as P3 only | Both original sections retain zero result references and classify `[true,false,true]`. Successful spend is estimated at USD 0.000002. Actual total remains three paid calls and USD 0.000003. Both reports explicitly set `success_estimated=true` for S4. This does not reopen the P2 finding under the requested grading. `original_benchmark_sections.log`. |
| R2-F2: another run's different-model analysis changes old successful spend | CLOSED | The original R2, R3, R4, and R5 sections keep successful spend at zero before and after the unrelated analysis. Total spend remains USD 0.01. `original_benchmark_sections.log`. |
| R2-F3: mock resume produces a benchmark labelled live | CLOSED | The real CLI refuses the mode change with exit 1. Benchmark exits 0, reports live mode, and finds no LLM calls. `mock_cli.log`. |
| R2-F7: mixed placeholder audience is denied by the benchmark | CLOSED | The original sections report `audience_placeholder=true`. The current assertion checks one affected creator out of five. `original_benchmark_sections.log`, `adversarial.log`. |
| R3-F3: partial failed S3 work retains successful attribution | CLOSED | Two paid calls remain in total at USD 0.02. No analysis, S3 score, or selected reference survives. Successful calls and USD are zero. `regressions.log`, `partial_S3_success`. |
| R3-F4: completed retry keeps a discarded finalist's producer | CLOSED | Real retry replaces c4 with c5. Five retained producers contribute USD 0.05 successful spend. Total S4 spend remains USD 0.06. `selection_regressions.log`. |
| R3-F4 supplement: replacement from another run's cache keeps the old producer | CLOSED | Five cache hits replace the selected results. Successful spend falls from USD 0.05 to zero, and selected producers become null. `regressions.log`, `cached_replacement_producer`. |
| R3-F5: upgraded legacy resume loses content attribution | CLOSED for the reported nonempty case | The old-schema resume retains five analyses, USD 0.05 successful and total S3 spend, and calibration n=5. S3 remains estimated. Partial tracking retains USD 0.011 successful spend and USD 0.03 total spend. `legacy_resume.log`, `selection_regressions.log`. The zero-retained-result case fails separately under R7-F1. |
| R4-F1: a failed call becomes the producer of another run's cache result | CLOSED | Both failed calls classify false. A has zero successful S4 spend, five cache hits, and USD 0.02 total spend. `new_regressions.log`. |
| R4-F2: interrupted retry counts discarded S4 results | CLOSED | Real cache-only blocking leaves zero recommendations, S4 scores, and reason references. Successful S4 spend is zero. Total S4 spend remains USD 0.05. `new_regressions.log`. |
| R5-F1: upgraded cache loses its own known producers on retry | CLOSED | The original upgrade fixture retains the same five recommendations and producers 1 through 5. Successful spend remains five calls, 250 input tokens, 250 output tokens, and USD 0.05. Retry adds no provider calls, and the split remains exact. `upgrade_accounting.log`. |
| Per-result confirmed, reused, unknown, untracked, and stale attribution | PASS for both content and reasons | Each mixed fixture classifies `[true,false,true,true,false]`. Five paid calls total USD 0.05. Three successful calls contribute USD 0.03, with the relevant stage estimated. Removing unknown and untracked results preserves the confirmed USD 0.01 and clears the estimate flag. A stale known call cannot be claimed for an unknown result. `attribution_matrix.log`. |
| Benchmark excludes stale result subjects | PASS | Four retained reasons count four of five paid producers. One retained content result counts USD 0.01 successful spend, while two paid calls remain USD 0.02 total. `accounting_safety.log`. |
| Unknown legacy producer retry | PASS | All five recommendations remain unchanged, with five estimated successful calls and USD 0.05. Only S4 is estimated. No new paid calls occur. `unknown_retry.log`. |
| Prior migration and transaction controls | PASS | The 80-row upgrade fixture preserves original fields. The 83-row control remains identical after its second migration. Retry rollback preserves six tables. A read-only old-schema run with retained results still reports five calls and USD 0.05. `upgrade_accounting.log`, `migration_safety.log`, `accounting_safety.log`. These controls do not resolve R7-F1. |
| Ledger totals and projections | PASS for aggregations that complete | Original R2 through R5 sections retain 1.5 credits, 3,350 input tokens, 335 output tokens, USD 0.0335, 14 non-cache calls, and two cache hits. Projections for 50, 200, and 500 candidates satisfy the stored formulas. Other runs remain excluded. `original_benchmark_sections.log`. |
| R7-F1: read-only legacy benchmark with no retained content | OPEN, P2 | The previous module reports one paid call and USD 0.01. Current aggregation raises TypeError, and the actual CLI produces no report. `legacy_empty_content.log`. |
| Full suite at requested HEAD | PASS | `272 passed in 90.18s (0:01:30)` under the external network/database guard. `suite.log`. |
| Prior behavior outside the changed benchmark code | Not independently re-reviewed for regressions | Some replay scripts also exercise their original pipeline and validation controls. New regression investigation stayed within the changed benchmark behavior. |
| Live figures match the live DB; live service and billing validity | UNPROVEN | Network and live database access were prohibited. Synthetic execution cannot establish these facts. |
| Reviewer-provider separation from all builders | UNPROVEN | This reviewer is Codex/OpenAI. The session does not establish every builder's provider. |

## Verification

I inspected the range, previous reports, surviving benchmark reproduction scripts, and benchmark callers. `src/koc/benchmark.py` is the only changed production file. The range also adds the previous reports and a regression test. No source fixes, commits, merges, or deployments were attempted.

The exact command against `/tmp/koc-review-r6/mixed_provenance.py` exits 1 because its original assertion expects the old defect, USD 0.01 successful spend. Its output now shows the correct zero. A byte-identical copy produces the same result. `mixed_provenance.py` under the R7 directory changes only the temporary working path, current revision label, and expected successful USD to zero. That copy also completes the stale-unknown control and exits 0.

`original_benchmark_sections.py` reads the surviving R2, R3, R4, and R5 `adversarial.py` files and executes their benchmark sections independently. It retains their helper functions, inputs, provider responses, and original assertions. The only SQL adaptation names the original four cache columns explicitly because the current schema has added a fifth column. It logs assertion failures rather than preventing later independent sections from running. Old assertions that demand a fixed defect naturally fail. The R3 untracked retry also fails its exact-success assertion, but its estimated label and correct ledger total make that residual split P3 under the requested rubric.

Other replay copies use the latest surviving R5 or R6 versions. Changes are limited to external working paths. These copies already contain the earlier documented fixture adaptations and corrected expectations. Some retain hardcoded `b81bfca` or `4366c34` output labels. Their current imports execute this checkout at `c9c1231`; explicitly loaded historical comparison modules use the revisions named in their scripts.

All project execution used `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python` through `/tmp/koc-review-r7/run-python`. The runner changes directory to `/tmp/koc-review-r7/work` and sets:

```sh
PYTHONPATH=/tmp/koc-review-r7/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

The external guard blocks socket connections, datagrams, and DNS. Its audit hook blocks repository `data/koc.db` opens and SQLite connections. Its subprocess wrapper preserves the guard in Python child environments. The permitted selector workaround caps `EpollSelector.select()` waits at 50 ms. `environment.json` confirms the active guard, imported benchmark path, disabled bytecode, and zero socket or DNS attempts.

Commands, with corresponding logs under `/tmp/koc-review-r7/`:

```sh
/tmp/koc-review-r7/run-python /tmp/koc-review-r6/mixed_provenance.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/mixed_provenance.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/original_benchmark_sections.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/adversarial.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/regressions.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/selection_regressions.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/legacy_resume.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/mock_cli.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/new_regressions.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/upgrade_accounting.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/accounting_safety.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/migration_safety.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/unknown_retry.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/attribution_matrix.py
/tmp/koc-review-r7/run-python /tmp/koc-review-r7/legacy_empty_content.py
/tmp/koc-review-r7/run-python -m pytest -q -p no:cacheprovider --basetemp=/tmp/koc-review-r7/pytest /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

All listed final commands exit 0 except the unchanged R6 script, whose obsolete defect assertion exits 1 as described above. The new legacy script asserts the observed product defect, so its exit 0 is evidence that the defect reproduces. Its first draft incorrectly expected the old pipeline's failed run to finish `done`. Inspection showed the legitimate `blocked` state, and the final script asserts that state. No product finding depends on that initial verification-script mismatch.
