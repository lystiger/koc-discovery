Overall FAIL

Independent review of `d5da7c3..eaecd19177a01cdda0a14933e761a37a38b138c2`, branch `worktree-agent-a582e8a6d3444ed53`, 2026-11-16. Three P2 correctness findings and one P3 presentation finding. No source changes.

## Findings

### F1 — P2: Missing brand-fit evidence is treated as eligibility

Locations: `src/koc/stages.py:177`, `src/koc/web/matching_api.py:171`.

D-B7 says **only if at least one run-selected analysed video has brand_fit >= 3**. Zero analysed videos cannot satisfy that condition. The builder's assumption contradicts D-B7. `best is None or best >= minimum` explicitly admits missing evidence, and the web can recommend these creators. They also enter refusal options and cheaper follower bands without an exclusion reason. S4 skipping creators without S3 does not protect the web pool.

Reproduction on the unchanged read-only backup, run `7372009b22764b339fbcf0f3efb4bc4e`:

1. Use product `Chống nắng`, count 1, budget 3,000,000 VND, follower range **30,800–30,800**, gender `Tất cả`, age groups `["18-24"]`, and `avoid_same_mcn=true`.
2. Call `result_for_campaign(conn, campaign, load_config()["rate_card"]["tiers"])`.
3. Observe `status="ok"`, creator **6585480482359263234**, and total **3,000,000 VND**. `db.run_analyses(conn, run_id, creator_id)` returns `[]`.

The real pool contains 56 creators, including **51 with no analyses**. A separate disposable-copy endpoint repro inserts only S1 for `review_s1_only`, at 10,001 followers. `POST /api/campaigns` selecting that exact follower count returns HTTP 200, `status="ok"`, and that creator. `brand_fit_gate` returns `eligible=true`, `max_brand_fit=null`, `reason_vi=null`. Requesting two creators advertises one for 3,000,000 VND; `_cheaper_band` also advertises that creator's band.

Fix: require a qualifying score, reject missing evidence with a reason, and apply that eligibility rule to every web candidate.

Evidence: `/tmp/koc-brand-fit-review/checks.py`, `checks.log`, `endpoints.py`, `endpoints.log`.

### F2 — P2: Missing or null S3 bypasses a failing gate

Locations: `src/koc/stages.py:186`, `src/koc/web/matching_api.py:171`.

`excluded_brand_fit` checks only creators with a non-null S3 score. The web starts from S1, so its candidate set is wider. A creator can have `brand_fit_gate(...)["eligible"] == false` and still be recommended because it is absent from the exclusion set. Fixing F1 alone leaves this bypass.

Reproduction, using an in-memory derivative of the backup:

1. Create a later completed `Chống nắng` run and add S1 for creator **7234931025289217051**, without S3. Its videos and low-fit analyses already exist from the earlier run.
2. Confirm `brand_fit_gate` returns `eligible=false`, `max_brand_fit=2` for the later run, using `db.run_analyses`' existing historical fallback.
3. Request count 1 with sufficient budget and follower range 0–1,000,000,000.
4. Observe `status="ok"`, `picked=[7234931025289217051]`, and `brand_fit_excluded=[]`.

A second repro sets that creator's S3 score to NULL in the copied original run, preserving its run-selected analyses. The shared gate returns false, but a request isolating its follower count still picks it. Deleting the S3 score produces the same result.

Fix: evaluate the shared gate over the S1 candidate set used by the web, rather than restricting exclusion enumeration to scored S3 creators. Keep S4's separate requirement for an S3 score.

Evidence: `/tmp/koc-brand-fit-review/additional.py`, `additional.log`, `checks.py`, `checks.log`.

### F3 — P2: Stored proposals bypass eligibility, and an S4 rewrite retains excluded recommendations

Locations: `src/koc/web/adapter.py:142`, `src/koc/pipeline.py:413`, `src/koc/pipeline.py:416`; readback at `src/koc/queries.py:13`.

The matching pool is filtered, but stored proposals read `recommendations` without applying the gate. Existing completed runs therefore continue recommending excluded creators. The S4 writer deletes selected reason references but only upserts recommendation rows; displaced creators remain in the table after reselection.

Reproduction on a disposable backup derivative:

1. `GET /api/runs/7372009b22764b339fbcf0f3efb4bc4e/proposal` returns HTTP 200 with **7234931025289217051** and **7450735628620760071** still in `picks`. Both fail the shared gate at maximum brand fit 2. `GET /runs/<run_id>` also displays the old recommendation cards.
2. Invoke the real `_s4(conn, run_id)` and its returned writer. Intercept `_cached_call` only to use the three genuine cache hits and supply offline zero-cost recommendations for the two misses; do not clear recommendations beforehand.
3. Observe **seven recommendation rows**, totaling **39,000,000 VND**, while stored S4 parameters report **28,500,000 VND**. `queries.top5` still includes excluded creator **7234931025289217051**, and omits an eligible replacement.

The new test `tests/core/test_brand_fit_gate.py:83` explicitly deletes recommendations before exercising the writer, hiding this retained-row behavior.

Fix: replace the run's recommendation selection atomically when committing S4, and enforce eligibility when serving stored proposals so existing completed runs cannot expose failing picks.

Evidence: `/tmp/koc-brand-fit-review/endpoints.py`, `endpoints.log`, `s4_commit.py`, `s4_commit.log`.

### F4 — P3: The new exclusion section never receives its data

Locations: `src/koc/web/templates/top5.html:14`, `src/koc/web/adapter.py:227`.

The template reads `top5_data.brand_fit_excluded`, but `get_top5_with_details` never adds that key. Its new `excluded_brand_fit` import is unused. The copied run has four excluded creators with reasons, yet `GET /runs/<run_id>` returns HTTP 200 without the `aria-label="KOC bị loại"` section.

Fix: populate the template's exclusion data from the shared function. This presentation defect is P3 under the requested grading; F3 separately covers incorrect picks.

Evidence: `/tmp/koc-brand-fit-review/endpoints.log`, `REAL_ADAPTER_EXCLUDED_KEY False` in `checks.log`.

## Acceptance checks

| Check | Result | Evidence |
| --- | --- | --- |
| Run-selected analyses, not stale prompt versions | PASS for the exercised run | Added newer high-fit rows under another prompt/model for all three selected videos of creator 7234931025289217051. Gate remained excluded at maximum 2. `stages.py:173` calls `db.run_analyses`; the existing helper's historical fallback is unchanged. |
| S4 selection and three blocked options | PASS for creators with scored analyses | `_best_five` matches the exact selection below. Intercepted `s4_options` inputs contain only five eligible creators, with costs 3M, 3M, 7.5M, 7.5M, 7.5M. Requesting six offers five for 28.5M, no six-person minimum, and the 10k–50k band. Blocked text counts four exclusions. Persisted readback fails separately in F3. |
| Web pool, refusal options, `_cheaper_band` | FAIL | F1 and F2 bypass eligibility. Positive control restricted to non-null S3 creators has exactly five eligible candidates. A six-person request offers five for 28.5M and no minimum for six. At a 6M budget, a cheaper-band request for three is unavailable; two cost 6M. |
| Mock runs | PASS | Full suite includes all seven new gate tests and existing mock pipeline, count/budget, cache-only, and smoke coverage. |
| Requested real-run IDs, costs, and exclusion reasons | PASS | Exact results below; `checks.py` assertions pass. |
| Existing S4 reason cache keys | PASS | Baseline and HEAD produce identical keys for the three survivors. Real cache validation and cache-only loading succeed. Exactly two new selection keys miss. No paid calls made. |
| Exclusion reasons on server-rendered proposal page | FAIL | F4. CLI/report use of the shared exclusion list does not repair the missing template data. |

Run `7372009b22764b339fbcf0f3efb4bc4e`, `_best_five` in rank order:

| Creator | Cost, VND |
| --- | ---: |
| 7485602050560148487 | 3,000,000 |
| 7594293671543079957 | 7,500,000 |
| 6730533371858437121 | 7,500,000 |
| 7164572563820250139 | 3,000,000 |
| 6872721641991209985 | 7,500,000 |
| **Total** | **28,500,000** |

Excluded IDs: **6976265099049305089**, **7234931025289217051**, **7288941699803694098**, **7450735628620760071**. Each has maximum brand fit **2** and reason `Loại vì video không hợp sản phẩm: brand_fit cao nhất 2/5 (cần ít nhất 3/5).`

Surviving reason cache keys, identical at baseline and HEAD, present and valid:

```text
7485602050560148487 e93503a460184c2f71cf7f1e6c30dacab47065d8c236f181587ee764ae154bc2
7594293671543079957 a7b68e267d61b641f5a167352922fe0537613ae1d3eecc15f3536dea9e07ad0c
6730533371858437121 599fb64a39c635111c28c4d90da35be610e62d01a6640b8fcb8aceb71c8b6b15
```

Only 7164572563820250139 and 6872721641991209985 need new reason generations. This cache result does not resolve F3's retained recommendation rows.

## Execution and isolation

The original database was accessed only through:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-brand-fit-review/koc.db'
```

The backup was opened using SQLite `mode=ro`, then made filesystem read-only. Mutations used in-memory derivatives or a separate disposable database. Backup SHA-256 remained `a8a4f7c10ba666f21ebe544e582fe663466bcadc82d28461ba6a407d9fc07a76`; read-only probes recorded zero changes.

All project Python commands loaded `/tmp/koc-brand-fit-review/sitecustomize.py`, which blocks network connections, datagram sends, and DNS. Child processes retain the guard even when replacing their environment. Parent, DNS, and child guard probes passed. The guard also rejects Python SQLite access to the original database. No network or paid API calls were made.

Full suite command:

```bash
KOC_REVIEW_POLL_LOOP=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:/tmp/koc-brand-fit-review \
PYTEST_ADDOPTS='-p no:cacheprovider --basetemp=/tmp/koc-brand-fit-review/full-suite' \
/home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

Result: **424 passed, 1 skipped in 90.61s**. The skipped optional production-copy test was then explicitly enabled with `KOC_REAL_RUN_COPY=/tmp/koc-brand-fit-review/koc.db` and rerun: **1 passed in 6.89s**. Logs: `full-suite.log`, `real-copy-test.log`.

The initial unmodified-scheduling suite stalled after 45 tests at the first TestClient request. A bounded reproduction captured the caller waiting in AnyIO and its event-loop thread waiting in `selectors.select`. Previous reviews document the same sandbox behavior. The external, opt-in workaround caps selector waits at 10 ms; source and tests remain unchanged. Full-suite completion without that scheduling workaround is **UNPROVEN** in this sandbox, not a demonstrated product regression. Diagnostic log: `hang.log`.

Rerun independent probes with the same guarded `PYTHONPATH`, replacing `-m pytest -q tests` with `/tmp/koc-brand-fit-review/checks.py`, `additional.py`, `endpoints.py`, or `s4_commit.py`. Endpoint probes also require `KOC_REVIEW_POLL_LOOP=1`.

Only repository artifact created by this review: `docs/build/REVIEW_brand_fit_gate.md`.
