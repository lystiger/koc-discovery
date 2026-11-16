# Independent review: live fixes, round 8

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `9334d9cf99fe2b9e81c8f311151a38df27299c1c`.
Review range: `c9c1231..9334d9c`. Previous report: `docs/build/REVIEW_live_fixes_r7.md`.

**Overall: PASS. R7-F1 and R6-F1 are CLOSED. No open P1 or P2 finding in the changed code.**

The missing-table guard at `src/koc/benchmark.py:78` restores read-only benchmarking for legacy runs without retained content results. The exact failed-S3 fixture reports its blocked status, one paid call, 50 input tokens, 50 output tokens, and USD 0.01 total spend. Successful spend remains zero, and S3 is labelled estimated. The parent revision crashes on that same database.

The full suite passes: **273 passed in 92.28s (0:01:32)**. Independent checks also pass for mixed provenance and 16 read-only schema/accounting cases.

No source files changed. This report is the only repository file created during this review. Scripts, synthetic databases, reports, and logs are under `/tmp/koc-review-r8/`. The unchanged original scripts also recreate their synthetic databases under `/tmp/koc-review-r7/` and `/tmp/koc-review-r6/`. All project execution used an external socket-blocking `sitecustomize.py`. I never opened or copied the repository's `data/koc.db`. The guard recorded zero socket or DNS attempts.

## Findings

No new P1 or P2 correctness regression found in the changed code.

### R7-F1: CLOSED

Location: `src/koc/benchmark.py:78`, protecting `_final_content()` at `src/koc/benchmark.py:85`.

I reran the unchanged `/tmp/koc-review-r7/legacy_empty_content.py`. It reaches the original assertion that expects the current benchmark to crash. That assertion now fails because aggregation succeeds. The fixture still uses the exact `7c76581` database helpers and production pipeline. A synthetic provider records USD 0.01 through the real budget guard, then fails validation before any content result is retained.

An external copy preserves that fixture and replaces the obsolete defect assertions with closure assertions. It verifies equality with the previously working `b81bfca` aggregation, zero successful spend, estimated S3 attribution, zero read-only connection changes, and successful execution of the actual benchmark CLI.

I also loaded the parent `c9c1231` benchmark and compared it with HEAD against this exact failed-run database:

```text
                                      c9c1231           9334d9c
stored run status                     blocked           blocked
run_results table                     absent            absent
llm_cache.call_id                     absent            absent
retained content results              0                 0
raw ledger paid calls / USD           1 / 0.01          1 / 0.01
reported total paid calls / USD       TypeError         1 / 0.01
reported successful calls / USD       no report         0 / 0.00
benchmark CLI exit code               1                 0
JSON report written                   false             true
read-only aggregation DB changes      0                 0
```

HEAD writes both JSON and Markdown. The database bytes remain unchanged after aggregation and CLI execution. Evidence: `legacy_empty_content_original.log`, `legacy_empty_content.log`, and `legacy_parent_compare.log` under `/tmp/koc-review-r8/`.

### R6-F1: CLOSED

Location: the unchanged per-result classification at `src/koc/benchmark.py:101`, checked for regression from the new `_exact()` guard.

I reran the unchanged `/tmp/koc-review-r6/mixed_provenance.py`. It recreates the interrupted legacy c4 cache, migrates it twice, executes A's two invalid paid calls, lets B populate the other caches, and resumes A through the real cache-only path. A retains four `reused` rows and one `unknown` row. Both failed paid calls classify false. A reports zero successful S4 calls and USD, five cache hits, two total paid calls, and USD 0.02 total spend. The run is done, S4 is estimated, and resume adds zero provider calls.

The unchanged script exits 1 because its original assertion expects the old USD 0.01 defect. An external copy changes only its temporary database path, current revision label, and expected successful USD to zero. That copy exits 0 and completes the stale-unknown control. Removing only c4's recommendation leaves four retained reused results, zero successful calls, and `success_estimated=false`.

Evidence: `mixed_provenance_original.log` and `mixed_provenance.log` under `/tmp/koc-review-r8/`. Historical revision labels in the unchanged script are literal labels. Its current benchmark import executes this checkout at `9334d9c`.

## Per-item verdicts

P1 and P2 apply to correctness bugs under the requested grading. An imperfect successful-path split explicitly labelled estimated is P3 and does not fail this review.

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| R7-F1 P2: legacy read-only benchmark crashes without retained content | CLOSED | Exact failed-S3 fixture aggregates and writes both reports. One paid call and USD 0.01 remain in total. Successful calls and USD are zero. Parent aggregation and CLI still fail on the same database. `legacy_empty_content.log`, `legacy_parent_compare.log`. |
| R6-F1 P2: unknown provenance overrides a known cross-run exclusion | CLOSED | Both failed calls remain excluded. Four reused results and one unknown result yield USD 0.00 successful and USD 0.02 total spend. Resume adds zero calls. `mixed_provenance.log`. |
| R6-F1 stale-unknown control | CLOSED | Four retained reused results yield zero successful calls and no estimate flag after the unknown result is removed. `mixed_provenance.log`. |
| Legacy schema missing both `llm_cache.call_id` and `run_results.provenance`, opened read-only | PASS | Exact `acb3e09` schema checks confirmed producers, null producers, untracked results, stale references, and an empty ledger. Confirmed results retain USD 0.03 successful spend. Null or absent references use estimated attribution. All cases match parent output. `read_only_matrix.log`. |
| Legacy schema without `run_results` | PASS | Four combinations of retained content/reasons and a zero-ledger case complete. Paid-stage estimates remain explicit. Cases that the parent can aggregate preserve all other fields. `read_only_matrix.log`. |
| Modern schema and mixed per-result attribution | PASS | Modern confirmed, unknown, untracked, stale, reused, and empty-ledger cases pass. Separate content/reasons mixtures classify `[true,false,true,true,false]`, with USD 0.03 successful and USD 0.05 total spend. Removing uncertain results preserves USD 0.01 confirmed spend and clears the estimate flag. `read_only_matrix.log`, `attribution_matrix.log`. |
| Ledger totals, run status, and read-only report generation | PASS within exercised fixtures | Paid matrix cases retain five calls, one cache hit, 0.875 credits, 150 input tokens, 75 output tokens, and USD 0.03. Another run's paid call stays excluded. All 16 CLI executions exit 0. JSON equals `build()` output, Markdown equals its renderer, connections record zero changes, and database file hashes remain identical. `read_only_matrix.log`. |
| Full suite at requested HEAD | PASS | `273 passed in 92.28s (0:01:32)` under the external guard. `suite.log`. |
| Earlier findings and behavior outside the changed code | Not independently re-reviewed | Only R7-F1, R6-F1, and regressions around the changed benchmark behavior receive new independent verdicts here. The full suite covers the repository. |
| Live figures, live service behavior, and billing validity | UNPROVEN | Network and live database access were prohibited. Synthetic fixtures cannot establish these facts. |
| Reviewer-provider separation from all builders | UNPROVEN | This reviewer is Codex/OpenAI. The session does not establish every builder's provider. |

## Verification

I inspected the complete range, previous reports, benchmark callers, and surviving original reproduction scripts. The only production change is the two-line missing-table guard in `src/koc/benchmark.py`. The range also adds the previous review and one regression test. No source fixes, commits, merges, or deployments were attempted.

`read_only_matrix.py` creates databases from the exact `7c76581`, `acb3e09`, and current schema definitions. It closes each fixture before opening it with SQLite `mode=ro`. CLI checks use the real Typer command with only its database path and connection opener patched to those read-only fixtures. No migration runs during verification. Schema assertions prove the legacy columns are absent. Database hashes prove that report generation preserves the files.

Parent comparisons distinguish intended estimate-label changes from regressions. Without `run_results`, HEAD marks every paid LLM stage estimated, including a stage with no retained result. Other fields match the parent whenever the parent completes. Cases with `run_results`, including the schema without provenance, match parent output exactly. The matrix's initial external expectations omitted this metadata difference and an unchanged stale-reference API attribution behavior. The final assertions account for both and verify parent equality. No product finding relies on those initial script mismatches.

All project execution used `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python` through `/tmp/koc-review-r8/run-python`. The runner changes directory to `/tmp/koc-review-r8/work` and sets:

```sh
PYTHONPATH=/tmp/koc-review-r8/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

The external guard blocks socket connections, datagrams, and DNS. Its audit hook blocks repository `data/koc.db` opens and SQLite connections. Its subprocess wrapper preserves the guard when tests replace Python child environments. The permitted selector workaround caps `EpollSelector.select()` waits at 50 ms. `environment.json` verifies the active guard, benchmark import path, disabled bytecode, guarded Python children, and zero socket or DNS attempts.

Commands, with corresponding logs under `/tmp/koc-review-r8/`:

```sh
/tmp/koc-review-r8/run-python /tmp/koc-review-r7/legacy_empty_content.py
/tmp/koc-review-r8/run-python /tmp/koc-review-r6/mixed_provenance.py
/tmp/koc-review-r8/run-python /tmp/koc-review-r8/legacy_empty_content.py
/tmp/koc-review-r8/run-python /tmp/koc-review-r8/legacy_parent_compare.py
/tmp/koc-review-r8/run-python /tmp/koc-review-r8/mixed_provenance.py
/tmp/koc-review-r8/run-python /tmp/koc-review-r8/attribution_matrix.py
/tmp/koc-review-r8/run-python /tmp/koc-review-r8/read_only_matrix.py
/tmp/koc-review-r8/run-python -m pytest -q -p no:cacheprovider --basetemp=/tmp/koc-review-r8/pytest /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

Both unchanged original scripts exit 1 at their obsolete defect assertions, as described above. Every other listed final command exits 0.
