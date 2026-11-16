# EVIDENCE v2.0 core track A (branch v2/core-a)

Env for every command: `PYTHONPATH=$PWD/src GEMINI_API_KEY=fake KALODATA_API_KEY=fake OPENROUTER_API_KEY=fake`, run under `unshare -rn` (no network). `data/koc.db` was never opened.
Python: `/home/lystiger/Projects/KOC-Discovery/.venv/bin/python`.

Full suite: `unshare -rn python -m pytest -q` -> `443 passed, 1 skipped in 74.53s` (baseline 429 passed, 1 skipped; +14 new tests).

## A1 `koc run --dry-run` estimate (commits "feat: run estimate ..." and review r1 fix)

Review r1 P2 fixed: the estimate now multiplies the published per-creator `units_success` / `units_total` of reports/benchmark.json by the creators each stage processes under the configured limits (S0, S1a = limit; S1b = min(s1a_limit, limit); S2 = S3 = min(s2_limit, s1_limit, S1b); S4 = brief count). Stage totals divided by funnel inputs are no longer used.

Command: `KOC_DB=/nonexistent/x.db unshare -rn python -m koc.cli run --dry-run`

```
Kế hoạch: S0 tối đa 200 nhà sáng tạo, S1a lọc còn 60, S1b chấm điểm còn 40, S2 còn 10, S3 phân tích, S4 chọn 5.
Ước tính toàn pipeline (từ reports/benchmark.json, chỉ là ước tính):
  Tín dụng Kalodata ước tính: 27.6–29.4 tín dụng.
  Chi phí LLM ước tính: 0.48–1.46 USD.
  Token LLM ước tính: 441.769–1.286.591 token.
  Thời gian ước tính: 35–58 phút.
```

- Matches the reviewer's published-unit projection (27.6–29.4 credits, 0.48–1.46 USD at 200). It differs from the live totals (26.0–27.6 credits, 0.43–1.32 USD) because units are per successful creator and S3 is projected at 10 creators, not the 9 that survived.
- Minutes: S2 = 64.4 s x 10 = 10.7 min; S3 = 175.7 s x 10 = 29.3 min (the live run took 26.4 min for 9 creators). Measured wall time was 43.3 min. The shown range is the unit-based total +-25 percent (`TIME_SPREAD`): a judgement call, UNPROVEN as a calibrated interval (one live run).
- Tests: `tests/core/test_estimate.py` (7 passed): `test_default_config_projects_published_per_creator_units`, `test_s2_limit_scales_s2_and_s3_proportionally` (s2_limit 10 -> 5 halves S2 minutes and S3 credits/minutes), `test_count_scales_s4`, the dry-run text test (S2 count from `s2_limit`, no "S2 còn 15").
- Web: `needs_run` field `run_estimate` (same function, brief count passed); `tests/web/test_matching_api.py::test_needs_run_carries_run_estimate_ranges`.
- UNPROVEN: the "CLI snapshot" is a substring test, not a stored snapshot file.

## A3 Kalodata cache freshness (commit "feat: Kalodata cache TTL ...")

Config: `config/pipeline.yaml` `cache_ttl_days: 7`. Command: `pytest -q tests/core/test_cache_ttl.py tests/core/test_cache_only.py tests/core/test_estimate.py` -> `19 passed`.

Frozen-clock tests (`db.now` monkeypatched):
- `test_default_ttl_is_seven_days`.
- `test_fresh_rank_detail_video_rank_are_served_from_cache`: at 6 d 23 h, 0 extra transport calls.
- `test_stale_rows_are_refetched_and_replaced`: at 7 d + 1 s, creator/rank, creator/detail and video/rank each refetch (calls 3 -> 6); the refreshed row is fresh again; `http_cache` still has 3 rows (upsert).
- `test_video_url_never_expires` (400 d), `test_llm_cache_never_expires` (400 d). Video analyses live in the `analyses` table and LLM output in `llm_cache`; neither has TTL code.
- `test_cache_only_serves_stale_rows_free`: a design choice, `--cache-only` ignores the TTL (60 d old row served, 0 calls), so it keeps its "no network, no credits" promise.
- C6 (rerun = 0 credits / 0 tokens) for a fresh run: the existing `tests/core/test_cache_only.py` and `tests/core/test_d2_pipeline.py::test_mock_run_is_resumable_cached_and_writes_five_recommendations` pass unchanged in the full suite.
- Note: a plain (non cache-only) rerun of a run older than 7 days now refetches and spends credits, by design. The live run `7372009b...` is older than 7 days after 2026-11-23; use `--cache-only` for a free rerun. UNPROVEN on the real DB (not touched).
- Docs (review r1 P3): `docs/ARCHITECTURE.md` (cache section) and `README.md` now describe `cache_ttl_days` = 7, the permanent analyses/LLM/`video/url` cache, and that a plain rerun of a run older than 7 days spends credits while `--cache-only` costs 0 credits / 0 tokens. The README roadmap bullet about cache TTL was removed because it is done.
- `category/rank` and `video/url` are not in the TTL set (the spec names rank/detail/video-rank); `category/rank` is only used by `koc categories`.

## A6 Test hygiene (commit "test: seed real brand_fit analyses ...")

- `grep -rn lenient tests | wc -l` -> `0` (autouse `lenient_brand_fit_gate` removed from `tests/conftest.py`).
- Helper `tests/analysis_seed.py::seed_brand_fit` writes a valid `ContentAnalysis` (brand_fit score 5) per synthetic creator; used in the fixtures of test_audience_placeholder, test_brief, test_d2_pipeline, test_r3_findings, test_s4_smoke_script, web test_matching_api and `tests/web/fixtures/seed.py` (sixth creator).
- Before seeding, with the fixture removed: `30 failed, 411 passed, 1 skipped` (matches REVIEW_brand_fit_gate_r2 F5). After: `441 passed, 1 skipped`, no test weakened (no assertion edited; `test_audience_placeholder._s4_analyses` passes `analyses=False` to keep its own analysis rows).
- `tests/core/test_brand_fit_gate.py` unchanged.
