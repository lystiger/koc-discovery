# Fix round 5 (TEST FAIL on AC19, see VERDICT_brand_platform.md)

Same rules as `BRIEF_brand_platform.md`. Verifier proof: `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier2/`.

1. A1 (High, AC19): `_audience_fit` in `src/koc/web/matching_api.py` drops a missing age part and averages only
   gender, so missing data raises the score (repro: remove one creator's 25-34 row on a fixture copy, target 25-34:
   audience 60.0 -> 82.5, fit 81.92 -> 86.42). Apply B14/B20 at the sub-part level: for each audience part
   (gender, age), a creator without a real (non-placeholder) value gets the pool minimum of that part, among
   creators that have it; if no creator in the pool has the part, drop it for everyone. Missing data must never
   raise a creator's audience score or fit. Add the verifier's repro as a test, plus "only gender in pool" and
   "nobody has age" cases.
2. A2 (Low): at 375 px the header CTA wraps to a second row (header 117 px). Keep the header one row: icon-only
   or shorter CTA on phone, accessible name unchanged.
3. A3 (Low): use an en dash for age ranges everywhere ("18–34 tuổi"), including reason text and labels.

Full verify list, screenshots at 375 and 1440. Update evidence rows, commit, stop.
