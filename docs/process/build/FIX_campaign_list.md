# Fix: "Chiến dịch của tôi" page (/chien-dich)

Same rules as `BRIEF_brand_platform.md` (design system, unslop Vietnamese, base-ui primitives, no network).
Screenshots of the current page (Lystiger: "looks buggy"):
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/cd/` (`empty_*.png`, `list_*.png`).

Defects seen:
- Empty state shows two identical green buttons stacked ("Tạo chiến dịch" and "Tạo chiến dịch đầu tiên"), plus the
  header's "Bắt đầu chiến dịch": three of the same CTA on one screen. Bare grey text, then a large blank area.
- Title "Chiến dịch" while the nav says "Chiến dịch của tôi"; the nav item is not marked active; no italic accent
  like every other page title.
- Rows are thin text lines: no KOC count, no status, no visible action, nothing says the row is clickable.
- 375 px: the budget wraps ("80.000.000" / "₫"); long brand names push it.

Build:
1. Title block "Chiến dịch *của tôi*" (shared title component), with one line under it. Nav item active
   (`aria-current="page"` + active style) on `/chien-dich*`.
2. Empty state: mascot (`mascot.webp`, small, float motion off under reduced motion), "Chưa có chiến dịch nào",
   one line on what happens, ONE primary CTA "Tạo chiến dịch đầu tiên", and a text link "Xem một bản đề xuất mẫu"
   (to `/de-xuat`, hidden when no run). No page-level "Tạo chiến dịch" button in the empty state.
3. Non-empty: one primary "Tạo chiến dịch" in the title row. Each campaign is a card (whole card is the link, visible
   focus ring): brand name (Newsreader, clamp 2 lines), product type · date and time ("16/11/2026, 11:06"), budget
   (nowrap), KOC result "5/5 KOC" or "3/5 KOC", a status chip: "Đã có đề xuất" / "Thiếu KOC" / "Chưa có KOC phù hợp",
   and a secondary link "Bản đề xuất" when there are picks. Newest first.
4. 375 px: card stacks name, meta, then budget + KOC + chip on one row; no wrap inside numbers, no sideways scroll.

Verify: empty DB and a DB with 3 campaigns (normal, long name, 0 picks) at 375 and 1440; exactly one primary CTA in the
page body; axe 0 serious; keyboard reaches each card. Screenshots into `docs/process/build/shots/readability/` (`campaigns_*`).
Add to AC21 evidence, commit, stop.
