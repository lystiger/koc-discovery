import pytest

from datetime import datetime, timezone

from kalodata_intake import mapping

NOW = datetime(2026, 11, 14, 11, 37, 58, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "raw, expected",
    [("1.2M", 1_200_000), ("₫1.5B", 1_500_000_000), ("45%", 45), ("12.3K", 12_300), ("1,234", 1234)],
)
def test_parse_number(raw, expected):
    assert mapping.parse_number(raw) == expected


def test_parse_number_unparseable_returns_none():
    assert mapping.parse_number("n/a") is None


def test_normalize_creator_observed_and_missing(creator_fields):
    creator = mapping.normalize_creator(creator_fields, "https://example.test/c/1", "30d", NOW)
    assert creator.followers.value == 1_200_000
    assert creator.followers.status == "observed"
    assert creator.followers.raw_field == mapping.KALODATA_CREATOR_FIELDS["followers"]
    # label absent from the raw record -> missing, value None
    assert creator.live_revenue_30d.status == "missing"
    assert creator.live_revenue_30d.value is None


def test_cover_is_derived_not_observed(video_fields):
    labels = mapping.KALODATA_VIDEO_FIELDS
    video_fields[labels["thumbnail_url"]] = "https://img.kalocdn.com/tiktok.video/v1/cover.png"
    video = mapping.normalize_video(video_fields, "https://example.test/v/1", "30d", NOW)
    assert video.thumbnail_url.status == "derived"


def test_field_sources_override_record_source(creator_fields):
    creator_fields["_field_sources"] = {mapping.KALODATA_CREATOR_FIELDS["sales_volume_30d"]: "https://example.test/rank"}
    creator_fields[mapping.KALODATA_CREATOR_FIELDS["sales_volume_30d"]] = "134.76k"
    creator = mapping.normalize_creator(creator_fields, "https://example.test/c/1", "30d", NOW)
    assert creator.sales_volume_30d.source == "https://example.test/rank"
    assert creator.followers.source == "https://example.test/c/1"


def test_collected_at_preserved_from_raw(creator_fields):
    creator = mapping.normalize_creator(creator_fields, "https://example.test/c/1", "30d", NOW)
    assert creator.followers.collected_at == NOW
    # missing fields keep the capture time too
    assert creator.live_revenue_30d.collected_at == NOW
