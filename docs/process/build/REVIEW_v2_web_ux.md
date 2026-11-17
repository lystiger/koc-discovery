Overall FAIL

Reviewed `0f5c03e..daa560c` on `v2/web-ux`. One P2 remains open. Source and tests unchanged.

- **P2 — [web/src/ui/pages.tsx:615](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a860491c95b9dccca/web/src/ui/pages.tsx:615): Incomplete content evidence.** Tee Tám’s score uses three analysed videos, but Nội dung links only one. Across five picks, boxes link **7/15 analysed videos**. Omitted videos also lack TikTok links and anchor targets in “Video khác.” Results/proposals misleadingly say “Máy xem 1 video.” Link every contributing video and count analysed videos separately from citations.
- **P3 — [tests/web/e2e/smoke.py:599](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a860491c95b9dccca/tests/web/e2e/smoke.py:599): Vacuous D4 assertion.** `count() >= 0` passes even when every no-frame row disappears. Assert a real fixture row and its layout.

| Requirement | Independent evidence |
|---|---|
| TikTok URLs, missing handles, `noopener`, accessible names | Source and React-rendered markup verified; five missing/placeholder-handle cases produce no link. All emitted TikTok links have `_blank` and `noopener noreferrer`. All-video coverage fails above. |
| Print profile URL | Correct short URL exists; print CSS enables it. Actual PDF appearance **UNPROVEN**. |
| Brand-fit exclusions | Correctly counts **4 failures**, separately lists **51 unanalysed KOCs**. All 12 per-video scores match read-only data. Disclosure source supplies scores and TikTok links; interactive expansion **UNPROVEN**. |
| Score breakdown | **45/20/35**, Vietnamese explanations, and missing-audience “Chưa có dữ liệu” verified across five picks. No audience zero. Emitted anchors resolve; eight analysed videos remain omitted. |
| “Cách chấm điểm” | Matching links and section IDs verified on results, proposals, and KOC pages. Browser click behaviour **UNPROVEN**. |
| D4/D5/D6 | All six supplied screenshots opened. Wide no-frame quotes and full-width proposal lists look fixed. Rendered frame names include timestamps. |
| Python changes | Minimal read-only enrichment: adapter `+18`, matching API `+2/-2`. All **13 brand-fit tests pass offline**. |

| Command/check | Result |
|---|---|
| `cd web && npm run build` | **PASS** in isolated copy. Original dependency symlink caused sandbox `EROFS`. |
| `npx eslint src --max-warnings=0` | **PASS**, exit 0; used `rtk bypass` to preserve command semantics. |
| Evidence’s `tests/web/e2e/smoke.py` | **BLOCKED** before assertions: socket creation raises `PermissionError`. |
| axe, zero serious | **UNPROVEN**; smoke could not start. |
| Full pytest under `unshare -rn`, fake keys | **UNPROVEN**: 431 collected, 51 passed, then TestClient stalled. Bounded retry also stalled. |
| Fresh Chromium screenshots | **BLOCKED** by sandbox socket restrictions. |

Full A5 also retains the builder-declared deferred header filters and sorting.

[Detailed review and evidence](/tmp/koc-web-independent-review/REVIEW.md). Original database accessed only through `sqlite3 -readonly … .backup`.