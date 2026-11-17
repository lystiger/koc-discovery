# KOC Discovery UI audit

Read-only audit of http://127.0.0.1:8766 (mock fixture data, branch feat/koc-mvp).
Pages: `/`, `/runs/run_mock_beauty_01`, `/runs/run_mock_beauty_01/creators/c_linh_01`, `/runs/run_mock_beauty_01/dashboard`.
Themes `?theme=a|b|c` (light; dark mode not captured, see limits). Widths 375 and 1440.
Screenshots: `docs/process/audit/shots/<page>_theme-<t>_<w>.png` (24 files, 4000 px tall).
HTML: fetched to scratchpad, not stored in the repo.

## Summary

Issue counts by theme and severity. Shared issues count once in each theme they affect.

| Theme | P1 | P2 | P3 | Total |
|---|---|---|---|---|
| A (Tài chính) | 4 | 14 | 9 | 27 |
| B (Phân tích) | 5 | 14 | 9 | 28 |
| C (Thương hiệu) | 4 | 14 | 10 | 28 |

Contrast: no failures. Light-theme `--quiet` on every surface token is 5.4 to 6.8:1 (computed from the CSS hex values). Dark-mode tokens compute to 7.5 to 8.9:1, but dark was not screenshotted, so that part is UNPROVEN.

## P1: broken or misleading

**F1. Home table clipped at 375 px (all themes).** The Trạng thái and Chiến dịch columns fall outside the `.table-wrap` scroll box, so "done" reads "dor" and the campaign is hidden. There is no scroll cue. Shots: `home_theme-a_375.png`, `home_theme-b_375.png`, `home_theme-c_375.png`.
Fix: under 720 px render each run as a stacked card (code, date, status, campaign, dashboard link), or drop the Bắt đầu column and let the status wrap.

**F2. Comparison table clipped at 375 px (theme B only).** `.comparison-table` has `min-width: 62rem` inside `.comparison-wrap` with `overflow-x: auto`. The right side ("Thương mại", "Bằng chứng") is cut off with no visible scroll affordance. Shot: `run_theme-b_375.png`. Theme A and C show cards at this width.
Fix: hide `.comparison-wrap` below 720 px and show the existing creator-row cards, or add a fade or scroll hint.

**F3. Five of 14 evidence `[n]` links on the run page point to ids that do not exist (all themes).** Ids present on each creator page were checked in the fetched HTML:
- `c_chou_02#v_c_chou_02_1:transcript:2`: page has `:transcript:1` only.
- `c_trinh_03#v_c_trinh_03_1@20.0s`: page has `@15.0s` and `@0.5s`.
- `c_mai_04#v_c_mai_04_2@10.0s`: page has `@20.0s` and `@0.5s`.
- `c_an_05#v_c_an_05_1@18.0s`: page has `@15.0s` and `@0.5s`.
- `c_an_05#v_c_an_05_3@05.0s`: page has `@45.0s` and `@0.5s`.

Links to `c_linh_01` (`#metric:c_linh_01:female_ratio`, `#v_c_linh_01_1@15.0s`, `#v_c_linh_01_2:risk:1`) and the other existing anchors do resolve.
Fix: generate `[n]` targets from the same evidence record that writes the card and the creator ids. Add a test that every run-page href fragment exists on its creator page.

**F4. Dashboard cost not labelled as an estimate (all themes).** "Gemini · hạn mức $5.0" with "$0.0756" and "1.5% · 58.860 tokens" carries no "ước tính". The brief requires every cost to be labelled. Shots: `dashboard_theme-{a,b,c}_1440.png`.
Fix: label the card "Chi phí Gemini ước tính" and the value "≈ $0.0756 (ước tính)".

**F5. Evidence repeated across videos and captions describe the script, not the frame (all themes).** On `c_linh_01`, all three videos ("3 video được chấm") carry the same transcript block ("Chào các bạn, hôm nay Linh sẽ test trực tiếp...") and the same risk text. Frame captions such as "15.0 giây · Chất kem mỏng nhẹ thẩm thấu nhanh trong 30 giây..." quote the script line as if it were the visual at that timestamp. The rubric scores (5/5, 4/5) are therefore not tied to differing evidence.
Fix: check that each video has its own transcript and risk segments before publishing. Caption frames with what is visible, or label the text "lời thoại" and show the timestamp it came from.

## P2: clearly wrong look, or slop

**F6. Home has no mock banner (all themes).** Runs, creators and dashboard show "GIẢ LẬP". Home (`/`) shows only a small "Giả lập" tag per row, so it fails the every-mock-page rule. Shots: `home_theme-*`.
Fix: add the same `<aside class="mock-banner">` to the list page.

**F7. Fee risk cites a metric it does not support (run page, all themes).** Trịnh's "Chi phí booking 7.000.000 ₫ ở mức cao nhất trong nhóm..." links to `#metric:c_trinh_03:video_gpm`, both for the fee note and the reach note. The fee is not a GPM value.
Fix: point the fee note at the fee/booking record.

**F8. All evidence markers read "[1]" with the same aria-label (all themes).** Every link has the visible text "[1]" and `aria-label="Bằng chứng 1"`, even the second and third citations on a card. Readers cannot tell citations apart, and screen-reader users hear the same label repeatedly.
Fix: number the markers per card (`[1]`, `[2]`, `[3]`) and set `aria-label` to "Bằng chứng 2 của ...".

**F9. Dashboard credit units missing (all themes).** "Kalodata · hạn mức 100.0" and "12.0 / 100.0" give no unit. The user asked for credits against the cap.
Fix: write "12.0 / 100.0 credit" and "Kalodata · hạn mức 100 credit".

**F10. Zero error counts shown as red (all themes).** The "Lỗi" column uses `.status.bad` on every 0, so the table looks alarming when nothing failed.
Fix: apply the red class only to values above 0. Show 0 in muted text.

**F11. English stage names inside Vietnamese UI (all themes).** "S0: Thu thập ứng viên (Candidate Retrieval)", "(Commercial Scoring)", "(Audience Fit)", "(Content Evaluation)", "(Final Selection)". The English adds nothing for a Vietnamese reader.
Fix: keep the Vietnamese names and drop the English in brackets.

**F12. Calibration card reads as validation (all themes).** "Đối chiếu điểm nội dung: 0.742 and 0.685, Spearman ρ từ cấu hình lần chạy" has no sample size, no interval and no note. The run page says "Run này chưa có xác suất đã hiệu chuẩn", so the dashboard should match.
Fix: add n and a caveat such as "n = ?, chưa đủ dữ liệu để kết luận" or hide the card when n is unknown.

**F13. Decimal separators mixed (all themes).** Run and dashboard use a dot for decimals ("95.0%", "12.0", "0.742", "4.2 s"). Creator uses a comma ("46,0%", "82,5%"). Thousands use a dot ("28.500.000 ₫", "51.300 tokens"). "4.2" next to "51.300" is ambiguous.
Fix: use the Vietnamese convention (comma decimal, dot thousands) everywhere, or the Western one everywhere, but not both.

**F14. Overclaim on audience fit (run and creator, all themes).** "Tỷ lệ người theo dõi là nữ đạt 82.5%, tập trung mạnh ở nhóm 18-34 tuổi hoàn toàn khớp đối tượng chiến dịch." The campaign targets 18-30 (header: "Nữ, 18-30 tuổi, da dầu mụn"), so 18-34 does not match exactly, and "hoàn toàn khớp" is unsupported.
Fix: "Nhóm 18-34 tuổi chiếm 83,5%, rộng hơn đối tượng 18-30 của chiến dịch."

**F15. Trend claim from an unitless slope (creator and run, all themes).** "Hiệu suất video GPM đạt 145.000 ₫ với xu hướng doanh thu tăng trưởng ổn định trong 30 ngày qua." The source is "Hệ số tăng trưởng doanh thu 0.28" with no unit, and nothing measures stability.
Fix: "Hệ số tăng trưởng doanh thu 30 ngày là 0,28 (không có đơn vị, chưa đo độ ổn định)." Or drop "ổn định".

**F16. Filler and unsupported reach claim (run, all themes).** "Lượng người theo dõi 245.000 giúp lan tỏa nhận diện thương hiệu mạnh mẽ trên toàn quốc." "Mạnh mẽ" and "trên toàn quốc" are not in the data.
Fix: "245.000 người theo dõi. Chưa có dữ liệu về phạm vi địa lý."

**F17. Vague, flattering evaluation (run, all themes).** "Độ uy tín chuyên môn y khoa cao, giải thích cơ chế bảo vệ màng lipid da thuyết phục." Judgement words with no evidence attached.
Fix: state the observable: "Giải thích cơ chế màng lipid, dẫn nguồn ở 0:20." (or whatever the transcript shows).

**F18. Unsupported claim about purchasing power (run, all themes).** "Tệp khán giả nhóm tuổi 25-34 chiếm 52%, có sức mua và khả năng chi trả cao." The data has no purchasing-power measure.
Fix: "Nhóm 25-34 tuổi chiếm 52%. Dữ liệu không đo sức mua."

**F19. Placeholder art in place of frames (creator and run, all themes).** Profile images and frame thumbnails are generated pink and lavender cards with alt-style text ("@linh.skindaily Hook 00:00.5", "Texture 00:15"). They look like broken or stock images at 1440 px, and they dominate the run page in theme C. Shots: `run_theme-c_1440.png`, `creator_theme-*_1440.png`.
Fix: use real frames, or show a neutral placeholder with a text label and a fixed aspect ratio, not a styled fake.

## P3: polish

**F20. Identifiers break mid-word in the metric table (creator, all themes).** "metric:c_linh_01:skincare_revenue_sha / re" and "engagement_per_vie / w" wrap inside the id. Fix: `overflow-wrap: anywhere` on `.evidence-id`, or show the human label and move the id to a tooltip.

**F21. Profile thumbnail clipped at the right edge (creator, theme C, 1440).** The alt-style text "@linh.skindaily Hook 00:00.5" is cut off by the image frame (`creator_theme-c_1440.png`). Fix: `object-fit: cover` with a centred crop, or a smaller placeholder.

**F22. Number wraps inside the stat at 375 px (dashboard, all themes).** "51.300 / 7.560" breaks after "/" on two lines. Fix: `white-space: nowrap` on `.stat-value` at small widths, or smaller font.

**F23. Score wraps at 375 px (run, all themes).** "88.3 / 100" splits so "/ 100" sits under the number. Fix: keep "/ 100" in a nowrap span.

**F24. Invalid nesting in the audience block (creator, all themes).** `<dt>` and `<dd>` sit inside `<div>` in `.profile-details`, not inside `<dl>`. Screen readers may not announce them as term/definition pairs. Fix: wrap the group in a `<dl>`.

**F25. Internal id shown to viewers (creator, all themes).** "Mã hồ sơ c_linh_01" is a system key. Fix: hide it or move it to a debug view.

**F26. Inline "Lưu ý:" labels (run, all themes).** Five risk notes start "Lưu ý: ..." in the warning colour. Rule 16 flags this pattern. Fix: drop the label and keep the warning colour, or let the note stand on its own.

**F27. Hyphen used as a dash (creator, run, all themes).** "Review KCN ... tập 1 - Trải nghiệm thực tế 8 tiếng", metric labels "18 - 24". Fix: use a colon or comma in titles, and write the range as "18 đến 24 tuổi" (rule 13 bans en dashes too).

**F28. Unexplained abbreviation (creator, all themes).** "KCN" in video titles is not expanded. Fix: "kem chống nắng" at first use.

**F29. Inconsistent timestamps (creator and run anchors).** "15.0s" versus "05.0s" and "@05.0s" in ids. The anchor ids are a symptom of F3; fix in the same change.

## Limits

- Dark mode was not screenshotted (headless default is light). Contrast for dark is computed from tokens only (UNPROVEN visually).
- Screenshots are fixed at 4000 px tall, so the empty space below content is a capture artifact, not a layout defect.
- Creator pages `c_chou_02`, `c_trinh_03`, `c_mai_04`, `c_an_05` were checked for ids in HTML, not screenshotted.
- The "Đề xuất" nav link on home points to `run_mock_skincare_02`, which was not audited.
- Nothing was edited except this file and the screenshots.

## Closest to done

Theme A is closest to done. It has no clipped comparison table at 375 px, and its cards and budget blocks stay readable at both widths. Its remaining problems (F1, F3, F4, F5) are shared with B and C, not specific to A. Theme B is next, held back by the clipped comparison table (F2), and theme C is furthest, with the placeholder art (F19) and crop issue (F21) dominating the look.
