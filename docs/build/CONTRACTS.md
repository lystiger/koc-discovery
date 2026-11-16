# CONTRACTS (frozen 2026-11-15) — KOC Discovery MVP

Changes only by orchestrator. Python 3.12+, Pydantic v2. Package `koc` under `src/koc/`.

## 1. Shared types — `src/koc/types.py` (Codex writes FIRST, before anything else; Agy imports only)

```python
from pydantic import BaseModel, Field
from typing import Literal

class Usage(BaseModel):
    provider: Literal["gemini"]
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
```

## 2. LLM module API — `src/koc/llm/` (Agy implements; Codex calls)

```python
def preprocess_video(mp4_path: str, out_dir: str, n_frames: int = 8) -> dict
    # ffmpeg: n_frames evenly spaced (+ first frame at 0.5 s for hook), 360 px wide JPEG; audio 16 kHz mono.
    # returns {"frames": [{"path","t_s"}], "audio_path": str, "duration_s": float, "sha256": str}

def analyze_video(video: VideoInput, brief: BrandBrief, *, budget_guard: "BudgetGuard") -> ContentAnalysis
    # One Gemini call: frames + audio + metadata -> JSON (response schema enforced), validated into ContentAnalysis.
    # Must call budget_guard.check(estimated_usd) before, budget_guard.record(usage) after.

def write_reasons(c: CandidateSummary, brief: BrandBrief, *, budget_guard: "BudgetGuard") -> Recommendation
    # One Gemini text call. Every cited id must exist in c.metric_evidence_ids values or c.analyses evidence; else retry once, then raise.
```

`BudgetGuard` is a Protocol defined by Codex in `src/koc/types.py`:
`check(estimated_usd: float) -> None` (raises `BudgetExceeded`), `record(usage: Usage) -> None`.
Caching of LLM calls is done by **core** (key = sha256(media sha256 + prompt_version + model + brief)); the llm module stays stateless.
Prices: `config/llm_prices.yaml` (Agy fills from official Google pricing page, with URL + date; UNVERIFIED if not found).
API key: env `GEMINI_API_KEY` only. SDK: `google-genai`.

## 3. SQLite tables (Codex owns `src/koc/db.py`)
- `runs(run_id PK, started_at, finished_at, status, params_json)`
- `tasks(task_id PK = run:stage:key, run_id, stage, key, status pending|running|done|failed, retries, error, updated_at)`
- `creators(creator_id PK, handle, data_json, updated_at)` — no contact fields ever
- `videos(video_id PK, creator_id, data_json, mp4_path, updated_at)`
- `metrics(creator_id, name, value, source, period, collected_at, PK(creator_id,name,period))` -> evidence id `metric:<creator_id>:<name>`
- `scores(run_id, creator_id, stage, score, breakdown_json, PK(run_id,creator_id,stage))`
- `analyses(video_id, prompt_version, model, analysis_json, PK(video_id,prompt_version,model))`
- `recommendations(run_id, creator_id, rank, est_cost_vnd, rec_json, PK(run_id,creator_id))`
- `api_calls(id PK, run_id, endpoint, request_hash, status, credits, latency_ms, cache_hit, created_at)`
- `llm_calls(id PK, run_id, kind content|reasons, request_hash, model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, cache_hit, created_at)`
- `http_cache(request_hash PK, endpoint, response_json, created_at)`; `llm_cache(request_hash PK, output_json, usage_json, created_at)`
Task marked done only in the same transaction as its result write.

## 4. Web (Agy, D2+) reads DB through `src/koc/queries.py` (Codex provides read-only functions):
`list_runs()`, `get_run(run_id)`, `top5(run_id)`, `creator_detail(run_id, creator_id)`, `run_costs(run_id)`.

## Amendment A1 (orchestrator, 2026-11-15, from REVIEW_llm_by_codex.md P1-3)
`analyze_video(video, brief, *, budget_guard, frames_dir: str | None = None)`: when frames_dir is given, frames are written to
`<frames_dir>/<video_id>/f_<t_ms>.jpg` and kept; every Evidence of kind "frame" gets frame_path set by code (never by the model)
to the nearest extracted frame. Core passes `data/media/frames`. Temp dir only when frames_dir is None (tests).

## Amendment A2 (orchestrator, 2026-11-15): OpenRouter as LLM provider
Lystiger cannot pay Google AI Studio; the LLM key is an OpenRouter key. Decision:
- `Usage.provider: Literal["gemini", "openrouter"]` (types.py, one-line change authorized for the LLM owner).
- `config/llm_prices.yaml` gets `provider: openrouter | gemini` (default `openrouter`) and model `google/gemini-3.8-flash`.
  Prices from https://openrouter.ai/api/v1/models (fetched 2026-11-15): prompt/image/audio 0.825 USD per 1M tokens, completion 4.125 USD per 1M.
  Model lists input modalities text, image, video, file, audio and parameters response_format, structured_outputs, reasoning.
- OpenRouter path: POST https://openrouter.ai/api/v1/chat/completions via httpx, key from env `OPENROUTER_API_KEY` only.
  Frames as `image_url` data URIs (JPEG base64), audio as `input_audio` (base64, format mp3), JSON via `response_format` json_schema strict,
  reasoning disabled, usage accounting on; cost = provider-reported cost when present, else price table. Same budget upper bound rules (R2-1).
- The `gemini` (google-genai) path stays and remains selectable; tests cover both with mocked transports.
- Cache key already includes model; add provider to it if not covered by model id.
