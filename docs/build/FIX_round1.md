# Fix round 1 (orchestrator review of d6c290e)

Same rules as `BRIEF_brand_platform.md`. Fix only the items below, add a test for each
behaviour change, re-run the full verify list, update `EVIDENCE_brand_platform.md`, commit, stop.

## Matching (spec R2.4 changed, decision B14)
1. Replace renormalised weights with a conservative fill: a missing component counts as the
   25th-percentile value of that component across the follower-filtered pool. Confidence badges
   still count real components only.
2. Treat S2 rows that core flags as placeholder as missing. Port `audience_is_placeholder` /
   `run_audience_is_placeholder` from `git show feat/koc-mvp:src/koc/stages.py` and cite the lines.
3. Re-run the real-DB probe (copy of `~/Projects/KOC-Discovery/data/koc.db`) and record the new
   confidence counts and the 5 picked handles with their components.

## Visual defects (compare with `design/taste/a-ban-de-xuat.html`)
4. Budget total renders as `₫20,000,000`. Vietnamese format everywhere, including NumberFlow:
   `20.000.000 ₫` (locale `vi-VN`, dot grouping, symbol after).
5. The remaining-budget segment of the allocation strip is solid green, so it reads as spent.
   Use the mock's hatched clay style and label it "Còn lại" when wide enough.
6. Reasons leak pipeline terms and English decimals: "Điểm nội dung S3 đạt 91.0/100", "82.5%".
   In display text, replace stage codes (S1-S4) with plain words (S3 -> "nội dung") and format
   decimals Vietnamese style (82,5%). Do not change stored data.
7. Form number fields show raw `30000000` / `10000`. Show grouped values while typing
   (`30.000.000`) and parse them back.
8. "Giới tính" is a native select while "Loại sản phẩm" uses base-ui. Use base-ui Select for both.
9. Proposal: remove the "KOC Discovery · 15/11/2026" line above the heading (eyebrow). Put the
   date in the assumptions block at the end.
