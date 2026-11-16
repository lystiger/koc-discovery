import pytest
from pydantic import ValidationError

from kalodata_intake.schemas import FieldValue, MediaAnalysis, missing


def test_missing_with_value_rejected():
    with pytest.raises(ValidationError):
        FieldValue(value=1, status="missing", raw_field="Followers", collected_at="2026-01-01T00:00:00Z")


def test_observed_without_value_rejected():
    with pytest.raises(ValidationError):
        FieldValue(value=None, status="observed", raw_field="Followers", collected_at="2026-01-01T00:00:00Z")


def test_missing_helper_is_valid():
    fv = missing("Followers", "label absent")
    assert fv.status == "missing" and fv.value is None and fv.raw_field == "Followers"


def test_media_analysis_rejects_extra_field():
    with pytest.raises(ValidationError):
        MediaAnalysis(video_id="v1", surprise=True)


def test_media_analysis_valid_passes():
    analysis = MediaAnalysis.model_validate({
        "video_id": "v1",
        "opening_hook": {"text": "wait for it", "start_s": 0.0, "end_s": 2.5},
        "product_appearances": [{"start_s": 3.0, "end_s": 6.0, "description": "bottle on table"}],
        "product_demonstration": {"present": True, "start_s": 3.0, "end_s": 9.0, "description": "applies serum"},
        "claims": [{"text": "cures acne", "modality": "on_screen", "start_s": 4.0}],
        "call_to_action": {"text": "tap the cart", "start_s": 20.0},
        "notes": None,
    })
    assert analysis.claims[0].modality == "on_screen"
