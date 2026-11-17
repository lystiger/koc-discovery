# EVIDENCE web5

## Scope

Replaced themes a/b/c with one light, Data-Dense Dashboard design. Removed the theme switcher, theme cookie, and request handling. Added server-rendered SVG charts for funnel, caps, weighted scores, finalist cost and score, audience shares, and video rubric. Kept mock banners and evidence links.

## Evidence

| Requirement | Result | Evidence |
|---|---|---|
| One responsive analytics dashboard | Implemented; screenshot review pending | `src/koc/web/templates/base.html`, `top5.html`, `dashboard.html`, `creator.html` |
| No theme switcher, cookie, or `?theme` behavior | Implemented | Removed theme helpers and context from `src/koc/web/app.py`; no theme selectors or attributes remain in `src/koc/web/` |
| Accessible server-rendered SVG charts | Implemented in code; runtime rendering unverified | `src/koc/web/charts.py`; each SVG emits `<title>`, `<desc>`, axis labels, and visible numeric data nearby |
| Finalist scatter and selected KOCs | Implemented; full 15-row run unverified | `adapter.get_finalists` selects up to 15 scored S2 rows and uses stored selected fees or configured rate-card estimates |
| Mock banner and evidence anchors | Preserved and covered by existing tests | `tests/web/test_app.py` |
| Python syntax | PASS | `python3 -m compileall -q src/koc/web` |
| Patch whitespace | PASS | `git diff --check` |
| Web test suite | UNPROVEN | Could not start: no `.venv/bin/pytest`; system Python reports `No module named pytest` and `No module named fastapi` |
| 375 px and desktop screenshots | UNPROVEN | No server run per instruction. Orchestrator will capture and review screenshots. |
| Impeccable automated context | UNPROVEN | Engine 0.1.22 was missing; setup needs network access and cache write permission. Skill references were read directly. |
| Git commit | UNPROVEN | `git add` could not create `.git/worktrees/KOC-Discovery-web5/index.lock`; the worktree metadata is read-only in this environment. Changes remain uncommitted. |

The fixture database contains six scored candidates, so it cannot prove the 15-candidate scatter case. The adapter limits real runs to 15 finalists.

## UI fix round 2

| Requirement | Result | Evidence |
|---|---|---|
| Chart text stays readable at desktop and mobile widths | Implemented; pixel rendering **UNPROVEN** | Score, funnel, budget, audience, and rubric bars now use HTML/CSS with fixed 12 px text in `src/koc/web/charts.py` and `base.html`. Scatter keeps a 720 × 265 px SVG in a horizontal scroll region. |
| Scatter uses data-focused domains and units | Implemented | `scatter_chart` pads min/max cost and maps scores from min − 5 to 100; axes read `Chi phí (₫ triệu)` and `Điểm`. |
| Weighted values do not concatenate | Implemented | Weighted score labels and values have separate lines in desktop rows and separate flex items in mobile cards; `top5.html`, `base.html`. |
| Mobile reasons wrap without a wide ranking table | Implemented; screenshot review **UNPROVEN** | `top5.html` renders KOC cards below 768 px; reason text uses normal card width. Desktop table remains for wider screens. |
| Every funnel stage shows its count | Implemented | `funnel_chart` emits a visible count beside each bar, including S0. |
| Rendered HTML invariants | PASS | Directly rendered top5, creator, and dashboard fixture routes; assertions passed for mobile cards, fixed scatter dimensions/units, S0 count, chart roles, and 26 creator bar values. |
| Web test suite | **UNPROVEN** | `pytest --collect-only` found 11 tests. Execution hangs on the first `TestClient` request in the available sibling virtualenv; faulthandler shows the caller waiting in `starlette.testclient` while the AnyIO portal is idle. System Python lacks pytest and FastAPI. |
| 375 px and 1440 px screenshots | **UNPROVEN** | Chromium could not start in this sandbox: crashpad reports `setsockopt: Operation not permitted`; the local fixture server also cannot bind to 127.0.0.1. Existing orchestrator screenshots were inspected before changes. |
| Syntax and whitespace | PASS | `python3 -m compileall -q src/koc/web tests/web`; `git diff --check`. |
| Git commit | **UNPROVEN** | `git add` failed because `/home/lystiger/Projects/KOC-Discovery/.git/worktrees/KOC-Discovery-web5/index.lock` is read-only. Changes remain unstaged and uncommitted. |
