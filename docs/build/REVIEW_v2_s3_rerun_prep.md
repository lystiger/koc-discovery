Overall FAIL

### Findings

#### P2-1 — Step 1 bash loop continues calling OpenRouter (and can still report `SMOKE PASS`) after `FreeGuard` stops on non-zero cost
- **Location:** [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L66-L69), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L81), [s3_free_smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_free_smoke.py#L52-L55)
- **Failure scenario:** When a `:free` model unexpectedly reports `usage.cost_usd > 0` in OpenRouter's response, `FreeGuard.record` raises `SystemExit(f"STOP: model reported cost {usage.cost_usd} USD")`, which exits Python with status `1` (the same exit status returned on normal model validation failure at line 199). In the Step 1 bash block (`for MODE in "" "--no-audio" "--text-only"; do if .venv/bin/python scripts/s3_free_smoke.py $MODE; then ...`), `if` suppresses `set -e` for all non-zero exit codes. Instead of stopping immediately as claimed at line 81 (`STOP: model reported cost ... (mô hình báo có phí: dừng ngay)`), the loop proceeds to `--no-audio` and `--text-only`, making up to 6 additional OpenRouter requests. Worse, because `--no-audio` and `--text-only` widen the candidate pool (`need_audio=False`), an image-only `:free` model can succeed with `0.0` USD in a fallback mode, setting `PASSED` and exiting `0` (`SMOKE PASS in mode: --no-audio`) after an earlier mode reported a non-zero cost.
- **Fix:** Exit with a distinct code on cost violation (e.g., `SystemExit(3)` after printing the `STOP:` error) and check the exit code in the bash loop (`rc=0; .venv/bin/python scripts/s3_free_smoke.py $MODE || rc=$?; [ "$rc" -eq 0 ] && { PASSED="${MODE:-full}"; break; }; [ "$rc" -eq 3 ] && exit 3`).

#### P2-2 — `scripts/s3_pending_videos.py` is not read-only: it opens `--db` read-write and inserts 10 `api_calls` rows per run
- **Location:** [s3_pending_videos.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_pending_videos.py#L31-L38), [kalodata.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/src/koc/kalodata.py#L134-L135), [benchmark.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/src/koc/benchmark.py#L295)
- **Failure scenario:** Unlike [s3_rerank_preview.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_rerank_preview.py#L50) and [s3_free_smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_free_smoke.py#L113) (both of which open `--db` with `sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)`), `s3_pending_videos.py` opens `--db` read-write via `db.connect(Path(args.db))` and calls `KalodataClient(conn, run_id=None, cache_only=True).video_rank(...)`. Every cache hit in `KalodataClient.request` executes `db.add_api_call(...)`, inserting 10 rows (`run_id=NULL, endpoint='video/rank', status='200', credits=0.0, cache_hit=1`) into `api_calls` (verified on `/tmp/agy_plan.db`: `api_calls` count rose from `361` to `371`). Although Block 2 in the runbook works around this by backing up `data/koc.db` to `$TMP/plan.db` first, running `s3_pending_videos.py --db data/koc.db` directly silently mutates the production DB and inflates `excluded_api_calls.calls` in `benchmark.py:295`.
- **Fix:** Open `args.db` read-only (`src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)`) and either `.backup()` into `sqlite3.connect(":memory:")` before constructing `KalodataClient`, or read `db.http_cache_get` directly on the read-only connection.

#### P2-3 — `EXIT` trap deletes `$TMP` before killing headless Chromium, and immediately deletes the `$TMP/bench` output promised to the operator
- **Location:** [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L94), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L122-L123), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L142-L144), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L167-L168)
- **Failure scenario:**
  1. Both Block 2 (line 94) and Block 3 (line 167) set `trap 'rm -rf "$TMP"; [ -n "${CPID:-}" ] && kill "$CPID" 2>/dev/null || true' EXIT` while launching Chromium with `--user-data-dir="$TMP/chromium"`. Because `rm -rf "$TMP"` runs while Chromium (`$CPID`) is still alive and writing to `$TMP/chromium`, `rm -rf "$TMP"` can fail with `Directory not empty` under `set -e` (which remains active inside `EXIT` traps in bash) and abort the trap before `kill "$CPID"` executes, leaving headless Chromium orphaned on port `9333`.
  2. Line 142 writes the new run's benchmark to `--out-dir "$TMP/bench"`, prints `"benchmark of the new run: $TMP/bench (deleted on exit; copy it now if you want it)"`, and two lines later exits the subshell `)`, triggering `rm -rf "$TMP"` immediately so the operator cannot copy `$TMP/bench`.
- **Fix:** In the `EXIT` trap, kill `"$CPID"` (and `wait "$CPID" 2>/dev/null || true`) before `rm -rf "$TMP"`. Write the optional benchmark of the new run to a path outside `$TMP` (e.g., `/tmp/koc_bench_$NEW`) so it survives subshell exit without touching `reports/` or `docs/BENCHMARK.md`.

#### P3-1 — Minor doc count in time estimate (`7 KOC` vs `6 KOC`) and missing unit test for `FreeGuard` cost stop
- **Location:** [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L37), [test_s3_free_smoke_script.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/tests/core/test_s3_free_smoke_script.py#L1-L107)
- **Failure scenario:**
  1. Line 37 of `RUNBOOK_v2_s3_rerun.md` states `S3 ~175 s mỗi KOC x 7 KOC`, whereas 6 of the 10 S3 creators have uncached videos (`*`) and 4 creators are 100% cached (`EVIDENCE_v2_s3_rerun_prep.md:36-55`).
  2. `tests/core/test_s3_free_smoke_script.py` tests the 3 modes, catalogue filtering, and `--model` suffix check, but does not test that `FreeGuard.record` aborts when the mocked OpenRouter response returns `usage.cost > 0`.

---

### Safety Verification Checklist

1. **`bash -n` and `set -euo pipefail`:**
   - All 4 bash blocks in `docs/build/RUNBOOK_v2_s3_rerun.md` pass `bash -n` (exit code `0`).
   - All variables (`BK`, `BEFORE`, `AFTER`, `OPENROUTER_API_KEY`, `KALODATA_API_KEY`, `PASSED`, `MODE`, `TS`, `TMP`, `CPID` via `${CPID:-}`, `CR0`, `USD0`, `PRE`, `ANS`, `NEW`, `CR1`, `USD1`) are initialized before expansion under `set -u`.
   - `KOC_DB="$TMP/pre.db" .venv/bin/koc run --cache-only` properly redirects all DB operations to `$TMP/pre.db`: verified in [cli.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/src/koc/cli.py#L18) (`DB_PATH = Path(os.getenv("KOC_DB", "data/koc.db"))`) and confirmed across `src/koc/` that all pipeline stages use the passed `conn`.
2. **No writes to `data/koc.db` before operator types `yes`:**
   - Verified in Block 2 (lines 93–118): backup and balance checks use `sqlite3 -readonly data/koc.db`; rehearsal runs on `$TMP/pre.db`; `s3_pending_videos.py` runs on `$TMP/plan.db`; `--dry-run` returns at [cli.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/src/koc/cli.py#L74) before `db.connect`; `read -rp "... Type yes to run: " ANS; [ "$ANS" = yes ]` aborts the subshell on any input other than `yes` before `.venv/bin/koc run`.
3. **No key leaks:**
   - Keys are read exclusively with `read -rsp` inside `( ... )` subshells and exported to the subshell environment; no `set -x`, no `echo` of key vars, no CLI argv passing, and [openrouter.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/src/koc/llm/openrouter.py#L87-L137) redacts keys in `__repr__` and error messages.
4. **`:free` smoke cost guard and DB safety:**
   - `scripts/s3_free_smoke.py` only selects `:free` models (`free_candidates` line 77, `assert args.model.endswith(":free")` line 165), prices the model at `0.0` in a temporary `llm_prices.yaml` under `/tmp/s3_smoke_*`, writes frames/silent mp4 under `/tmp/s3_smoke_*`, opens `--db` with `file:{db_path}?mode=ro` in `--text-only` mode, and checks `usage.cost_usd > 0` in `FreeGuard.record` after every `generate_json` call (subject to P2-1 in the outer bash loop).
5. **Production selection/cache lookup in `s3_pending_videos.py`:**
   - Uses `KalodataClient.video_rank(creator_id, page_size=100)`, `select_videos(..., n=3)`, `hashlib.sha256(path.read_bytes()).hexdigest()`, and `pipeline.content_analysis_cached` (which checks `_content_key` and `_legacy_content_row`), matching `pipeline._s3_creator` (`src/koc/pipeline.py:346-370`).
6. **Cost estimate derivation (`6.5–7.7` credits, `0.23–0.69` USD):**
   - **Credits:** 13 uncached videos × `0.5` (`video_url` price in `config/kalodata_prices.yaml`) = `6.5` floor; upper bound from `reports/benchmark.json` `units_total.S3.credits` (`1.777778 / 3 × 13 = 7.704` → `7.7`), with `22.1` credits remaining under the `60` cap (`37.9` used).
   - **USD:** S3 `13 × (0.0451643 / 3) = 0.1957` to `13 × (0.1362991 / 3) = 0.5906` USD + S4 `5 × 0.0054334 = 0.0272` to `5 × 0.0195054 = 0.0975` USD = `0.2229–0.6882` USD → `0.23–0.69` USD, with `3.6758` USD remaining under the `5.0` USD cap (`1.3242` used).
7. **Rollback block safety:**
   - Checks `! pgrep -f "uvicorn|koc.web" >/dev/null`, saves `data/koc_before_rollback_<TS>.db`, restores `$BK`, removes `data/koc.db-wal` and `data/koc.db-shm`, and verifies `pragma integrity_check`, `runs`, `api_calls`, and `llm_calls` via `sqlite3 -readonly`.
8. **Expected outputs match code output:**
   - Verified `--dry-run`, `--cache-only` rehearsal, Diễn tập 3 step-by-step skip, `s3_pending_videos.py`, and SQL queries against `/tmp/agyprep.db`.

---

### Command Results

1. **Read-only DB backup and integrity check:**
   ```
   $ sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db '.backup /tmp/agyprep.db'
   $ sqlite3 -readonly /tmp/agyprep.db "pragma integrity_check; select run_id,status from runs; select round(sum(credits),2) from api_calls; select round(sum(cost_usd),4) from llm_calls"
   ok
   e9e1271471f24a3db215442334548033|running
   7372009b22764b339fbcf0f3efb4bc4e|done
   37.9
   1.3242
   ```

2. **`bash -n` syntax check on all 4 runbook blocks:**
   ```
   Found 4 bash blocks
   block 1: bash -n rc=0, lines=18
   block 2: bash -n rc=0, lines=57
   block 3: bash -n rc=0, lines=10
   block 4: bash -n rc=0, lines=11
   ```

3. **Offline `--cache-only` rehearsal on DB copy (`/tmp/agy_pre.db`):**
   ```
   Đã hoàn tất lượt chạy 703cda04ff404df7b7c3a55273a6b2fa.
   S0|done|1
   S1a|done|200
   S1b|done|60
   S2|done|10
   S2|skipped|30
   S3|blocked|1  (blocked: Chế độ chỉ-cache: thiếu dữ liệu đã lưu cho tệp video 7695457484974099730; không gọi mạng nên dừng lượt chạy.)
   S3|pending|9
   credits=37.9, usd=1.3242
   ```

4. **Offline `scripts/s3_pending_videos.py` on DB copy (`/tmp/agy_plan.db`):**
   ```
   6730533371858437121 @emduyencantho 7581276298509683976 7700025929283718408* 7686825228000906514*
   6872721641991209985 @k_dung26 7700828901895081236(off-topic) 7703164953263344916(off-topic) 7697097183732026641(off-topic)
   6976265099049305089 @dunghana2882 7702567422238231828(off-topic) 7700630539698687240(off-topic) 7676534167454092552(off-topic)
   7164572563820250139 @dieuduong_quynhhoa 7533211696635219208 7703531291328793877 7707875062786870548*
   7234931025289217051 @ducvietbe__ 7605826096197569813(off-topic) 7694339958831582485(off-topic) 7700201671380520210(off-topic)
   7288941699803694098 @gaixinhh114 7706170815640767765(off-topic) 7688027815312493845(off-topic) 7706556087222291733(off-topic)
   7450735628620760071 @rio100806 7695457484974099730* 7698027306689809671* 7701751823807466759*
   7471573167103378440 @cleanboy.tips 7706841783648701714* 7707286014947052806* 7701519564823153938*
   7485602050560148487 @meixiuriviu 7701594488619191573 7702310286232931605* 7703462921245822229*
   7594293671543079957 @teetamofficial 7700088062222535944* 7694231815078432001* 7699877846918909202(off-topic)
   videos picked: 30; needing paid analysis (*): 13; video/url cost 6.5 credits
   ```
   *(Post-run check on `/tmp/agy_plan.db`: `SELECT COUNT(*) FROM api_calls` increased from `361` to `371` due to 10 `run_id=NULL` `video/rank` cache-hit inserts — see P2-2.)*

5. **Full test suite offline (`unshare -rn`):**
   ```
   $ unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q'
   504 passed, 1 skipped in 93.48s (0:01:33)
   ```
