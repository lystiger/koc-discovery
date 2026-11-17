Overall PASS

Reviewed `v2/web-search` (`46b2ea6..2bad1bd` and full range `fd9b471..2bad1bd`). All five P2 and two P3 findings from r1 are closed. No P1 or P2 findings remain open.

### Findings (P1 / P2 / P3)

- **P1 / P2:** None.
- **P3 — Merged `chosen` objects drop explicit `price_per_video_vnd` and rely on `/ 3` fallback.** [pages.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/pages.tsx#L388): `(result.ranked_pool ?? chosen).map((creator) => chosenById.get(creator.creator_id) ?? creator)` replaces `ranked_pool` entries for `picked` and `alternates` with `chosen` entries from `match()`, which do not carry `price_per_video_vnd`. In production (`VIDEOS_PER_KOC = 3`), [filters.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx#L44) `Math.round(creator.cost_vnd / 3)` yields the exact same `1_000_000 / 2_500_000 / 5_000_000` values; only a crafted payload or future `VIDEOS_PER_KOC != 3` change without updating `filters.tsx` would diverge for picked/alternate rows.
- **P3 — Smoke sort-reset step checks URL before React render commit under heavy CPU contention.** [smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/tests/web/e2e/smoke.py#L730-L732): clicking `"Điểm cao nhất"` asserts `not_to_have_url(re.compile("sx="))` (`history.replaceState`) and immediately calls `fill("e")` without waiting for `aria-pressed="true"` on the chip. When run concurrently with heavy CPU load (`pytest` + `vite build`), the input handler can read the pre-click `filter.sort = "price-asc"` closure; standalone `smoke.py` passes cleanly.

### Round 1 Finding Status & Independent Verification

1. **r1 P2 — Search duplicated instead of extending the header: CLOSED**
   - Per the orchestrator clarification in [v2_plan.md](file:///home/lystiger/Projects/LysStack/projects/koc-discovery/v2_plan.md#L55-L56), the header palette in [App.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/App.tsx#L44-L68) remains the global diacritic-insensitive jump search, while [filters.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx#L88-L90) is scoped and labelled as an in-list filter (`aria-label="Lọc và sắp xếp KOC trong danh sách"`, input `aria-label="Lọc KOC theo tên hoặc handle"`, placeholder `"Lọc theo tên hoặc handle"`). At 375 px ([styles.css](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/styles.css#L722-L723)), `.filter-search` spans full width (`flex-basis: 100%`) so the placeholder is not truncated.

2. **r1 P2 — Scored creators remain unsearchable (`ranked_pool`): CLOSED**
   - [matching_api.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/src/koc/web/matching_api.py#L301-L307) adds `ranked_pool(pool, limit=200)`, which scores the gate-passing `pool` from `get_pool()` via `score_creators(pool)` (not `_rank(pool)`'s 15-cap), sorts by `(-fit, creator_id)`, and attaches `price_per_video_vnd = cost_vnd // VIDEOS_PER_KOC` with zero paid API/LLM calls. [api.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/src/koc/web/api.py#L141) enriches `ranked_pool` in `_campaign_review_data`, and [pages.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/pages.tsx#L388-L395) filters over `pool` while marking `picked` rows with `.pick-badge` (`"Được chọn"`).
   - **Independent evidence:**
     - On a synthetic DB with 20 creators passing `brand_fit` (`score=5`) and 3 failing (`score=1`), `result_for_campaign` + `_campaign_review_data` returned `len(picked) == 5`, `len(alternates) == 5`, `ranked_count == 15`, and `len(ranked_pool) == 20` (> picks + alternates), with zero `fail_*` IDs in `ranked_pool` and all 3 in `brand_fit_excluded`.
     - On the read-only copy `/tmp/agyweb.db` of `data/koc.db` (run `7372009b22764b339fbcf0f3efb4bc4e`, 60 S1 creators, 55 excluded by `excluded_brand_fit`), `ranked_pool` contained exactly the 5 brand-fit-eligible creators (`overlap with excluded_brand_fit == set()`).

3. **r1 P2 — Price bands compare against three-video totals: CLOSED**
   - [filters.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx#L44-L54) computes `pricePerVideo(creator) = creator.price_per_video_vnd ?? Math.round(creator.cost_vnd / 3)` and compares `PRICE_BANDS` (`< 2_000_000`, `2_000_000..4_000_000`, `>= 4_000_000`) against `pricePerVideo(creator)`.
   - **Independent evidence:** Transpiled [filters.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx) via TypeScript in Node and ran `applyFilter` on creators across all three rate-card tiers (`1_000_000`, `2_500_000` including legacy `cost_vnd: 7_500_000` without `price_per_video_vnd`, and `5_000_000` per video):
     - `price: "lt2"` selected `['c_1m_a', 'c_1m_b']` (1M tier only).
     - `price: "2-4"` selected `['c_25m', 'c_legacy_25m']` (2.5M tier only).
     - `price: "gte4"` selected `['c_5m']` (5M tier only).

4. **r1 P2 — “Highest score” does not sort by score: CLOSED**
   - [filters.tsx](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/web/src/ui/filters.tsx#L45-L58) defines `byFit = (a, b) => b.fit - a.fit || a.creator_id.localeCompare(b.creator_id)` and applies it for default (`sort: ""`), `"score"` (`Điểm cao nhất`), and as the secondary tie-breaker for `price-asc` and `price-desc`.
   - **Independent evidence:** Node execution on unsorted input `[fit 88 (c_5m), fit 95 (c_1m_b), fit 99 (c_25m), fit 95 (c_1m_a), fit 91 (c_legacy_25m)]` returned `['c_25m', 'c_1m_a', 'c_1m_b', 'c_legacy_25m', 'c_5m']` for both `sort: ""` and `sort: "score"` (descending `fit`, with `c_1m_a` before `c_1m_b` on tied `fit = 95`), `['c_1m_a', 'c_1m_b', 'c_25m', 'c_legacy_25m', 'c_5m']` for `price-asc`, and `['c_5m', 'c_25m', 'c_legacy_25m', 'c_1m_a', 'c_1m_b']` for `price-desc`.

5. **r1 P2 — Previous-runs GET writes to the database: CLOSED**
   - [api.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/src/koc/web/api.py#L283-L305) returns `[]` if the DB file does not exist and opens existing DBs via `sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)` without calling `_conn()` or `campaigns.ensure_table()`.
   - **Independent evidence:** Copied `data/koc.db` to `/tmp/agyweb.db` (`4,284,416` bytes) and invoked `previous_runs(req, product_type="Chống nắng")`. It returned `[{'run_id': '7372009b22764b339fbcf0f3efb4bc4e', 'started_at': '2026-11-14T22:53:08.830945+00:00', 'creator_ids': ['7485602050560148487', '7594293671543079957', '6730533371858437121', '7164572563820250139', '6872721641991209985']}]`, file byte length and SHA-256 digest before and after were identical, and `SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'` remained `None`.

6. **r1 P3 — Limit applied before eligibility checks: CLOSED**
   - [api.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/src/koc/web/api.py#L293-L301) iterates through `_done_run_ids(conn, product_type)`, filters for `re.fullmatch(r"[0-9a-f]{32}", run_id)` and non-empty `recommendations`, appends to `result`, and breaks only when `len(result) == 10`. Verified by `test_previous_runs_applies_eligibility_before_the_limit_of_ten` in [test_matching_api.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/tests/web/test_matching_api.py#L240-L248).

7. **r1 P3 — Smoke price/sort coverage cannot catch these defects: CLOSED**
   - [smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-aade6e3de2521345a/tests/web/e2e/smoke.py#L680-L742) now checks cost-internal leakage (`credit`, `usd`, `token`) on both filtered and empty states before clearing filters, injects a mixed-price pool (`1_000_000`, `2_500_000`, `5_000_000` per video) with a fit tie (`zz_cheap_a` and `zz_cheap_b` at `97.0`), and asserts exact row ID ordering for every price band (`lt2`, `2-4`, `gte4`), every follower tier (`lt50`, `50-100`, `gte100`), both price sort directions (`price-asc`, `price-desc`), default score sort order across mixed prices after resetting sort, and `.pick-badge` presence.

8. **Visual inspection (`docs/shots/v2_web2/`):**
   - Inspected all 9 screenshots (`filter_drawer_375.png`, `form_exclude_1440.png`, `form_exclude_375.png`, `needs_run_estimate_1440.png`, `needs_run_estimate_375.png`, `results_empty_1440.png`, `results_empty_375.png`, `results_filtered_1440.png`, `results_filtered_375.png`). Mobile filter input is full-width with untruncated placeholder `"Lọc theo tên hoặc handle"`, `"Được chọn"` badge renders cleanly on picked creators in filtered views, status line shows `"Hiển thị 2/6 KOC"`, and `needs_run` estimate and exclusion boxes are well-aligned at both 375 px and 1440 px.

### Command Results

- `cd web && npm run build && npx eslint src --max-warnings=0` (via `rtk bypass`): **PASS** (`tsc -b && vite build` succeeded in 2.73s; `eslint src --max-warnings=0` exited 0 with 0 warnings/errors).
- `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python tests/web/e2e/smoke.py`: **PASS** (`{"screenshots": 27, "serious_axe_violations": [], "matching_seconds": 0.151, "campaign_id": "635b295a84744974a44c8a500ef09a8a"}`, exit 0; tracked screenshot diffs restored with `git checkout`).
- `unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q'`: **PASS** (`470 passed, 1 skipped in 83.34s`).
- `git diff --exit-code` & `git status -s`: **PASS** (working tree clean; `/tmp/agyweb.db` removed; `data/koc.db` never opened for writes).
