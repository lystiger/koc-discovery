# Brand platform evidence

## Readability round (B25, B26, AC21, I1-I4)

| ID | Verdict | Proof |
|---|---|---|
| AC21 / B25. Three-part KOC review | PASS | `src/koc/web/api.py:97-156,236-241` matches metric citations per point and moves detected audience caveats into one note. `web/src/ui/pages.tsx:104-124,295-304,329-356,462-477` renders bulleted strengths/weaknesses, 15 px text at 1.55 line-height, and two columns from 768 px. Real run `7372009b22764b339fbcf0f3efb4bc4e`: all five KOC pages show the audience note once, with none in review blocks; desktop max height 2,236 px at 900 px viewport. |
| AC21 / I1. Numbered evidence markers | PASS | `src/koc/web/api.py:108-135,287-324` separates matched metric IDs from video/transcript IDs. `web/src/ui/pages.tsx:73-105,462-490` numbers point metrics and shows video markers once under the review block; markers resolve to rows and briefly highlight them. `tests/web/test_api.py:282-313` checks point matching. Real run audit: no point holds all cited IDs, every metric marker matches its raw key/label, and video markers stay outside points on all five KOCs. |
| AC21 / B26. KOC evidence table and disclosures | PASS | `src/koc/web/api.py:211-223` reuses the same video's nearest frame within 3 seconds. `web/src/ui/pages.tsx:478-490` orders sections, sorts cited moments, and leaves rows without a nearby frame as time chips. Real screenshots at 375/1440 are in `docs/build/shots/readability/real/`; all frames loaded, no “Không có ảnh” boxes appeared, desktop max height was 2,236 px. |
| AC21 / I2. Metric units | PASS | `web/src/ui/pages.tsx:484-500` formats shares and rates as percentages, money in ₫ with nghìn/triệu, and revenue trends with a signed daily unit. Real KOC screenshots show these units. |
| AC21 / I3. Numbers in review prose | PASS | `web/src/ui/pages.tsx:50-59` formats large decimals for display and converts fractional values next to share labels to percentages. Stored database values remain unchanged. Real KOC screenshot shows `508.440,73` as `508.441`. |
| AC21 / I4. Run proposal budget allocation | PASS | `web/src/ui/pages.tsx:303-310` segments the budget by each KOC's share and labels each share. `web/src/styles.css` makes segments contiguous. Browser smoke checks segment widths sum to the track width. Real proposal PDF and screenshots show all five allocations. |
| AC21. Responsive, accessibility, and PDF verification | PASS | `KOC_REAL_RUN_COPY=/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/audit2/koc.db PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/pytest -q tests` → 316 passed, 1 skipped. `cd web && npm run build && rtk bypass npm run lint` passed. `tests/web/e2e/smoke.py` → 18 screenshots, 0 serious axe violations, PDF has 3 A4 pages. Real run audit: five KOCs at 375/1440, one audience note, no horizontal overflow or missing-frame boxes, all frames loaded, max desktop height 2,236 px. Artifacts: `docs/build/shots/readability/`. |
| AC21 / Campaign list (`FIX_campaign_list.md`) | PASS | `src/koc/web/campaigns.py:49-58` returns picked count newest-first. `web/src/ui/pages.tsx:141-178` renders the titled empty state and campaign cards with counts, statuses, budget, local date/time, and proposal links. `web/src/ui/SharedSite.tsx:25-42` marks the navigation item active; `web/src/ui/App.tsx:112` removes duplicate header CTA on the list. `cd web && npm run build` and `./node_modules/.bin/eslint src --max-warnings=0` passed. One-shot Playwright check: empty DB and three campaign cases (0/5, 3/5, 5/5) at 375/1440; exactly one page primary CTA; proposal sample link hidden without a run and shown with a run; no horizontal overflow; reduced-motion mascot stops; keyboard reaches all three cards; 0 serious axe violations. Screenshots: `docs/build/shots/readability/campaigns_empty_{375,1440}.png`, `campaigns_list_{375,1440}.png`. |

Round 4 fixes complete. Criterion 13 remains UNPROVEN until Lystiger reviews the visual direction.

## Round 6 fixes

| ID | Verdict | Proof |
|---|---|---|
| R1. Separate filled audience scoring from observed display and confidence | PASS | `src/koc/web/matching_api.py:98-116` keeps B20 pool-minimum fills and tracks real audience parts separately. `src/koc/web/matching.py:19-32` uses filled values for fit, but excludes unobserved audience from components and confidence. Missing S2 and placeholder-only cases: `tests/web/test_api.py:260-305`; gender-only data and age note: `tests/web/test_matching.py:68-80`. KOC detail hides audience score/metrics without real S2 at `src/koc/web/api.py:98-122`. Results show “Chưa phân tích” and the missing-age note at `web/src/ui/pages.tsx:202-212`; proposal shows its audience status at `web/src/ui/pages.tsx:257-260`. |
| R2. En dash in age ranges | PASS | `src/koc/web/matching_api.py:24-30` normalizes all two-digit ranges in reasons and rubric text. `web/src/ui/pages.tsx:43-48,175` formats visible copy and age ticks. `tests/web/test_matching.py:101-103` covers “độ tuổi 18–24” and rubric “18–30 tuổi”. |
| R3. Phone header CTA text and one-row layout | PASS | `web/src/ui/SharedSite.tsx:37` provides short visible “Bắt đầu” plus the full accessible name. `web/src/styles.css:53,249-261` shows it without wrapping at phone width. `tests/web/e2e/smoke.py:162-171` checks text, nowrap, CTA visibility and header height ≤70 px. Screenshots: `docs/build/shots/react/chromium/landing_375.png`, `results_375.png`. |

Round 6 verification: `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/pytest -q tests` → 90 passed; `cd web && npm run build` passed; `rtk bypass npm run lint` passed. Browser smoke → 14 screenshots at 375/1440 px, 0 serious axe violations, matching in 0.014 s. Screenshots live in `docs/build/shots/react/chromium/` and were visually inspected at phone and desktop widths. Criterion 13 remains UNPROVEN until Lystiger reviews.

## Round 5 fixes

| ID | Verdict | Proof |
|---|---|---|
| A1. Missing audience sub-parts use pool minima | PASS | `src/koc/web/matching_api.py:85-115` scores gender and age separately, fills missing parts from per-part pool minima, and caps a filled average at the creator's observed-part average. `tests/web/test_matching.py:54-89` reproduces audience 60.0 → 82.5 and fit 81.92 → 86.42 without the fix; it also covers gender-only targets, no age values in the pool, and monotonic missingness. `tests/web/test_api.py:163-185` deletes one creator's 25–34 metric on the fixture DB copy and confirms audience and fit do not rise. |
| A2. Phone header CTA stays on one row | PASS | Round 6 replaces the icon-only CTA with visible “Bắt đầu”; see R3. |
| A3. Age ranges use en dashes | PASS | Round 6 normalizes reason and rubric copy plus visible age ticks; see R2. |

Round 5 verification: `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/pytest -q tests` → 89 passed; `npm run build` passed; `rtk bypass npm run lint` passed; Playwright smoke → 14 screenshots, 0 serious axe violations. Screenshots were visually inspected at 375 and 1440 px.

Landing style record: UI-UX Pro Max searches surfaced generic Brutalism/pink/Inter recommendations. B12 and B15-B16 already fix the selected editorial direction, so the React landing keeps warm paper `#F6F3EE`, deep green `#2F5D50`, clay `#B5643C`, Newsreader headings, and Be Vietnam Pro body text. Tokens live in `web/src/styles.css`.

| AC | Verdict | Proof |
|---|---|---|
| 1. Form validation and save | PASS | `tests/web/e2e/smoke.py:230-278` checks inline validation, valid save, 1.2-second search state, result route, and Sonner success toast. API errors return inline at `web/src/ui/pages.tsx:89-106`. |
| 2. Matching rules, budget, MCN, speed | PASS | Full suite: `79 passed in 12.99s`. Browser smoke: 5 picks, under budget, distinct MCNs, `0.012s`. `tests/web/test_matching.py` checks the pool minimum fill and confidence. Real DB copy probe with default follower range and MCN rule: count 5 has five “Một phần”; count 10 has nine “Một phần” and one “Sơ bộ”. Picks recorded under Round 3 N1. |
| 3. No technical data on brand pages | PASS | `tests/web/e2e/smoke.py:128-131` scans form, results, proposal, and KOC detail at both widths. |
| 4. Missing and placeholder scores render correctly | PASS | `tests/web/test_api.py:260-305` checks placeholder-only and no-S2 rows: filled fit does not rise, displayed audience is null, confidence excludes it, and KOC detail hides missing audience metrics. UI renders “Chưa phân tích” in results, detail and proposal: `web/src/ui/pages.tsx:202-212,257-260`; placeholder and missing-detail browser checks: `tests/web/e2e/smoke.py:390-410`. |
| 5. Printable A4 proposal, at most 3 pages | PASS | `tests/web/e2e/smoke.py:308-333` verifies the A4 PDF, no screen controls, and a non-zero proposal logo box in print. `docs/build/shots/react/proposal_1440.pdf` renders the stacked logo on page 1 and remains within 3 pages. |
| 6. Search partial handle | PASS | `tests/web/e2e/smoke.py:300-305` searches `chou.bea` and opens creator detail. |
| 7. Mobile sheet and desktop detail | PASS | Direct detail route opens a Vaul sheet at 375 px: `tests/web/e2e/smoke.py:158-159`. Results remain underneath during client-side navigation: `tests/web/e2e/smoke.py:280-286`. |
| 8. Operator cost totals match shared query | PASS | `tests/web/test_api.py:54-64` compares API totals with `queries.run_costs`. |
| 9. Required UI libraries; no hand-built twins | PASS | `web/package.json:11-36` retains base-ui, cmdk, vaul, sonner, NumberFlow, and recharts. B19 removed clsx from this criterion because the app does not use it. |
| 10. Tests, build, and lint | PASS | Round 6: `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/pytest -q tests`: 90 passed. `npm run build` and `rtk bypass npm run lint` exit 0. Playwright smoke: 14 screenshots, 0 serious axe violations, matching in 0.014s. |
| 11. Vietnamese UI labels | PASS | `src/koc/web/adapter.py:30-38` and `web/src/ui/pages.tsx:225-230` use Vietnamese metric labels, including an explanation for GPM. `tests/web/test_api.py:137-138` asserts rendered reason labels. |
| 12. Responsive screenshots and axe | PASS | Round 6 smoke produces 14 screenshots at 375/1440 px in `docs/build/shots/react/chromium/`. Axe reports 0 serious violations. Header CTA checks are in `tests/web/e2e/smoke.py:162-171`; KOC evidence links have distinct accessible names (`tests/web/e2e/smoke.py:239-241`). |
| 13. Match picked taste direction | UNPROVEN | Implementation screenshots: `docs/build/shots/react/`. The picked reference is `design/taste/a-ban-de-xuat.html`. Lystiger visual review is still required. |
| 14. Landing, sample proposal, and trust counts | PASS | `GET /api/stats` counts the latest S1 pool, creators with S3 scores, and analyzed video IDs in `src/koc/web/api.py`. `tests/web/test_api.py:48-72` compares each value to direct fixture SQL. `tests/web/e2e/smoke.py:74-109,159-168` checks the no-campaign state, both start CTAs, newest proposal link, and three rendered stats. Visual comparison: `docs/build/shots/react/landing_1440.png` and `landing_375.png` against `design/landing/shots/hero-b-1440.png` and `hero-b-375.png`. |
| 15. Reduced motion and mobile overflow | PASS | `tests/web/e2e/smoke.py:309-339` checks reduced-motion landing visibility and skips searching animation on submit. It also checks normal-motion hero art, handoff, budget strip, and 375 px overflow. |
| 16. Campaign list route and links | PASS | `web/src/ui/App.tsx:50-56,91-105` routes navigation and palette entries to `/chien-dich`. Form cancel links there in `web/src/ui/pages.tsx`; smoke checks route, cancel action, and palette navigation. `tests/web/test_api.py:75-90` verifies newest-first campaign ordering. |
| 17. DETOLA logo, icons, titles, fonts, and hero asset | PASS | `web/src/ui/pages.tsx:219` restores the stacked lockup on the proposal. `tests/web/e2e/smoke.py:308-333` checks screen visibility and non-zero print-media bounds. `docs/build/shots/react/proposal-print-page-1.png` shows the logo in print. Other assets and title checks remain as above. |
| 18. Shared product chrome, titles, steps, and search state | PASS | `web/src/ui/SharedSite.tsx:8-12` shortens step labels. `web/src/styles.css:60,53,237-243` uses the landing pill size and a 200 px mobile logo. `tests/web/e2e/smoke.py:159-165,186-201,263` checks 50 px / 16 px primary pills, mobile logo width, non-touching step labels, and evidence navigation. Screenshots: `docs/build/shots/react/{form,results,landing}_{375,1440}.png`. |
| 19. Contiguous age target, range slider, scoring, and labels | PASS | `src/koc/web/api.py:15-25` validates ordered contiguous buckets with Vietnamese 422 messages. `src/koc/web/matching_api.py:98-116` keeps pool-minimum scoring and exposes whether selected age data is missing. `tests/web/test_api.py:100-185,280-305` checks range rules, legacy input, sub-part scoring and no-S2 confidence/display; `tests/web/test_matching.py:54-97` checks missing age, gender-only data and en dashes. `tests/web/e2e/smoke.py:228-237,298-301` checks chip state, slider keyboard use, accessible labels and visible en-dash ticks. |

## Round 4 fixes

| ID | Status | Proof |
|---|---|---|
| C1. Stacked proposal logo on screen and in print | PASS | `tests/web/e2e/smoke.py:308-333` checks screen visibility and non-zero print-media bounds. `docs/build/shots/react/proposal-print-page-1.png` shows the logo in the A4 PDF. |
| C2. One results evidence link per KOC, named detail links | PASS | `tests/web/e2e/smoke.py:188-201,239-241,263` checks at most one count link per row, `#evidence` navigation, per-item type names, and unique accessible names. |
| C3. Consistent primary pill size | PASS | The smoke checks every `.pill-button` on all seven routes at both widths: 50 px tall and 16 px text. |
| C4. Mobile header logo and step labels | PASS | At 375 px, smoke checks a 200 px wordmark and non-overlapping step label bounds. Screenshots: `docs/build/shots/react/landing_375.png` and `form_375.png`. |

## Round 2 defects

| ID | Verdict | Proof |
|---|---|---|
| D1. Largest valid affordable set below requested count | PASS | `tests/web/test_matching.py:78-99` covers MCN conflicts, undersized pools, budget-limited sets, and the found/requested warning. |
| D2. Explain zero picks; edit action; hide proposal action | PASS | `tests/web/test_matching.py:102-105` checks the empty-pool warning. `tests/web/e2e/smoke.py:273-277` checks “Sửa yêu cầu” and no proposal link. |
| D3. Omit components absent from the whole pool | PASS | `tests/web/test_matching.py` checks all-missing components are excluded and missing values use the minimum observed pool score under B20. |
| D4. Render evidence links only for existing targets | PASS | Fixture tests check existing targets. Real DB copy browser probe rendered 33 “Xem bằng chứng” links; the first link resolved to `7685681792774409493:transcript:2`. Cited videos are included in creator detail even when beyond its first five videos. Screenshot: `docs/build/shots/react/real_results_1440.png`. |
| D5. Wrap long brand names on screen and in print | PASS | `web/src/styles.css:33,53` enables wrapping. `tests/web/e2e/smoke.py:288-295` checks 60 unbroken characters at 375/1440 px and print media. |
| D6. Rate-card gaps never cost 0 ₫ | PASS | Decision: use the nearest configured tier and retain the UI’s “ước tính / video” label. `src/koc/web/matching_api.py:110-120` selects the nearest tier. `tests/web/test_api.py:131-147` checks a 500,000-follower creator receives the 5,000,000 ₫ estimate. |
| D7. Results remain under mobile KOC sheet | PASS | `web/src/ui/App.tsx:74-102` renders the background route and detail overlay; result links use React Router state in `web/src/ui/pages.tsx:149-157`. Smoke assertion: `tests/web/e2e/smoke.py:280-286`. |
| ESLint included in lint; clsx criterion removed | PASS | `web/package.json:6-9` runs `tsc -b` and ESLint. `web/eslint.config.js` defines ESLint flat config. B19 amends AC9; clsx stays absent. |

## Round 3 defects

| ID | Verdict | Proof |
|---|---|---|
| AC5. Hide screen-only controls in print | PASS | `.skip-link` is hidden in `web/src/styles.css`; PDF text check in `tests/web/e2e/smoke.py` confirms its label is absent. |
| AC9. clsx requirement removed by B19 | PASS | No dependency change. AC9 evidence now reflects B19: only use of listed UI libraries and absence of hand-built twins matter. |
| AC11. Translate stored metric keys | PASS | `display_reason_text` uses `METRIC_LABELS_VI`. Real DB copy results and creator detail show Vietnamese labels; browser scan found none of the four reported raw keys. |
| AC12. Valid allocation semantics with zero picks | PASS | `.allocation` has `role="img"`; smoke runs axe rule `aria-prohibited-attr` on a zero-pick results page with no violations. |
| N1 / B20. Fill missing scores with pool minimum | PASS | `tests/web/test_matching.py` expects fit 70.0 rather than the 25th-percentile fit 77.0. Real DB copy, count 5: `@meixiuriviu`, `@teetamofficial`, `@ducvietbe__`, `@dunghana2882`, `@rio100806` (all “Một phần”). Count 10 adds `@emduyencantho`, `@dieuduong_quynhhoa`, `@gaixinhh114`, `@k_dung26` (all “Một phần”), and `@cleanboy.tips` (“Sơ bộ”). |
| N2. Resolve real DB evidence IDs | PASS | `cited_evidence_ids` supports metric IDs, numeric video IDs, timestamps without `v_`, and transcript IDs. Result page shows 33 evidence links; clicked transcript link resolves to a DOM target. Detail API includes cited videos outside the default first five. |
| N3. Landing matches mock | PASS | Smoke confirms hero `<em>` is italic, the 375 px “Bắt đầu” button stays on one line, and the trust heading is centered. Viewed `landing_375.png` and `landing_1440.png`; both preserve the selected layout and palette. |
| N4. Empty database message | PASS | Browser smoke empties fixture scores and verifies “Chưa có dữ liệu KOC”; a populated DB with an empty follower-range still gets the follower-range message. |

## Coherence round defects

| ID | Verdict | Proof |
|---|---|---|
| N5. Evidence cleanup preserves clock times | PASS | `tests/web/test_matching.py:5-15` keeps `20:30:15` intact while matching timestamp, metric, and transcript evidence IDs. |
| N6. Operator page has no page-level horizontal scroll | PASS | `docs/build/shots/react/operator_real_375.png` uses a copy of the real DB. Browser measured `document.documentElement.scrollWidth=375` at a 375 px viewport; table scroll stays in its wrapper. |
| N7. Metric labels use Vietnamese explanations | PASS | `src/koc/web/adapter.py:30-38` and `web/src/ui/pages.tsx:225-230` translate GPM, views, skincare, follower range and video/live labels. API test checks the GPM and skincare labels. |
| N8. Printed proposal ends without a beige block | PASS | A4 PDF has 2 pages. `docs/build/shots/react/proposal-last-page-2.png` shows the final page; print CSS sets page surfaces to white in `web/src/styles.css`. |

Real DB probes used writable copies of `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier2/real.db` under `/tmp`. Campaign writes were confined to those disposable copies. No production database writes occurred.

## Budget refusal, leftover and review list fix (D-B1, D-B2)

| ID | Verdict | Proof |
|---|---|---|
| D-B1. Refused campaign and next choices | PASS | `web/src/types.ts:34-55` models `status`, `options`, `warnings`, and `leftover_vnd` without reading dropped `picks` or singular `warning`. `web/src/ui/pages.tsx:142-185,372-409` fetches result status for campaign chips, defaults missing status to the existing success flow, lists every warning, hides null options, and resubmits the same input with one selected change. `tests/web/e2e/budget_refusal.py:116-166` covers all three retries, retained brand fields, null options, list chip, and no proposal link. Screenshots: `docs/build/shots/readability/refuse_{375,1440}.png`. |
| D-B2. Leftover budget on results, proposal, and run proposal | PASS | `web/src/ui/pages.tsx:297-308,441-449` displays `leftover_vnd` when supplied and shows the exact “Còn lại … chưa dùng” copy on all three pages. The focused Playwright run checks 2.000.000 ₫ on results, proposal, and run proposal at 375/1440; `tests/web/e2e/budget_refusal.py:168-197`. |
| Compact strengths and weaknesses | PASS | `web/src/ui/pages.tsx:104-106,327-343,490-497` keeps markers after each point and renders results/run proposal review columns. `web/src/styles.css:233-239` sets compact bullets; results span the card width. Browser assertions check both columns, bullet style, and inline markers. Screenshots: `docs/build/shots/readability/lists_{375,1440}.png`. |
| Lint, build, smoke, and axe | PASS | `cd web && rtk bypass npm run lint && rtk bypass npm run build` passed. `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python tests/web/e2e/budget_refusal.py` passed with mocked `page.route` responses and 0 serious/critical axe violations. `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python tests/web/e2e/smoke.py` passed: 18 screenshots, no serious axe violations. The smoke CTA check now skips the campaign list, which hides that CTA in `web/src/ui/App.tsx:112`. |

## Shared interactive budget strip (FIX_money_bar.md)

Style follows approved direction A in `design-system/koc-discovery/MASTER.md`: warm paper `#f6f3ee`, green `#315f53`, clay `#b5643c`, Newsreader and Be Vietnam Pro. Generic search suggestions did not override the approved mock.

| ID | Verdict | Proof |
|---|---|---|
| MB1. Shared landing-style strip | PASS | `web/src/ui/BudgetStrip.tsx:35-87` renders the same rounded track, clay initial chips, compact creator amounts and names, and remaining segment. `web/src/ui/LandingPage.tsx:93` and `web/src/ui/pages.tsx:349,418,467` use it on landing, results, campaign proposal and run proposal. Viewed `money_landing_{375,1440}.png`, `money_results_{375,1440}.png`, `money_proposal_{375,1440}.png`, and `money_run_proposal_{375,1440}.png`; remaining label and amount fit at both widths. |
| MB2. Unspent amount stays visible | PASS | `web/src/ui/BudgetStrip.tsx:38-39,66-78` gives small leftovers at least `max(12%, 4.5rem)`, adds short amount inside the hatched segment, and prints the exact unused amount below. Smoke asserts positive width and visible copy on every route. |
| MB3. Full-width allocation | PASS | `web/src/styles.css:141,144-161` lets the track fill its strip and shrinks creator segments proportionally. Landing demo spans its content column. Smoke checks run-proposal segment widths sum to track width within 2 px. |
| MB4. Keyboard, pointer, touch and row feedback | PASS | `web/src/ui/BudgetStrip.tsx:48-55,109-145` supports arrows, Home/End, hover, focus, click, touch popover and creator links. `web/src/ui/pages.tsx:313-319,335-356,404-424,448-475` highlights matching creator rows. Smoke checks keyboard movement, hover, click, touch and popup contents. Tooltip capture: `money_tooltip_1440.png`. |
| MB5. Accessible text, reduced motion and print | PASS | `web/src/ui/BudgetStrip.tsx:79-85` supplies a visually hidden amount/share list and static print labels. `web/src/styles.css:388-390,422-426` disables reveal transitions, hides popovers and prints labels. Smoke runs axe with popup open (0 serious violations), reduced-motion assertions, and PDF text checks including `5 tr` and leftover copy. |
| MB6. Build and responsive smoke | PASS | `cd web && npm run build` and `rtk bypass npm run lint` passed. `PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python tests/web/e2e/smoke.py` passed: 27 screenshots, 0 serious axe violations, matching in 0.046 s. Screenshot artifacts: `docs/build/shots/readability/money_*.png`. |

## Needs-run campaign state (FIX_needs_run.md)

| ID | Verdict | Proof |
|---|---|---|
| D-B3/D-B4. Needs-run instructions and campaign status | UNPROVEN | `web/src/ui/pages.tsx:172-185,340-341,361-403` renders the needs-run state, dry-run and real commands, copy buttons, refusal warning from the first note, and “Chờ chạy dữ liệu” list chip. `web/src/types.ts:39-46` declares status and command fields. `npm run build` passed. `npm run lint` failed with 3,417 diagnostics in generated JavaScript under `web/src`. Browser smoke was attempted once but could not bind its local socket: sandbox `PermissionError`; visual, copy, and axe behavior remain unverified. |
