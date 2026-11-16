from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DataStatus = Literal["observed", "estimated", "missing", "derived"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FieldValue(BaseModel):
    value: Any | None
    status: DataStatus
    raw_field: str | None = None
    source: str | None = None
    collected_at: datetime = Field(default_factory=_now)
    period: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _value_matches_status(self):
        if self.status == "missing" and self.value is not None:
            raise ValueError("missing field must have value None")
        if self.status != "missing" and self.value is None:
            raise ValueError(f"{self.status} field needs a value; use missing()")
        return self


def missing(raw_field: str | None, note: str, source: str | None = None,
            collected_at: datetime | None = None) -> FieldValue:
    extra = {} if collected_at is None else {"collected_at": collected_at}
    return FieldValue(value=None, status="missing", raw_field=raw_field, source=source, note=note, **extra)


def _absent() -> FieldValue:
    return missing(None, "not collected")


class Creator(BaseModel):
    creator_id: str
    username: FieldValue = Field(default_factory=_absent)
    profile_url: FieldValue = Field(default_factory=_absent)
    followers: FieldValue = Field(default_factory=_absent)
    category: FieldValue = Field(default_factory=_absent)
    female_audience_percentage: FieldValue = Field(default_factory=_absent)
    audience_age_distribution: FieldValue = Field(default_factory=_absent)
    audience_geography: FieldValue = Field(default_factory=_absent)
    gmv_30d: FieldValue = Field(default_factory=_absent)
    sales_volume_30d: FieldValue = Field(default_factory=_absent)
    video_revenue_30d: FieldValue = Field(default_factory=_absent)
    live_revenue_30d: FieldValue = Field(default_factory=_absent)


class Video(BaseModel):
    video_id: str
    creator_id: str
    video_url: FieldValue = Field(default_factory=_absent)
    published_at: FieldValue = Field(default_factory=_absent)
    views: FieldValue = Field(default_factory=_absent)
    likes: FieldValue = Field(default_factory=_absent)
    comments: FieldValue = Field(default_factory=_absent)
    shares: FieldValue = Field(default_factory=_absent)
    estimated_video_gmv: FieldValue = Field(default_factory=_absent)
    thumbnail_url: FieldValue = Field(default_factory=_absent)
    media_access_status: FieldValue = Field(default_factory=_absent)
    transcript_status: FieldValue = Field(default_factory=_absent)


def field_values(model: BaseModel) -> dict[str, FieldValue]:
    return {k: getattr(model, k) for k in type(model).model_fields if isinstance(getattr(model, k), FieldValue)}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpeningHook(_Strict):
    text: str
    start_s: float
    end_s: float


class ProductAppearance(_Strict):
    start_s: float
    end_s: float
    description: str


class ProductDemonstration(_Strict):
    present: bool
    start_s: float | None = None
    end_s: float | None = None
    description: str | None = None


class Claim(_Strict):
    text: str
    modality: Literal["spoken", "on_screen"]
    start_s: float


class CallToAction(_Strict):
    text: str
    start_s: float


class MediaAnalysis(_Strict):
    video_id: str
    opening_hook: OpeningHook | None = None
    product_appearances: list[ProductAppearance] = []
    product_demonstration: ProductDemonstration | None = None
    claims: list[Claim] = []
    call_to_action: CallToAction | None = None
    notes: str | None = None
