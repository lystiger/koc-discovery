# VERDICT: ui/readability (TEST gate)

- Branch `ui/readability` @ `1829c08`; diff `feat/koc-mvp...HEAD -- web/`.
- Verifier: Claude (independent of the Codex builder). Date 2026-11-16.
- Scratch dir: `S=/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier3`. Paths below are relative to `$S`.
- Data: read-only `.backup` of `data/koc.db`, taken after the core S4 rerun. Run `7372009b22764b339fbcf0f3efb4bc4e` returns 5 picks: 7485602050560148487 3M, 7594293671543079957 7.5M, 6730533371858437121 7.5M, 7164572563820250139 3M and 6872721641991209985 7.5M. The total is 28.500.000 ₫ of 30.000.000 ₫. This matches the coordinator's expected values, and the strip shows these 5 segments in this order (`rp_top.png`).

## Overall (r1): **FAIL**. Superseded by r2 below: **PASS**.

There are two FAILs on Medium items and one on a High item:

- The required smoke gate is red (High).
- The run proposal and campaign proposal lists are wrong (Medium).
- axe reports serious violations on the budget strip (Medium).

## Gates

| Check | Result | Proof |
|---|---|---|
| `npm run lint && npm run build` | PASS | The build finished: `✓ built in 2.96s`, with no lint output. |
| `tests/web/e2e/smoke.py` | **FAIL** | `smoke.py:94 assert len(campaign["result"]["picked"]) == 5` raised `AssertionError`. After the merge, the core's shared pricing refuses the fixture's 30M/5 campaign. A direct probe (`$S/probe.py`) returns `refused 0 ['Ngân sách 30.000.000 ₫ chưa đủ cho 5 KOC: cần tối thiểu 60.000.000 ₫.']`. The smoke stops at that line, so none of the branch's smoke checks ran: strip, keyboard, popover, refusal mocks, needs_run mocks and axe. |
| api.py merge `a73321d` | PASS | `src/koc/web/api.py:14` keeps both imports (`METRIC_LABELS_VI` and `normalize_result`). `api.py:377` uses `_campaign_review_data(conn, {**result, "result": normalize_result(...)})`, which keeps the HEAD shaping and the core normalisation. `create_campaign` (`api.py:357-365`) keeps `result_for_campaign` and `_campaign_review_data`. pytest was not run. |
| Orchestrator commit `1829c08` | PASS (with a note) | The breakdown labels are nowrap with an ellipsis. The popover opens above the strip (`side="top"`). The needs-run chip colour is added. "Còn lại" is never ellipsised: the clip probe lists only KOC names (`out.json` `pages.*.clip`), and `land_strip375.png` shows "Còn lại / 1,5 tr" in full. Note: on the landing page at 375 px, the popover opened above the strip covers the caption and the total (`land_strip375.png`). This is acceptable for a transient popover. |

## BRIEF_readability.md and AC21

| Item | Verdict | Proof |
|---|---|---|
| Tóm tắt line, one helper, thresholds | PASS | `koc_7594293671543079957_1440.png`: "Phù hợp 76/100 · bán hàng mạnh (88) · nội dung khá (60) · chưa có dữ liệu khán giả". This also appears on the results and run pages. |
| Điểm mạnh and Điểm yếu in two columns at ≥768 px, stacked below | PASS on the KOC page and results; see FIX_budget_refuse §3 for the proposals | On all 5 KOC pages at 1440 px, the columns are on the same row (`koc.json` `swcols.sameRow:true`, x=120 and x=732). At 375 px they are stacked (`koc_7594293671543079957_375.png`). |
| Shared audience caveat shown once per page, never inside a KOC | PASS | The run page has 1 "Kalodata" note above the list (`out.json` `run_proposal@*.audNote:1`) and none in the Điểm yếu lists. Each KOC page has at most 1 (`koc.json`). |
| Numbered markers that resolve and highlight | PASS | 0 unresolved `#` hrefs on the run page and on 5 KOC pages. 0 duplicate accessible names (`koc.json` `labels.dups:[]`). Clicking "Bằng chứng 1" adds `evidence-highlight` to the matching metric row (`mk.py`). |
| Evidence per point (r2 §1): no point holds all the IDs | PASS | Tee Tám has metric markers 1–2 and 3–4 on separate points, and video markers 5–8 on a separate "Bằng chứng từ video" row (`koc_7594293671543079957_1440.png`). |
| KOC page section order and Số liệu chính units (I2) | PASS | The headings run name → Tóm tắt → Điểm mạnh/Điểm yếu → Số liệu chính → Bằng chứng từ video on all 5 pages. Units shown include "+267,2 nghìn ₫/ngày", "100%", "322,4 nghìn ₫" and "0,25%". |
| Video evidence table, no "Không có ảnh" box | PASS (Low defect D4) | 0 "Không có ảnh" on every page, and 0 broken images. |
| KOC page ≤ about 2.5 screens at 1440 px | PASS | Heights are 1860, 1993, 2069, 2319 and 2052 px at a 900 px viewport. The largest is 2.58 screens. |
| I3 number formatting in prose | PASS (Low note) | "687643.86"-style values are grouped. The engagement rate still reads "0,0025" in Điểm yếu text, but the brief covers only shares. |
| I4 run strip shows each KOC's share | PASS | The popover shows "21,7% ngân sách". The run page strip has 5 segments plus "Còn lại" (`rp_top.png`). |
| Strengths and weaknesses text ≥15 px, line-height 1.55 | PASS on the KOC page | Computed font size is `15px` (`koc.json`). |

## FIX_campaign_list.md

| Item | Verdict | Proof |
|---|---|---|
| "Chiến dịch *của tôi*" title, nav active | PASS | `aria-current=page` is on "Chiến dịch của tôi" (`out.json`) (`list_*_1440.png`). |
| Empty state: mascot, one CTA, sample link | PASS | `list_empty_375.png` and `list_empty_1440.png` show one primary button. The header CTA is hidden. |
| Cards: name clamped to 2 lines, meta with time, budget nowrap, n/5 KOC, chip, "Bản đề xuất" | PASS | `list_full_1440.png` and `list_full_375.png` show a long name clamped, and the chips "Đã có đề xuất", "Ngân sách chưa đủ" and "Chờ chạy dữ liệu". At 375 px, budget, KOC count and chip sit on one row and `scrollWidth` is 375. |
| Keyboard reaches each card | UNPROVEN | Not tested by keyboard, and the smoke did not reach this check. |

## FIX_budget_refuse.md

| Item | Verdict | Proof |
|---|---|---|
| Refused panel, warnings, null options hidden, no proposal link or strip | PASS | `result_refused_*.png`: the API returned `cheaper_follower_band: null` and 2 cards are shown. The page has 0 strips and 0 proposal links (the 1440 count of 1 is the "Đề xuất mẫu" nav link). |
| Option card re-submits | PASS | "Chọn 1 KOC (3.000.000 ₫)" opened new campaign `c98cedbb…`, with status ok and 1 KOC (`option_resubmit_1440.png`). |
| D-B2 leftover text | PASS | "Còn lại 1.500.000 ₫ chưa dùng" appears on results, the campaign proposal, the run proposal and print. |
| §3 compact bulleted lists, no bordered rows, full width, on results **and run proposal** | **FAIL (Medium, D1)** | Results PASS (`ro_top.png`). Run proposal and campaign proposal: no bullets, 19 px padding, a border under every point, the columns end about 160 px before the card edge, and the markers float to the right (`rp_top.png`, `print_run_1440.png`). The same happens in print. |
| §4 Playwright mocks (refused, re-submit) | **FAIL** | They are in `smoke.py` but never execute (see Gates). |

## FIX_money_bar.md and addendum

| Item | Verdict | Proof |
|---|---|---|
| One `BudgetStrip` everywhere, landing look | PASS | `web/src/ui/BudgetStrip.tsx` is used on landing, results, the proposal and the run page (`land_strip.png`, `ro_top.png`, `rp_top.png`). |
| Leftover always visible with its amount; addendum "Còn lại" never clipped | PASS | The remaining segment is 67.5 px wide at 375 px and 132.7 px at 1440 px, with the text "Còn lại\n1,5 tr" (`out.json` `landing@*`). |
| Full width | PASS | On the landing page at 1440 px the strip is 1160 px wide, which is the content column. |
| Keyboard, arrow keys, popover, "Xem KOC" only in the app | PASS | ArrowRight moves focus to "Chou Chou". On the landing page the popover shows name, ₫ and % and has no link. |
| §5 accessibility: axe 0 serious, including with the popover open | **FAIL (Medium, D2, D3)** | `button-name` (serious) fires on results, the proposal, the run page and the landing page at 375 px (5 nodes) and at 1440 px (2 nodes). `aria-dialog-name` (serious) fires on the landing page when the popover is open (`out.json` `axe`). |
| Print: static, labels printed, logo | PASS | `print_run_1440.png` and `run_proposal.pdf` (4 pages, with the logo image embedded, 134x122). No strip button takes pointer events. A text list of the segments is printed. |

## FIX_needs_run.md

| Item | Verdict | Proof |
|---|---|---|
| Panel, two steps, real command without ` --dry-run` | PASS | `result_needs_run_*.png`: step 2 is `koc run --product-type Serum …`. |
| Copy button and "Đã sao chép" toast | PASS | The clipboard holds the dry-run command, and the toast text is `['Đã sao chép']`. |
| Khác: `<id>` highlighted, note visible | PASS | `result_khac_*.png`. |
| No proposal link, strip or KOC list; chip "Chờ chạy dữ liệu" | PASS | 0 strips. The chip appears in `list_full_*.png`. |
| §5 mocked tests | **FAIL** | They do not run (see Gates). |
| Refusal-note-first state | UNPROVEN | This state was not reachable with live data, and the mock did not run. |

## Defects

| ID | Severity | Defect | Repro and cause |
|---|---|---|---|
| D0 | High | The smoke gate is red after the merge, so every smoke check added on this branch is untested. | Run `PYTHONPATH=src python -u tests/web/e2e/smoke.py` and it fails at `smoke.py:94`. The fixture campaign (30M, 5 KOC) is now `refused`, because the merged pricing needs a minimum of 60M. Fix: update the fixture budget or rates in the smoke, then re-run it. |
| D1 | Medium | On the run proposal and the campaign proposal, screen and print, Điểm mạnh and Điểm yếu render as bordered, padded rows without bullets and do not use the full width. | Open `/de-xuat/<run>` at 1440 px. Cause: `web/src/styles.css:245` `.proposal-list li { padding: 19px 0; display: flex; … border-bottom }` is a descendant selector, so it also matches the nested `.review-columns li`. `display:flex` removes the list marker. Fix: use `.proposal-list > li`. Lines 394 and 424 have the same issue. |
| D2 | Medium | Creator segment buttons have no accessible name when the name is hidden (axe `button-name`, serious). | Run axe on `/de-xuat/<run>` at 375 px. Cause: `styles.css:162` sets `@container (max-width: 96px) … .budget-segment-name { display:none }`, and `.budget-initial` is `aria-hidden` (`BudgetStrip.tsx:132`). Fix: add `aria-label` on the trigger. |
| D3 | Medium | The popover dialog has no accessible name (axe `aria-dialog-name`, serious, when open). | Hover a landing segment, then run axe. Cause: `BudgetStrip.tsx:136` `Popover.Popup` has no `aria-label` and no `Popover.Title`. |
| D4 | Low | A transcript row with no frame puts the quote into the 120 px thumbnail column ("Còn cái độ chống nắng củ…"), and the marker sits mid-row. | `koc_7594293671543079957_1440.png` at 0:49 and 1:22. |
| D5 | Low | Frame markers are named "Bằng chứng 5: Khung hình video", without the time the brief asks for ("video 0:15"). | `web/src/ui/pages.tsx:561`. |

## Notes

- The brand-fit gate data reduction is not counted as a UI defect.
- Before this run, the working tree already had 39 modified screenshots under `docs/build/shots/readability/`, with mtimes 15:24–15:26, before `1829c08`. They are not from this verifier and were left untouched.

## r2: re-check of fix commit `b7d49b1`

Scope: only the r1 FAIL and UNPROVEN items. Fresh read-only DB copy and server on port 8795, then stopped. Proof paths are relative to `$S/r2/`.

| Item | r2 | Proof |
|---|---|---|
| D0 smoke gate (High) | PASS | One run printed `{"screenshots": 27, "serious_axe_violations": [], "matching_seconds": 0.13, …}` with exit code 0. |
| smoke.py edits (lines 84, 389-390, 436, needs_run setup at 560) | PASS | The 65M budget covers the 60M tier-x3 minimum. The form test uses 65.000.000. The proposal asserts "60.000.000 ₫". `UPDATE runs SET status='failed'` turns the empty-data campaign into needs_run, which `Chưa có dữ liệu KOC` asserts. The changes are minimal and weaken no assertion. |
| D1 lists on the run proposal and campaign proposal (Medium) | PASS (Low note D6) | All 15 strength and weakness items on both pages, at 375 px, 1440 px and in print: `display:list-item`, `list-style: disc`, border 0, padding 0 (`out.json`, `run_1440.png`, `prop_print.png`). Print columns span 1280 of 1440 px. |
| D2 and D3 axe on the strip (Medium) | PASS | axe reports 0 serious with the popover closed and with it open, on landing, results, the campaign proposal and the run proposal, at 375 px and 1440 px. The popup's `aria-label` is "Chi phí của …". Narrow segments keep their name in the accessibility tree through the visually hidden `@container` rule (`styles.css:162`). |
| Keyboard reaches each campaign card | PASS | Tab focus reaches `campaign-card-main` and then `campaign-proposal` (`out.json` `tabs`, `list_focus.png`). |
| needs_run with a refusal note first | PASS | The note is mocked through `page.route`. The first note shows as a warning above step 1, the second note is listed below the steps, and axe reports 0 serious (`needs_run_refusal_375.png`). |

New:

| ID | Severity | Defect |
|---|---|---|
| D6 | Low | On the screen run proposal and campaign proposal at 1440 px, the review columns end at x=930 while the card ends at x=1090. The ~160 px price column stays empty beside the lists, so "full card width" is only partly met. Print is full width. |

The Low items D4, D5 and D6 stay open for v2.0.

**Overall (r2): PASS.** No High or Medium item fails.
