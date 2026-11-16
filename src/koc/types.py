"""Shared types between core and llm module. FROZEN: see docs/build/CONTRACTS.md; change only via orchestrator."""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field
from typing import Literal

class Usage(BaseModel):
    provider: Literal["gemini", "openrouter"]
    model: str                      # e.g. "gemini-3.8-flash"
    prompt_version: str             # e.g. "content_v1"
    input_tokens: int
    output_tokens: int
    audio_tokens: int | None = None
    image_tokens: int | None = None
    latency_ms: int
    cost_usd: float                 # computed from config price table
    cache_hit: bool = False

class VideoInput(BaseModel):
    video_id: str
    creator_id: str
    title: str | None
    publish_date: str | None
    views: int | None
    likes: int | None               # video/rank digg_count
    comments: int | None
    shares: int | None
    revenue_vnd: float | None
    mp4_path: str                   # local file, downloaded by core via video/url

class Evidence(BaseModel):
    evidence_id: str                # "<video_id>@<start_s>" or "<video_id>:transcript:<n>"
    video_id: str
    start_s: float
    end_s: float | None
    kind: Literal["frame", "speech", "on_screen_text"]
    quote_vi: str                   # exact Vietnamese text or concise VI description of the frame
    frame_path: str | None

class RubricScore(BaseModel):
    criterion: Literal["hook", "product_clarity", "demonstration", "claim_quality", "cta", "brand_fit", "production_quality"]
    score: int = Field(ge=0, le=5)
    rationale_vi: str
    evidence_ids: list[str]

class ContentAnalysis(BaseModel):
    video_id: str
    transcript_vi: str | None
    rubric: list[RubricScore]       # exactly 7, one per criterion
    risks_vi: list[str]             # e.g. exaggerated/medical claims
    evidence: list[Evidence]
    usage: Usage

class BrandBrief(BaseModel):
    product_vi: str                 # "kem chống nắng"
    audience_vi: str                # "Nữ, 18-30 tuổi"
    budget_vnd: int                 # 30_000_000

class CandidateSummary(BaseModel):   # input to reasons
    creator_id: str
    handle: str
    followers: int | None
    commercial_score: float
    audience_score: float | None
    content_score: float | None
    final_score: float
    est_cost_vnd: int
    metrics: dict[str, float | int | str | None]   # metric name -> value
    metric_evidence_ids: dict[str, str]           # metric name -> evidence id ("metric:<creator_id>:<name>")
    analyses: list[ContentAnalysis]

class Recommendation(BaseModel):
    creator_id: str
    reasons_vi: list[str]           # 3-5 bullets
    cited_evidence_ids: list[str]   # must all exist in input
    caveats_vi: list[str]
    usage: Usage


class BudgetExceeded(RuntimeError):
    """Raised when a paid call would push cumulative spend past the hard cap."""


class ProviderAccountError(RuntimeError):
    """Raised when an LLM provider account cannot make paid requests."""


class BudgetGuard(Protocol):
    def check(self, estimated_usd: float) -> None: ...
    def record(self, usage: Usage) -> None: ...


class CacheOnlyMiss(RuntimeError):
    """Raised in cache-only mode when a paid call would be needed (no network is opened)."""

    def __init__(self, what: str):
        super().__init__(f"Chế độ chỉ-cache: thiếu dữ liệu đã lưu cho {what}; không gọi mạng nên dừng lượt chạy.")
