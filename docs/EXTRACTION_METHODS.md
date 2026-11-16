# Extraction Methods

Five methods assessed. Sources: `docs/FACTS.md` (Methods 1-5), `scripts/capture_creator.py`, `scripts/api_probe.py`, `reports/api_probe_2026-11-15.json`.

## Summary

| # | Method | Availability | Used? | Automation permitted? | Verdict |
|---|---|---|---|---|---|
| 1 | CSV / Excel export | Button on creator list and detail tables | No | UNVERIFIED | Untested |
| 2 | Documented Open API | Key from Account page; credit-priced | Yes (7 calls, 3 creators) | Documented; terms UNVERIFIED | Works for commercial data |
| 3 | Browser UI capture | Trial account; 10 detail visits/day | Yes (4 visits) | No (operator-supervised by design); terms UNVERIFIED | Works; audience only here |
| 4 | Network inspection | Undocumented internal endpoints | Notes only | No (not automated) | Not used |
| 5 | Linked video assets (MP4) | Player URL, signed | Yes (1 file) | No bulk; terms UNVERIFIED | Works for one file |

## 1. CSV / Excel export
- **Fields:** UNVERIFIED (export not clicked).
- **Availability:** "Export" button on creator rank list and on creator detail tables (video, product, live) (`docs/FACTS.md` Method 1).
- **Permissions:** Trial entitlement UNVERIFIED.
- **Limits / throughput / failure:** UNVERIFIED.
- **Automation permitted?** UNVERIFIED.
- **Evidence:** `docs/FACTS.md` Method 1 ("Not clicked/tested").

## 2. Documented API (Kalodata Open Center)
- **Docs:** `https://www.kalodata.com/open-center/docs`. HTTP POST + JSON. Secret key in header.
- **Auth header:** `secret-key: <key>`, first candidate, HTTP 200 (`docs/FACTS.md` API probe).
- **Endpoints listed:** tiktok/creator (detail, ranking list, avatar); tiktok/video (detail, ranking list, video URL); product, shop, livestream, category.
- **Fields (creator/detail):** 31 fields returned (see `docs/DATA_DICTIONARY.md`). No audience gender, age or geography.
- **Fields (video/detail):** see `docs/DATA_DICTIONARY.md`. No likes, comments or shares in the excerpt read.
- **Video URL:** CloudFront signed URL + `expires_at`. Not called.
- **Pricing:** detail 0.1 credit/call; rank 0.1 x ceil(rows/100); video URL 0.5 credit/call; product images/comments 0.01. 1 point ~ 0.1 USD (docs).
- **Rate limit:** 100 req / 10 s (earlier view); 500 req / 10 s (current view) (`docs/FACTS.md` line 62).
- **Throughput:** 7 calls in one run. Wall time not recorded. At-scale throughput UNMEASURED.
- **Failure conditions:** `scripts/api_probe.py` stops on non-200 or `success` false (lines 81-84). Auth candidates treated as failed on 401/403 or auth-like text (`api_probe.py` `find_header`). Rate-limit (429) behaviour: UNVERIFIED (not hit).
- **Automation permitted?** Documented API use. Usage terms and plan entitlement UNVERIFIED.
- **Evidence:** `reports/api_probe_2026-11-15.json` (6 bodies, all 200, `success: true`); `docs/FACTS.md` Method 2 and API probe.

## 3. Browser UI capture (authorized, operator-supervised)
- **Pages:** creator rank list `/creator` (268,815 creators in VN list, pagination); creator detail `/creator/detail?id=<id>`; video detail `/video/detail?id=<id>` (`docs/FACTS.md` Method 3).
- **Fields:** see `docs/DATA_DICTIONARY.md`. Audience (gender, age) only here.
- **Setup:** Lystiger logs in manually in headed Chromium (CDP 127.0.0.1:9333). Script attaches to the operator's tab with `creator/detail` in the URL (`scripts/capture_creator.py`). No cookies, headers or network bodies read.
- **Throughput:** 15-20 s per creator (7 s settle + scroll) + >= 5 s pacing (`docs/FACTS.md` line 32).
- **Limits:** trial 10 detail-page visits/day (4 used at capture, 6 left). "Top 5 Locations" locked. Live recordings locked. Creator debut time `****`. Video ad metrics `****` in table (ROAS visible on video detail).
- **Failure conditions:** page not open in tab (script takes last `creator/detail` tab, errors if none); regex parsing of `innerText` returns None on layout change (`capture_creator.py` `grab`); "Views" regex depends on row text order (`capture_creator.py:80`); Item Sold must be passed in (not on detail page).
- **Automation permitted?** No. Script is designed for supervised, authorized-UI use. Terms UNVERIFIED.
- **Evidence:** `docs/FACTS.md` Access, Method 3; `scripts/capture_creator.py` docstring and lines 52-83.

## 4. Network inspection
- **Endpoints seen (paths only):** `/creator/queryList`, `/creator/count`, `/creator/enrich` (JSON envelope `success`, `data`, `message`, `cached`, `code`).
- **Status:** Undocumented internal endpoints. Not automated. Query strings, headers and bodies not logged (`docs/FACTS.md` Method 4).
- **Limits / throughput / failure:** UNVERIFIED (not measured; endpoints may change without notice).
- **Automation permitted?** No. Not used by this spike.
- **Evidence:** `docs/FACTS.md` Method 4.

## 5. Linked video assets (MP4)
- **Source:** Kalodata player serves MP4 from `live.kalocdn.com` with signed `key` and `time` params. "Download" and "Storyboard Export" buttons exist on video detail (`docs/FACTS.md` Method 3, 5).
- **Result:** 1 file: `7705660238917143816.mp4`, 5,441,136 B, 24.6 s, h264 576x1024 + aac. 24.7 s download (`docs/FACTS.md` Method 5).
- **TikTok URLs:** derived from handle + id, not fetched.
- **Limits:** URL expiry UNVERIFIED (signed params). Only one file tested.
- **Automation permitted?** No bulk use. Single supervised download. Terms UNVERIFIED.
- **Evidence:** `docs/FACTS.md` Method 5; `reports/agy/MEDIA_FINDINGS.md` section 2.
