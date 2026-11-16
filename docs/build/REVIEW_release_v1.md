Overall: FAIL

# Independent final release gate: v1.0

Reviewed detached HEAD `0b2c417c780344bb6bef65c5883d026920d41c5e` on 2026-11-16. This is a release gate, not another review of the previously reviewed diffs. One P2 blocks release: submission documents incorrectly describe uncached calls as paid calls. The recorded credits, tokens, USD, selected creators, and booking total otherwise agree with the live database.

Scope: external `SPEC.md` C1-C11, `CONTRACTS.md`, and `brief.md`, including D-B1 through D-B7 and the v1/v2 release plan. The release plan explicitly defers the full dry-run estimate and the web exclusion note to v2. C9 uses `docs/build/VERDICT_integration.md` as requested.

## Criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| C1: offline test suite | PASS | Full suite: **429 passed, 1 skipped in 91.44s**. The skipped real-copy test was then enabled against this review's backup: **1 passed in 7.18s**. Commands and the sandbox scheduling accommodation appear below. No application or test source was changed. |
| C2: dry-run plan, no network or writes | PASS, v1 scope | `koc run --dry-run` exited 0 under the socket blocker, printed the plan and 28.2 projected credits. A nonexistent `KOC_DB` remained absent. It prints zero dry-run tokens rather than a future token estimate, and incorrectly says S2 retains 15; the release plan explicitly defers both corrections. Literal original C2 token projection is therefore not delivered, rather than independently verified. `src/koc/cli.py:50`, `README.md:132`. |
| C3: live five-KOC result | PASS | Read-only backup of run `7372009b22764b339fbcf0f3efb4bc4e`: status `done`, exactly five recommendations, **28,500,000 VND**, 1,500,000 VND unused. All reasons were read and are Vietnamese, with 3-4 reasons per creator. **41/41 cited IDs** resolve through that creator's `db.run_analyses` evidence or `metrics` rows. All five pass the real `koc.stages.brand_fit_gate`, with maximum brand_fit scores **4, 4, 3, 3, 3**. See result table below and `src/koc/stages.py:164`. |
| C4: call ledger | PASS | Live-run `api_calls`: **243 rows**, 28 cache hits, **27.6 credits**. `llm_calls`: **97 rows**, 5 cache hits, **1,016,946 input / 149,736 output tokens**, **1.324219 USD**. Endpoint/model, cache flag, latency and cost/token columns exist; no live LLM row has an empty model, prompt version or request hash. Schema and writers: `src/koc/db.py:18`, `src/koc/db.py:176`, `src/koc/budget_guard.py:26`. API requests reserve a ledger row before transport at `src/koc/kalodata.py:49`. These are recorded ledger values, not an independent provider billing reconciliation. |
| C5: SIGKILL and resume | PASS | Ran `scripts/kill_resume_test.sh` offline with the external guarded Python wrapper. Exit 0: **`SIGKILL + resume: S1b PASS`**, **`SIGKILL + resume: S3 PASS`**. Script assertions cover duplicate result/task rows, repeated uncached request hashes, completion and zero-credit/zero-token finished resume. This is the requested mock kill-boundary test; it does not prove arbitrary live in-flight request exactly-once delivery. |
| C6: finished-run cache replay | PASS | Fresh derivative of the backup, actual pipeline, `cache_only=True`, no mock provider. Applied only the documented manual S3 skip for **7471573167103378440**. Replay `19d5fe65a0974cb2b329b251fd09fe78` finished `done`: **142/142 API cache hits, 32/32 LLM cache hits, 0 credits, 0 input tokens, 0 output tokens, 0 USD**, identical ordered creator IDs, ranks and booking prices. Before that skip, only that creator's S3 task was blocked by a content cache miss. |
| C7: hard caps | PASS | Full suite includes `tests/core/test_kalodata.py:21` refusal-before-transport and `tests/core/test_budget_guard.py:10` cumulative LLM budget checks. Configured credit cap is **60**, stricter than SPEC's 100; LLM cap is **5 USD**. Code: `src/koc/kalodata.py:49`, `src/koc/budget_guard.py:17`; config: `config/kalodata_prices.yaml:6`, `config/llm_caps.yaml:1`. |
| C8: benchmark and scaling | FAIL | JSON and Vietnamese Markdown exist, with per-stage times, costs, tokens, a five-KOC live run, explicitly mocked 50-candidate run and projections to 500. Recomputed live-run totals, funnel, calibration and projections agree. Fresh offline 50-candidate mock also completed with five picks and zero spend. However, **`docs/BENCHMARK.md:15` falsely labels 195/307 calls as paid**; F1 below. |
| C9: UI | PASS | Requested replacement audit `docs/build/VERDICT_integration.md:9` records 375/1440 screenshots, no horizontal overflow, zero serious/critical axe findings, citation anchors and frame fetches. Independently checked the current five-pick proposal API, all five creator APIs, legacy result/detail/dashboard pages, and **54 referenced frame files**. All checked routes returned 200. Enabled `test_real_run_copy_proposal_totals_and_evidence` on this backup: **1 passed**, including its frame URL checks. Inspected the two committed app screenshots in `docs/pitch/assets/`; displayed budget, followers and current creator agree with the backup. Fresh browser layout/a11y testing on this HEAD was not repeated; the responsive proof is the accepted integration audit, not a claim of new screenshots. |
| C10: Vietnamese architecture, README and submission claims | FAIL | Vietnamese README and architecture exist; Mermaid, setup/run commands, limits, extensions and explicitly unimplemented offline Whisper option via `openaipublic.azureedge.net` are present. Supported CLI checks below exited 0. Numeric and AI-description checks largely agree, but **`README.md:121` and `docs/pitch/index.html:729` repeat the false paid-call count**; F1. |
| C11: history secrets and creator contacts | PASS | Scanned **all refs and reflogs**, not just HEAD: **231 commit objects, 1,156 trees, 1,269 blobs**. Searched blob/commit contents for `sk-...` and KALODATA/OPENROUTER/GEMINI assignments. All 226 candidates were test dummy literals or source/document expressions; **no credential found**. Recursively inspected JSON values in every TEXT column of every table in the untouched backup for creator-contact/email/phone/telephone/WhatsApp/WeChat/Zalo/contact keys: **zero contact fields**. Storage strips `creator_contact_*` recursively at `src/koc/db.py:254`. No actual key values are included in this report. |

## Finding F1 — P2: uncached calls are presented as paid calls

Locations: `docs/BENCHMARK.md:15`, `README.md:121`, `docs/pitch/index.html:729`. The generated wording originates at `src/koc/benchmark_render.py:60`.

The submission labels **195 / 307** as “Số lượt gọi trả phí” or “Lượt gọi trả phí” (paid calls). Those are counts of **non-cache calls**, including free UI reads and zero-charge errors. The aggregator increments `calls` without testing cost at `src/koc/benchmark.py:225` and `src/koc/benchmark.py:235`.

On the live-run backup:

| Scope | Non-cache calls, as published | Calls with positive recorded credits or USD | Zero-cost calls included in published count |
|---|---:|---:|---:|
| Successful path, using the existing benchmark attribution | 195 | 184 | 11 |
| All attempts | 307 | 247 | 60 |

The 60 zero-cost attempts comprise **59 Kalodata/UI rows and one LLM row**. The API rows include **48 `ui/creator_detail`**, two `video/rank`, and nine `video/url` rows. The documents themselves say S2 page views cost zero (`docs/BENCHMARK.md:139`), so the paid-call label contradicts their own cost explanation as well as the ledger.

Reproduce on a fresh backup, never the original:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-release-cost-check.db'
sqlite3 -readonly /tmp/koc-release-cost-check.db <<'SQL'
SELECT 'api', COUNT(*), SUM(cache_hit=0), SUM(credits>0)
FROM api_calls WHERE run_id='7372009b22764b339fbcf0f3efb4bc4e';
SELECT 'llm', COUNT(*), SUM(cache_hit=0), SUM(cost_usd>0)
FROM llm_calls WHERE run_id='7372009b22764b339fbcf0f3efb4bc4e';
SQL
```

Observed output:

```text
api|243|215|156
llm|97|92|91
```

Thus `215 + 92 = 307` uncached calls, while `156 + 91 = 247` have positive recorded spend. To reproduce the successful-path distinction, count rows returned by `koc.benchmark._classify_api` and `_classify_llm` whose attribution is `True`, then count positive `credits`/`cost_usd` among them: `195 / 184`.

Required correction: rename this row to **uncached calls** consistently in the renderer, generated benchmark, README and deck, or compute an actual positive-cost count and label it precisely. Regenerate the benchmark if changing its renderer. Credits, tokens and USD require no correction based on this check. This is P2 under the requested rule that false submission cost claims block release.

## Live result and citation check

| Rank | Creator ID / handle | Followers | Final score, rounded | Booking estimate VND | Maximum brand_fit | Resolved citations |
|---|---|---:|---:|---:|---:|---:|
| 1 | 7485602050560148487 / @meixiuriviu | 12,200 | 78.6 | 3,000,000 | 4 | 8/8 |
| 2 | 7594293671543079957 / @teetamofficial | 74,900 | 75.7 | 7,500,000 | 4 | 8/8 |
| 3 | 6730533371858437121 / @emduyencantho | 56,900 | 73.4 | 7,500,000 | 3 | 8/8 |
| 4 | 7164572563820250139 / @dieuduong_quynhhoa | 33,500 | 73.2 | 3,000,000 | 3 | 8/8 |
| 5 | 6872721641991209985 / @k_dung26 | 86,300 | 65.7 | 7,500,000 | 3 | 9/9 |

For each creator, the checker constructed the allowed IDs from that creator's run-selected analyses plus `metric:<creator_id>:<name>` from its actual metric rows. It checked every recommendation's `cited_evidence_ids` against that set and called the production gate directly, outside pytest's lenient fixture. Four of the nine scored creators are excluded, each with maximum brand_fit 2. All ten S2 captures are placeholders; all five selected S4 audience contributions are null. C3 PASS establishes the requested count, budget, language, citation existence and gate conditions; it does not verify the underlying model's claims against every video.

## Numeric and AI claim audit

The scratch checker extracted `DECK_DATA` with Node and compared it with current code and the read-only database. **46 numeric assertions matched**, covering totals, funnel counts, projections, calibration and each pick's followers, score and cost. Paid-call labeling was checked separately and failed as F1. Samples below exceed the requested 15 numeric claims.

| Published claim / location | Independent evidence | Result |
|---|---|---|
| 200 live candidates — README:100; deck:23 | `runs.params_json.limit=200` | PASS |
| 5 picks — README:104; deck:138 | Five `recommendations` rows | PASS |
| 28,500,000 VND total — README:104; deck:137 | `SUM(recommendations.est_cost_vnd)=28500000` | PASS |
| 1,500,000 VND unused — README:104; deck:138 | `runs.params_json.s4.leftover_vnd=1500000` | PASS |
| 12,200 followers, first pick — README:108; deck:140 | `creators.data_json.creator_followers=12200` | PASS |
| 74,900 followers, second pick — README:109; deck:141 | Creator row for 7594293671543079957 | PASS |
| Final scores 78.6 / 75.7 / 73.4 / 73.2 / 65.7 — README:108; deck:140 | S4 score rows, rounded to one decimal | PASS |
| 26.00 successful-path credits — README:118; deck:53 | Fresh benchmark aggregation: 26.0 | PASS |
| 27.60 total credits — README:118; deck:54 | Direct ledger SUM: 27.6 | PASS |
| 355,351 successful-path input tokens — README:119; deck:53 | Fresh benchmark attribution: 355351; S3 remains explicitly estimated | PASS |
| 44,568 successful-path output tokens — README:119; deck:53 | Fresh benchmark attribution: 44568 | PASS |
| 1,016,946 total input tokens — README:119; deck:54 | Direct ledger SUM: 1016946 | PASS |
| 149,736 total output tokens — README:119; deck:54 | Direct ledger SUM: 149736 | PASS |
| 0.4336 successful-path USD — README:120; deck:53 | Fresh benchmark, rounded to four decimals | PASS |
| 1.3242 total USD — README:120; deck:54 | Direct SUM 1.324219, rounded | PASS |
| 2,598.5 recorded seconds — deck:58 | Sum of `stage_wall_ms` = 2598485 ms | PASS |
| Funnel 200 / 60 / 40 / 10 / 9 / 5 — README:123; deck:44 | Tasks grouped by stage/status; five recommendation rows | PASS |
| 27.33 credits at 50 candidates — architecture:99; deck:77 | Fresh `benchmark.project`: 27.3278, rounded | PASS as a projection |
| 29.38 credits at 200 candidates — architecture:99; deck:78 | Fresh `benchmark.project`: 29.3778, rounded | PASS as a projection |
| 29.68 credits at 500 candidates — architecture:99; deck:79 | Fresh `benchmark.project`: 29.6778, rounded | PASS as a projection |
| 1.4605 USD projected — architecture:99; deck:77 | Fresh projected total 1.460518, rounded | PASS as a projection |
| Spearman +0.494 and -0.259, n=9 — README:125; deck:83 | Fresh calibration: +0.493728 and -0.259416, both n=9 | PASS |
| 53/60 S1 scores saturated in each named component — README:130; deck:153 | JSON component counts: `(60, 53, 53)` | PASS |
| 10/10 placeholder captures — README:129; deck:158 | Production `placeholder_audience_creators`: 10; S2 done count: 10 | PASS |
| Brand-fit threshold 3, four exclusions — architecture:54; deck:64 | Config threshold 3; production exclusions list length 4 | PASS |
| 3 videos, 8 frames, 360 px, mono 16 kHz, first 90 seconds — architecture:42; deck:88 | `src/koc/pipeline.py:281`, `src/koc/llm/content.py:271`, `src/koc/llm/media.py:153`, `src/koc/llm/media.py:172`, `src/koc/llm/media.py:190` | PASS |
| 195/307 paid calls — README:121; benchmark:15; deck:729 | Actual positive-spend counts 184/247, using the same attribution | FAIL, F1 |

AI behavior checks: the docs correctly describe frames plus audio through OpenRouter, minimal reasoning, structured output, evidence-constrained reasons, and transcript assembly from returned speech quotes rather than a separate ASR pass. Whisper is explicitly unimplemented. The known S1 skincare-share defect, audience placeholders, three-video selection limitation and small calibration sample are disclosed; this review does not silently treat those measurements as verified demographic fit or model accuracy. The deck explicitly acknowledges the erroneous “100% skincare” prose at `docs/pitch/index.html:771`; the v1 release plan defers S1 remediation.

The published benchmark JSON renders byte-for-byte to the committed Markdown. Current live-run fields reproduce, except the snapshot-wide excluded-call count: this backup has 118 outside-run API rows, while the published benchmark has 229 and includes its historical mock run. That historical mock run ID is absent from the current live database, so its exact original timing and row count are not independently replayed. A fresh mock scaling run `890706367c424ea69a17bc0b57f73f20` completed 50 candidates to five picks, with zero credits, tokens and USD. Its 176 calls versus the artifact's 146 depend on whether 30 mock MP4s already exist; the artifact is explicitly a mock measurement, not a live scaling claim.

## Commands, offline isolation and evidence

Only the initial SQLite backup accessed the original database:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-release-v1.gDv5LL/live.db'
```

All later database checks used that backup or disposable derivatives. Socket-blocking `sitecustomize.py` and helper scripts live outside the repository under `/tmp/koc-release-v1.gDv5LL/`. They block IPv4/IPv6 connects, datagram sends, connection creation and DNS. No paid transport was used.

The sandbox also denies `send()` on Unix socketpairs: an independent socketpair probe returned `PermissionError(1, 'Operation not permitted')`. Consequently even a standalone FastAPI app with no repository code hangs in TestClient's thread handoff. This reproduced with `unshare -rn` and without the blocker. An external selector workaround caps waits at 10 ms; the standalone TestClient then returned `{'ok': True}`. The full suite and API checks used that polling accommodation. Native scheduling completion remains **UNPROVEN in this sandbox**; this is not attributed to application code. The earlier brand-fit review documents the same limitation at `docs/build/REVIEW_brand_fit_gate_r2.md`.

Full-suite command, retaining the requested interpreter and tests:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/koc-release-v1.gDv5LL/offline:src \
timeout 240 /home/lystiger/Projects/KOC-Discovery/.venv/bin/python \
  -m pytest -q tests -p no:cacheprovider
```

```text
429 passed, 1 skipped in 91.44s (0:01:31)
```

The skipped test was then run with `KOC_REAL_RUN_COPY=/tmp/koc-release-v1.gDv5LL/live.db`:

```text
tests/web/test_api.py::test_real_run_copy_proposal_totals_and_evidence
1 passed in 7.18s
```

Other fresh checks:

- `PYTHON=/tmp/koc-release-v1.gDv5LL/python bash scripts/kill_resume_test.sh`: both SIGKILL cases PASS, exit 0.
- Production `start(..., limit=200, cache_only=True)` followed by the documented single S3 skip and `resume(...)`: identical top five, all cache hits, zero spend.
- `koc --help`, `koc status`, finished `koc resume`, `koc benchmark --run <live-run> --out-dir <tmp>`, and legacy `koc report --run <live-run>`: all exited 0 on a disposable database and working directory. No supported-command crash observed.
- `git rev-list --objects --all --reflog` with `git cat-file --batch`: all historical objects inspected for the specified credential patterns, including deleted file versions and review logs.

Scratch evidence: `pytest_poll.log`, `real_ui_test.log`, `db.log`, `c5.log`, `c6.log`, `claims.log`, `scaling.log`, `commands.log`, `ui.log`, `secrets.log`, and helper scripts under `/tmp/koc-release-v1.gDv5LL/`. Potential secret candidates are kept only in the private scratch JSON, not copied into this report. Review-created test media was removed. No source, config, existing documentation, original database, branch or tag was changed. This report is the only retained repository artifact.
