# Fix round 3 (TEST re-run FAIL, see VERDICT_brand_platform.md)

Same rules as `BRIEF_brand_platform.md`. Fix each item, add a test where it is behaviour, re-run the full
verify list, update `EVIDENCE_brand_platform.md`, commit, stop. Verifier proof and repro scripts:
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier2/`.

1. AC5: hide `.skip-link` (and any other screen-only control) in the print stylesheet. Re-check the PDF.
2. AC9: spec amended (B19), clsx no longer required. Do not re-add it. Update the evidence row.
3. AC11: the stored reason text on the real DB contains metric keys (`skincare_revenue_share`, `video_gpm`, ...).
   Replace known keys in display text with their Vietnamese labels (reuse the label map from round 2). Real-DB test.
4. AC12: `aria-prohibited-attr` on `.allocation` (`web/src/ui/pages.tsx:128`) when there are 0 picks. Give it a valid role
   or drop the aria attribute; add the 0-pick case to the axe smoke.
5. N1 / B20: missing components are filled with the pool minimum, not the 25th percentile. Update tests; re-run the
   real-DB probe with count 5 and 10 and record picks and confidence.
6. N2: evidence links on the real DB. Read how real recommendations store evidence ids (a separate field, a different
   format from the fixture) and render "Xem bằng chứng" for those that resolve. Test on a real-DB copy.
7. N3: landing must match the mock: italic `<em>` in the hero headline (load Newsreader italic), "Bắt đầu" header
   button must not wrap at 375 px, centre the "Dữ liệu đang có" block the way the mock lays out its sections.
8. N4: an empty database gets its own empty state ("Chưa có dữ liệu KOC"), not the follower-range message.
