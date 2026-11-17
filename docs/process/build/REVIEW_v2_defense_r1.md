Overall FAIL

Reviewed `88bb084..62cebac`. Excluded later web-button commit. No source or tests changed. Three P2 findings remain open.

P1: None found.

P2 findings:

1. **Historical scores contradict the new “không tính điểm” label.**  
   `src/koc/web/adapter.py:36`, `web/src/ui/pages.tsx:652`; consumers: `src/koc/web/api.py:187`, `src/koc/web/matching_api.py:209`.

   Existing scores retain the old 25% proxy contribution. Web pages and new campaigns reuse those scores without scoring-version metadata.

   Concrete example: `@meixiuriviu`, run `0e555cac…`, returns S1 **89.3479**; current weights produce **85.7976**. Final score remains **79.01**, versus **77.01** after reweighting.

   Preserving historical results is reasonable. Presenting them alongside “proxy, không tính điểm” without a legacy-score label is misleading. README labels its table correctly; application views do not. Record/display scoring provenance, or explicitly recompute derived views.

2. **Documentation promises per-reason citation enforcement that code does not provide.**  
   `docs/LIMITATIONS.md:13`; implementation: `src/koc/llm/reasons.py:134`.

   Validation requires one nonempty, valid **global** `cited_evidence_ids` list. It does not require evidence attached to each reason.

   Independent reproduction: three uncited reasons plus one valid global metric ID returned **`errors=[]`**.

   Describe the existing global citation check accurately. Per-reason citation coverage and factual support remain separate checks.

3. **New slide overstates the off-topic-video gate.**  
   `docs/pitch/index.html:342`; implementation: `src/koc/stages.py:176`.

   “Loại KOC có video lạc đề” implies creators with off-topic videos are excluded. Actual gate accepts a creator when **any one** analysed video reaches brand-fit **3/5**.

   Stored counterexamples remain selected:

   - `@rio100806`: brand-fit **3, 4, 1**.
   - `@teetamofficial`: **4, 1, 2**.

   State: exclude creators whose **best analysed video** scores below 3/5. `docs/LIMITATIONS.md:12` describes this more accurately.

P3 findings:

4. **93/101 describes saturation after clamping, not raw revenue equality.**  
   `docs/LIMITATIONS.md:9`; clamping: `src/koc/stages.py:38`.

   Comparing detail revenue against each creator’s latest cached rank row produced:

   | Raw detail/rank ratio | Responses |
   |---|---:|
   | Exactly 1 | 80 |
   | Above 1 | 13 |
   | Below 1 | 8 |
   | Clamped to 1 | **93** |

   Even allowing equality against **any** cached rank response yields **88/101**, not 93.

   No independent category/overall revenue pair was established. Payloads contain generic revenue fields, without a separate category-revenue breakdown. Cache hashes verify category-bearing requests for 60 detail responses; 41 request scopes remain unresolved.

   Disabling the unreliable share is defensible. The stronger assertion that no unfiltered total exists anywhere is **UNPROVEN**. Document the missing verified denominator and distinguish raw ratios from clamped components.

5. **Top-40 membership stays unchanged; ordering does not.**  
   `docs/LIMITATIONS.md:9`; preview: `scripts/s1_reweight_preview.py:69`.

   Both runs retain **40/40 members**, but **17 positions change**. Example: creator `6747508885333443585` moves from **#30 to #18**. Top-ten order stays unchanged.

   Replace “giữ nguyên thứ hạng” for S1 with “giữ nguyên thành viên top 40.” Scope the observation to these two stored runs.

Independent verification:

- **Math passes:** remaining weights total 75; multiplying by `100/75` gives **46.6667/20/20/13.3333**. Config rounds correctly and sums to **100**. Changing only the proxy does not change newly calculated S1.
- **Preview numbers reproduce:**

  | Run | Old final scores, rank order | Reweighted final scores | Drop |
  |---|---|---|---|
  | `0e555cac95fb4fb49168410e40ea92d5` | 79.01, 77.66, 76.15, 74.68, 74.06 | 77.01, 76.32, 74.04, 72.49, 71.80 | 1.3364–2.2587 |
  | `7372009b22764b339fbcf0f3efb4bc4e` | 78.59, 75.72, 73.43, 73.24, 65.74 | 76.59, 73.47, 71.24, 71.12, 63.35 | 1.9970–2.3925 |

  Both final top-five orders remain unchanged. Old-weight reconstruction has maximum drift **0.0000**. README’s rounded **1.3–2.4** claim is accurate.

- **Preview is read-only:** `scripts/s1_reweight_preview.py:24` opens the file with `mode=ro`, backs up into memory, and updates only memory. Offline execution succeeded. `/tmp/def.db` SHA-256 stayed:
  `ad42671180bb133e2374e447f839b3be5623edf3051877070cd118df6acdf5e7`.
- **Pricing matches:** `src/koc/pricing.py:14` applies configured per-video rates ×3: **3m/7.5m/15m VND per creator**. Outside-band follower counts use the nearest tier.
- **Audience handling matches these runs:** ten known placeholders are excluded from final audience scoring. Detection remains heuristic (`src/koc/stages.py:118`).
- **Age-overlap limitation is accurate:** `src/koc/stages.py:102` includes an entire overlapping band. Current sampled runs drop that audience component.
- **Web pool claim matches:** an unrun Serum request returned `needs_run`, a dry-run command, and an estimate. Payment confirmation remains an operator procedure.
- **Faithfulness reproduces:** `stored_summary()` returns **0.875 reasons / 0.10 caveats** for `0e555cac…`, across five KOCs. These are model-judged support scores, not human accuracy or citation-coverage rates.
- **Benchmark/estimate unaffected:** regenerated `units_success`, `units_total`, and both totals exactly match published benchmark values. Default estimate remains **27.6–29.4 credits**, **$0.48–$1.46**, **441,769–1,286,591 tokens**, **35–58 minutes**.

Command results:

- Requested SQLite backup succeeded; original `data/koc.db` was never written.
- Requested offline pytest invocation stalled at `tests/core/test_brief.py:335`. Loopback setup emitted `Cannot open netlink socket: Operation not permitted`.
- Minimal asyncio reproduction also lost cross-thread wakeups. An external `/tmp` runner added selector polling without editing project files.
- Audited offline suite: **557 passed, 1 skipped in 200.06s**.
- Skipped real-DB test rerun with `KOC_REAL_RUN_COPY=/tmp/def-web-test.db`: **1 passed**.
- Focused scoring/estimate/benchmark/audience/gate checks: **38 passed, 5 deselected**.
- `git diff --check 88bb084..62cebac`: clean. Tracked working tree unchanged.

**Requested rating-sheet deletion finding: UNPROVEN.** No responsible test was identified. The complete audited suite retained `docs/eval/RATING_SHEET_top5.md` byte-for-byte; no deletion event referenced it. The explicit unlink at `tests/web/fixtures/seed.py:54` deletes its fixture DB path. Evidence does not support attributing the reported sheet deletion to that test.