import re
from datetime import datetime
from typing import Any

from .schemas import Creator, FieldValue, Video, missing

# Placeholder raw Kalodata labels. Orchestrator to fix against real captures.
KALODATA_CREATOR_FIELDS = {
    "username": "Handle",
    "profile_url": "View on TikTok",
    "followers": "Followers",
    "category": "Category",
    "female_audience_percentage": "Follower gender: Female",
    "audience_age_distribution": "Follower age",
    "audience_geography": "Top 5 Locations",
    "gmv_30d": "Revenue",
    "sales_volume_30d": "Item Sold",
    "video_revenue_30d": "Video Revenue",
    "live_revenue_30d": "Live Revenue",
}
KALODATA_VIDEO_FIELDS = {
    "video_url": "View on TikTok",
    "published_at": "Publish Date",
    "views": "Views",
    "likes": "Likes",
    "comments": "Comments",
    "shares": "Shares",
    "estimated_video_gmv": "Revenue",
    "thumbnail_url": "Cover",
    "media_access_status": "Media Access",
    "transcript_status": "Transcript",
}
# Values the capture step builds rather than reads off the page.
DERIVED_LABELS = {"View on TikTok", "Media Access", "Transcript", "Cover"}
# Optional per-record reasons for missing labels: raw["_missing_notes"][label] = reason
# Optional per-label source overrides: raw["_field_sources"][label] = url the value was read from
CREATOR_ID_LABEL = "Creator ID"
VIDEO_ID_LABEL = "Video ID"
VIDEO_CREATOR_ID_LABEL = "Creator ID"

NUMERIC_CREATOR = {
    "followers", "female_audience_percentage", "gmv_30d",
    "sales_volume_30d", "video_revenue_30d", "live_revenue_30d",
}
NUMERIC_VIDEO = {"views", "likes", "comments", "shares", "estimated_video_gmv"}

_MULTIPLIER = {"": 1, "%": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
_NUMBER = re.compile(r"^(-?\d+(?:\.\d+)?)([KMB%]?)$", re.IGNORECASE)


def parse_number(raw: Any) -> int | float | None:
    """'1.2M' -> 1200000, '₫1.5B' -> 1500000000, '45%' -> 45. None if unparseable."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return raw
    if not isinstance(raw, str):
        return None
    text = re.sub(r"[₫$€£,\s]", "", raw)
    match = _NUMBER.match(text)
    if not match:
        return None
    result = round(float(match.group(1)) * _MULTIPLIER[match.group(2).upper()], 6)
    return int(result) if result.is_integer() else result


def _require(fields: dict, label: str) -> str:
    value = fields.get(label)
    if value in (None, ""):
        raise ValueError(f"raw record lacks {label!r}")
    return str(value)


def creator_id(fields: dict) -> str:
    return _require(fields, CREATOR_ID_LABEL)


def video_id(fields: dict) -> str:
    return _require(fields, VIDEO_ID_LABEL)


def _value(fields: dict, label: str, numeric: bool, source: str, period: str | None,
           collected_at: datetime) -> FieldValue:
    source = fields.get("_field_sources", {}).get(label, source)
    if fields.get(label) in (None, ""):
        note = fields.get("_missing_notes", {}).get(label, "label absent from raw record")
        return missing(label, note, source, collected_at)
    raw = fields[label]
    value = parse_number(raw) if numeric else raw
    if value is None:
        return missing(label, f"unparseable number: {raw!r}", source, collected_at)
    status = "derived" if label in DERIVED_LABELS else "observed"
    return FieldValue(value=value, status=status, raw_field=label, source=source, period=period,
                      collected_at=collected_at)


def normalize_creator(raw: dict, source: str, period: str | None, collected_at: datetime) -> Creator:
    fields = {
        name: _value(raw, label, name in NUMERIC_CREATOR, source, period, collected_at)
        for name, label in KALODATA_CREATOR_FIELDS.items()
    }
    return Creator(creator_id=creator_id(raw), **fields)


def normalize_video(raw: dict, source: str, period: str | None, collected_at: datetime) -> Video:
    fields = {
        name: _value(raw, label, name in NUMERIC_VIDEO, source, period, collected_at)
        for name, label in KALODATA_VIDEO_FIELDS.items()
    }
    return Video(
        video_id=video_id(raw),
        creator_id=_require(raw, VIDEO_CREATOR_ID_LABEL),
        **fields,
    )
