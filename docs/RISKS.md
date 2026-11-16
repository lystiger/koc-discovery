# Risks

Likelihood and impact are qualitative judgments (Low / Medium / High). Evidence column cites the source. "Observed" = seen in repo evidence. "Judgment" = assessment, not measured.

| ID | Risk | Likelihood | Impact | Evidence | Mitigation |
|---|---|---|---|---|---|
| R1 | Trial cap of 10 detail-page visits/day limits UI capture (audience, video detail) | High (observed cap) | High | FACTS line 13 | Use API for commercial data. Use UI only on the shortlist. Price a paid plan (UNVERIFIED) |
| R2 | Audience demographics available only through UI. No API path | High (observed) | High | FACTS line 64; `reports/api_probe_2026-11-15.json` | Same as R1. Keep audience data to shortlist |
| R3 | Vietnamese ASR not working. Spoken claims and CTA unknown | High (observed) | Medium | FACTS line 59; MEDIA_FINDINGS section 4 | Fix HF login and retry a Vietnamese-capable model. Until then, mark spoken fields BLOCKED |
| R4 | Terms of service unknown for UI capture, MP4 download and API use | Unknown | High | No ToS in evidence | Read Kalodata terms before any automated run. Keep capture operator-supervised |
| R5 | Kalodata UI change breaks capture (regex on innerText, label placeholders) | Medium (judgment) | High | `scripts/capture_creator.py` `grab`; mapping.py placeholder comment | Schema validation (`intake validate`). Source evidence per field. Fixture tests on saved pages |
| R6 | Agy visual error ("pouches static") propagates as fact | Observed (1 error) | Medium | MEDIA_FINDINGS section 7; FACTS line 57 | Spot-check frames by hand. Mark field VERIFIED only after check |
| R7 | Agy token and cost data lost, so inference cost is unknown | Observed | Medium | FACTS line 58 | Save run stdout, stderr and timing outside the work dir before each run |
| R8 | Item sold provenance gap (value from list row, recorded with detail URL) | Fixed 2026-11-15 | Medium | FACTS line 46 (historical); `_field_sources` in `data/raw/creator_*.json` | Source for `sales_volume_30d` is the rank list URL. Verified in `source_evidence` |
| R9 | Raw API bodies contain creator contact fields (PII) | Low (judgment) | High (PII) | `scripts/api_probe.py:75-78` redacts non-empty `creator_contact_*`; `reports/api_probe_2026-11-15.json` shows "[redacted]"; FACTS line 66 | Redaction in script (done). Check contact fields in any new probe before commit |
| R10 | Stored status wrong: `thumbnail_url` shown `observed` but constructed. `transcript_status` constant | Fixed 2026-11-15 for `thumbnail_url` | Medium | capture_creator.py:82, 84; DB rows | "Cover" added to `DERIVED_LABELS` in mapping.py; `intake validate` rebuilt. `transcript_status` remains constant (not proof of no speech) |
| R11 | Rounding: UI values differ from API (displayed precision) | Observed | Low | DATA_DICTIONARY parity table | Prefer API for commercial figures. Document UI as rounded |
| R12 | Period semantics unclear for video revenue: 4 of 6 videos published before 2026-10-15 | Observed | Medium | `data/sample_videos.json` publish dates; FACTS line 43 | Verify with Kalodata what window the video table uses (UNVERIFIED) |
| R13 | Sample too small (3 creators, 6 videos) to generalize | High (judgment) | High | FACTS line 43 | Larger shortlist before scale claims |
| R14 | Signed URLs (MP4 player, API video URL) expire | Medium (judgment) | Medium | FACTS line 24, 39 (`expires_at` exists; expiry not measured) | Fetch on demand. Store `expires_at` |
| R15 | `resume` does not retry failed tasks. Re-run of finished run rewrites `finished_at` | Observed (code read) | Medium | `src/kalodata_intake/db.py next_pending_tasks`; `cli.py _process` | Retry failed tasks on resume. Add test |
| R16 | API cost overrun at scale | Medium (judgment) | Medium | FACTS line 25 (credit prices). Equivalence to USD UNVERIFIED | API probe loop capped at 6 calls; header discovery 0 calls when `KALODATA_AUTH_HEADER` is set (else 1-6). Planned credit counter for the build (not built yet) |
| R17 | API rate limit differs between docs views (100 vs 500 req / 10 s) | Observed | Low | FACTS line 62 | Re-check docs before scaling. Throttle to lower figure |
| R18 | Likes, comments, shares unavailable. Engagement metrics missing from model | Observed | Medium | `data/sample_videos.json` | Accept gap or find another source (UNVERIFIED) |
| R19 | Category unavailable on detail page | Observed | Medium | `data/sample_creators.json` | Use filters or other source (UNVERIFIED) |
| R20 | Trial entitlement for CSV export unknown | Unknown | Low | FACTS line 17 | Test export once, with Lystiger's approval |
