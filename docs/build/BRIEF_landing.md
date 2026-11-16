# DEV brief: landing page (R9, AC14-16)

Same rules as `BRIEF_brand_platform.md` (read it first): this worktree and branch only, commit as you
go, never merge or push, Vietnamese UI copy passed through unslop, craft floor before UI edits.

## Contract
- Spec R9 and AC14-16: `~/Projects/LysStack/projects/koc-discovery/brand-platform/spec.md`.
- Decisions B15-B16: `~/Projects/LysStack/projects/koc-discovery/brand-platform/brief.md`.
- Visual and motion contract: `design/landing/hero.html` opened with `?v=b`
  (screenshots `design/landing/shots/hero-b-{1440,375}.png`). Keep its copy, layout, tokens,
  the SVG overlay and every keyframe. Drop the `?v=` switching and the unused A/C art.
- Art: copy `design/landing/assets/b-hero.webp` into the app's assets. Give the `<img>` explicit
  width/height so nothing shifts. Do not use `c-hero.*`.

## Build
1. `GET /api/stats` in `src/koc/web/api.py`: creators in the latest S1 pool, creators with an S3
   score, videos with an analysis row. Test it against direct SQL on the fixture DB.
2. Landing route at `/`; campaign list at `/chien-dich`; update nav, the cmdk palette entries,
   redirects after save/cancel and any test that expects the list at `/`.
3. "Xem một bản đề xuất mẫu" links to the newest campaign's proposal; hide it when there is none.
4. Trust section: three numbers from `/api/stats` with plain labels, rendered with NumberFlow.
   No testimonials, logos or claims the data does not support.
5. Reduced motion: the existing media query in the mock already stops everything; keep it working
   in the React build.

## Verify, then stop
- Full list from `BRIEF_brand_platform.md` (pytest, build, lint, axe 0 serious, screenshots of every page
  at 375 and 1440 into `docs/build/shots/react/`, including `landing_*`).
- Extend the Playwright smoke: landing CTAs, `/chien-dich` list, a reduced-motion run
  (`emulate_media(reduced_motion="reduce")`) that checks no running animations via
  `document.getAnimations()`, and a scrollWidth check at 375 px.
- Compare `landing_1440.png` and `landing_375.png` with the mock screenshots; fix differences.
- Add rows 14-16 to `docs/build/EVIDENCE_brand_platform.md`, refresh the others you touched, commit, stop.
