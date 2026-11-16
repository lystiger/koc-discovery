# Fix round 6 (TEST FAIL on AC4, AC19 after round 5, see VERDICT_brand_platform.md)

Same rules as `BRIEF_brand_platform.md`. Verifier proof: `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier2/`.

1. R1 (High): a creator with no real audience data (no row, or only placeholder rows) now gets an audience
   score from averaged pool minimums, shown as "Khán giả 77" and tiered "Đầy đủ". Separate scoring from display:
   - Scoring: unchanged from round 5 (pool-minimum fill per sub-part, B14/B20); missing data never raises fit.
   - Display and confidence: audience counts as observed only if the creator has at least one real sub-part.
     Otherwise show "Chưa phân tích" on results, KOC page and proposal, and the tier ignores the filled value
     (cannot be "Đầy đủ"). A creator with gender but no age shows the audience score with a note that age is missing.
   Tests: no S2 row, placeholder-only rows, gender-only creator; assert label, tier and that fit does not rise.
2. R2 (Low): en dash in every age range in UI copy, including "độ tuổi 18–24" and rubric text ("18–30 tuổi").
3. R3 (Low): phone header CTA shows the short text "Bắt đầu" (no wrap, white-space: nowrap) instead of an arrow only;
   header stays one row at 375 px.

Full verify list, screenshots at 375 and 1440. Update evidence rows, commit, stop.
