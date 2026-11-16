# Integration evidence: core fixes on React branch

Branch: `ui-test/react-pick-ui-library`

Core merge: `6fb40f4745543284ff61c298565b637e09f941ee`

Real-run audit copy: `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/integration/koc.db`

Source database remained read-only.

| Must hold | Status | Proof |
|---|---|---|
| 1. Placeholder audiences show no female or age measurements or citations. | PASS | `src/koc/web/adapter.py:141,286-299` uses core placeholder detection and hides placeholder audience scores and metrics. `src/koc/web/matching_api.py:147-172` applies the same per-creator helper and treats both audience parts as missing. `src/koc/web/api.py:103-124` hides audience metrics and S2 from KOC detail. Audit of run `7372009b22764b339fbcf0f3efb4bc4e`: 10 placeholder creators; no non-null female/age metrics or female/age citations in any React creator-detail API response. Top-five cards show `audience_score=None`. |
| 2. Age slider does not use placeholder age values; gender-only data displays measured gender share and missing-age note. | PASS | `src/koc/web/matching_api.py:169-172` nulls both audience parts for placeholders. `tests/web/test_api.py:259-278` checks every placeholder gets a null audience score. `tests/web/test_matching.py:68-80` checks gender-only value `72`, `audience_age_missing=True`, and retains that value in matching. Age targets cannot affect placeholder ranking because no age part enters matching. |
| 3. Real run shows exactly five recommendations under 30M, with Vietnamese reasons and caveats, and resolving evidence. | PASS | Real-run copy returns 5 KOCs at `28,500,000 ₫` of `30,000,000 ₫`. The React route renders all 5 with Vietnamese reasons, caveats, score parts, and evidence counts. Every cited evidence ID has a target in its KOC detail; all 47 frame URLs return HTTP 200. Screenshots: `run_proposal_{375,1440}.png`, `run_koc_{375,1440}.png`. |
| 4. Python suite, React lint/build, and Playwright smoke pass. | PASS | `PYTHONPATH=src ~/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests`: `307 passed in 59.33s`. `cd web && rtk bypass npm run lint`: exit 0. `cd web && rtk bypass npm run build`: Vite built 2,363 modules, exit 0. `PYTHONPATH=src ~/Projects/KOC-Discovery/.venv/bin/python tests/web/e2e/smoke.py`: 18 screenshots, 0 serious axe violations, matching in `0.032s`. |
| 5. No network or paid calls during integration. | PASS | Work used local Git, copied SQLite DB, local FastAPI, local Chromium, pytest, npm lint/build, and Playwright. No `koc run`, `koc resume`, Kalodata, LLM, or external network calls were made. |
| 6. AC20 real-run proposal page. | PASS | `/de-xuat/<run_id>` and `/de-xuat` render the latest real run; `/de-xuat/<run_id>/koc/<creator_id>` renders KOC evidence. API returns caveats and removes placeholder audience metric rows (`src/koc/web/api.py:95-191,213-247`); UI shows only the core placeholder text, sanitized copy, and human-readable video times (`web/src/ui/pages.tsx:297-371`). Landing and header use the run first, then newest campaign, and hide both links when neither exists (`web/src/ui/LandingPage.tsx:17-22`, `web/src/ui/SharedSite.tsx:27-31`); Playwright checked fallback and hidden states. Real-run checks: 5 KOCs, `28.500.000 ₫` / `30.000.000 ₫`, no banned copy or raw metric keys, 47 frames HTTP 200. `axe`: 0 serious/critical issues at 375/1440. A4 PDF: 3 pages with logo; navigation and buttons hidden. Screenshots: `docs/build/shots/integration/run_proposal_{375,1440}.png`, `run_koc_{375,1440}.png`. Selected editorial palette and fonts remain documented in `docs/build/DESIGN.md:72-97` (ground `#F6F3EE`, paper `#FFFDF9`, green `#2F5D50`, Newsreader, Be Vietnam Pro). |

## Screenshots

Landing, campaign, KOC, and operator baseline screenshots use the React SPA or existing Jinja operator routes. The real run proposal and KOC detail screenshots below use the new React routes.

- `docs/build/shots/integration/landing_375.png`
- `docs/build/shots/integration/landing_1440.png`
- `docs/build/shots/integration/top5_375.png`
- `docs/build/shots/integration/top5_1440.png`
- `docs/build/shots/integration/creator_375.png`
- `docs/build/shots/integration/creator_1440.png`
- `docs/build/shots/integration/dashboard_375.png`
- `docs/build/shots/integration/dashboard_1440.png`
- `docs/build/shots/integration/run_proposal_375.png`
- `docs/build/shots/integration/run_proposal_1440.png`
- `docs/build/shots/integration/run_koc_375.png`
- `docs/build/shots/integration/run_koc_1440.png`

## Merge resolution

- `.gitignore`: union of core and React entries.
- `docs/build/DESIGN.md`: core design first; approved React editorial direction after it.
- `src/koc/web/adapter.py` and `src/koc/web/app.py`: core data logic with React API router, SPA fallback, and existing Jinja routes.
- `src/koc/web/matching_api.py` now imports `placeholder_audience_creators` from `koc.stages`; duplicate placeholder detection was removed.
