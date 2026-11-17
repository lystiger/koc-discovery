# DEV brief: readability round (B25, B26, AC21; audit defects I1-I4)

Same rules as `BRIEF_brand_platform.md`. Branch `ui/readability` (cut from `feat/koc-mvp`). Read B25, B26 and
AC21 in `~/Projects/LysStack/projects/koc-discovery/brand-platform/`. Keep the design system (DESIGN.md,
landing tokens, shared header/footer/buttons). Vietnamese copy through unslop. No network or paid calls; real
data only via a copy of `data/koc.db` in
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/audit/koc.db`.
Avoid editing `src/koc/web/adapter.py` (the core session is changing it); put new shaping in `api.py` or the client.

## 1. KOC review, three parts (results, run proposal, proposal print, KOC page)
- **Tóm tắt**: one line built from scores, e.g. "Phù hợp 79/100 · bán hàng mạnh (89) · nội dung khá (65) ·
  chưa có dữ liệu khán giả". Thresholds: ≥ 80 mạnh, 60-79 khá, < 60 yếu. One shared helper.
- **Điểm mạnh | Điểm yếu** side by side (two columns ≥ 768 px, stacked below; print: two columns). Strengths =
  reasons, weaknesses = caveats. On list pages show the first 2 of each plus "Xem chi tiết"; the KOC page shows all.
- A caveat whose text is the same (after normalising) for every KOC on the page shows once in a page-level note
  above the list, and is removed from each KOC. Covers the Kalodata audience caveat.

## 2. Evidence markers (I1)
- Replace runs of inline evidence links with numbered markers after each point: small chips "1" "2"... numbered per
  page in order of first use; the same evidence id always gets the same number. Accessible name
  "Bằng chứng 3: video 0:15" / "Bằng chứng 5: số liệu Tỷ trọng doanh thu chăm sóc da". Clicking scrolls to and
  briefly highlights the matching evidence row.

## 3. KOC page evidence table
- Order: header (name, handle, followers, fit, cost) → Tóm tắt → Điểm mạnh | Điểm yếu → Số liệu chính →
  Bằng chứng từ video.
- **Số liệu chính**: the 4-6 metrics that are cited or scored, plain units (I2): money in ₫ with nghìn/triệu,
  shares as %, rates as % with 1-2 decimals, trends as "+267 nghìn ₫/ngày" or a plain "tăng/giảm" when the unit is
  unknown. Rows carry their marker numbers. "Xem tất cả số liệu" disclosure for the rest.
- **Bằng chứng từ video**: one compact table per video (header: title, views, number of cited moments). Rows only for
  cited moments, sorted by time: **Thời điểm** (m:ss) | **Khung hình** (thumbnail about 120x68, click to enlarge in
  a dialog) | **Nội dung** (quote or frame note, clamp 2 lines, expand on click) | **Dùng cho** (marker chips).
  Videos with no cited moment collapsed under "Video khác (n)". Full transcript behind "Xem toàn bộ lời thoại".
- Phone: each row becomes a compact card (thumb left, time + text right), no sideways scroll.
- Target: at 1440 px the page is at most about 2.5 viewport heights with disclosures closed.

## 4. Other defects
- I3: in reason/caveat prose, format raw numbers: decimals over 1.000 get grouped and rounded ("687643.86" →
  "687.644"), shares 0-1 written "1.0" next to a share label → "100%". Display only; never change stored text.
- I4: run proposal budget strip shows each KOC's share, like the campaign proposal.

## Verify, then stop
Full verify list from `BRIEF_brand_platform.md` plus: real-run copy KOC pages (all 5) and run proposal at 375 and
1440; assert two columns at 1440 and stacked at 375; the shared Kalodata caveat appears exactly once on the run page;
no two evidence controls on a page share an accessible name; every marker resolves; KOC page height at 1440 with
disclosures closed; axe 0 serious; PDF. Screenshots into `docs/process/build/shots/readability/`. Add AC21 rows to
`EVIDENCE_brand_platform.md`, commit, stop.
