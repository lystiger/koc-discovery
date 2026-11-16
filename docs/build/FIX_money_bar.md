# Fix: one budget strip everywhere (landing look, interactive, unspent money visible). FRONTEND ONLY

Lystiger (2026-11-16): make the in-app money bars look like the landing page's, and make the landing bar interactive
and wider: it hides the money that is not spent. Same rules as `BRIEF_brand_platform.md`. Do not edit Python.

Today there are three strips: the landing demo (`LandingPage.tsx`), `BudgetStrip` and `RunBudgetStrip`
(`web/src/ui/pages.tsx` ~297 and ~441). Replace them with ONE `BudgetStrip` component used on the landing, results,
campaign proposal and run proposal (screen and print).

1. Look: the landing style (one rounded track, one coloured segment per KOC with its name inside when it fits, the
   hatched "Còn lại" segment). Same tokens as the landing.
2. Unspent money is always visible: the "Còn lại" segment has a minimum visual width (about 12% of the track, or
   enough for its label) even when small, the amount is printed under the strip ("Còn lại 1.500.000 ₫ chưa dùng"),
   and the KOC segments shrink proportionally to make room. If leftover is 0, no segment.
3. Wider: full width of its card/column on every page; on the landing the demo spans the whole content column.
4. Interactive: each segment is focusable (keyboard, arrow keys move between segments) and shows a base-ui Tooltip /
   Popover with KOC name, cost, share of budget (%), and a link "Xem KOC" in the app (not on the landing demo).
   Hover/focus highlights the matching KOC row on results and proposals. Touch: tap opens the popover.
   Under reduced motion: no fill animation, tooltips still work.
5. Accessibility: the strip has a text equivalent (a visually hidden list of segments with amounts); no
   `aria-prohibited-attr` (earlier AC12 defect). Print: static, labels printed, no tooltips.
6. Tests: the smoke checks the leftover segment is visible (width > 0) whenever leftover > 0, keyboard navigation,
   tooltip contents, axe 0 serious with a tooltip open.

Verify: lint, build, smoke, axe; screenshots at 375/1440 of landing, results, proposal, run proposal, plus one with a
tooltip open, into `docs/build/shots/readability/` (`money_*`). Add evidence rows, commit, stop.

## Addendum (Lystiger's screenshot of the landing strip, 2026-11-16)
The reference is exactly the landing card: big Newsreader total top right, a caption top left, segments with the KOC's
initial in a round clay chip plus the name, and under the track each KOC's short amount ("6,5 tr") above the name.
Defect in that reference: the "Còn lại" segment is clipped at the right edge ("C la"). It must show "Còn lại" and the
short amount fully, at every width. Use this exact design on every page.
