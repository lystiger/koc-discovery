# Kalodata Intake Feasibility: Phase 0 Answers

Date: 2026-11-15. Sources: `docs/FACTS.md` (evidence log), `reports/agy/MEDIA_FINDINGS.md`, `reports/agy/media_analysis_7705660238917143816.json`, `reports/api_probe_2026-11-15.json`, `src/kalodata_intake/`, `scripts/`. Sample: 3 creators, 6 videos, 1 media test.

Verdict key: VERIFIED (checked with evidence in this repo), PARTIALLY VERIFIED (some parts checked), UNVERIFIED (no evidence), BLOCKED (tried, cannot proceed).

## Summary

| # | Question | Verdict |
|---|---|---|
| 1 | Creator data extractable? | VERIFIED |
| 2 | Audience demographics? (UI yes, API no) | VERIFIED |
| 3 | Commercial metrics? | VERIFIED |
| 4 | Individual video URLs? | PARTIALLY VERIFIED |
| 5 | Frames + audio analyzable? | PARTIALLY VERIFIED (ASR BLOCKED) |
| 6 | Missing / unreliable data | VERIFIED |
| 7 | Permitted methods | PARTIALLY VERIFIED |
| 8 | Measured extraction + inference costs | PARTIALLY VERIFIED |
| 9 | Resume after interruption | PARTIALLY VERIFIED |
| 10 | 3-day MVP feasible | PARTIALLY VERIFIED. Recommendation: GO, scoped |

## 1. Creator data extractable?
**VERIFIED.** 9 of 11 creator fields populated for all 3 creators (username, profile_url, followers, female %, age buckets, revenue, item sold, video revenue, live revenue). Category and audience geography are missing.
- Evidence: `reports/feasibility.json` `field_status` (creator.* observed=3 or derived=3); `data/sample_creators.json`.
- Evidence: API `creator/detail` returned 31 fields for all 3 creators (`reports/api_probe_2026-11-15.json`, all status 200, `success: true`).

## 2. Audience demographics?
**VERIFIED** (3-creator sample). UI yes, API no.
- UI: follower gender % and age buckets (18-24, 25-34, 35-44, 45-54, 55+) on creator detail page (`docs/FACTS.md` Method 3). Stored for 3/3 creators (`data/sample_creators.json`).
- API: no gender, age or geography field. Probe with `need_extra=true` fills only `revenue_trend` and `top3_product_ids`, both null in plain calls (`docs/FACTS.md` API probe; `reports/api_probe_2026-11-15.json`).
- Geography: UI "Top 5 Locations" locked on trial plan (requires credits). Missing 3/3.
- Limit: UI capture uses the trial cap of 10 detail-page visits per day (see Q8 and Q10).

## 3. Commercial metrics?
**VERIFIED.** Revenue, video revenue, live revenue, item sold and followers available. API gives full precision; UI gives rounded display values.
- API values match UI at display precision only, not exact. Deltas are in `docs/DATA_DICTIONARY.md` (parity table). Example: chanhbeauty93 revenue UI 34,060,000,000 vs API 34,059,023,179.45.
- `docs/FACTS.md` line 63 already says "to display rounding". Largest delta: 4,975,111.58 VND (trangtrankoc video revenue: UI 2.48B, API 2,484,975,111.58).
- Followers match exactly for all 3.
- Item sold comes from the creator rank list row, not the detail page. Source is recorded as the rank list URL (`_field_sources`, fixed 2026-11-15).

## 4. Individual video URLs?
**PARTIALLY VERIFIED.**
- Kalodata `video_id` and video table rows captured for 3/3 creators (2 each): `data/sample_videos.json` (6 rows).
- TikTok URL (`https://www.tiktok.com/@<handle>/video/<id>`) is built by the capture script, not fetched. Status UNVERIFIED that it resolves (`docs/FACTS.md` Method 5).
- One Kalodata-hosted MP4 downloaded: 7705660238917143816, 5,441,136 B, 24.6 s (`docs/FACTS.md` Method 5).
- API `video/url` returns a CloudFront signed URL with `expires_at`. Documented, not called (UNVERIFIED).

## 5. Frames + audio analyzable?
**PARTIALLY VERIFIED.** Frames: yes. Audio speech: BLOCKED.
- Frames: 12 frames at fps=0.5, 360x640, in 538 ms. Agy output validated against schema (`reports/agy/MEDIA_FINDINGS.md` section 2; `reports/agy/media_analysis_7705660238917143816.json`). Orchestrator checked frames 1, 4, 8, 12 by eye: on-screen text, products and backdrop correct; one error (Q6).
- Scene-change frames: 0 (max score 0.0358 vs threshold 0.3). Static tripod shot.
- Audio: extracted to 16 kHz mono WAV (216 ms). No caption/subtitle stream.
- Vietnamese ASR: BLOCKED. `voxtype --engine parakeet` gives English gibberish (Vietnamese unsupported). `--engine whisper`: `whisper-cli` not found. `ggml-base.en` is English-only (`docs/FACTS.md` Media test).
- faster-whisper model download `Systran/faster-whisper-small` hit HTTP 429 from huggingface.co (anonymous). Pending `hf auth login` (`docs/FACTS.md` line 70).
- Spoken claims and spoken CTA: UNVERIFIED.

## 6. Missing / unreliable data
**VERIFIED** (inventory). Detail in `docs/DATA_DICTIONARY.md` and `docs/RISKS.md`.

| Item | Status | Evidence |
|---|---|---|
| Likes, comments, shares | Missing for 6/6 videos. Not on list or detail page. API excerpt read does not list them (full API video/detail UNVERIFIED) | `data/sample_videos.json`; `docs/FACTS.md` Method 3 |
| Category | Missing 3/3. Detail page has only a filter | `scripts/capture_creator.py` note; `data/sample_creators.json` |
| Audience geography | Missing 3/3. Locked on trial | `scripts/capture_creator.py` note |
| Item sold provenance | Value from rank list row. Source now recorded as the rank list URL via `_field_sources` (fixed 2026-11-15). Was the detail URL (`docs/FACTS.md` line 46, historical) | `data/raw/creator_*.json`; `data/sample_creators.json` |
| Video row provenance | Video values come from the creator detail video table, so source is the creator detail URL. `Media Access` for 7705660238917143816 also has its own video detail URL (`_field_sources`) | `data/raw/creator_*.json` |
| Capture time | Stored per field from raw `collected_at`. Was ingestion time (fixed 2026-11-15) | `src/kalodata_intake/mapping.py` |
| Rounding | UI values rounded (e.g. 34.06B). API precise | Q3 |
| Agy "static pouches" error | Agy says pouches static and untouched. Orchestrator sees host holding them in frames 4 and 12. MEDIA_FINDINGS marks this VERIFIED: wrong | `reports/agy/MEDIA_FINDINGS.md` section 7; `docs/FACTS.md` line 57 |
| Agy "all frames" | MEDIA_FINDINGS says all 12 frames inspected. Orchestrator checked 4. Other 8: UNVERIFIED | `docs/FACTS.md` line 57 |
| Cover file | `.png` extension, actual JPEG 1080x1920 | `reports/agy/MEDIA_FINDINGS.md` 1b |
| Thumbnail status | Was stored as `observed` (wrong). URL is constructed at `scripts/capture_creator.py:82`. Now `derived` after adding `Cover` to `DERIVED_LABELS` (fixed 2026-11-15) | `data/sample_videos.json` |
| Publish date format | MM/DD/YYYY (`08/30/2026`, `10/14/2026` confirm). 4 of 6 videos published before 10/15/2026 (period start) | `data/sample_videos.json` |
| `transcript_status` | Constant `none_from_source` (`scripts/capture_creator.py:84`). Not evidence of silence | script |
| Views parse | Regex on row text (`scripts/capture_creator.py:80`). One sample per field checked only | script |

## 7. Permitted methods
**PARTIALLY VERIFIED.**
- Kalodata Open API: documented for programmatic use, key from Account page, credit-priced (`docs/FACTS.md` Method 2). Terms of use: UNVERIFIED.
- Browser UI capture: operator-supervised. Lystiger logs in manually; capture attaches to his tab over CDP; no cookies, headers or bodies stored (`docs/FACTS.md` Access; `scripts/capture_creator.py` docstring). Terms: UNVERIFIED.
- Network inspection: paths only, undocumented endpoints, not automated (`docs/FACTS.md` Method 4).
- MP4 download: one file via session player request (`docs/FACTS.md` Method 5). Terms: UNVERIFIED.
- CSV export: button present, not tested (`docs/FACTS.md` Method 1).
- PII: creator contact email is not stored (`docs/FACTS.md` line 29). Contact fields are redacted in `reports/api_probe_2026-11-15.json`. `scripts/api_probe.py` redacts them at lines 75-78 (see RISKS R9).
- No legal or ToS review is in the evidence. Automated bulk use is not permitted by this spike's design; that is a decision for Lystiger.

## 8. Measured extraction + inference costs
**PARTIALLY VERIFIED.** Measured where marked.

| Item | Measured | Cost | Basis |
|---|---|---|---|
| API `creator/detail` | 7 calls total: 1 header-discovery call + 6 probe calls. About 0.7 credit | 0.1 credit/call. About $0.01/call if 1 point = 0.1 USD and credit = point (UNVERIFIED equivalence) | `reports/api_probe_2026-11-15.json`; `docs/FACTS.md` Pricing and probe |
| API `video/url` | Not called | 0.5 credit/call (documented) | `docs/FACTS.md` Method 2 |
| API rank list | Not called | 0.1 x ceil(rows/100) | `docs/FACTS.md` Method 2 |
| UI capture | 4 detail visits used (3 creator, 1 video), 6 left at capture time. 15-20 s per creator + >=5 s pacing | No charge measured (trial) | `docs/FACTS.md` Access, Method 3 |
| Agy media run | 1 call. Tokens, latency, cost NOT captured (run logs lost, exit 1). Estimate 12 x 258 = 3,096 image tokens (Agy assumption) | UNVERIFIED | `reports/agy/MEDIA_FINDINGS.md` section 5; `docs/FACTS.md` line 58 |
| ffmpeg preprocessing | ffprobe 147 ms; frame extraction 538 ms; audio 216 ms | No cost | `reports/agy/MEDIA_FINDINGS.md` section 2 |
| Vietnamese ASR | None produced | BLOCKED | Q5 |

## 9. Resume after interruption
**PARTIALLY VERIFIED.**
- Ad hoc test: process killed (`os._exit`) during 3rd video upsert. After crash: tasks done 4, pending 4, running 1; 2 creators and 2 videos committed. `kalodata intake resume`: done 9, 3 creators, 6 videos. Second resume: no change (`docs/FACTS.md` Resume test). The killer script is not in the repo.
- Repo unit test `tests/test_db.py:56` simulates the crash by setting status `running` and calling `reset_running`. It does not kill a process.
- Rollback on failed write: `tests/test_db.py:39` (task stays `running`, no row written).
- Limit (code read): `next_pending_tasks` returns only `pending`. Failed tasks are not retried by `resume` (`src/kalodata_intake/db.py`, `cli.py _process`).
- Limit (code read): `resume` on a finished run still rewrites `finished_at`.

## 10. 3-day MVP feasible?
**PARTIALLY VERIFIED.** Recommendation: **GO**, scoped as below. The "3 days" duration is UNVERIFIED: no build-time data in the evidence.

Scope (from evidence):
- Commercial data: Kalodata API for the whole shortlist. Verified at 3 creators. Throughput at scale UNMEASURED. Docs rate limit 500 req / 10 s (earlier view showed 100).
- Audience data: UI capture only, and only for the shortlist. Trial cap: 10 detail visits/day. Derived arithmetic: 3 days x 10 = 30 detail visits total, creator and video visits combined (`docs/FACTS.md` line 13; line 30 counts video visits too). Whether a paid plan lifts this cap is UNVERIFIED, and so is its price.
- Video analysis: shortlist only. Frames work. Spoken content blocked until Vietnamese ASR works.
- Pricing for a shortlist via API (derived, UNVERIFIED equivalence): 100 creator detail calls = 10 credits.

Conditions to stay GO:
1. Confirm API plan entitlement and cost for the shortlist size.
2. Fix Vietnamese ASR (HF login pending, see Q5) or accept spoken claims as out of scope.
3. Read the Kalodata terms before any automated UI use.
