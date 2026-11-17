# Fix: TikTok links instead of avatars. FRONTEND ONLY

Lystiger (2026-11-16): no KOC avatar images; link to the KOC's TikTok instead. Same rules as
`BRIEF_brand_platform.md`. Do not edit Python. No requests to TikTok in tests (assert hrefs only).

1. Build links client-side from data the API already sends: profile `https://www.tiktok.com/@<handle without @>`,
   video `https://www.tiktok.com/@<handle>/video/<video_id>`. Skip the link when handle or video_id is missing.
2. KOC page header and every proposal/results row: the handle becomes a link "@handle ↗" (opens in a new tab,
   `rel="noopener noreferrer"`, accessible name "Mở trang TikTok của <tên> (mở tab mới)"). Keep the letter chip; no images.
3. Evidence table: each video header gets "Xem trên TikTok ↗"; each row's time stays in-page (no TikTok deep-link
   promise, TikTok has no reliable timestamp parameter).
4. Print/PDF: show the profile URL as text under the name (short form `tiktok.com/@handle`).
5. Tests: hrefs correct for real-run creators, missing-handle case renders plain text, axe 0 serious.

Verify: lint, build, smoke, axe; screenshots 375/1440 (`tiktok_*`). Add evidence rows, commit, stop.
