Overall FAIL

Reviewed `fa1df3e..50fcdd8` and `0f5c03e..50fcdd8`. Deferred wave 2 features excluded.

- **P2 — r1 OPEN, partially fixed:** [web/src/ui/pages.tsx:128](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a860491c95b9dccca/web/src/ui/pages.tsx:128) falls back to cited videos for saved campaigns lacking `analysed_video_ids`. Campaign GET enrichment at [src/koc/web/api.py:152](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a860491c95b9dccca/src/koc/web/api.py:152) never supplies that field. Replayed `fa1df3e` campaign creation, persisted it in memory, then applied HEAD’s GET enrichment and React rendering: **7/15 links remain**, including “Máy xem 1 video” for creators scored from three. New campaigns and run proposals expose 15/15. Enrich older saved campaigns from their recorded `run_id`; add a saved-campaign regression test.
- **P3 — r1 CLOSED:** [tests/web/e2e/smoke.py:604](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a860491c95b9dccca/tests/web/e2e/smoke.py:604) now requires a real no-frame fixture row and checks quote position and width. Restoring the thumbnail-column layout would fail these assertions.
- **P3 — OPEN, stale visual evidence:** [docs/build/EVIDENCE_v2_web_ux.md:47](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a860491c95b9dccca/docs/build/EVIDENCE_v2_web_ux.md:47) references expanded screenshots that still display raw `brand_fit`. Both screenshots predate `bde79f6`; HEAD produces Vietnamese wording. Refresh those captures.

No P1 or additional P2 found.

| Command/check | Result |
|---|---|
| `npm run lint && npm run build`, isolated archive of HEAD | **PASS**, exit 0. Asset filenames and sizes match supplied build log. |
| `PYTHONPATH=src …/python -m pytest -q -p no:cacheprovider tests/core/test_brand_fit_gate.py tests/core/test_run_analyses.py` | **21 passed**, 8.51s; main repository venv used. |
| Read-only API checks and React markup checks | Five KOC pages each expose all three video anchors, content links, and TikTok links. Four exclusions contain 12 video scores. |
| Historical campaign replay | **FAIL:** saved result still renders 7/15 content links. |
| Supplied full pytest log | **431 passed, 1 skipped**. Source/tests unchanged since recorded `bde79f6`. |
| Supplied smoke log | Reports 27 screenshots and zero serious axe violations; smoke source matches HEAD. Browser execution not independently repeated because sockets are unavailable. |
| `git diff --check 0f5c03e..HEAD` | **PASS**. |

Python additions are small, read-only enrichments. Focused tests cover analysed IDs and exclusion scores; Vietnamese gate wording is asserted. Missing coverage concerns saved campaigns.

Opened all three new screenshots. Expanded layouts and method landing look readable; print appearance remains **UNPROVEN**.

Source/tests unchanged. Database opened only with `mode=ro`.