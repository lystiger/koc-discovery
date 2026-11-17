# EVIDENCE v2.0 item 2 / A2: `koc run --exclude-run`

Branch `v2/exclude-run`. All commands offline (`unshare -rn`, fake keys, `--mock`, temp DB). No paid call, data/koc.db untouched.

## Design
- `pipeline.run_exclusions(conn, run_ids)`: collects the `recommendations` (final picks) of each named run. Unknown run or run with no picks raises a Vietnamese `RuntimeError`.
- `start(..., exclude_run_ids)` validates before `db.create_run`, so a bad id creates no run and spends nothing. Result stored in `runs.params_json["exclude"] = {"run_ids", "creator_ids"}`; `resume` reads it from params.
- S0 skips excluded ids (no S1a task, so never in S1 pool, S2, S3 or S4); `_best_five` also filters them as a second guard.
- Identity: each run has its own `params_json` containing the exclusion set; the S0 rank request is still served from http_cache (0 credits) and then filtered, so the pool, S4 candidate summaries and reasons keys differ and the cached same 5 is not returned. LLM cache keys unchanged (they hash media/candidate content).
- Web: `run_command` appends `--exclude-run <id>` per `exclude_run_ids` entry (shell-quoted). `web/` untouched.

## A2 proof (mock, temp DB)
```
koc run --limit 20 --mock --category-ids 111
  run1 picks: 1 10 11 12 13
koc run --limit 20 --mock --category-ids 111 --exclude-run <run1>
  Đã loại 5 KOC đã đề xuất ở lần chạy 39831b53...
  run2 picks: 14 15 16 17 18
  params.exclude = {"creator_ids":["1","10","11","12","13"],"run_ids":["39831b53..."]}
koc run ... --exclude-run nope
  Không tìm thấy lượt chạy nope để loại KOC. Dùng `koc status` để xem các lượt chạy.   exit=1, runs table still 2 rows
```

## Tests
- `tests/core/test_exclude_run.py` (7): excluded ids absent from S1 pool and picks, params stored, plain rerun still returns same 5 while exclusion changes them, two runs excluded together, unknown id and no-picks run fail with 0 runs/api_calls/llm_calls, CLI Vietnamese line and error.
- `tests/web/test_matching_api.py::test_run_command_appends_exclude_run_flags`.
- Full suite: `PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake unshare -rn .venv/bin/python -m pytest -q` -> 437 passed, 1 skipped (baseline 429 + 8 new).

## Review r1 fixes
- Web reachable over HTTP: `CampaignInput.exclude_run_ids` (list of 32-hex run ids, max 10; garbage gives 422). `POST /api/campaigns` saves the ids and the `needs_run` command ends with `--exclude-run <id>` flags. Tests: `test_http_exclude_run_ids_saved_and_in_command`, `test_http_exclude_run_ids_rejects_garbage` (TestClient). The React checkbox is a separate web wave.
- Per V2-2 (clarified): exclusion removes ALL final picks of the named run (N = its count). `test_count_10_run_excludes_all_ten_picks`: a `--count 10` run's 10 picks all leave the next pool (pool shrinks by exactly 10) and its picks.
- `test_resume_keeps_exclusion`: resume of a blocked excluded run keeps the exclusion.

## Review r2 fix (cached matching)
- `get_pool` drops creators that are final picks of any run in `exclude_run_ids` (free, no paid run); `_cheaper_band` inherits it. If the exclusion leaves the request refused, `result_for_campaign` returns `needs_run` (refusal `options` kept) whose command carries the `--exclude-run` flags.
- HTTP tests: `test_http_exclusion_applies_to_cached_matching` (finished run exists: without exclusion picks are c0,c1; with it status ok and neither appears) and `test_http_exclusion_leaving_too_few_gives_needs_run_with_flags`.

## Review r3 fix
- `needs_run` is returned only when the exclusion itself causes a pool shortage (pool after exclusion < count <= pool without it). Budget refusals with enough candidates stay `refused` with warnings and options, as without exclusions. Test: `test_http_budget_refusal_stays_refused_with_exclusion` (2 creators, budget below minimum, exclusion outside the pool); the shortage test is unchanged.

## UNPROVEN
- Not run against a live-data DB copy (mock pool only).
- `--dry-run --exclude-run` does not validate (dry run opens no DB by design).
