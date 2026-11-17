Overall FAIL

Reviewed `v2/web-search`, `fd9b471..d890f12`. Five P2 findings remain open. Source and tests unchanged.

- **P2 — Search duplicated instead of extending the header.** [web/src/ui/filters.tsx:86](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx:86): adds another text-search input. The existing header palette gains diacritic folding but no tier, price, or sort controls. Both searches appear in the desktop screenshot. Consolidate the requested behavior into the existing header search, as V2-1/A5 require.

- **P2 — Scored creators remain unsearchable.** [web/src/ui/pages.tsx:386](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/pages.tsx:386): filters only `picked + alternates`. Independent backend probe produced **15 ranked creators but only 6 searchable records**. Header name lookup cannot replace filtering scored creators by tier, price, and score. The builder’s disclosed limit narrows V2-1 without approval. Supply the scored pool for client-side filtering, without paid calls.

- **P2 — Price bands compare against three-video totals.** [web/src/ui/filters.tsx:50](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx:50): controls say “Giá mỗi video,” but `cost_vnd` includes three videos. Current tiers yield totals of **3 / 7.5 / 15 million VND**, versus per-video prices of **1 / 2.5 / 5 million**. Actual filter output: `<2m` selects nobody; `2–4m` selects the cheapest tier; `≥4m` selects both remaining tiers. Compare a per-video value. Fixed boundaries alone are acceptable for the current rate card; incorrect units are not.

- **P2 — “Highest score” does not sort by score.** [web/src/ui/filters.tsx:51](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx:51): only price sorts run. Concatenating budget-selected picks with alternates does not preserve descending score. Backend-generated example returned scores `[99, 100]`; the actual client filter retained that order. Add explicit descending `fit` sorting with a stable tie-breaker.

- **P2 — Previous-runs GET writes to the database.** [src/koc/web/api.py:285](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/src/koc/web/api.py:285): `_conn()` calls `campaigns.ensure_table()`, which creates and commits a table. On a temporary pipeline DB, invoking this GET handler changed database bytes and created `campaigns`. Use a connection path that performs only reads; initialize schema elsewhere.

- **P3 — Limit applied before eligibility checks.** [src/koc/web/api.py:288](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/src/koc/web/api.py:288): slices ten finished runs before checking valid IDs and recommendations. Ten newer runs without picks hide an older eligible run; reproduced response was `[]`. Filter eligible runs first, then take ten.

- **P3 — Smoke price/sort coverage cannot catch these defects.** [tests/web/e2e/smoke.py:667](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/tests/web/e2e/smoke.py:667): never selects a price band. Sorting runs after selecting one follower tier, whose prices are identical; descending order is never asserted. Test mixed prices, both directions, default score order, and expected IDs for every price band. URL restoration, empty-state clearing, checkbox request bodies, and null-estimate assertions are meaningful.

Other acceptance evidence:

- **PASS:** client/server diacritic folding; URL filter round-trip; invalid-parameter handling.
- **PASS:** previous-run IDs are valid lowercase 32-hex values, product-scoped, and accepted by `CampaignInput`. Both generated commands retain repeated `--exclude-run` flags.
- **PASS:** estimate matches `src/koc/estimate.py`: **27.6–29.4 credits, 0.48–1.46 USD, 441,769–1,286,591 tokens, 35–58 minutes**. Screenshots show “ước tính”; supplied smoke verifies hiding on null.
- Opened **all nine screenshots**. New controls, empty states, exclusion checkbox, and 375 px drawer are readable. Palette and typography follow the approved design system.
- Supplied smoke retains brand-page credit/USD guards. Its new guard executes after clearing filters, so it does not independently prove filtered/empty-state copy.

Command results:

- Independent pytest, with `PYTHONPATH=src`, on `tests/web/test_matching.py` and `tests/core/test_estimate.py`: **69 passed**.
- Independent Node probes executed actual transpiled filters: reproduced price-band and score-order failures; folding and URL checks passed.
- Independent Python probes used temporary databases only: reproduced GET writes and premature limiting; validated ID scope, exclusion flags, and estimate values.
- API `TestClient` rerun stalled under sandbox restrictions and was interrupted. Browser/smoke and full-suite results rely on supplied logs: **lint/build passed; smoke exit 0, zero serious axe findings; pytest 467 passed, 1 skipped**.
- `git diff --check fd9b471..HEAD`: trailing blank-line warning in `v2_web2_lint.log:4`.
- `git diff --exit-code`: **passed**. Pre-existing untracked files unchanged. `data/koc.db` was never opened.