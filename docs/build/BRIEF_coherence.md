# DEV brief: coherence round (R10, AC18) + quick fixes N5-N8

Same rules as `BRIEF_brand_platform.md`. Read spec R10 and AC18
(`~/Projects/LysStack/projects/koc-discovery/brand-platform/spec.md`) and decision B21.

## Coherence
The landing page (`/`, built from `design/landing/hero.html?v=b`) is the reference. Bring every other page to it:
1. One `SiteHeader` and one `SiteFooter` component used by every route, per R10. Remove the old app header.
2. One button system: the landing pill primary (with arrow icon) and text-link secondary. Replace the square
   buttons everywhere (form submit and cancel, results actions, proposal "In / Lưu PDF", empty states).
3. One title block component: Newsreader 600, green italic `<em>`, the landing's rise entrance.
4. `StepIndicator` with the landing's three drawn icons: form = step 1, results = step 2, proposal = step 3.
   Hidden in print.
5. Form page layout per R10 with `design/landing/assets/mascot.webp` (copy into the app's assets, explicit
   width/height, float motion). Group fields under "Sản phẩm", "Ngân sách", "KOC bạn cần" in Newsreader.
6. After a valid submit, show a searching state for about 1.2 s: mascot plus the budget strip filling and the
   line "Đang tìm KOC phù hợp…", then route to results. Skip it entirely under reduced motion. Errors still
   return to the form with inline messages.
7. Copy: Vietnamese, unslop rules. Keep existing wording unless it conflicts with the landing.

## Quick fixes (verdict fc2c810)
8. N5: the evidence-id cleanup must not touch clock times such as "20:30:15". Add a test.
9. N6: `/van-hanh` scrolls sideways by 48 px at 375 px on the real DB. Make wide tables scroll inside their own
   container; page scrollWidth must equal 375.
10. N7: metric labels fully Vietnamese, e.g. "GPM video (doanh thu trên 1.000 lượt xem)". Keep abbreviations only
    with the Vietnamese explanation.
11. N8: the printed proposal must not end in a large beige block; check the last page of the PDF.

## Verify, then stop
Full verify list from `BRIEF_brand_platform.md`, screenshots of every page at 375 and 1440, reduced-motion run,
PDF check. Compare the form and results screenshots with the landing screenshot for header, buttons and titles.
Add row 18, update rows you touched, commit, stop.
