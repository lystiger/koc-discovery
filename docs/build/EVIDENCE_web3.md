# UI polish evidence

## Changes

- Theme a keeps the ranked editorial list.
- Theme b renders the five recommendations as a compact comparison table with component scores, estimated cost, key metrics, evidence count, expandable reasons, and profile links.
- Theme c renders five creator profiles with large hook frames and adjacent score and estimated cost.
- At mobile widths, the ranked-list score and cost block spans the row below the creator name. Creator metrics use a stacked label, value, and source/period/evidence layout.
- Evidence IDs in recommendation reasons and caveats become numbered superscript links. Evidence rows keep the raw IDs.
- `docs/build/DESIGN.md` records the layouts and the selected palette and system fonts.

## Checks

- `python3 -m py_compile src/koc/web/adapter.py`: passed.
- `git diff --check`: passed.
- `pytest -q tests/web`: not run. The command failed because the active Python environment has no `pytest` module.
- `uv run --offline pytest -q tests/web`: not run. `uv` is not installed.
- Direct TestClient or Jinja rendering: unavailable. The active Python environment has no FastAPI, Starlette, or Jinja2 modules.
- Screenshot review: inspected the supplied `docs/build/shots/a|b|c` captures. They show the prior shared ranked-list layout. This environment cannot render the updated templates, so the new visual result is **UNPROVEN**. The orchestrator should capture the changed pages after checkout.
- Commit: not created. `git add` could not write `/home/lystiger/Projects/KOC-Discovery/.git/worktrees/KOC-Discovery-web3/index.lock` because the shared gitdir is read-only.

## UI guidance

The UI-UX Pro Max search returned an Enterprise Gateway / Dark Mode direction. It did not match the three directions in the brief, so the existing palettes and system fonts remain authoritative. The Impeccable launcher could not load engine 0.1.22 because its cache path is unwritable; its checked-in craft-floor and polish guidance informed this pass.
