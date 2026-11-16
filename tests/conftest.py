from datetime import datetime, timezone

import pytest

from kalodata_intake import db, mapping

NOW = datetime(2026, 11, 14, 11, 37, 58, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture
def creator_fields():
    labels = mapping.KALODATA_CREATOR_FIELDS
    return {
        mapping.CREATOR_ID_LABEL: "c1",
        labels["username"]: "alice",
        labels["followers"]: "1.2M",
        labels["female_audience_percentage"]: "45%",
        labels["gmv_30d"]: "₫1.5B",
    }


@pytest.fixture
def creator(creator_fields):
    return mapping.normalize_creator(creator_fields, "https://example.test/c/1", "30d", NOW)


@pytest.fixture
def video_fields():
    labels = mapping.KALODATA_VIDEO_FIELDS
    return {
        mapping.VIDEO_ID_LABEL: "v1",
        mapping.VIDEO_CREATOR_ID_LABEL: "c1",
        labels["views"]: "12.3K",
        labels["estimated_video_gmv"]: "₫500M",
    }


@pytest.fixture
def video(video_fields):
    return mapping.normalize_video(video_fields, "https://example.test/v/1", "30d", NOW)


@pytest.fixture
def raw_file(tmp_path, creator_fields, video_fields):
    import json

    path = tmp_path / "raw.json"
    path.write_text(json.dumps([
        {"type": "creator", "source": "https://example.test/c/1", "period": "30d", "fields": creator_fields},
        {"type": "video", "source": "https://example.test/v/1", "period": "30d", "fields": video_fields},
    ]))
    return path
