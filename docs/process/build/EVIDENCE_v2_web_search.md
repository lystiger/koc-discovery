# EVIDENCE: v2.0 web wave 2 (branch v2/web-search)

Base: feat/koc-mvp at fd9b471. Scope: V2-1b (search and filter), A1 (run estimate in the needs_run panel), V2-2 (exclusion checkbox), V2-8 (design on the new parts only). No redesign, no new dependency.

## Design source (V2-8)

- Ran `ui-ux-pro-max --design-system "search filter sort list influencer marketing"`. It returned "Marketplace / Directory", Flat Design, green #059669 and Inter/Playfair. This conflicts with the approved `design/system/koc-discovery/MASTER.md` direction (same outcome as wave 1), so the palette and fonts were NOT applied. Taken from it: "avoid hidden filters" (filters are visible on desktop, a labelled "Bộ lọc" button with a count badge on mobile), 150-200 ms transitions, visible focus, 44 px targets.
- Reused: tokens `--paper/--surface/--ink/--green/--border`, Newsreader + Be Vietnam Pro, `.age-chip` (pressed chip), `.switch-row` (checkbox row), `.needs-run-*`. Libraries already installed: Vaul (mobile filter drawer), cmdk (header search), lucide-react. Per `pick-ui-library`: drawer = Vaul, command menu = cmdk, no custom replacement.

## Items

| # | Item | Proof |
|---|---|---|
| 1 | Header search extended (not duplicated) | `App.tsx`: `SearchPalette` keeps its single palette. cmdk `filter` and the saved-campaign filter now use `fold()` (diacritics and đ). Server `GET /api/creators` folds the same way (`api.py _fold`). Pytest `test_creator_search_ignores_diacritics`; smoke types "trinh my pham" and finds "Trịnh Mỹ Phẩm". |
| 2 | Results filter bar | `web/src/ui/filters.tsx` (`FilterBar`, `applyFilter`, `FilterEmpty`), wired in `CampaignResultsPage`. Text (name or handle, diacritic-insensitive), follower tier (<50k, 50-100k, >=100k, the pricing tiers), price band per video (<2 tr, 2-4 tr, >=4 tr), sort (score default, price asc, price desc). Client-side only. State is in the URL (`?q=&tier=&gia=&sx=`, `useSearchParams`, replace): a copied link restores the filter (smoke reloads the URL), unknown values are ignored (`?tier=bogus&sx=bogus` shows all 5). Empty: "Không có KOC nào khớp bộ lọc. Thử bỏ bớt điều kiện hoặc tìm tên khác." plus "Xóa bộ lọc" button; status line "Hiển thị x/y KOC. Xóa bộ lọc". 375 px: search stays inline, the three chip groups move into a Vaul drawer ("Bộ lọc", badge count, "Xem N KOC", "Xóa bộ lọc"). When a filter is active the list is one combined list that keeps each KOC's original rank number. |
| 3 | needs_run estimate (A1) | `RunEstimateBox` in `pages.tsx`, above the command. Credits, USD, tokens, minutes each as `low–high`, label "ước tính", "quét tối đa 200 KOC". Null `run_estimate` renders nothing (smoke intercepts the GET and nulls it). Only on the operator needs_run panel; brand pages unchanged: the existing "no token/credit/usd/latency/task" assertions on form, results, proposal still pass, and the new filtered/empty states are asserted free of those words too. |
| 4 | Exclusion checkbox (V2-2) | New read-only `GET /api/runs/previous?product_type=` (`api.py previous_runs`): finished runs of that product type that have picks, newest first, max 10, only 32-hex ids (the exact pattern `CampaignInput.exclude_run_ids` accepts). Form shows "Loại KOC đã đề xuất ở lần trước" only when the product type has such runs; note reads "Lần chạy ngày 16/11/2026: loại 5 KOC đã được đề xuất khỏi kết quả." (several runs: dates listed, KOC count is the distinct union). Ticking sends all listed run ids as `exclude_run_ids`; unticked sends no field (smoke asserts both request bodies). Changing the product type resets the tick. When the exclusion leaves too few KOC the API returns needs_run with the `--exclude-run` flags; the panel then shows "Lệnh có --exclude-run. Lần chạy ngày …: loại 5 KOC …" and both commands contain the flags (smoke asserts). Pytest: `test_previous_runs_lists_done_runs_with_picks`, `test_previous_runs_skips_runs_without_picks`. |

## Checks run

- `rtk bypass npm run lint`: pass. `npm run build`: pass. Logs `docs/process/build/logs/v2_web2_lint.log`, `_build.log`.
- `PYTHONPATH=src python tests/web/e2e/smoke.py`: `{"screenshots": 27, "serious_axe_violations": [], ...}`, exit 0 (`_smoke.log`). Smoke additions: filter by text/tier/sort/price at 1440 and 375 (drawer), URL restore, bad params, empty state and clear, header-search diacritics, form checkbox request bodies, needs_run estimate (4 ranges, label, above the command), exclusion note, null estimate. Axe serious run on: filtered results, empty state, filter drawer (open), form with checkbox, needs_run with estimate (both widths): 0 serious. The smoke rewrites tracked `docs/process/build/shots/readability/*`; reverted with `git checkout`.
- Full pytest offline (`unshare -rn`, `PYTHONPATH=src`, fake keys): 467 passed, 1 skipped (`_pytest.log`).
- `data/koc.db` was never opened; smoke uses a temp fixture DB.

## Screenshots (`docs/shots/v2_web2/`, 375 and 1440)

`results_filtered_*` (tier 50-100 + price sort asc), `results_empty_*`, `needs_run_estimate_*` (estimate + exclusion note + commands), `form_exclude_*` (checkbox ticked), `filter_drawer_375.png`. I opened results_filtered_1440 (re-captured), results_filtered_375, results_empty_375, needs_run_estimate_1440 and _375, form_exclude_375, filter_drawer_375. Fixed after viewing: screenshots caught chips mid-transition (now waits), truncated mobile search placeholder (shortened). Not opened: results_empty_1440, form_exclude_1440.

## UNPROVEN / notes for Lystiger

- The filter works on what the page holds: the picked KOC plus up to 5 alternates (here 6). The API does not send the whole ranked pool (`ranked_count` only), so "all ranked creators" is not searchable on the results page; the header search still finds any KOC in the DB by name. Sending the full pool would be a payload change; not done.
- Price bands and tiers are fixed constants matching the current rate card (1 / 2.5 / 5 tr per video); if the rate card changes the band edges need updating. With the current card, tier and price filter select nearly the same KOC.
- The checkbox sends every listed earlier run (up to 10), not a per-run choice. The fixture run ids are not 32-hex, so the smoke adds a finished run with a real-style id; real runs use `uuid4().hex`.
- Real-data run on a copy of `data/koc.db` was not done in this wave (fixture only).
- `tests/web/e2e/budget_refusal.py` stale selector (noted in wave 1) not touched.
- Print layout of the new bar was not viewed (hidden by `@media print` rule only).

## r2 fixes (after REVIEW_v2_web_search r1 FAIL)

Orchestrator ruling kept: the header palette is the global jump search; the results-page field is a filter, relabelled "Lọc theo tên hoặc handle" (aria-label "Lọc KOC theo tên hoặc handle"; the bar's aria-label says "trong danh sách"). At 375 px the field now takes its own full-width row so the longer placeholder is not cut.

| Finding | Fix and proof |
|---|---|
| P2 scored pool | `matching_api.ranked_pool` sends every scored creator that passed the gates (compact: id, name, handle, followers, avatar, mcn, fit, components, confidence, cost_vnd, `price_per_video_vnd`, reason, evidence_ids), best fit first, max 200, in `result.ranked_pool`; enriched on GET like picks (`_campaign_review_data`). The filter runs over it client-side; picks and alternates keep their richer objects and picks get a "Được chọn" badge; budget strip, proposal and the unfiltered layout still use the picks. No paid calls. Older saved campaigns without the field fall back to picks + alternates. Pytest `test_campaign_result_sends_scored_pool_with_per_video_price` (12 creators, pool 12 > 7 shown). |
| P2 price bands | Bands compare `price_per_video_vnd` (fallback cost/3): <2 tr, 2-4 tr, >=4 tr select the 1 / 2.5 / 5 tr tiers. Smoke selects every band and every follower tier on a pool with mixed prices (synthetic rows added by intercepting the GET) and asserts the exact id order. |
| P2 score sort | Default and "Điểm cao nhất": `fit` descending, creator id tie-breaker (`byFit`); price sorts tie-break on the same. Smoke: two rows with equal fit appear id-ascending; both price directions and score order asserted on mixed prices (also after clearing the price sort inside an active text filter). |
| P2 GET writes | `GET /api/runs/previous` opens the DB with SQLite `mode=ro`, no `_conn()`/`ensure_table`. Pytest `test_previous_runs_get_does_not_modify_database`: file bytes identical before/after, no `campaigns` table created. |
| P3 limit order | Eligibility (32-hex id, has picks) is checked first, then 10 are kept. Pytest `test_previous_runs_applies_eligibility_before_the_limit_of_ten` (ten newer pick-less runs do not hide the older one). |
| P3 smoke | Described above; the credit/USD/token guard now also runs on the filtered and the empty state before the filters are cleared. |

Checks: lint pass, build pass, smoke exit 0 with `serious_axe_violations: []`, pytest 470 passed, 1 skipped (offline, `PYTHONPATH=src`, fake keys). Logs: `docs/process/build/logs/v2_web2_r2_{lint,build,smoke,pytest}.log` (trailing blank lines stripped). Screenshots in `docs/shots/v2_web2/` regenerated; opened results_filtered_375/1440, results_empty_375, filter_drawer_375 (new badge, full-width filter field, "Hiển thị 2/6" now over the pool). Not opened: needs_run and form shots (unchanged code), results_empty_1440.

Notes: the fixture pool has only 6 scored creators, so "pool larger than picks" is proven by pytest (12) and the smoke's synthetic rows, not by the fixture itself. The "Hiển thị x/y" total is the pool size. Row numbers in a filtered list are the position in that list, not the pick rank. The `_rank` cap of 15 still bounds picks and alternates; the pool is not capped to 15.
