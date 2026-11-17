# UI audit v2: KOC Discovery (feat/koc-mvp), mock data

Read-only audit. Server: http://127.0.0.1:8766. Only this file and `docs/process/audit/shots_v2/*.png` were written.

Screenshot map (`shots_v2/`):
- `index_{375,1440}.png` = `/` (Đợt chạy)
- `run_{375,1440}.png` = `/runs/run_mock_beauty_01` (Đề xuất KOC; the page title, not the URL, says Đề xuất)
- `creator_{375,1440}.png` = `/runs/run_mock_beauty_01/creators/c_linh_01`
- `dashboard_{375,1440}.png` = `/runs/run_mock_beauty_01/dashboard` (Vận hành)

Method notes: screenshots were read visually. DOM probes were run on copies of the served HTML, and headless Chromium clamps the window to a 500 px minimum, so the 375 DOM numbers are indicative only. Contrast was computed from CSS hex values (WCAG relative luminance).

## Severity counts

| Severity | Count | Meaning |
|---|---|---|
| P1 | 5 | Broken or misleading |
| P2 | 9 | Clearly wrong look, slop, or unlabelled/small text |
| P3 | 6 | Polish |

## Passing checks

- GIẢ LẬP banner ("Dữ liệu mô phỏng, chỉ dùng để kiểm thử.") present once on all 4 pages.
- Every cost is labelled "ước tính" in the visible copy (index: "Phí booking ước tính", "Chi phí ước tính"; run: "Gemini · chi phí ước tính"; creator: "Phí booking ước tính"). Dashboard shows "Kalodata" in credits, not currency.
- Every in-page `href="#..."` resolves on the Đề xuất creator page: `#metric:c_linh_01:female_ratio`, `#metric:c_linh_01:revenue_trend_slope`, `#v_c_linh_01_1@15.0s`, `#v_c_linh_01_2:risk:1`. Other pages have no hash links.
- No emoji, no em dashes (0 across all pages), no `<strong>Label:</strong>` lines.
- Contrast of main grey text passes: `--quiet #475569` is 7.58:1 on white and 7.24:1 on `#F8FAFC`. `#92400E` (risk text) is 7.09:1. `#B91C1C` is 6.47:1.
- Phone layout is fine on Đợt chạy and Vận hành (cards stack, no page-level overflow reported).
- Arithmetic checks out: creator score 88,3 = 0,45×88,5 + 0,20×92,0 + 0,35×86,0; index budget 28,5 M of 30 M = 95,0%.

## P1 (broken or misleading)

1. **Creator bars render with no fill.** `.bar-fill` (creator page CSS, line ~64) has no `background`. Only the inline `width` is set, so the rubric bars ("Chấm theo tiêu chí", 3 videos), the Khán giả bars and the metric bars show only the light track. The dashboard and Đề xuất bars work because they set an inline `background`. Shots: `creator_1440.png`, `creator_375.png`. Fix: add `background: var(--primary)` to `.bar-fill` in the creator template's CSS, or inline it like the dashboard does.

2. **Đề xuất heading contradicts its own table.** Heading "15 ứng viên vào vòng cuối" sits above a table with 6 rows, 5 of them "Được chọn" plus Hoa Beauty "Không chọn". The dashboard says S3 has 15 candidates and S4 has 5. Shot: `run_1440.png`. Fix: take the count from the data, e.g. "6 ứng viên vào vòng cuối, 5 được chọn".

3. **Dashboard "Thời gian xử lý" hides its value column on phones.** At 375 only "Giai đoạn" shows. The "Giây" values (4,2 / 18,5 / 45,0 / 112,3 / 8,1) are cut off, and this table has no "Vuốt ngang" hint, unlike "Tác vụ" above it. Shot: `dashboard_375.png`, crop around y≈1280–1800. Fix: wrap it in the same `.table-wrap` with the hint, or stack rows as label/value pairs on narrow widths.

4. **Creator page overflows at 375.** Video cards (h3 titles, blockquote transcripts, "Khung hình" frames, 15 ứng viên table) run past the right edge; text such as "Review kem chống nắng cho da dầu mụn, tập 1: Tr…" is clipped. The DOM probe (500 px minimum) reports scrollWidth 686. Shot: `creator_375.png`. Fix: make `.video` a single column with `min-width: 0` on the grid children and `grid-template-columns: minmax(0, 1fr)` below the breakpoint.

5. **Gemini cost is rounded to a misleading value.** KPI card says "$0,0756" (ước tính), but the progress bar caption says "0,1 / 5,0 USD" (1,5%). "0,1" implies about 2%, and the KPI uses "$" while the bar uses "USD". Shot: `dashboard_1440.png`. Fix: show "0,076 / 5,0 USD" in both places and use one currency form.

## P2 (clearly wrong look, slop, or small/unlabelled text)

6. **Sort arrows with no sorting.** `th.sortable::after` adds "↕" (`#94A3B8`, 2.56:1 on white, below 4.5:1) to "Điểm", "Phí ước tính", "Chi phí ước tính", "Điểm cuối", "Creator". The page has no `<script>`, so nothing sorts. The affordance is false. Shots: `run_1440.png`, `index`-style tables. Fix: remove the arrows, or make real sort buttons with `aria-sort`.

7. **Citation markers are 9.45 px.** `.evidence-reference { font-size: .72em }` inside 13,1 px text gives 9,45 px for 28 `[1]`–`[3]` markers on the Đề xuất page (computed style). Shot: `run_1440.png`. Fix: set `font-size: .75rem` (12 px) and keep `vertical-align: super`.

8. **Other text under 11 px on the creator page.** `.metric-source` is 10.88 px (7 lines such as "browser · last30Day · metric:c_linh_01:age_18_24_share"), `.score-parts span` is 10.08 px, and the avatar initials are 10.88 px. Shot: `creator_1440.png`. Fix: `.metric-source { font-size: .75rem }` and `.score-parts span { font-size: .72rem }`.

9. **Scatter "Chi phí và điểm của ứng viên" clips its last axis label and has no scroll hint.** The SVG is 720 px wide, `16,1` at the right edge is cut off, and the wrapper `.scatter-scroll` scrolls silently. Shot: `run_1440.png`, crop of the scatter card. Fix: `viewBox` scaled to `width:100%`, or shrink the x domain so the final tick fits.

10. **Scatter accessible name says 15 candidates but plots 6 points.** `aria-labelledby` text reads "Chi phí và điểm của 15 ứng viên", while the visible card has 6 dots. Fix: name the finalists count from data, e.g. "6 ứng viên vòng cuối".

11. **Stacked bar has no legend.** "Điểm theo trọng số" uses three colours (dark blue, mid blue, orange) for 45 / 20 / 35% with no key; the caption only lists the weights. Shot: `run_1440.png`. Fix: add a small legend row with swatches, or label the segments.

12. **Repeated stage labels.** Dashboard rows read "S0 · S0: Thu thập ứng viên", "S1 · S1: Chấm điểm thương mại", etc. The stage code appears twice. Shot: `dashboard_1440.png`. Fix: "S0: Thu thập ứng viên".

13. **Mixed number formats.** Dashboard "Đối chiếu điểm nội dung" shows "0.742" and "0.685" with a dot decimal, while the rest of the app uses the comma (12,0; 88,3). Shot: `dashboard_1440.png`. Fix: "0,742" and "0,685".

14. **Copy overclaims and filler (creator page).** Quoted exact text:
    - "Phong cách năng động, lối nói chân thật rất phù hợp nhãn hàng mỹ phẩm trẻ trung." ("rất phù hợp" is unsupported superlative filler).
    - "Bảng thành phần không cồn khô, không hương liệu nhân tạo, rất an toàn cho làn da đang điều trị mụn." (safety claim in a frame description; the frame is a placeholder, so the claim has no evidence behind it).
    - "Chăm da khoa học • Review chân thực không nhận seeding bẩn • Da hỗn hợp thiên dầu" (bullet tagline with unverifiable claims).
    Shot: `creator_1440.png`. Fix: "Phong cách nói chân thật, hợp nhóm khách hàng trẻ." and "Bảng thành phần không cồn, không hương liệu nhân tạo (theo lời thoại)." Drop "rất an toàn" and "không nhận seeding bẩn" unless sourced.

## P3 (polish)

15. "Khung hình giả lập. Chưa có ảnh video thật." appears 8 times on the creator page; it is honest but repetitive. Say it once per video.
16. Empty grey boxes ("Khung hình giả lập") fill the hero and every frame row. Labelled, but they read as broken images. Use a neutral striped placeholder with the label once.
17. Redundant rows: "Tỷ lệ (%)" plus a sentence repeating the same four percentages under Khán giả; "Điểm đóng góp có trọng số trên thang 100" plus "Điểm cộng có trọng số: ..." on the Đề xuất page.
18. Header and value disagree: "Điểm / 5" in the table header, "Điểm trên 5" as a label above it.
19. Mixed English in Vietnamese copy: "Đề xuất creator", "Tokens vào / ra", "Cache Kalodata", "credit", "GPM", "Cache Gemini", "Review". Keep, or gloss once (e.g. "Token vào / ra").
20. Scatter `aria-label` values are raw ("15000000 đồng"). Format as "15.000.000 ₫" to match the visible text.

## Contrast (computed)

| Text colour | On white | On #F8FAFC | Verdict |
|---|---|---|---|
| `#475569` (`--quiet`, muted text) | 7.58:1 | 7.24:1 | pass |
| `#92400E` (`.risk`) | 7.09:1 | 6.78:1 | pass |
| `#7F1D1D` (mock banner text on `#FEF2F2`) | 10.02:1 | 9.58:1 | pass |
| `#D97706` (accent, focus ring, scatter dots) | 3.19:1 | 3.04:1 | pass for non-text only; fails if used as text |
| `#94A3B8` (sort arrow) | 2.56:1 | 2.45:1 | fail (fix via finding 6) |

No small grey body text fails 4.5:1. Only the sort arrow does.

## Chart accessibility (6)

- Dashboard: two `role="img"` charts, both with `aria-label` and text values. Titles and units present ("Số ứng viên còn lại", "credit", "USD"). Pass.
- Đề xuất: scatter has `role="img"` plus `aria-labelledby`, but the name is wrong (finding 10). Stacked bar has `role="img"` and an aria-label, but no legend (finding 11).
- Creator: 4 `role="img"` containers with aria-labels. The rubric bars are labelled, but their fills are invisible (finding 1), so the visible chart is empty. Values are in text (table below each), so data is recoverable.
- Stage bars (dashboard) have values and an `aria-label`. Pass.

## Not verified

- Live rendering at other widths (only 375 and 1440 were run).
- Keyboard focus order and the native `<select>` run switcher were not exercised.
- Scroll behaviour inside `.scatter-scroll` and `.table-wrap` was judged from the screenshots, not by scrolling.
