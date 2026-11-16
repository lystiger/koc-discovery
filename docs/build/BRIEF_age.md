# DEV brief: age picker (B22, AC19)

Same rules as `BRIEF_brand_platform.md`. Read decision B22 and AC19 in
`~/Projects/LysStack/projects/koc-discovery/brand-platform/`.

1. Buckets: `18-24`, `25-34`, `35-44`, `45-54`, `55+`. `target.age_groups` stays a list (backward compatible)
   but must be one contiguous run of these buckets. Pydantic validates order and contiguity; 422 with a
   Vietnamese message otherwise. Old saved campaigns load unchanged.
2. Form ("Khán giả mục tiêu"): replace the two checkboxes with
   - quick-pick pill chips: "Gen Z · 18–24", "18–34", "Người đi làm · 25–34", "25–44", "35–54";
   - a two-handle range slider (base-ui `Slider`, already the primitive library) with bucket ticks and labels;
   - a live line "Đang chọn: 18–34 tuổi". Default 18–34.
   A chip sets the slider; a chip shows active (aria-pressed) while the slider equals its range. Style per the
   landing (pill chips, green accent, warm paper). Thumbs keyboard-operable with Vietnamese aria labels
   ("Tuổi nhỏ nhất", "Tuổi lớn nhất") and aria-valuetext ("25–34 tuổi"). Mobile: chips wrap, slider full width.
3. Matching (`src/koc/web/matching_api.py`): map each bucket to `age_<a>_<b>_pct` / `_share` (`55+` -> `age_55_plus_*`).
   Age fit = sum of the selected buckets' shares, only when every selected bucket has a non-placeholder value;
   otherwise the age part is missing and follows B14/B20 (pool minimum, or dropped when nobody has it).
   Tests: contiguity validation, old campaign, 35-54 on fixture data, a creator missing one bucket.
4. Show the chosen range in plain words on results and the proposal ("Khán giả nữ, 18–34 tuổi").

Full verify list, screenshots at 375 and 1440 (include the form with a chip active and the slider moved),
axe on the form. Add evidence row 19, commit, stop.
