# TEST gate: brand platform

You are the independent VERIFIER. The builder was a different provider. You judge; you never fix.

## Rules
- Write exactly one file: `docs/build/VERDICT_brand_platform.md`. Do not edit, create or delete
  anything else in the repo (you may write scratch files under `/tmp`). Do not commit.
- Every verdict needs proof you produced yourself: command output, `file:line`, or a screenshot path
  under `/tmp`. Reasoning alone is UNPROVEN.

## Inputs
- Spec and criteria 1-19: `~/Projects/LysStack/projects/koc-discovery/brand-platform/spec.md`
- Decisions B1-B14: `~/Projects/LysStack/projects/koc-discovery/brand-platform/brief.md`
- Builder's claims: `docs/build/EVIDENCE_brand_platform.md` (check each row, do not trust it)
- Visual contracts: `design/taste/a-ban-de-xuat.html` (app pages), `design/landing/hero.html?v=b` (landing), `design/logo/` (logo, variant 2)

## Run
- `PYTHONPATH=src ~/Projects/KOC-Discovery/.venv/bin/pytest -q tests`
- `cd web && npm run build && npm run lint`
- Start the app on a fixture DB in `/tmp` (see `tests/web/fixtures/seed.py`, `python -m koc.web --db ... --port 8790`),
  then drive it with Python Playwright (`executable_path="/usr/bin/chromium"`) at 375 and 1440 px:
  submit the form with an invalid then a valid campaign, open results, a KOC (sheet on 375, page on 1440),
  the proposal (print to PDF, count pages), Ctrl+K search, the operator page. Run axe on each page.
- Scan visible text of brand pages for: token, credit, USD, latency, task, S1, S2, S3, S4.
- Matching on a read-only copy of `~/Projects/KOC-Discovery/data/koc.db` in `/tmp`: confirm no pick
  wins only through missing data (B14) and placeholder audience rows count as missing.
- Landing: CTAs, `/api/stats` vs direct SQL on the real DB copy (no network calls to Kalodata), reduced motion via
  `emulate_media(reduced_motion="reduce")`, no horizontal scroll at 375 px, logo fonts in the header and printed proposal, favicon.
- Coherence (AC18): header, footer, buttons, titles identical across landing, form, results, KOC, proposal, operator;
  step indicator correct; searching state after submit, skipped under reduced motion.
- Age (AC19): quick picks set the slider and show active; keyboard and screen reader on thumbs; API rejects gaps;
  old campaign loads; placeholder age rows (30.5/39.5) never count as real fit on the real DB copy.
- Hunt for what the tests miss: empty campaign list, a budget too small for any set, 1 KOC, 10 KOCs,
  a follower range that matches nobody, very long brand name, product type "Khác".

## Output
`docs/build/VERDICT_brand_platform.md`: a table with one row per criterion 1-19 (PASS / FAIL / UNPROVEN
and proof), then a list of defects found outside the criteria with severity and repro steps, then an
overall verdict: PASS only if no criterion is FAIL. Criterion 13 (Lystiger's visual sign-off) stays UNPROVEN.
