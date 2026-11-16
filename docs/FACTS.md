# Evidence log (orchestrator, 2026-11-14)

Source of truth for the docs. Every line has its evidence.

## Environment
- Python 3.14.8, venv `.venv`, deps playwright/httpx/pydantic/typer/pytest (+setuptools). `kalodata intake inspect` output.
- ffmpeg /usr/bin/ffmpeg; chromium; Playwright cached chromium builds.
- agy CLI present, model `gemini-3.8-flash-high` (from `agy models`). codex CLI present, default gpt-6.1-sol low (~/.codex/config.toml).
- uv not installed.

## Access
- Account: Kalodata **trial**, region VN, logged in manually by Lystiger in headed Chromium (temp profile, CDP 127.0.0.1:9333). No cookies/headers read or stored.
- Trial limits seen on page: "Trial accounts are allowed 10 visits to the detail pages per day"; "Trial accounts get 10 searches per day" (AI); creator debut time masked `****`; video ad metrics masked `****`; "Top 5 Locations" locked (credits); live recordings locked.
- Detail visits used: 4 (3 creator detail + 1 video detail). 6 remaining at capture time.

## Method 1: CSV/Excel export
- "Export" button present on creator rank list and on creator detail tables (video, product, live). Not clicked/tested: export content and trial entitlement UNVERIFIED.

## Method 2: Documented API (Kalodata Open Center)
- https://www.kalodata.com/open-center/docs : HTTP POST + JSON, secret key in headers, generated in Account page. Rate limit 100 req / 10 s.
- Endpoints include tiktok/creator: detail, ranking list, avatar; tiktok/video: detail, ranking list, video URL; product, shop, livestream, category.
- creator/detail response fields: creator_id, nickname, handle, region, status, bio, contact (email/tiktok/whatsapp/line/facebook/ins/zalo), revenue, sales_volumn, unit_price, video_revenue, live_revenue, video_views, live_views, live_gpm, video_gpm, new_followers, video_number, live_number, shop_number, product_number, creator_followers, revenue_trend. Param `need_extra` (bool). **No audience gender/age/geo and no category in documented response.**
- video/detail fields: video_id, region, title, belonged_creator_id/handle, product count, revenue, sales volume, views, GPM, ad views, ROAS, ad cost, is-ad flag, ai_video. No likes/comments/shares listed in the excerpt read.
- video/url: returns "CloudFront signed video URL" + expires_at.
- Pricing (open-center/pricing): detail APIs 0.1 credit/call; rank APIs 0.1 x ceil(rows/100); video URL 0.5 credit/call; product images/comments 0.01; "1 point is approximately equivalent to 0.1 USD". API key not created, no API call made (needs purchase + Lystiger approval).

## Method 3: Authorized browser UI extraction (used)
- Creator rank list `/creator`: handle, nickname, revenue, item sold, followers, follower change, content views, avg unit price, engagement rate. 268,815 creators in VN list (pagination).
- Creator detail `/creator/detail?id=<creator_id>` (1 visit): followers, follower gender %, follower age buckets (18-24, 25-34, 35-44, 45-54, 55+), revenue/live/video/showcase revenue (30 d), live and video views, video table (cover -> video_id, title, revenue, views, publish date; ad metrics masked), shops, products, contact email (NOT stored: unnecessary PII).
- Video detail `/video/detail?id=<video_id>` (1 visit): views, item sold, revenue, follower change, ad view/revenue ratio, ad spend, ROAS (shown unmasked here), publish date, duration, music, "Download", "View on TikTok", "Storyboard Export". Player serves MP4 from live.kalocdn.com with signed `key` + `time` params. Likes/comments/shares not shown.
- Cover image: https://img.kalocdn.com/tiktok.video/<video_id>/cover.png (HTTP 200, 340,764 B png).
- Throughput measured: ~15-20 s per creator (7 s settle + scroll capture) plus >=5 s pacing; bound by trial cap of 10 detail visits/day.
- Script: scripts/capture_creator.py (reads visible text + DOM of operator-opened tab).

## Method 4: Network inspection (feasibility notes only)
- Creator list page calls `/creator/queryList`, `/creator/count`, `/creator/enrich` (JSON envelope success/data/message/cached/code). Undocumented internal endpoints; not automated. Paths only were logged (no query, headers, bodies).

## Method 5: Linked video assets
- 1 MP4 downloaded via the session's own request from the player URL: 7705660238917143816.mp4, 5,441,136 B, 24.6 s, h264 576x1024 + aac, 24.7 s download.
- TikTok URLs are derived (`https://www.tiktok.com/@<handle>/video/<id>`), not fetched.

## Data collected (data/intake.db)
- Creators: chanhbeauty93 (2.4m followers, 60% female, 18-24 30.5% / 25-34 39.5%, revenue ₫34.06b), trangtrankoc (786.6k, 77.65% female, 18-24 64.08%, ₫25.47b), hannaholala (2.1m, 71.01% female, 25-34 49.5%, ₫22.36b). Period 2026-10-15..2026-11-13.
- Videos: 2 per creator (top revenue rows of creator detail video table).
- Field status (`kalodata intake validate`): creators observed = username, followers, female %, age dist, gmv, sales volume, video rev, live rev; derived = profile_url; missing = category (not on page), audience_geography (locked). Videos observed = published_at, views, estimated_video_gmv, thumbnail_url; derived = video_url, media_access_status, transcript_status; missing = likes, comments, shares. Invalid rows: 0.
- Caveat: `sales_volume_30d` (Item Sold) comes from the creator rank list row, not the detail page; source_evidence records the detail URL for it (known provenance gap).

## Resume test
- Simulated crash (os._exit during 3rd video upsert): tasks done 4 / pending 4 / running 1, 2 creators 2 videos committed. `kalodata intake resume`: done 9, 3 creators, 6 videos. Second resume: no change.
- pytest: 18 passed.

## Media test (Agy, gemini-3.8-flash-high, prompt v1, 1 agy call of cap 3)
- Input: local MP4 7705660238917143816 + cover. Sandbox, no network.
- ffprobe 147 ms; frames fps=0.5 @360 px -> 12 frames in 538 ms; scene-change (gt(scene,0.3)) -> 0 frames (max score 0.0358, static live shot); audio -> 16 kHz mono wav 216 ms; no subtitle stream.
- Cover file is JPEG 1080x1920 despite .png name.
- Transcription BLOCKED: no local ASR (whisper/vosk) installed; Agy did not transcribe audio. Spoken claims/CTA UNVERIFIED.
- MediaAnalysis JSON validated and recorded (`kalodata media record`, media_tests row 1). Orchestrator checked 4 frames by eye (frames 1/4/8/12): on-screen text "Mua 2 tính xiền 1", red + blue Downy refill pouches, "Mega Chanhbeauty" live backdrop all correct. Error: Agy says pouches stay static/untouched; host holds them in frames 4 and 12.
- Tokens/latency/cost: NOT captured. agy run log files were lost (agy_run1.json/.stderr/.time missing after run; exit code 1). Agy's own estimate: 258 tokens/image x 12 = 3,096 image tokens (assumption, UNVERIFIED).
- Local ASR check (Lystiger's F9 = voxtype dictation): `voxtype transcribe --engine parakeet` (parakeet-tdt-0.6b-v3) on the clip -> English gibberish ("Mom but look at mommy ..."): Vietnamese unsupported. `--engine whisper` -> "whisper-cli not found"; local model ggml-base.en is English-only. Vietnamese ASR not available locally as installed.

## API probe (2026-11-15, Lystiger ran scripts/api_probe.py, 7 calls ~0.7 credit)
- Auth header: `secret-key: <key>` (first candidate, HTTP 200). Docs page rate limit now shows 500 req / 10 s (was 100 on earlier view).
- creator/detail returns 31 fields; values match UI capture to display rounding for all 3 creators (revenue, video/live revenue, sales volume, followers), at full precision (e.g. 34059023179.45 VND).
- `need_extra=true` only adds `revenue_trend` (daily series) and `top3_product_ids`. **No audience gender/age/geo via API** (VERIFIED for 3 creators). Only `creator_region`.
- Audience demographics therefore come from the creator detail page UI only (VERIFIED in browser). Page-visit cap: this same account shows the trial cap of 10 detail visits/day (observed 2026-11-14, see Access); whether a paid membership lifts it is UNVERIFIED.
- reports/api_probe.json: contact fields redacted.

## Vietnamese ASR install (2026-11-14)
- `pip install faster-whisper` OK (faster-whisper 1.2.1, ctranslate2 4.9.0).
- Model download `Systran/faster-whisper-small`: HTTP 429 Too Many Requests from huggingface.co (anonymous); model.bin stopped at 127.9 MB (.incomplete). Direct `curl` of resolve URLs also 429. Pending Lystiger `hf auth login`.
- 2026-11-15: a later re-run of `scripts/api_probe.py` returned an HTTP 400 HTML error and was discarded; the evidence file is `reports/api_probe_2026-11-15.json` (6 HTTP 200 records, contacts redacted). Script now writes a new timestamped file per run; same-second runs get `_1`, `_2` suffixes (no overwrite).
- 2026-11-15 rebuild (review A2): `Cover` is derived; `sales_volume_30d` source is the rank list URL; video source is the creator detail URL; stored capture time is raw `collected_at`. Supersedes lines 45-46 above. `intake validate`: invalid rows 0.

## Kalodata credit reconciliation (2026-11-16, live run)
- Baseline: account balance 153.5 at internal counter 11.0 (22:58 UTC 2026-11-14 timestamps in DB).
- Later: account balance 145.2 at internal counter 19.3.
- Account delta 8.3 = counter delta 8.3 (45 creator/detail at 0.1, 45 video/rank incl. not-found at 0 credits).
- Conclusion: config/kalodata_prices.yaml prices for creator/detail and video/rank match real billing. S2 UI view price still UNVERIFIED (placeholder 1.0).
