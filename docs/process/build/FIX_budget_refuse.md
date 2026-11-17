# Fix: refusal UI (D-B1), leftover budget display (D-B2), strengths/weaknesses list polish. FRONTEND ONLY

Decisions: `~/Projects/LysStack/projects/koc-discovery/brief.md` D-B1, D-B2. Same rules as `BRIEF_brand_platform.md`.
Scope (Lystiger, 2026-11-16): this branch does the frontend only. The core session owns the matching logic
(`src/koc/web/matching.py`, `matching_api.py`) and implements the refusal in the API. Do not edit any Python file.

## API contract the core session will implement (build the UI against it)
`POST /api/campaigns` and `GET /api/campaigns/{id}` result, when no valid set of exactly N exists:
```
"result": {"status": "refused", "picked": [], "warnings": [str, ...], "leftover_vnd": int, "budget_vnd": int,
  "options": {
    "max_count_within_budget": {"count": int, "cost_vnd": int} | null,
    "min_budget_for_count":    {"budget_vnd": int} | null,
    "cheaper_follower_band":   {"follower_min": int, "follower_max": int, "cost_vnd": int} | null }}
```
Otherwise `status: "ok"` and the existing fields plus `leftover_vnd`. Core also sends `picks` and the singular
`warning` for now; do not read them, they will be dropped. Declare status, options, warnings, leftover_vnd in `types.ts`.

## Build
1. Refused result page: a clear panel "Ngân sách chưa đủ cho N KOC" (warnings listed, none overwritten) and up to three
   choice cards: "Chọn k KOC (x ₫)", "Tăng ngân sách lên y ₫", "Đổi sang người theo dõi a–b (z ₫)". Each re-submits
   the campaign with that change (new campaign, same brand fields) and opens its result. Hide null options. No proposal
   link while refused. Campaign list chip: "Ngân sách chưa đủ". Until the API sends `status`, treat a missing status as "ok".
2. D-B2: show the leftover as "Còn lại 1.500.000 ₫ chưa dùng" on results, proposal and run page.
3. Polish (orchestrator review of `9bd8e86`): strengths/weaknesses as compact bulleted lists (bullet dots on both
   columns, no bordered row per point, no large padding), the two columns use the full card width, markers inline at
   the end of a point. Results and run proposal.
4. Tests: Playwright with a mocked refused response (`page.route`) covering all-options, some-null options and the
   re-submit of each option; leftover text on results/proposal/run page.

Verify: lint, build, the smoke, axe; screenshots of the refused state and the polished lists at 375/1440 into
`docs/process/build/shots/readability/` (`refuse_*`, `lists_*`). Add evidence rows, commit, stop.
