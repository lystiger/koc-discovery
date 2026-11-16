Overall PASS

Independent review of `eaecd19..163dc62bd2c03eb363e190470cb6e58c12b5f8d2`, branch `worktree-agent-a582e8a6d3444ed53`, 2026-11-16. F1, F2, F3, and F4 are CLOSED. No P1 or P2 finding remains open. One P3 test-isolation finding remains open. Source and tests were not modified.

## Findings

### F1 — P2, CLOSED: Missing brand-fit evidence is treated as eligibility

Locations: `src/koc/stages.py:177`, `src/koc/web/matching_api.py:171`.

The gate now requires a score at or above the configured minimum. Missing evidence returns `eligible=false`, `max_brand_fit=null`, and a Vietnamese exclusion reason.

Reran both original reproductions against the fresh backup and disposable derivatives:

1. The unchanged-backup request for creator **6585480482359263234**, exactly **30,800 followers**, count 1, budget **3,000,000 VND**, gender `Tất cả`, age groups `["18-24"]`, and `avoid_same_mcn=true` returns `status="refused"` with no picks. This creator still has no analyses.
2. The inserted S1-only creator `review_s1_only`, at exactly **10,001 followers**, is rejected by the shared gate and by `POST /api/campaigns`. The endpoint returns HTTP 200, `status="refused"`, no picks, and zero booking cost. The exclusion list contains the creator.
3. The original count-2 request has no maximum-count, minimum-budget, or cheaper-band option. A further derivative removes all five passing S1 candidates. The S1-only creator cannot produce any option or cheaper-band offer by itself.

The original wider cheaper-band probe still finds the 10,000–49,999 band at **3,000,000 VND** because genuine passing creators occupy that band. This result is valid. The isolated no-evidence probe distinguishes that result from the former bypass.

Evidence: `/tmp/koc-brand-fit-review-r2/checks.py`, `checks.log`, `endpoints.py`, `endpoints.log`.

### F2 — P2, CLOSED: Missing or null S3 bypasses a failing gate

Locations: `src/koc/stages.py:185`, `src/koc/web/matching_api.py:171`, `src/koc/web/matching_api.py:298`.

The web now enumerates exclusions over S1, the same candidate set used by its pool.

Reran all three original variants for **7234931025289217051**. A later completed run with only S1, the original run with a NULL S3 score, and the original run with S3 deleted all retain a failing maximum brand fit of **2**. Every request refuses the isolated creator, returns no picks, and includes the creator in `brand_fit_excluded`.

Positive controls still pass. The scored-only pool contains five passing creators. Requesting six offers five for **28,500,000 VND** and no six-person minimum budget. At a **6,000,000 VND** budget, the cheaper band supports two creators for **6,000,000 VND**, but cannot support three.

Evidence: `/tmp/koc-brand-fit-review-r2/checks.log`, `additional.py`, `additional.log`.

### F3 — P2, CLOSED: Stored proposals bypass eligibility, and an S4 rewrite retains excluded recommendations

Locations: `src/koc/queries.py:16`, `src/koc/pipeline.py:413`, `src/koc/pipeline.py:417`.

`queries.top5` now applies the real gate before its count limit. On the unchanged backup, the stored proposal returns only the three passing incumbents. Neither **7234931025289217051** nor **7450735628620760071** appears as a recommended pick or card. Both the proposal API and run page return HTTP 200. The run page still lists excluded creators as unselected finalists and explains their exclusion.

Reran the real `_s4` writer without deleting recommendations first. The probe uses the three genuine reason-cache hits and offline zero-cost responses for the two misses. The committed selection contains exactly **five recommendation rows**, totaling **28,500,000 VND**, matching the stored S4 total. The S4 score rows and selected reason references contain exactly those same five IDs.

Additional atomicity checks use the production `db.complete_task` boundary at `src/koc/db.py:97`:

1. A SQLite trigger aborts insertion of the first replacement, after earlier writes and deletions have occurred. Rollback restores recommendations, scores, selected results, run parameters, and task state exactly.
2. During a successful writer invocation, a second read-only connection sees the complete old state until commit. After commit, both connections see the complete new state.
3. The rewritten proposal API, run adapter, and parsed HTML recommendation cards contain exactly the five passing IDs. The API total is **28,500,000 VND**.
4. Removing all analyses for a stored passing pick makes the real gate reject it. Queries, the proposal endpoint, and run cards all stop recommending that pick.

Evidence: `/tmp/koc-brand-fit-review-r2/s4_commit.py`, `s4_commit.log`, `atomic.py`, `atomic.log`, `run-after.html`.

### F4 — P3, CLOSED: The new exclusion section never receives its data

Location: `src/koc/web/adapter.py:234`.

The adapter now supplies `brand_fit_excluded`. The unchanged-backup run page returns HTTP 200 and contains `aria-label="KOC bị loại"`. Its adapter data contains the four scored exclusions and their Vietnamese reasons.

Evidence: `/tmp/koc-brand-fit-review-r2/checks.log`, `endpoints.log`.

### F5 — P3, OPEN: The global autouse fixture weakens test isolation

Location: `tests/conftest.py:63`.

Verdict: **P3, acceptable for this review's correctness gate, with test-isolation debt**. The fixture changes production eligibility behavior in every test except `tests/core/test_brand_fit_gate.py`. Broad-suite success therefore does not prove that all tests use the real gate.

An external pytest plugin disabled only `lenient_brand_fit_gate`, without modifying repository files. The suite then reported **399 passed, 30 failed, 1 skipped**. The failures depend on synthetic creators with S3 scores or stored recommendations but no qualifying analysed videos. Examples include `tests/web/test_matching_api.py:20` and `tests/core/test_audience_placeholder.py:11`. Rejecting those creators is the intended D-B7 behavior. Those failures do not establish a production correctness defect.

The fixture still evaluates the real gate first and changes only results with `max_brand_fit=None`. It does not conceal the scored low-fit cases covered by the gate module. That module exercises actual analysed mock runs, selection, web exclusion, refusal, S4 replacement, and stored readback under the real gate. The independent probes above also exercise real-data endpoints and missing-evidence readback without the fixture.

To check the remaining interaction directly, `strict_paths.py` runs production S4 scheduling with a scored creator that has no analyses. The run blocks without a crash, recommendation, or LLM call. A complete six-creator mock run supplies qualifying analysis records, returns six passing picks and cards, and survives a cache-only retry without new non-cache LLM calls or extra recommendation rows.

No production failure hidden by this fixture was demonstrated in the changed paths. Prefer explicit qualifying analysis records in synthetic fixtures, or a narrowly requested fixture, over the global override. The 30 failures remain a limit on interpreting the normal suite, not a claim that the strict suite passes.

Evidence: `/tmp/koc-brand-fit-review-r2/real_gate_plugin.py`, `strict-suite.log`, `strict_paths.py`, `strict_paths.log`; `tests/core/test_brand_fit_gate.py:111`, `tests/core/test_brand_fit_gate.py:146`, `tests/core/test_brand_fit_gate.py:159`.

## Acceptance checks

| Check | Result | Evidence |
| --- | --- | --- |
| All previous repros | PASS | Rebuilt all four surviving scripts with assertions for the corrected behavior. F1–F4 are CLOSED. |
| Exact real-run selection and costs | PASS | `_best_five` returns the ordered IDs and total below. |
| Atomic S4 replacement | PASS | Five rows after offline rewrite. Injected failure rolls back the whole commit. A second connection observes no partial selection. |
| Stored proposal and run view | PASS | Three eligible incumbents before rewrite, five eligible picks after rewrite. Missing-evidence readback is also rejected. |
| Web pool | PASS | Five creators, all passing the real gate, with no unanalysed creator. |
| Refusal options and cheaper bands | PASS | Five-person maximum at 28.5M, no six-person minimum, two-person cheaper band at 6M, no three-person group at 6M. |
| Run-selected analyses | PASS | Added newer high-fit rows under a different prompt and model for the low-fit creator's three selected videos. Maximum remains 2. |
| Existing reason-cache keys | PASS | The three surviving keys remain identical to the prior comparison baseline and validate as genuine cache hits. Only the two replacement IDs miss. |
| Mock pipeline, count, and retry | PASS | Gate module runs without the lenient fixture. Independent six-person cache-only retry adds no non-cache calls. |
| Autouse fixture | P3 | Test-isolation debt. No demonstrated production correctness defect in the changed paths. |
| Full requested suite | PASS with stated isolation limits | 429 passed, 1 skipped. Network guard and external selector workaround enabled. |

Run `7372009b22764b339fbcf0f3efb4bc4e`, `_best_five` in rank order:

| Creator | Cost, VND |
| --- | ---: |
| 7485602050560148487 | 3,000,000 |
| 7594293671543079957 | 7,500,000 |
| 6730533371858437121 | 7,500,000 |
| 7164572563820250139 | 3,000,000 |
| 6872721641991209985 | 7,500,000 |
| **Total** | **28,500,000** |

The four scored exclusions remain **6976265099049305089**, **7234931025289217051**, **7288941699803694098**, and **7450735628620760071**. Each has maximum brand fit **2** and reason `Loại vì video không hợp sản phẩm: brand_fit cao nhất 2/5 (cần ít nhất 3/5).`

Surviving reason-cache keys remain present and valid:

```text
7485602050560148487 e93503a460184c2f71cf7f1e6c30dacab47065d8c236f181587ee764ae154bc2
7594293671543079957 a7b68e267d61b641f5a167352922fe0537613ae1d3eecc15f3536dea9e07ad0c
6730533371858437121 599fb64a39c635111c28c4d90da35be610e62d01a6640b8fcb8aceb71c8b6b15
```

## Execution and isolation

The original database was accessed only through:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-brand-fit-review-r2/koc.db'
```

The backup was made filesystem read-only. Probes opened it with SQLite `mode=ro`; mutations used memory or separate disposable databases. Its SHA-256 remained `a8a4f7c10ba666f21ebe544e582fe663466bcadc82d28461ba6a407d9fc07a76`. The read-only probe recorded zero changes.

All project Python commands loaded `/tmp/koc-brand-fit-review-r2/sitecustomize.py`. The guard blocks network connections, datagram sends, and DNS, propagates into child processes, and rejects Python SQLite access to the original database. Parent, DNS, and replacement-environment child probes passed. No network or paid API calls were made.

Full suite command:

```bash
KOC_REVIEW_POLL_LOOP=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:/tmp/koc-brand-fit-review-r2 \
PYTEST_ADDOPTS='-p no:cacheprovider --basetemp=/tmp/koc-brand-fit-review-r2/full-suite' \
/home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

Result: **429 passed, 1 skipped in 90.46s**. Log: `/tmp/koc-brand-fit-review-r2/full-suite.log`.

The optional production-copy test was also enabled on the untouched backup. It fails at `tests/web/test_api.py:259`, expecting five picks where the strict gate correctly returns three surviving incumbents. After the simulated offline rewrite, the same test passes with the lenient fixture disabled: **1 passed in 7.39s**. This distinction matters because serving old rejected picks would make that untouched-backup assertion pass incorrectly. Logs: `real-copy-test.log`, `rewritten-copy-test.log`.

The strict-suite audit adds `-p real_gate_plugin` and uses a separate `/tmp` base directory. Result: **30 failed, 399 passed, 1 skipped in 89.15s**. F5 explains the synthetic-data failures. The ordinary suite's pass is not a strict-suite pass.

The external, opt-in selector workaround from round 1 caps selector waits at 10 ms. A fresh endpoint test without that workaround timed out after 15 seconds with exit 124. Full-suite completion with unmodified scheduling remains **UNPROVEN** in this sandbox. Logs: `native-scheduling.log`, `full-suite.log`. No source or test scheduling code was changed.

Rerun individual probes with the guarded `PYTHONPATH` above, replacing `-m pytest -q tests` with `/tmp/koc-brand-fit-review-r2/checks.py`, `additional.py`, `endpoints.py`, `s4_commit.py`, `atomic.py`, or `strict_paths.py`. The last probe changes its working directory, so it requires an absolute repository `src` entry in `PYTHONPATH`. Use fresh disposable derivative paths for repeat runs.

Only repository artifact created by this review: `docs/build/REVIEW_brand_fit_gate_r2.md`.
