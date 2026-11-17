# SPEC: KOC Discovery MVP (Phase 1)

Status: Ready (grill closed 2026-11-15). Deadline 2026-11-18 18:00.
Repo: ~/Projects/KOC-Discovery, branch `feat/koc-mvp` from `main` (tag phase0-pass).
Decisions: brief.md (rounds 1-3). Contracts: CONTRACTS.md (frozen; change only via orchestrator).
Language: all user-visible text, docs, README, reports, reasons in **Vietnamese**. Code identifiers/comments English.
Kalodata API docs (offline copy): `docs/research/kalodata_api/*.txt` in the repo. Auth header `secret-key`.

## Goal
Recommend 5 TikTok KOCs for a Vietnamese sunscreen brand (women 18-30, 30,000,000 VND), with evidence
including AI video analysis, minimal tokens/credits, built for 50-500 candidates, resumable.

## Pipeline (funnel, cheapest first)

```
S0 candidates  creator/rank (VN, skincare category, followers 10k-300k, last30Day)  -> 200
S1 score       creator/detail(need_extra) + video/rank(creator_id) ; no LLM          -> 40
S2 audience    creator detail page UI (supervised browser, >=5 s pacing)              -> 15
S3 content     3 videos/KOC: video/url MP4 -> ffmpeg 8 frames + audio -> Gemini       -> scores
S4 select      final score, budget optimizer (best 5 of 15, sum <= 30M), reasons (LLM) -> 5
```

## Scoring
- S1 commercial (0-100): video GPM 35, skincare revenue share 25, revenue trend slope 15,
  video-vs-live revenue share 15, follower-band fit 10. Engagement (likes/comments/shares per view from video/rank)
  is reported and used as tie-break; weights in `config/scoring.yaml`.
- S2 audience (0-100): female % and share aged 18-24 + 25-34.
- S3 content (0-100): rubric 0-5 x 7 criteria per video, mean of 3 videos (hook, product clarity, demonstration,
  claim quality, CTA, brand fit, production quality). Calibration: Spearman of content score vs views/followers and
  video GPM across finalists, reported.
- Final = 0.45 commercial + 0.20 audience + 0.35 content.
- Budget: per-tier rate card in `config/rate_card.yaml`, labelled ESTIMATE (UOC TINH). Optimizer: max sum(final score)
  over 5-combinations of top 15 with sum(cost) <= 30,000,000 VND; no two with same MCN when known.

## Cost controls (hard, in code)
- Kalodata credit counter: hard cap 100 credits per DB (all runs); refuse call that would exceed. Pricing table in config
  (detail 0.1, rank 0.1 x ceil(rows/100), video/url 0.5).
- Gemini: hard cap 5 USD cumulative (from logged usage x configured price); refuse call that would exceed.
- Cache: every Kalodata request and LLM call keyed by sha256 of canonical request (+ media sha256, prompt version, model).
  Rerun of a finished run = 0 credits, 0 tokens (must be proven by test + benchmark).

## Ownership (one writer per area)
| Area | Owner | Paths |
|---|---|---|
| Core: config, schemas, db, Kalodata client, cache, credit counter, S0/S1/S2/S4 scoring+budget, pipeline, CLI, benchmark | Codex (Luna 6 high) | `src/koc/` except `src/koc/llm/`, `src/koc/web/`; `tests/core/`; `config/` |
| LLM: Gemini client, media preprocessing (ffmpeg), S3 analysis, S4 reasons, prompts, usage/cost | Agy (Gemini 3.8 Flash high) | `src/koc/llm/`, `tests/llm/`, `prompts/` |
| UI (after core data contract proven, D2) | Agy | `src/koc/web/`, `tests/web/` |
| Audit: UI screenshots, gates, claim check | Haiku | read-only + `docs/process/audit/` |
| Spec, contracts, gates, final report | Orchestrator | `docs/process/build/` |

Builders never edit another owner's paths. Need a contract change -> write `docs/process/build/CHANGE_REQUEST_<owner>.md`, stop that part.

## Acceptance criteria (verified by reviewer of the other provider)
C1 `pytest -q` green; offline (Kalodata + Gemini mocked; fixtures from `reports/api_probe_2026-11-15.json` and docs examples).
C2 `koc run --dry-run` prints the plan + projected credits/tokens, no network, no writes.
C3 Live demo run produces exactly 5 KOCs, total estimated cost <= 30,000,000 VND, each with Vietnamese reasons citing
   evidence IDs (metric rows, video timestamps, quotes) that exist in the DB.
C4 Every Kalodata call and LLM call logged (endpoint/model, credits or tokens in/out, latency, cost, cache hit).
C5 Kill mid-run (SIGKILL in S1 and in S3) then `koc resume`: completes, no duplicate rows, no repeated paid calls.
C6 Rerun finished run: 0 credits, 0 LLM tokens (cache), same top 5.
C7 Hard caps enforced (tests: call refused when cap would be exceeded).
C8 `reports/benchmark.json` + `docs/BENCHMARK.md` (VI): per stage time, credits, tokens, USD; 5-KOC run and 50-candidate scaling run; projection to 500.
C9 UI (FastAPI+Jinja, VI): ranked 5 with score breakdown + budget; KOC detail with metrics, video evidence (frames, timestamps, transcript quotes), reasons; run dashboard (stages, tasks, tokens, credits, time). Screenshots at 375 and 1440 px pass Haiku audit.
C10 `docs/ARCHITECTURE.md` (VI, Mermaid diagram + key decisions), README (VI: run, limits, extensions, offline Whisper option via openaipublic.azureedge.net).
C11 No secrets in git (keys only via env: KALODATA_API_KEY, GEMINI_API_KEY); creator contact fields never stored.

## Verification commands
`.venv/bin/pytest -q` ; `.venv/bin/koc run --dry-run` ; `.venv/bin/koc run --limit 200` (live, Lystiger keys) ;
`kill -9` test script `scripts/kill_resume_test.sh` ; `.venv/bin/koc run` again (expect 0 cost) ; `.venv/bin/koc serve`.
