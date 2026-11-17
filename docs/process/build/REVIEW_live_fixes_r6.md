# Independent review: live fixes, round 6

Date: 2026-11-16, Asia/Ho_Chi_Minh. Reviewer: Codex/OpenAI.

Checkout: `/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4`.
Branch: `worktree-agent-a53b8ba5fbb1a25f4`. HEAD: `b81bfca6ecd613570289f4ad4d17a266a57bf534`.
Review range: `4366c34..b81bfca`. Previous report: `docs/process/build/REVIEW_live_fixes_r5.md`.

**Overall: FAIL. R5-F1 is CLOSED. One new P2 benchmark-accounting regression remains OPEN. No P1 finding reported.**

The exact upgraded-run retry now preserves the five successful producers and USD 0.05. Migration preserves existing data and is idempotent. However, one retained result with unknown provenance makes the benchmark discard verified attribution for every result in that stage. A mixed legacy/current-cache reproduction then counts a known failed call as successful, even though the selected result records confirmed reuse from another run.

The full suite passes: **271 passed in 89.78s (0:01:29)**. The independent mixed-provenance reproduction exposes the regression despite that result.

No source files changed. This report is the only repository file created during this review. Scripts, synthetic databases, and logs are under `/tmp/koc-review-r6/`. All project execution used an external socket-blocking `sitecustomize.py`. I never opened or copied the repository's `data/koc.db`. The guard logged zero socket or DNS attempts.

## Findings

### R6-F1. P2: One unknown producer causes the benchmark to count a known failed call for a reused result

Location: `src/koc/benchmark.py:66`, through the stage-wide producer fallback at `src/koc/benchmark.py:95` and `src/koc/benchmark.py:108`.

The new `_exact()` condition returns false for the entire stage when any retained subject has unknown provenance. `_classify_llm()` consequently ignores all recorded producer identities in that stage. Its hash/prompt/model heuristic can then classify a failed call as successful for a different subject whose provenance is explicitly `reused`.

Executed reproduction:

1. Create an on-disk database through the exact `acb3e09` DB helpers and cache writer. Generate a valid c4 reason through the old production `_s4()`, without invoking its final write callback. This models interruption after cache persistence and before result commitment. The cache has one entry and `run_results` has zero rows.
2. Close the database, reopen it with current code, and run `init_db()` twice. The c4 cache producer correctly remains unknown.
3. Create runs B and A with the same five candidates. A makes two paid calls for c0, an original and a repair. Both return an invalid creator ID and fail validation. Neither produces a recommendation.
4. Execute B with valid responses. B pays for c0 through c3 and reuses the legacy c4 cache entry.
5. Resume A through real `resume(cache_only=True)`. A selects all five cached recommendations without another provider call. A records `reused` with null call IDs for c0 through c3, and `unknown` for c4.
6. Aggregate the same database with the previous `4366c34` benchmark module and the current benchmark module.

```text
                                            4366c34       b81bfca
A status                                    done          done
A retained recommendations                  5             5
A S4 paid calls / total USD                  2 / 0.02      2 / 0.02
A original c0 call classified successful     false         true
A failed repair classified successful       false         false
A S4 successful calls                       0             1
A S4 successful input/output tokens         0 / 0         50 / 50
A S4 successful USD                         0.00          0.01
A S4 cache hits                             5             5
success_estimated                           false         true
new provider calls during A resume          0             0
```

A never paid for the unknown c4 result. Its only paid calls are the two failed c0 attempts, and c0's selected result explicitly records reuse. Therefore A's successful spend is known to be zero. The estimated-stage label does not justify overriding that verified exclusion. Total spend remains correct, but successful totals, per-candidate costs, and waste are wrong.

As a control, remove only c4's retained recommendation while leaving its stale unknown reference. Current code returns to zero successful calls and `success_estimated=false`. This isolates the regression to the new unknown-producer condition. The original all-known cross-run-cache reproduction still passes.

Fix: preserve confirmed producer attribution and confirmed cross-run exclusions when a stage contains unknown subjects. Restrict the heuristic to subjects whose producers cannot be verified. Keep the stage's estimated label whenever that restricted heuristic is needed.

Evidence: `/tmp/koc-review-r6/mixed_provenance.py` and `mixed_provenance.log`. The script reproduces the same result on two executions. It asserts the observed defect, so its exit code is not a product PASS verdict. Only provider responses are synthetic. Recommendation generation, validation, cache keys, migration, selection, resume, ledger writes, and aggregation use production code.

## Per-item verdicts

| Item | Verdict | Executed evidence |
| --- | --- | --- |
| R5-F1 P2: upgraded cache loses same-run producer attribution on retry | CLOSED | The original `acb3e09` database and supported retry retain identical recommendation content, producer IDs 1 through 5, five successful calls, 250 input tokens, 250 output tokens, and USD 0.05. No new provider calls. `success_estimated=false`. Both baseline and upgrade agree. `upgrade_accounting.log`. |
| Existing-database migration preserves data | PASS | The exact old database preserves all original field values in 80 rows across 13 tables after two initializations. A separate 83-row fixture also preserves every original field after backfill. New columns are checked separately. `upgrade_accounting.log`, `migration_safety.log`. |
| Migration idempotence | PASS | In the 83-row fixture, the complete snapshot after the second initialization equals the first, including new producer and provenance columns. Existing non-null producers remain unchanged. `migration_safety.log`. |
| No last-paid-row-by-hash inference in migration | PASS for executed probes | A later unselected paid call has the same hash as a retained cache entry. Migration selects its recorded producer, call 3, rather than later call 6. An unreferenced cache entry remains null despite matching paid call 7. `migration_safety.log`. |
| Unknown legacy producers use estimated accounting | PASS in isolation | Delete producer references from an independent old-schema fixture, migrate twice, and execute the real retry. All five selected rows become `unknown`. The same recommendations retain five estimated successful calls, 250 input/output tokens each, and USD 0.05. Only S4 is labelled estimated. No new paid calls. `unknown_retry.log`. |
| Confirmed cross-run reuse excludes failed calls | PASS when every retained producer is known | The original R4-F1 reproduction keeps both failed calls out of success, with five cache hits and USD 0.02 total spend. `new_regressions.log`. The mixed-provenance variant fails separately under R6-F1. |
| R6-F1 P2: mixed unknown/reused provenance overrides known exclusions | OPEN | Four `reused` rows and one `unknown` row cause a failed original call to count as one successful call and USD 0.01. Previous benchmark code reports zero on the same database. `mixed_provenance.log`. |
| Interrupted retry invalidates discarded S4 attribution | PASS | Real cache-only S3 blocking leaves zero recommendations, S4 scores, and reason references. Successful S4 spend is zero. Total S4 spend remains USD 0.05. `new_regressions.log`. |
| Retry transaction preserves data on failure | PASS | A SQLite trigger aborts S4-score deletion. Recommendations, references, scores, tasks, run state, and the LLM ledger all match their original snapshots. `accounting_safety.log`. |
| Benchmark excludes stale result subjects | PASS for executed exact-attribution probes | Four retained reasons count four producers despite a fifth stale reference. One retained content result counts one call and USD 0.01 despite a second stale reference. Total content spend remains two calls and USD 0.02. A stale unknown reference alone does not trigger fallback. `accounting_safety.log`, `mixed_provenance.log`. |
| Read-only benchmark handles the previous schema | PASS | Aggregation opens the original synthetic `acb3e09` database read-only, without migration. It reports five successful calls and USD 0.05, with zero database changes. `migration_safety.log`. |
| Full suite at requested HEAD | PASS | `271 passed in 89.78s (0:01:29)` under the external network/database guard. `suite.log`. This includes existing benchmark, migration, provenance, cache-only, and prior-finding tests. |
| Prior behavior outside the changed code | Not independently re-reviewed | The requested regression search covers migration, producer selection, and benchmark accounting. The full suite ran across the repository. Earlier report verdicts are not claimed as new independent reproductions. |
| Live figures match live DB; live service/model/billing validity | UNPROVEN | Network and live database access were prohibited. Synthetic execution cannot establish these facts. |
| Reviewer-provider separation from all builders | UNPROVEN | This reviewer is Codex/OpenAI. The session does not establish every builder's provider. |

## Verification

I inspected all four changed files and the previous report. Regression searches stayed within the changed migration, producer/provenance, and benchmark behavior. No source fixes, commits, merges, or deployments were attempted. P2 grading applies to the executed incorrect benchmark totals, not style or semantic wording.

`upgrade_accounting.py` reuses the exact round-5 reproduction from `/tmp/koc-review-r5/`. The old fixture generation, provider responses, candidates, baseline pipeline, and retry remain intact. The adaptation changes the current revision label, accepts the added provenance column during preservation comparisons, and expects the repaired USD 0.05 outcome. Additional assertions check calls, tokens, producer IDs, and the absence of an estimated label.

`new_regressions.py` and `accounting_safety.py` are copies of the round-5 scripts with their external working paths updated. The former retains its old hardcoded `pipeline_revision` output label; its imported production pipeline is this checkout at `b81bfca`, not `4366c34`.

All project execution used `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python` through `/tmp/koc-review-r6/run-python`. The runner changes directory to `/tmp/koc-review-r6/work` and sets:

```sh
PYTHONPATH=/tmp/koc-review-r6/guard:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/src:/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4
PYTHONDONTWRITEBYTECODE=1
```

The external guard blocks socket connections, datagrams, and DNS. Its audit hook blocks repository `data/koc.db` opens and SQLite connections. Its subprocess wrapper preserves the guard in Python child environments. The permitted selector workaround caps `EpollSelector.select()` waits at 50 ms. No guard-attempt log was created because no socket or DNS operation was attempted.

Commands, with corresponding logs under `/tmp/koc-review-r6/`:

```sh
/tmp/koc-review-r6/run-python /tmp/koc-review-r6/upgrade_accounting.py
/tmp/koc-review-r6/run-python /tmp/koc-review-r6/new_regressions.py
/tmp/koc-review-r6/run-python /tmp/koc-review-r6/accounting_safety.py
/tmp/koc-review-r6/run-python /tmp/koc-review-r6/migration_safety.py
/tmp/koc-review-r6/run-python /tmp/koc-review-r6/unknown_retry.py
/tmp/koc-review-r6/run-python /tmp/koc-review-r6/mixed_provenance.py
/tmp/koc-review-r6/run-python -m pytest -q -p no:cacheprovider --basetemp=/tmp/koc-review-r6/pytest /home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a53b8ba5fbb1a25f4/tests
```

Every command completed with exit code 0 and its observation assertions satisfied. R6-F1 remains an observed product defect. `docs/process/build/REVIEW_live_fixes_r5.md` was already untracked before this review and was not modified.
