# Fix round 4 (TEST FAIL on AC17 after coherence round, see VERDICT_brand_platform.md)

Same rules as `BRIEF_brand_platform.md`. Verifier proof: `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier2/shots/`.

1. C1 / AC17 (High): the proposal lost its stacked logo; print hides the shared header/footer, so the PDF has
   no logo. Put the stacked lockup back at the top of the proposal page, visible on screen and in print
   (non-zero width in print media). Add a smoke assertion on the PDF / print-media bounding box.
2. C2 (Medium): results rows show 2-4 identical "Xem bằng chứng" links. Show one link per KOC row,
   "Xem bằng chứng (n)", opening the KOC page at its evidence section. Keep per-item links on the KOC page,
   each named by its type (e.g. "Số liệu bán hàng", "Video 0:15"). Unique accessible names.
3. C3 (Low): one button size everywhere; use the landing's size for primary pills.
4. C4 (Low): at 375 px make the header logo larger and stop the form's step labels touching (shorter labels
   or stacked layout on phone).

Full verify list, screenshots at 375 and 1440, PDF check. Update evidence rows, commit, stop.
