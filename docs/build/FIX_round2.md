# Fix round 2 (TEST gate FAIL, see VERDICT_brand_platform.md)

Same rules as `BRIEF_brand_platform.md`. Fix every item, add a test for each, re-run the full verify
list, update `EVIDENCE_brand_platform.md`, commit, stop. Read the verifier's repro steps and proof in
`docs/build/VERDICT_brand_platform.md` and its scratch scripts under
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier/`.

## Criteria that failed
1. AC4: the KOC detail page shows placeholder S2 audience data as real ("Điểm Khán giả 65",
   "Khán giả nữ 60"). Apply the same placeholder rule as matching: show "Chưa phân tích".
2. AC11: no English keys or raw statuses in the UI. Map rubric and metric keys (`brand_fit`,
   `claim_quality`, `hook`, `cta`, `age_18_24_pct`, `video_vs_live_share`, ...) and task statuses
   (`done`, `blocked`, `running`, ...) to Vietnamese labels. Unknown keys get a readable fallback, not the raw key.
3. AC12: Sonner success toast contrast 4.25:1, raise to at least 4.5:1. Fix `aria-hidden-focus`
   with the Ctrl+K palette open. Extend the smoke test to run axe with the toast visible and with
   the palette open, so this cannot regress.

## Defects
4. D1: when no valid set of the requested size exists (MCN rule or pool too small), pick the largest
   valid, affordable set below the requested count and show a warning saying how many were found.
5. D2: zero picks shows an empty state that explains why (e.g. no KOC in the follower range) and
   offers "Sửa yêu cầu". Hide the proposal action when there are no picks.
6. D3: if no creator in the filtered pool has a component (e.g. no real audience data at all),
   leave that component out of the fit for everyone and renormalise over the rest. The 25th-percentile
   fill (B14) applies only when some creators have the component.
7. D4: render "Xem bằng chứng" only when the evidence target exists.
8. D5: long unbroken brand names wrap (`overflow-wrap:anywhere`) on screen and in print.
9. D6: a creator outside every rate-card tier gets no 0 ₫ cost. Exclude them from selection and say
   so in the alternates, or use the nearest tier marked as an estimate. Pick one and note it in evidence.
10. D7: on mobile, opening a KOC from results keeps results under the Vaul sheet (client-side
    navigation, not a full page load).
11. Make `npm run lint` run ESLint as well as `tsc`; remove `clsx` if it stays unused.
