Overall: PASS

# Independent release review, round 2: v1.0

Reviewed branch `fix/v1-calls-label`, HEAD `2879256b36117fab332d9c95ca2df43928c5971c`, against `0b2c417c780344bb6bef65c5883d026920d41c5e` on 2026-11-16. F1 is fixed. No new release-blocking findings or regressions were found in the requested diff and offline suite.

Scope is the round-1 release gate in `docs/build/REVIEW_release_v1.md`, using the same external SPEC C1-C11 and agreed v1 deferrals. C8 and C10 were rechecked. C1 was rerun with the real-copy test enabled. C2-C7, C9 and C11 retain their round-1 verdicts and evidence, copied below; their complete standalone audits were not repeated. This review does not claim fresh browser screenshots or a fresh all-history secret scan.

## Criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| C1: offline test suite | PASS | Fresh round-2 full suite: **430 passed in 100.20s**, exit 0. `KOC_REAL_RUN_COPY` enabled the real-copy proposal/evidence test, so no tests were skipped. Network namespace, socket blocker and the round-1 selector accommodation were active. Exact command appears below. |
| C2: dry-run plan, no network or writes | PASS, v1 scope | `koc run --dry-run` exited 0 under the socket blocker, printed the plan and 28.2 projected credits. A nonexistent `KOC_DB` remained absent. It prints zero dry-run tokens rather than a future token estimate, and incorrectly says S2 retains 15; the release plan explicitly defers both corrections. Literal original C2 token projection is therefore not delivered, rather than independently verified. `src/koc/cli.py:50`, `README.md:132`. |
| C3: live five-KOC result | PASS | Read-only backup of run `7372009b22764b339fbcf0f3efb4bc4e`: status `done`, exactly five recommendations, **28,500,000 VND**, 1,500,000 VND unused. All reasons were read and are Vietnamese, with 3-4 reasons per creator. **41/41 cited IDs** resolve through that creator's `db.run_analyses` evidence or `metrics` rows. All five pass the real `koc.stages.brand_fit_gate`, with maximum brand_fit scores **4, 4, 3, 3, 3**. See the result table in `docs/build/REVIEW_release_v1.md` and `src/koc/stages.py:164`. |
| C4: call ledger | PASS | Live-run `api_calls`: **243 rows**, 28 cache hits, **27.6 credits**. `llm_calls`: **97 rows**, 5 cache hits, **1,016,946 input / 149,736 output tokens**, **1.324219 USD**. Endpoint/model, cache flag, latency and cost/token columns exist; no live LLM row has an empty model, prompt version or request hash. Schema and writers: `src/koc/db.py:18`, `src/koc/db.py:176`, `src/koc/budget_guard.py:26`. API requests reserve a ledger row before transport at `src/koc/kalodata.py:49`. These are recorded ledger values, not an independent provider billing reconciliation. |
| C5: SIGKILL and resume | PASS | Ran `scripts/kill_resume_test.sh` offline with the external guarded Python wrapper. Exit 0: **`SIGKILL + resume: S1b PASS`**, **`SIGKILL + resume: S3 PASS`**. Script assertions cover duplicate result/task rows, repeated uncached request hashes, completion and zero-credit/zero-token finished resume. This is the requested mock kill-boundary test; it does not prove arbitrary live in-flight request exactly-once delivery. |
| C6: finished-run cache replay | PASS | Fresh derivative of the backup, actual pipeline, `cache_only=True`, no mock provider. Applied only the documented manual S3 skip for **7471573167103378440**. Replay `19d5fe65a0974cb2b329b251fd09fe78` finished `done`: **142/142 API cache hits, 32/32 LLM cache hits, 0 credits, 0 input tokens, 0 output tokens, 0 USD**, identical ordered creator IDs, ranks and booking prices. Before that skip, only that creator's S3 task was blocked by a content cache miss. |
| C7: hard caps | PASS | Full suite includes `tests/core/test_kalodata.py:21` refusal-before-transport and `tests/core/test_budget_guard.py:10` cumulative LLM budget checks. Configured credit cap is **60**, stricter than SPEC's 100; LLM cap is **5 USD**. Code: `src/koc/kalodata.py:49`, `src/koc/budget_guard.py:17`; config: `config/kalodata_prices.yaml:6`, `config/llm_caps.yaml:1`. |
| C8: benchmark and scaling | PASS | F1 resolved at `src/koc/benchmark_render.py:60` and `docs/BENCHMARK.md:15`. JSON renders byte-for-byte to the committed Vietnamese Markdown. Fresh read-only live aggregation matches every published live field. Cold-media 50-candidate mock independently reproduces S3 **70** calls, total **176**, five picks, zero spend and **259** excluded API rows. Warm-media control reproduces the old **40 / 146 / 229** counts. Projections through 500 remain unchanged and reproduce. |
| C9: UI | PASS | Requested replacement audit `docs/build/VERDICT_integration.md:9` records 375/1440 screenshots, no horizontal overflow, zero serious/critical axe findings, citation anchors and frame fetches. Independently checked the current five-pick proposal API, all five creator APIs, legacy result/detail/dashboard pages, and **54 referenced frame files**. All checked routes returned 200. Enabled `test_real_run_copy_proposal_totals_and_evidence` on this backup: **1 passed**, including its frame URL checks. Inspected the two committed app screenshots in `docs/pitch/assets/`; displayed budget, followers and current creator agree with the backup. Fresh browser layout/a11y testing on this HEAD was not repeated; the responsive proof is the accepted integration audit, not a claim of new screenshots. |
| C10: Vietnamese architecture, README and submission claims | PASS | F1 resolved at `README.md:121` and `docs/pitch/index.html:729`: **195 / 307** are labelled uncached calls. The README and generated benchmark explicitly include zero-cost calls. The deck data and pitch source guide both use **259** excluded calls (`docs/pitch/index.html:56`, `docs/pitch/README.md:96`). Numeric samples below pass. Architecture, commands, limits, extensions, AI disclosures and the explicitly unimplemented offline Whisper option retain the round-1 PASS evidence. |
| C11: history secrets and creator contacts | PASS | Scanned **all refs and reflogs**, not just HEAD: **231 commit objects, 1,156 trees, 1,269 blobs**. Searched blob/commit contents for `sk-...` and KALODATA/OPENROUTER/GEMINI assignments. All 226 candidates were test dummy literals or source/document expressions; **no credential found**. Recursively inspected JSON values in every TEXT column of every table in the untouched backup for creator-contact/email/phone/telephone/WhatsApp/WeChat/Zalo/contact keys: **zero contact fields**. Storage strips `creator_contact_*` recursively at `src/koc/db.py:254`. No actual key values are included in this report. |

## Findings

No open findings.

**F1, round-1 severity P2: resolved.** The renderer now emits "Số lượt gọi không qua cache (gồm cả lượt 0 đồng)" at `src/koc/benchmark_render.py:60`. The generated benchmark uses that text at `docs/BENCHMARK.md:15`. The README uses the corresponding uncached-call label at `README.md:121`, and the deck uses "Lượt gọi không qua cache" at `docs/pitch/index.html:729`.

Fresh attribution on the read-only backup reproduces **195 successful-path uncached calls and 307 total uncached calls**. Positive recorded-cost counts remain **184 and 247**, respectively. The corrected wording therefore describes the actual metric without changing its values. The S3 successful-path attribution remains explicitly estimated, as disclosed in the benchmark. These checks reconcile recorded ledger values, not provider invoices.

Reproduction: run the scratch verifier below. It counts non-cache rows returned by `_classify_api` and `_classify_llm`, then separately counts positive `credits` or `cost_usd`. It also asserts that `render_markdown(json.loads(reports/benchmark.json))` exactly equals `docs/BENCHMARK.md`, extracts `DECK_DATA` with Node, and compares its numbers with fresh aggregation and direct SQL.

## Excluded-call regeneration

All current excluded-call claims agree: `reports/benchmark.json:305`, `docs/BENCHMARK.md:48`, `docs/pitch/index.html:56`, and `docs/pitch/README.md:96` publish **259**, with **10.30 credits**. No stale 229-call exclusion claim remains in the six requested files. The historical round-1 report correctly retains its old snapshot count.

The current live backup contains **118** outside-run API rows and no historical mock scaling run. Two fresh mock runs on separate disposable copies explain the snapshot change:

| Media state | Mock API rows | Mock S3 calls, API plus LLM | Mock total calls | Outside-run API rows | Outside-run credits |
|---|---:|---:|---:|---:|---:|
| Cold, no mock videos | 141 | 70 | 176 | 118 + 141 = 259 | 10.30 |
| Warm, 30 existing mock videos | 111 | 40 | 146 | 118 + 111 = 229 | 10.30 |

The cold run logs 50 `creator/detail`, one `creator/rank`, 60 `video/rank` and 30 `video/url` rows. The warm control reuses those 30 videos and omits the downloads. Thus **259 - 229 = 176 - 146 = 70 - 40 = 30**. Mock credits, input tokens, output tokens and USD are zero in both runs. Total database credits remain **37.90 = 27.60 + 10.30**.

A cold-copy regeneration matches every published top-level field outside `scaling_run`, including `excluded_api_calls`. Its scaling status, mode, limit, funnel, stage call/cache/cost/token fields and totals also match. The new generated mock ID and timing differ, as expected for a new execution. The committed historical mock ID `f5adab7df38f460ebea54ede55528760` and its exact 645 ms duration cannot be independently recovered from the current live backup. Their consistency between JSON and rendered Markdown passes; their historical measurement remains UNPROVEN. This is the same historical-run evidence limit disclosed in round 1, not a new regression.

## Numeric claim samples

The one-shot scratch verifier completed **168 assertions**, including structured comparisons. The following individual numeric samples exceed the requested eight:

| Claim and current location | Fresh evidence | Result |
|---|---|---|
| 195 successful-path uncached calls, `README.md:121`, `docs/BENCHMARK.md:15`, `reports/benchmark.json:162`, deck data `docs/pitch/index.html:53` | Classified non-cache successful rows = 195 | PASS |
| 307 total uncached calls, same document rows, `reports/benchmark.json:171`, deck data `docs/pitch/index.html:54` | Direct SQL: 215 API + 92 LLM = 307 | PASS |
| 26.00 successful-path credits, `README.md:118`, `docs/BENCHMARK.md:11` | Fresh attribution = 26.0 | PASS |
| 27.60 total credits, same rows | Direct ledger sum, rounded = 27.60 | PASS |
| 355,351 successful input tokens, `README.md:119`, `docs/BENCHMARK.md:12` | Fresh attribution = 355351 | PASS, S3 attribution estimated |
| 44,568 successful output tokens, `README.md:119`, `docs/BENCHMARK.md:13` | Fresh attribution = 44568 | PASS, S3 attribution estimated |
| 1,016,946 total input tokens, `README.md:119`, `docs/BENCHMARK.md:12` | Direct ledger sum = 1016946 | PASS |
| 149,736 total output tokens, `README.md:119`, `docs/BENCHMARK.md:13` | Direct ledger sum = 149736 | PASS |
| 0.4336 successful USD, `README.md:120`, `docs/BENCHMARK.md:14` | Fresh attribution = 0.433646, rounded to four decimals | PASS |
| 1.3242 total USD, same rows | Direct ledger sum = 1.324219, rounded to four decimals | PASS |
| 259 excluded API calls, `reports/benchmark.json:305`, `docs/BENCHMARK.md:48`, deck `docs/pitch/index.html:56`, pitch guide `docs/pitch/README.md:96` | Fresh cold-copy regeneration = 259 | PASS |
| 10.30 excluded credits, `reports/benchmark.json:306`, same document claims | Outside-run ledger sum = 10.3 before and after mock | PASS |
| 37.90 whole-database credits, `docs/pitch/README.md:96` | Direct SQL on the disposable mock copy = 37.9 | PASS |
| 33 cache hits, `reports/benchmark.json:172`, `docs/pitch/index.html:57`, `docs/pitch/README.md:98` | Direct SQL: 28 API + 5 LLM = 33 | PASS |
| 2,598.5 recorded seconds, `docs/pitch/index.html:58` | Fresh live `wall_time_ms` = 2598485 | PASS |
| Five recommendations and 28,500,000 VND booking total, `README.md:104` | Five recommendation rows, `SUM(est_cost_vnd)` = 28500000 | PASS |
| 1,500,000 VND unused, `README.md:104` | 30000000 budget minus 28500000 booking total | PASS |
| 27.33 projected credits for 50 candidates, `docs/BENCHMARK.md:80`, deck `docs/pitch/index.html:77` | Fresh `project` = 27.3278, rounded | PASS as projection |
| 29.38 projected credits for 200 candidates, `docs/BENCHMARK.md:96`, deck `docs/pitch/index.html:78` | Fresh `project` = 29.3778, rounded | PASS as projection |
| 29.68 projected credits for 500 candidates, `docs/BENCHMARK.md:112`, deck `docs/pitch/index.html:79` | Fresh `project` = 29.6778, rounded | PASS as projection |
| 1.4605 projected USD at all three limits, same projection locations | Fresh `project` = 1.460518, rounded | PASS as projection |
| Mock limit 50, `reports/benchmark.json:696`, `docs/BENCHMARK.md:143` | Fresh cold mock, limit = 50, status done | PASS |
| Mock S3 70 calls, `reports/benchmark.json:739`, `docs/BENCHMARK.md:151` | Fresh cold mock S3 = 70 | PASS |
| Mock total 176 calls, `reports/benchmark.json:786`, `docs/BENCHMARK.md:153` | Fresh cold mock total = 176 | PASS |
| Mock zero credits, tokens and USD, `reports/benchmark.json:788`, `docs/BENCHMARK.md:153` | Fresh cold and warm mock ledgers = zero | PASS |

## Regression and isolation evidence

Inspected the complete `git diff 0b2c417..HEAD`, including the added round-1 report. The only executable-code change is the renderer label. The other changes are that report, matching labels, the excluded count, and regenerated mock ID, calls and timings. All live benchmark fields, projections, calibration, funnel, costs and tokens are unchanged from the base commit and reproduce from the backup. `git diff --check 0b2c417..HEAD` passes.

The original database was accessed only for this SQLite read-only backup:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-release-v1-r2.JTsPHt/live.db'
```

All later database reads used that copy; mock runs used disposable derivatives. Verification Python ran inside `unshare -rn`, with the round-1 socket blocker copied into the scratch directory. The blocker rejects IPv4/IPv6 connects, datagram sends, connection creation and DNS. An audit hook also rejects Python SQLite connections naming the original database. No live transport or paid calls were used.

The sandbox still rejects Unix socketpair `send()`: the fresh standalone probe returned `PermissionError(1, 'Operation not permitted')`. The copied `sitecustomize.py` retains the round-1 selector accommodation, capping waits at 10 ms so TestClient callbacks progress. Native scheduling completion without this accommodation remains UNPROVEN in this sandbox. Product and test source were not changed.

Full suite:

```bash
unshare -rn env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/tmp/koc-release-v1-r2.JTsPHt/offline:src \
  KOC_DB=/tmp/koc-release-v1-r2.JTsPHt/unused.db \
  KOC_REAL_RUN_COPY=/tmp/koc-release-v1-r2.JTsPHt/live.db \
  timeout 240 /home/lystiger/Projects/KOC-Discovery/.venv/bin/python \
  -m pytest -q tests -p no:cacheprovider
```

```text
430 passed in 100.20s (0:01:40)
```

This retains the requested interpreter, `src` import path and complete `tests` target. Additional environment settings provide offline isolation and a safe real-run copy. Disabling pytest's cache avoids a repository cache write. Compared with round 1's 429 passed plus one skipped, the real-copy test now runs within the full suite and passes.

Focused verifier:

```bash
unshare -rn env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/tmp/koc-release-v1-r2.JTsPHt/offline:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python \
  /tmp/koc-release-v1-r2.JTsPHt/verify.py
```

```text
COLD a88fd65aa5124f89b028dbf079b17343 API 141 S3 70 TOTAL 176 EXCLUDED {'calls': 259, 'credits': 10.3}
WARM 876fa5461c274804aeed035ee086fb1d S3 40 TOTAL 146 EXCLUDED {'calls': 229, 'credits': 10.3}
COLD_EXTRA_ENDPOINTS [('creator/detail', 50), ('creator/rank', 1), ('video/rank', 60), ('video/url', 30)]
ASSERTIONS 168 PASS
```

Scratch evidence is under `/tmp/koc-release-v1-r2.JTsPHt/`: `pytest.log`, `claims.log`, `claims.json`, `verify.py`, `cold_benchmark.json`, `full.diff`, the copied blocker, and disposable databases. Test-created raw captures were removed. Existing ignored mock video fixtures were retained. No source, config, existing documentation, original database, branch or tag was changed. This report is the only addition shown by `git status`.
