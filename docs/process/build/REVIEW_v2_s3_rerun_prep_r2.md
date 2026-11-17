Overall PASS

### Round 1 Findings Verification (`e9dc01e` / `8b47aa8..HEAD`)

#### P2-1 — Step 1 bash loop continues calling OpenRouter after `FreeGuard` stops on non-zero cost: **CLOSED**
- **Location:** [s3_free_smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_free_smoke.py#L52-L56), [s3_free_smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_free_smoke.py#L187-L188), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L66-L71), [test_s3_free_smoke_script.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/tests/core/test_s3_free_smoke_script.py#L113-L122)
- **Failure scenario & fix verification:**
  - `FreeGuard.record` ([s3_free_smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_free_smoke.py#L54-L56)) now prints `STOP: model reported cost {usage.cost_usd} USD` with `flush=True` and raises `SystemExit(3)`. Because `main()` re-raises `SystemExit` at line 187–188 (cleaning up `tmp` in `finally` at line 201–202), Python exits with status `3`, distinct from model output validation failure (`1`) and missing candidate/media (`2`).
  - Furthermore, inside `koc.llm.content.analyze_video` ([content.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/src/koc/llm/content.py#L383)), `budget_guard.record(usage)` runs immediately after `generate_json` on attempt `0`, so a non-zero cost aborts before any repair retry or subsequent candidate model is called.
  - In Block 1 of the runbook ([RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L68-L70)):
    ```bash
    rc=0; .venv/bin/python scripts/s3_free_smoke.py $MODE || rc=$?
    if [ "$rc" -eq 0 ]; then PASSED="${MODE:-full}"; break; fi
    if [ "$rc" -eq 3 ]; then echo "STOP: a :free model reported a cost"; exit 3; fi
    ```
  - **Evidence:**
    1. Ran `s3_free_smoke.main` with mocked OpenRouter returning `usage.cost = 0.01`: printed `STOP: model reported cost 0.01 USD` and raised `SystemExit(3)`.
    2. Simulated the Step 1 `for MODE in "" "--no-audio" "--text-only"` loop under `set -euo pipefail` with a stub script returning `(3, 1, 0)`: the loop stopped immediately on the first iteration (`calls made: 1`, printed `STOP: a :free model reported a cost`, exited subshell with code `3`). With stub returns `(2, 1, 0)`, it tried all 3 modes and exited `0` (`SMOKE PASS in mode: --text-only`).

#### P2-2 — `scripts/s3_pending_videos.py` opens `--db` read-write and inserts 10 `api_calls` rows: **CLOSED**
- **Location:** [s3_pending_videos.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/scripts/s3_pending_videos.py#L31-L35), [test_s3_pending_videos_script.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/tests/core/test_s3_pending_videos_script.py#L14-L34)
- **Failure scenario & fix verification:**
  - `s3_pending_videos.py` now opens `--db` read-only via `src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)`, copies it into `conn = sqlite3.connect(":memory:")` with `src.backup(conn)`, and immediately closes `src`. All `KalodataClient` cache-hit logging (`db.add_api_call`) happens solely in `:memory:`.
  - **Evidence:** Backed up production DB with `sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db '.backup /tmp/agyprep2.db'` and ran `PYTHONPATH=src .venv/bin/python scripts/s3_pending_videos.py --db /tmp/agyprep2.db --media-dir /home/lystiger/Projects/KOC-Discovery/data/media`. Both `sha256sum /tmp/agyprep2.db` (`0bb5d3eb4204c60f4e878f418d8165b31fa5fe033f91fd252c7f94a95e4c304c`) and `SELECT COUNT(*) FROM api_calls` (`361`) were identical before and after execution.

#### P2-3 — `EXIT` trap order (`rm -rf` before `kill`) and `$TMP/bench` deleted on subshell exit: **CLOSED**
- **Location:** [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L96), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L144), [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L169)
- **Failure scenario & fix verification:**
  - Both Block 2 (line 96) and Block 3 (line 169) now use:
    ```bash
    TMP=$(mktemp -d); trap '{ [ -z "${CPID:-}" ] || { kill "$CPID" 2>/dev/null; wait "$CPID" 2>/dev/null; }; } || true; rm -rf "$TMP"' EXIT
    ```
  - **Reasoning under `set -euo pipefail`:**
    1. **Does Chromium get killed before `rm -rf "$TMP"`?** Yes: `kill "$CPID"` and `wait "$CPID"` execute and reap the background Chromium process before `rm -rf "$TMP"` runs, so Chromium cannot write new files into `--user-data-dir="$TMP/chromium"` during `rm -rf`.
    2. **Can the trap abort under `set -euo pipefail`?**
       - `${CPID:-}` safely expands to `""` under `set -u` when the script exits before Chromium is started (e.g., if the user does not type `yes` at line 120 or if an earlier check fails). In that case `[ -z "${CPID:-}" ]` succeeds (`0`), short-circuiting `||`.
       - When `CPID` is set, `{ kill "$CPID" 2>/dev/null; wait "$CPID" 2>/dev/null; }` runs inside the left-hand side of `{ ...; } || true`. In bash, `set -e` is disabled for the entire left-hand compound command of an `||` list, so neither a non-zero exit from `kill` (if Chromium already exited) nor the `143` (`SIGTERM`) exit status returned by `wait "$CPID"` triggers `set -e`, and the outer `|| true` guarantees the compound statement returns `0` before `rm -rf "$TMP"` runs.
    3. **Does `/tmp/koc_bench_$NEW` survive?** Yes: line 144 writes `--out-dir "/tmp/koc_bench_$NEW"`, which is outside `$TMP` and outside the repo (`reports/` and `docs/BENCHMARK.md` remain untouched).
  - **Evidence:** Tested the exact trap under `set -euo pipefail` across three states: (a) `CPID` unset, (b) `CPID` actively writing files inside `$TMP/chromium` every 50 ms while `/tmp/koc_bench_$NEW/benchmark.json` exists, and (c) `CPID` already dead before exit. In all three cases the subshell exited `0`, `CPID` was terminated, `$TMP` was completely removed, and `/tmp/koc_bench_$NEW/benchmark.json` survived.

#### P3-1 — Minor doc count in time estimate (`7 KOC` vs `6 KOC`) and missing unit test for `FreeGuard` cost stop: **CLOSED**
- **Location:** [RUNBOOK_v2_s3_rerun.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/docs/build/RUNBOOK_v2_s3_rerun.md#L37), [test_s3_free_smoke_script.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a18400a76b9a34149/tests/core/test_s3_free_smoke_script.py#L113-L122)
- **Evidence:** Line 37 now reads `S3 ~175 s mỗi KOC x 6 KOC (6 trong 10 KOC có video chưa phân tích)`, and `test_nonzero_cost_stops_with_exit_code_3` is included and passing in `tests/core/test_s3_free_smoke_script.py`.

---

### Check for New P1 / P2 / P3 Issues in `e9dc01e` and `8b47aa8..HEAD`

- **No open P1, P2, or P3 issues found.**
- `git diff 8b47aa8..HEAD` touches only `docs/process/build/{EVIDENCE_v2_s3_rerun_prep,REVIEW_v2_s3_rerun_prep,RUNBOOK_v2_s3_rerun}.md`, `scripts/{s3_free_smoke,s3_pending_videos}.py`, and `tests/core/{test_s3_free_smoke_script,test_s3_pending_videos_script}.py`. No production files under `src/koc/` or `config/` were altered, and `data/koc.db` was never modified.

---

### Command Results

1. **Mocked `cost > 0` check on `scripts/s3_free_smoke.py` and Step 1 loop simulation (stub returning `3, 1, 0` vs `2, 1, 0`):**
   ```text
   == x/y:free  mode: frames + audio  video 7701594488619191573
   Cảnh báo: Chi phí thực tế (0.010000 USD) vượt quá mức ước tính (0.000000 USD)
   STOP: model reported cost 0.01 USD
   SystemExit code: 3
   --- Case A: stub returns 3, 1, 0 ---
   ##### s3_free_smoke.py 
   stub invoked (call #1), returning 3
   STOP: a :free model reported a cost
   Case A subshell exit code: 3, calls made: 1
   --- Case B: stub returns 2, 1, 0 ---
   ##### s3_free_smoke.py 
   stub invoked (call #1), returning 2
   ##### s3_free_smoke.py --no-audio
   stub invoked (call #2), returning 1
   ##### s3_free_smoke.py --text-only
   stub invoked (call #3), returning 0
   SMOKE PASS in mode: --text-only
   Case B subshell exit code: 0, calls made: 3
   ```

2. **`scripts/s3_pending_videos.py` on read-only backup `/tmp/agyprep2.db` with `sha256sum` before/after:**
   ```text
   before: sha256=0bb5d3eb4204c60f4e878f418d8165b31fa5fe033f91fd252c7f94a95e4c304c api_calls=361
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
   after:  sha256=0bb5d3eb4204c60f4e878f418d8165b31fa5fe033f91fd252c7f94a95e4c304c api_calls=361
   SHA256 MATCH: OK
   ```

3. **`bash -n` on all 4 fenced bash blocks in `docs/process/build/RUNBOOK_v2_s3_rerun.md` and `EXIT` trap verification:**
   ```text
   Found 4 bash blocks
   block 1: bash -n rc=0, lines=20, stderr=''
   block 2: bash -n rc=0, lines=57, stderr=''
   block 3: bash -n rc=0, lines=10, stderr=''
   block 4: bash -n rc=0, lines=11, stderr=''
   === Trap test: unset ===
   subshell rc=0, TMP exists=no
   === Trap test: running ===
   subshell rc=0, TMP exists=no
   CPID alive=no
   bench exists=yes
   === Trap test: dead ===
   subshell rc=0, TMP exists=no
   ```

4. **Full offline test suite (`unshare -rn`):**
   ```text
   $ unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q'
   506 passed, 1 skipped in 91.60s (0:01:31)
   ```
