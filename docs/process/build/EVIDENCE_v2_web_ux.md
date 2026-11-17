# EVIDENCE: v2.0 web UX (branch v2/web-ux)

Base: feat/koc-mvp at 0f5c03e. Scope: v2_plan item 7, V2-3, V2-4, V2-8, criterion A5 (this wave only; search/filter and the needs_run estimate panel are not built).

## Design source (V2-8)

- `ui-ux-pro-max --design-system "KOC influencer discovery marketing dashboard Vietnamese"` returned a generic pink/brutalist system (Lexend Mega, #EC4899). It conflicts with the approved direction in `design/system/koc-discovery/MASTER.md`, so it was NOT applied. Same outcome as the earlier brand-platform search recorded in MASTER.md.
- Taken from the skill: its pre-delivery checklist only (visible focus, 44 px touch rows on the excluded triggers, contrast 4.5:1, no emoji icons, responsive 375/1440, reduced motion untouched, no tooltips for the new parts).
- Reused unchanged: palette tokens (`--paper`, `--surface`, `--ink`, `--green`, `--border`, `--warning`), Newsreader + Be Vietnam Pro, `.bar-track`, `.notice` look. Library: `@base-ui/react/collapsible` for the excluded-KOC disclosure (already a dependency); `lucide-react` chevron.

## Items

| # | Item | Proof |
|---|---|---|
| 1 | TikTok links | `web/src/ui/explain.tsx:11-31` (URL builders, `TikTokLink`, `PrintProfileUrl`, `TikTokVideoLink`). Used on results rows (`pages.tsx:345`), campaign proposal (`:494`), run proposal (`:536`), KOC header (`:610`), per-video "Xem trên TikTok ↗" in the evidence table (`:620`). Opens in a new tab with `rel="noopener noreferrer"`. Accessible name = visible "@handle" plus sr-only "Mở trang TikTok của <tên> (mở tab mới)": a pure `aria-label` failed axe `label-content-name-mismatch` (serious), so the exact name is split into visible text and hidden text. Missing handle (empty, `@<creator_id>`, all digits) renders plain text. Print shows `tiktok.com/@handle` (`.print-url`, `styles.css` print block). Test: `tests/web/e2e/smoke.py` block "v2 web" asserts hrefs, target/rel, plain text for a blanked handle, video href, and 0 requests to tiktok.com. |
| 2 | Excluded box | The run proposal did not send `brand_fit_excluded` (`get_run_proposal` dropped it) and no endpoint sent per-video scores. Minimal Python change: `src/koc/web/adapter.py` `excluded_with_videos` (nickname + each analysed video's brand_fit), used in `get_run_proposal` and `matching_api.result_for_campaign`. Test `tests/core/test_brand_fit_gate.py::test_excluded_carry_video_brand_fit`. Types: `web/src/types.ts` `ExcludedKoc`. UI: `ExcludedBox` (`explain.tsx:64`), base-ui Collapsible per KOC, shows brand_fit per video, video links and profile link. Real run: "Đã loại 4 KOC vì không hợp thương hiệu" (run proposal; campaign result). Decision to flag: on the campaign result the API also lists 51 KOC with no analysed video (S1-stage gate). They were not judged unfit, so they sit in a separate collapsed line "51 KOC khác chưa có video được phân tích", not in the N. |
| 3 | Score breakdown | `CreatorBreakdown` (`pages.tsx:126`) + `ScoreBreakdown` (`explain.tsx:34`): Thương mại 45% / Khán giả 20% / Nội dung 35%, each with score, one-line "vì sao" from data already sent, links. Rows and proposals build the line from cited metric ids and video ids; the KOC page uses metric values (GPM, share, trend) and rubric averages. Audience null renders "Chưa có dữ liệu" (never 0); real run: all 5 picks show it. Links are in-page anchors to `#metric:<id>:<name>` and `#video-<video_id>` (the video article got that id, `pages.tsx:620`). The old per-row `ScoreBars` with tooltips and `RunScoreBars` were replaced by the box. |
| 4 | Cách chấm điểm | `ScoringMethod` (`explain.tsx:48`), id `cach-cham-diem` (results, proposals) and `cach-cham-diem-koc` (KOC page, avoids duplicate ids in the mobile drawer over the results page). The breakdown header links to it. Steps are labelled "Bước 0-4", not "S0-S4": smoke asserts brand pages show no "S1" (`smoke.py` run_proposal check), so the stage codes stay hidden. The cost note says "ước tính" and names the 43-minute run and the per-KOC fee basis; it omits credits and USD because the existing smoke gate forbids "credit/usd/token" on brand pages. Both choices are for Lystiger to override. Print hides this section to keep the proposal at 3 pages. |
| 5 | VERDICT Lows | D4: `.evidence-row.no-frame` grid (`styles.css:659`, mobile `:671`): quote takes the full column, marker on its own row (`koc_1440.png`, rows 0:49 and 1:22). D5: `pages.tsx evidenceLinkName` regex accepted only ids ending in `s`; real ids end `@16.14`, so the time never showed. Now "Bằng chứng 5: Khung hình video 0:16". D6: price moved into a header row (`.proposal-item-head`), lists use the full card width (`proposal_1440.png`: columns span the card). |

## Checks run

- `cd web && npm run lint && npm run build`: pass (run `rtk bypass npm run lint`; the rtk wrapper rewrites `eslint src` to a whole-tree lint that scans dist).
- `PYTHONPATH=src python tests/web/e2e/smoke.py`: `{"screenshots": 27, "serious_axe_violations": [], ...}`. Smoke edits: the `.score-line` assertion now reads `.score-box-part`, plus the v2 block (the run rewrites tracked `docs/process/build/shots/readability/*`; I reverted those).
- `pytest -q`: 430 passed, 1 skipped.
- Real-run data: DB copied with `sqlite3 -readonly data/koc.db ".backup <copy>"`, API served on 8801 from the copy, a campaign POSTed to the copy only. `data/koc.db` untouched.

## Screenshots (docs/shots/v2_web/)

`results_375.png`, `results_1440.png` (campaign results), `proposal_375.png`, `proposal_1440.png` (run proposal), `koc_375.png` (mobile drawer), `koc_1440.png` (KOC page). I opened results_1440 (incl. the bottom crop with the excluded box and method), proposal_1440, koc_1440, results_375 and koc_375. proposal_375 was captured but not opened.

## UNPROVEN / notes

- `tests/web/e2e/budget_refusal.py` times out on `.budget-panel`, a selector that exists nowhere in `web/src`: stale script, not caused by this change (not fixed).
- Print: only the page count (<= 3, smoke) is proven; the print layout of the excluded box and the `.print-url` line was not viewed.
- Excluded video titles are "Video đã phân tích" because the stored titles are absent for these videos; the UI labels them "Video 1/2/3".
- The expanded state of an excluded KOC was verified by the smoke click (href check), not by screenshot.
- Mobile row: the cost line now sits below the breakdown box.

## r2 fixes (after REVIEW_v2_web_ux r1 FAIL)

| Finding | Fix and proof |
|---|---|
| P2 Nội dung box linked 7 of 15 analysed videos | The API now sends `analysed_video_ids` per pick: `adapter.analysed_video_ids` (`src/koc/web/adapter.py`), set on campaign picked/alternates (`matching_api.result_for_campaign`) and run proposal picks (`api.get_run_proposal_api`). Pytest: `tests/core/test_brand_fit_gate.py::test_picks_carry_all_analysed_video_ids`, `tests/web/test_api.py` proposal assertion. UI: the box links every analysed video and says the real count ("Máy xem 3 video"); the KOC page gives every analysed video an anchor (`id="video-<id>"`, also on the "Video khác" details) and its "Xem trên TikTok ↗"; `revealEvidence` opens every ancestor `<details>`. Real run (`scratchpad/real.py`, read-only DB copy): 3 content links per pick on the run proposal, sum 15; on each of the 5 KOC pages 3 anchor targets, 3 content links, 3 TikTok video links. Campaigns saved before this change lack the field and fall back to cited videos. |
| P3 vacuous D4 assertion | `smoke.py` now opens fixture KOC `c_chou_02` (a transcript row without a frame), asserts at least one `.evidence-row.no-frame`, the quote starts within 64 px of the row's left edge and is at least 60% of the row width; it also asserts content links == `[id^="video-"]` targets. |

Screenshots added (`docs/shots/v2_web/`): `excluded_expanded_1440.png`, `excluded_expanded_375.png` (first excluded KOC open: per-video brand_fit and TikTok links), `method_link_landing_1440.png` (after clicking "Cách chấm điểm" in a score box: section visible, `scrollY` 4130, section top 462 px in a 1000 px viewport). I opened the 1440 pair; `excluded_expanded_375.png` not opened.

Raw logs (the reviewer sandbox cannot open sockets): `docs/process/build/logs/v2_web_r2_lint.log`, `_build.log`, `_smoke.log` (`serious_axe_violations: []`, exit 0), `_pytest.log` (run under `unshare -rn` with loopback up and fake keys: 431 passed, 1 skipped).

## r3 fixes (after REVIEW_v2_web_ux r2 FAIL)

| Finding | Fix and proof |
|---|---|
| P2 saved campaigns showed 7/15 content links | `_campaign_review_data` (`src/koc/web/api.py`, used by `GET /api/campaigns/{id}`) now fills `analysed_video_ids` for every picked/alternate creator from the campaign's recorded `run_id`, overwriting any stored value. The React fallback (cited videos) only applies to a campaign with no `run_id`. Regression test `tests/web/test_api.py::test_saved_campaign_without_analysed_video_ids_is_enriched_on_get`: persists a campaign result without the field, GETs it, asserts the field equals `db.run_analyses` for every pick. |
| P3 stale excluded screenshots | `excluded_expanded_1440.png` and `excluded_expanded_375.png` re-captured from a fresh server: the reason now reads "độ hợp thương hiệu cao nhất 2/5 (cần ít nhất 3/5)" (opened the 375 one; the 1440 one is regenerated by the same script and was not re-opened). |

Logs for r3 (replace the r2 logs as the evidence): `docs/process/build/logs/v2_web_r3_lint.log`, `_build.log`, `_smoke.log`, `_pytest.log` (the pytest command is the offline one with `PYTHONPATH=src` and fake keys under `unshare -rn`).
