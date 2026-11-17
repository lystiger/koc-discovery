# DEV brief: logo and hero art (AC17, B17-B18)

Same rules as `BRIEF_brand_platform.md`. Small round: touch only what this needs.

1. Logo, variant 2 in green, from `design/logo/`:
   - `detola-koc-3-header.svg`: header lockup on every page (replaces the "KOC Discovery" text logo), ~40 px tall, links to `/`.
   - `detola-koc-2-stack-discover.svg`: landing footer and proposal header, including the print stylesheet.
   - `detola-koc-4-icon.svg`: `favicon.svg`, plus 32 px `favicon.png` and 180 px `apple-touch-icon.png` (render with Playwright/Chromium or ImageMagick).
   - The lockups contain `<text>` in Be Vietnam Pro 700 and Newsreader 600. An SVG in `<img>` cannot use page fonts, so render them as inline React components (or convert the text to paths). Make sure Be Vietnam Pro 700 is loaded. Give the logo an accessible name "DETOLA KOC Discovery".
   - Page titles: "<page> · DETOLA KOC Discovery"; landing title "DETOLA KOC Discovery".
2. Hero art: replace the app's copy of `b-hero.webp` with `design/landing/assets/b-hero.webp` (new render). Keep width/height attributes correct.
3. Verify: full list from `BRIEF_brand_platform.md`; screenshots of every page at 375 and 1440; check the logo text in the header screenshot is set in the right fonts, not a fallback. Add row 17 to `EVIDENCE_brand_platform.md`, commit, stop.
