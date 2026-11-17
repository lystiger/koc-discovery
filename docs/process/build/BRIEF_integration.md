# DEV brief: integrate core fixes (feat/koc-mvp @ 6fb40f4) into the React branch

Contract: `~/Projects/LysStack/projects/koc-discovery/brand-platform/integration_core.md` (read it fully) and B23.
Same rules as `BRIEF_brand_platform.md`. No network, no Kalodata or LLM calls, no `koc run` / `koc resume` live.
Never touch `~/Projects/KOC-Discovery/data/koc.db`; use a copy in
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/integration/`.

## Merge
1. `git merge --no-ff 6fb40f4` on `ui-test/react-pick-ui-library`. Expected conflicts: `.gitignore`,
   `docs/process/build/DESIGN.md`, `src/koc/web/adapter.py`, `src/koc/web/app.py`.
2. Resolve:
   - `adapter.py`, `app.py`: core data logic wins: `koc.stages.placeholder_audience_creators`, `koc.stages.final_score`
     (renormalised), "Không có dữ liệu (Kalodata chỉ hiển thị số liệu mẫu)" for placeholder creators, the
     dashboard 'skipped' status, frame URLs `/media/frames/<video_id>/`. React keeps its `/api` router, SPA
     fallback, landing, stats endpoint, campaigns and matching API.
   - `.gitignore`: union. `DESIGN.md`: keep both sections, core first, React UI section after.
3. One source of truth for placeholders: React's matching (`matching_api.py`, audience display rules from rounds
   5-6) must use `koc.stages.placeholder_audience_creators` instead of its own copy, keeping B14/B20 fill and the
   round-6 display rule. Remove the duplicated helper only if nothing else uses it.

## Must hold (integration_core.md "Must hold" 1-5)
- The 10 live-run creators are placeholders: no female or age number is shown or cited for them anywhere
  (results, KOC page, proposal, age slider effects, run views).
- Real run `7372009b22764b339fbcf0f3efb4bc4e` on the DB copy: the run's recommendations show exactly 5 KOCs,
  total 28.500.000 ₫ ≤ 30M, Vietnamese reasons and caveats, every cited evidence id resolves (metric rows,
  video timestamps, quotes, frames). Find where the React app renders a run's recommendations; if no React page
  does, say so in evidence and stop for the orchestrator rather than invent one.
- Full suite: `PYTHONPATH=src ~/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests` (core + React tests),
  `cd web && npm run lint && npm run build`, the Playwright smoke.

## Stop
Screenshots at 375 and 1440 of landing, the run's top 5, a KOC detail and the run dashboard on the real-run copy,
into `docs/process/build/shots/integration/`. Write `docs/process/build/EVIDENCE_integration.md` (one row per must-hold point,
with proof). Commit the merge and evidence. Do not merge into `feat/koc-mvp`; stop.

## Also (G1, low, from VERDICT fc2c810+ round 6)
A creator with gender but no age shows "Khán giả 81", partly from the filled age value. Display only the measured
part (gender share) as the audience number, keep the "Thiếu dữ liệu độ tuổi" note; scoring unchanged. Test it.
