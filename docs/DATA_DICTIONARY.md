# Data Dictionary

Normalized model: `src/kalodata_intake/schemas.py` (`Creator`, `Video`). Labels: `src/kalodata_intake/mapping.py`. API field names: `docs/FACTS.md` (API section) and `reports/api_probe_2026-11-15.json`.

Status column = status as stored in `data/intake.db` (what `kalodata intake validate` reports). Status values: `observed` (read from source), `derived` (built by capture code), `missing` (not available, with note). Values in `data/sample_creators.json` and `data/sample_videos.json`.

Note: the mapping file's own comment says the labels are placeholders to fix against real captures. The labels below are the ones the capture script uses.

## Creator

| Field | Type | Kalodata UI label | API field | Status | Notes |
|---|---|---|---|---|---|
| `creator_id` | string | Creator ID (from detail URL `id`) | `creator_id` | key | Primary key. Not a FieldValue. |
| `username` | string | Handle | `creator_handle` | observed | Stored without `@`. API value has `@`. |
| `profile_url` | string (URL) | View on TikTok | none | derived | `https://www.tiktok.com/@<handle>`. Not fetched. |
| `followers` | integer | Followers | `creator_followers` (string) | observed | Exact on 3/3. UI shows e.g. 2.4m. |
| `category` | string | Category | none | missing | Detail page has no creator category (only a filter). |
| `female_audience_percentage` | number (%) | Follower gender: Female | none | observed | UI only. Stored as number, no `%`. |
| `audience_age_distribution` | object `{bucket: "xx.x%"}` | Follower age | none | observed | UI only. Values kept as strings with `%`. Buckets 18-24, 25-34, 35-44, 45-54, 55+. |
| `audience_geography` | object | Top 5 Locations | none | missing | Locked on trial (requires credits). |
| `gmv_30d` | number (VND) | Revenue | `revenue` | observed | 30-day window. UI rounded (see parity). |
| `sales_volume_30d` | integer | Item Sold | `sales_volumn` (API typo) | observed | Value from creator rank list row, not detail page. `source` = `https://www.kalodata.com/creator` (via `_field_sources`). |
| `video_revenue_30d` | number (VND) | Video Revenue | `video_revenue` | observed | UI rounded. |
| `live_revenue_30d` | number (VND) | Live Revenue | `live_revenue` | observed | UI rounded. |

Period for UI values: `2026-10-15..2026-11-13` (stored in `period`).

API-only creator fields (not in the normalized model): `creator_status`, `creator_region`, `creator_belonged_shop_id`, `creator_bio`, `unit_price`, `video_views`, `live_views`, `live_gpm`, `video_gpm`, `new_followers`, `video_number`, `live_number`, `shop_number`, `product_number`, `revenue_trend` (`need_extra=true`), `top3_product_ids` (`need_extra=true`). Contact fields (`creator_contact_*`) are PII: not stored.

## Video

| Field | Type | Kalodata UI label | API field | Status | Notes |
|---|---|---|---|---|---|
| `video_id` | string | Video ID (from detail URL `id`) | `video_id` | key | Primary key. |
| `creator_id` | string | Creator ID (video table) | `belonged_creator_id` | key | Foreign key to creator. |
| `video_url` | string (URL) | View on TikTok | none (`video/url` gives signed MP4 URL, not TikTok) | derived | TikTok URL pattern. Not fetched. |
| `published_at` | string `MM/DD/YYYY` | Publish Date | UNVERIFIED (not in excerpt read) | observed | Stored as text, not ISO. Format confirmed MM/DD by `08/30/2026`. |
| `views` | integer | Views | `views` | observed | UI-rounded (stored values such as 888400 imply K/B display text; raw text not kept). |
| `likes` | integer | Likes | none in excerpt | missing | Not on list or detail page. |
| `comments` | integer | Comments | none in excerpt | missing | Same. |
| `shares` | integer | Shares | none in excerpt | missing | Same. |
| `estimated_video_gmv` | number (VND) | Revenue (video table) | `revenue` | observed | Period semantics UNVERIFIED: 4 of 6 videos published before 10/15/2026. |
| `thumbnail_url` | string (URL) | Cover | none | derived | Built in `scripts/capture_creator.py:82` as `img.kalocdn.com/tiktok.video/<id>/cover.png`. One URL checked HTTP 200. File is JPEG. |
| `media_access_status` | string | Media Access | none | derived | Constant `player_mp4_listed (not downloaded)` (`capture_creator.py:83`) or `downloaded_via_kalodata_player_mp4` (1 row). |
| `transcript_status` | string | Transcript | none | derived | Constant `none_from_source` (`capture_creator.py:84`). Not proof of no speech. |

Provenance of video rows: `source` = the creator detail page the row was read from (`https://www.kalodata.com/creator/detail?id=<creator_id>`). The one video with its own detail visit (7705660238917143816) has `Media Access` overridden to `https://www.kalodata.com/video/detail?id=7705660238917143816`.

API fields for video detail (from FACTS): `video_id`, `region`, `title`, `belonged_creator_id/handle`, product count, revenue, sales volume, views, GPM, ad views, ROAS, ad cost, ad flag, `ai_video`. `title` and ad metrics are not normalized. Ad metrics masked on UI video table (`****`) but ROAS shown on video detail page (`docs/FACTS.md` Method 3).

## Parity check: UI vs API (3 creators, period 30 d)

UI values are the stored values. API values from `reports/api_probe_2026-11-15.json` (plain call). Delta = UI - API.

| Creator | Field | UI stored | API | Delta |
|---|---|---|---|---|
| @chanhbeauty93 | revenue | 34,060,000,000 | 34,059,023,179.45 | +976,820.55 |
| @chanhbeauty93 | video revenue | 14,100,000,000 | 14,095,950,665.99 | +4,049,334.01 |
| @chanhbeauty93 | live revenue | 18,850,000,000 | 18,847,322,141.33 | +2,677,858.67 |
| @chanhbeauty93 | sales volume | 134,760 | 134,757 | +3 |
| @trangtrankoc | revenue | 25,470,000,000 | 25,466,609,160.26 | +3,390,839.74 |
| @trangtrankoc | video revenue | 2,480,000,000 | 2,484,975,111.58 | -4,975,111.58 |
| @trangtrankoc | live revenue | 22,430,000,000 | 22,428,466,659.36 | +1,533,340.64 |
| @trangtrankoc | sales volume | 110,080 | 110,079 | +1 |
| @hannaholala | revenue | 22,360,000,000 | 22,362,554,583.10 | -2,554,583.10 |
| @hannaholala | video revenue | 2,700,000,000 | 2,704,047,288.80 | -4,047,288.80 |
| @hannaholala | live revenue | 17,660,000,000 | 17,663,188,355.13 | -3,188,355.13 |
| @hannaholala | sales volume | 23,580 | 23,576 | +4 |
| all 3 | followers | 2,400,000 / 786,600 / 2,100,000 | "2400000" / "786600" / "2100000" | 0 |

Read: UI values agree with API to display rounding (B to 2 dp; K for sales). Not exact.
