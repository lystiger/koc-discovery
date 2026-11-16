# DEV brief: brand platform (React)

You are the DEV builder. Work only in this worktree (`~/Projects/KOC-Discovery-react`,
branch `ui-test/react-pick-ui-library`). Commit on this branch as you go. Never merge,
never push, never touch other branches or worktrees.

## Read first
1. Spec, the contract: `~/Projects/LysStack/projects/koc-discovery/brand-platform/spec.md`
   (requirements R1-R8, acceptance criteria 1-13).
2. Decisions: `~/Projects/LysStack/projects/koc-discovery/brand-platform/brief.md` (B1-B13).
3. Visual contract: `design/taste/a-ban-de-xuat.html` and its screenshots in
   `design/taste/shots/a-ban-de-xuat-{1440,375}.png`. Lystiger picked this direction.
   Carry its tokens (colors on `:root`, Newsreader headings, Be Vietnam Pro body, tabular
   numbers), its ranked-row layout and its budget allocation strip to every page.
   Pages the mock does not show (form, KOC detail, proposal, operator) use the same world.
4. Library picks: `~/.claude/skills/pick-ui-library/SKILL.md`. Use base-ui, cmdk, vaul,
   sonner, @number-flow/react, recharts, clsx (cva only if a component has real variants).
   Do not hand-build a toast, drawer, dialog, dropdown, select, tooltip or command palette.
5. Craft floor: `~/Work/skills-review/impeccable/.claude/skills/impeccable/reference/craft-floor.md`.
   Read it before UI edits. Do not run Impeccable's launcher or scripts.
6. Copy: all user-visible text in Vietnamese. Apply `~/.claude/skills/unslop/SKILL.md`
   to it: plain words, no em dashes, no filler, sentence case.

## Where things go
- Frontend: new `web/` (Vite + React + TypeScript + Tailwind). `npm run build` writes `web/dist`.
- Backend: `src/koc/web/api.py` (FastAPI router under `/api`), `src/koc/web/matching.py`
  (pure `match(input, pool) -> result`), `src/koc/web/campaigns.py` (the `campaigns` table).
  Mount the router and serve `web/dist` with SPA fallback from `src/koc/web/app.py`.
  Keep existing Jinja routes working.
- Tests: `tests/web/test_matching.py`, `tests/web/test_api.py`, Playwright smoke in
  `tests/web/e2e/` (Python Playwright, `executable_path="/usr/bin/chromium"`).
- Do not change core modules (`src/koc/*.py` outside `web/`, `src/koc/llm/`) or core tables.

## Scoring source
Core scoring with S2/S3 lives on branch `feat/koc-mvp`. Read it with
`git show feat/koc-mvp:src/koc/stages.py` (`audience_score`, `final_score`) and
`git show feat/koc-mvp:src/koc/pipeline.py`. Match their formulas in `matching.py`,
adding the renormalisation over null components from spec R2. Cite the source lines
in a comment.

## Data
Development DB: generate with `tests/fixtures/seed.py` (see how `tests/web` fixtures use it).
Also run once against a copy of `~/Projects/KOC-Discovery/data/koc.db` (read only; copy to
`/tmp`) and record how many matches come back "Đầy đủ", "Một phần", "Sơ bộ".

## Verify before you stop
- `pytest -q tests` (pre-existing failures: list them, do not fix core).
- `cd web && npm run build && npm run lint`.
- Playwright screenshots of every page at 375 and 1440 px into `docs/build/shots/react/`.
  Open them and compare against the mock. Fix what looks wrong before stopping.
- axe on every page (`@axe-core/playwright` or axe-core injected), 0 serious issues.

## Stop condition
Write `docs/build/EVIDENCE_brand_platform.md`: one row per acceptance criterion 1-13 with
PASS / FAIL / UNPROVEN and its proof (command output, file:line or screenshot path).
Criterion 13 is UNPROVEN until Lystiger looks. Then commit and stop. Do not merge.
If blocked (quota, missing dependency, spec contradiction), write the blocker at the top
of the evidence file, commit, and stop.
