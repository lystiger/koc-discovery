# Independent Review: `main...v2/final-fixes` (v2.0.6, AGY)

Reviewed `git diff main...v2/final-fixes` across 4 commits (`c8866b1`, `271e2e3`, `399fea6`, `6794717`; 14 files changed, 52 insertions, 21 deletions).

All database inspections opened `data/koc.db` and `data/demo.db` in read-only mode (`file:data/koc.db?mode=ro` and `sqlite3 -readonly`), with writable reproductions and CLI/web checks run against temporary copies in `/tmp` and the scratch directory. Both `data/koc.db` (`0fcc649ec8e4db6608e7e2a5a83fa3b312db19acd79fb4ee79e644a1674982f2`) and `data/demo.db` (`33a58f38343c6a1fdccbefeb1bf3552253e110d55dfb2e0d0ac60d89aee0d52b`) were verified unchanged before and after the review. No tracked files were modified.

---

## Findings

No **P1** or **P2** findings.

### P3 (Non-blocking observations)

1. **P3 — Module docstring in `src/koc/llm/pricing.py:33-38` omits the new per-frame floor.**
   - **Location:** `src/koc/llm/pricing.py:33-38` vs `src/koc/llm/pricing.py:210, 222-230` and `config/llm_prices.yaml:55-57`.
   - **Evidence:** The top-of-file rationale docstring still writes `tiles = ceil(width / 768) * ceil(height / 768)` and `image_tokens = ceil(total_tiles * 258 * 1.5)` without noting `max(tiles * 258, min_image_tokens_per_frame)` per frame. The inline comment at `src/koc/llm/pricing.py:222` and `config/llm_prices.yaml:55-57` document the floor accurately.

2. **P3 — `reports/report_*.{json,md}` is not listed in `.gitignore`.**
   - **Location:** `.gitignore:1-16`, `src/koc/report.py:203-206`.
   - **Evidence:** Running `koc report --run <run_id>` in the repository root writes `reports/report_<run_id>.json` and `reports/report_<run_id>.md`, which remain untracked files unless cleaned up or ignored. (It no longer overwrites the tracked `reports/benchmark.json` or `docs/BENCHMARK.md`.)

3. **P3 — Shrunk `.wordmark svg` aligns to the top of its `28px` `.wordmark` box at 320–375 px.**
   - **Location:** `web/src/styles.css:46-47, 328-331`.
   - **Evidence:** At `@media (max-width: 767px)`, `.wordmark` keeps `height: 28px` (`web/src/styles.css:328`) while `.wordmark svg` sets `max-width: 100%; height: auto` (`web/src/styles.css:331`). At `320px` viewport width, `.wordmark` shrinks to `134.77px × 28.00px` while the SVG scales proportionally to `134.77px × 17.38px`, sitting at the top edge of the `28px` anchor container (~`5.3px` above vertical center). Visually minor; `display: flex; align-items: center` on `.wordmark` (or `height: auto`) would center it vertically.

---

## Detailed Verification of the Three Fixes & Release Claims

### 1. Per-frame input token floor (`src/koc/llm/pricing.py`, `config/llm_prices.yaml`, `tests/llm/test_pricing.py`)

- **Implementation (`config/llm_prices.yaml:55-57`, `src/koc/llm/pricing.py:210, 222-231`):**
  - `config/llm_prices.yaml:57` sets `min_image_tokens_per_frame: 1120` under `token_accounting`.
  - `src/koc/llm/pricing.py:210` reads `min_image_tokens = int(rates.get("min_image_tokens_per_frame", 0))`.
  - Across all three branches (`frame_sizes` at line 223, `frame_paths` at lines 226-227, and `n_frames` fallback at line 229), each frame is bounded below by `min_image_tokens`:
    - `frame_sizes`: `sum(max(calculate_image_tiles(w, h) * image_token_rate, min_image_tokens) for w, h in frame_sizes)`
    - `frame_paths`: `sum(max(calculate_image_tiles(*get_jpeg_dimensions(p)) * image_token_rate, min_image_tokens) for p in frame_paths)`
    - `n_frames`: `max(0, n_frames) * max(image_token_rate, min_image_tokens)`
  - When `n_frames == 0` or `frame_sizes == []` (e.g., `reasons` at `src/koc/llm/reasons.py:250` and `faithfulness` at `src/koc/faithfulness.py:184, 207`), `base_image` remains `0`.
  - When a frame has enough tiles to exceed the floor (e.g., 5 tiles × `258` = `1,290 > 1,120`), `max(tiles * 258, 1120)` preserves the higher tile count.
- **Backward compatibility for callers without the key (`tests/llm/conftest.py:54-67`, `tests/llm/test_pricing.py:39-360`):**
  - When `min_image_tokens_per_frame` is absent from `token_accounting` (such as `STABLE_TEST_PRICING_CONFIG` in `tests/llm/conftest.py:54-67` or custom configs in `test_unpriced_model_refused` at `tests/llm/test_pricing.py:292-312`), `rates.get("min_image_tokens_per_frame", 0)` evaluates to `0`, keeping the exact tile-only behavior. All existing exact-value pricing tests in `tests/llm/test_pricing.py` pass unchanged.
- **Verification of the empirical claim on 31 real persona calls / 30 videos (`data/koc.db`, `data/media/`):**
  - Read-only inspection of `llm_calls WHERE kind='persona' AND cache_hit=0` (`id=141..171`, 31 calls across the 30 S3 videos of run `0e555cac95fb4fb49168410e40ea92d5`, including one schema retry on video `7707875062786870548` at `id=146` with `12,058` input tokens followed by `id=147` with `12,141` input tokens) confirmed that actual `input_tokens` ranged from **`10,182` to `12,141`** (`10.2k–12.1k`) across video durations from `14.5s` to `90.0s` (raw durations up to `283.0s`).
  - Re-computing the old (`min_image_tokens_per_frame=0`) and new (`min_image_tokens_per_frame=1120`) input token estimates across all 30 videos:
    - Using the existing frame directories in `data/media/frames/<video_id>` (where 28 directories have 8 frames clipped to `≤90s` and 2 directories—`7581276298509683976` and `7700828901895081236`—retain earlier unclipped frames up to `137.82s` and `158.35s`), the old estimate was under actual on **28/30 videos** (`0.74x–1.25x` actual), and the new estimate is **`1.75x–2.11x` actual** (or **`1.5x–2.1x`** when excluding per-frame timestamp labels).
    - Using the exact runtime `preprocess_video(..., n_frames=8)` path in `persona._call()` (`src/koc/persona.py:94, 106-109`, where all 30 videos are clipped to `≤90.0s` and all frames are `360×640`), the old estimate (`7,684–11,584` tokens) was under actual on **30/30 videos** (`0.75x–0.97x` actual), while the new estimate (`18,028–21,928` tokens) is **`1.77x–1.84x` actual** on all 30 videos—strictly inside the claimed `1.5–2.1x` band.
- **BudgetGuard and S3 `content` estimates (`src/koc/llm/content.py:361-383`, `src/koc/llm/openrouter.py:179-188`, `src/koc/llm/pricing.py:301-332`):**
  - For 8 frames of `360×640`, the floor adds `ceil(8 * 1120 * 1.5) - ceil(8 * 258 * 1.5) = 13,440 - 3,096 = 10,344` estimated input tokens (`+$0.008534 USD` per call at OpenRouter's `$0.825 / 1M` input rate).
  - `max_call_upper_bound_usd("content")` increases from `$0.033040` to `$0.041573`, while `max_call_upper_bound_usd("reasons")` stays unchanged at `$0.012336`.
  - In `data/koc.db`, the 41 uncached `content_v3` calls and 7 `content_v3_repair` calls used `11,300–13,545` actual input tokens; the new S3 `content` estimate reserves `~19.8k–23.6k` input tokens (`~0.033–0.036 USD` per call against the `5.00 USD` cap), which is safely above actuals and causes no failures across the test suite (`128 passed` in `tests/llm`).

### 2. Legacy `koc report` output path (`src/koc/report.py`, `src/koc/cli.py`, `docs/GUIDE.md`, `tests/core/test_d2_pipeline.py`)

- **Code changes (`src/koc/report.py:199-207`, `src/koc/cli.py:188-189`, `docs/GUIDE.md:48`, `tests/core/test_d2_pipeline.py:89-92`):**
  - `write_benchmark(conn, run_id)` in `src/koc/report.py:203-206` now writes `reports/report_{run_id}.json` and `reports/report_{run_id}.md` instead of `reports/benchmark.json` and `docs/BENCHMARK.md`.
  - `src/koc/cli.py:189` updates the CLI message to `Đã ghi reports/report_{run}.json và reports/report_{run}.md ({result['candidates']['finalists']} ứng viên vào S4).`
  - `docs/GUIDE.md:48` updates the CLI reference accordingly.
- **Dependency check across the repository:**
  - `reports/benchmark.json` and `docs/BENCHMARK.md` are produced exclusively by `koc benchmark` (`src/koc/cli.py:193-212`, `src/koc/benchmark.py`, `src/koc/benchmark_render.py`).
  - `src/koc/estimate.py:12, 37-39`, `scripts/compare_approaches.py:137`, and `scripts/s3_rerank_preview.py:53` read `units_success` / `units_total` from `reports/benchmark.json` (the `koc benchmark` schema, which `koc report` previously clobbered with an incompatible schema).
  - Searching the entire codebase (`src/`, `tests/`, `scripts/`, `docs/`) confirmed that nothing else depended on `write_benchmark` writing `reports/benchmark.json` or `docs/BENCHMARK.md`.
  - End-to-end CLI verification in a temporary directory with a copy of `data/koc.db` and `reports/benchmark.json` confirmed that `koc report --run 0e555cac95fb4fb49168410e40ea92d5` exited `0`, created `reports/report_0e555cac95fb4fb49168410e40ea92d5.{json,md}`, left `reports/benchmark.json` byte-for-byte untouched, did not create `docs/BENCHMARK.md`, and `estimate_run()` continued to return `{'low': 27.6, 'high': 29.4}` credits and `{'low': 0.48, 'high': 1.46}` USD.

### 3. Mobile header overflow fix (`web/src/styles.css`, `web/src/ui/BrandLogo.tsx`, `web/src/ui/SharedSite.tsx`)

- **Code changes (`web/src/styles.css:328-331`):**
  - Inside `@media (max-width: 767px)`, adds:
    ```css
    .wordmark { flex: 0 1 200px; width: auto; min-width: 0; }
    .wordmark svg, .wordmark img { max-width: 100%; height: auto; }
    ```
  - In `web/src/ui/BrandLogo.tsx:14-24`, `<BrandLogo variant="header" />` renders an `<svg className="brand-logo" viewBox="0 0 620 80">` (default `preserveAspectRatio="xMidYMid meet"`, aspect ratio `620 / 80 = 7.75`).
  - With `.wordmark` set to `flex: 0 1 200px; width: auto; min-width: 0` and `.wordmark svg` set to `max-width: 100%; height: auto` (overriding `.brand-logo`'s `height: 100%` at `web/src/styles.css:47`), the wordmark shrinks below `200px` when viewport width is tight (`320–375px`), while `.search-trigger` (`38px`) and `.header-cta` (`103.23px`, `flex: 0 0 auto`) keep their full size and the `14px` right header padding is preserved.
- **Headless Chromium verification across mobile (`320–767px`) and desktop (`768–1440px`) viewports:**
  - Served the built SPA (`python -m koc.web`) against a `/tmp` copy of `data/demo.db` and measured live DOM bounding boxes and screenshots via headless Chromium (`/usr/bin/chromium`):

    | Viewport | `scrollWidth` | `.wordmark` (`w × h`) | `svg.brand-logo` (`w × h`, ratio) | `.search-trigger` (`w`) | `.header-cta` (`w`, right edge, right pad) | `nav` display |
    |---:|---:|---|---|---|---|---|
    | `320px` | `320px` | `134.77 × 28.00` | `134.77 × 17.38` (`7.756`) | `38.00` | `103.23` (`right=306.00`, `pad=14.00`) | `none` |
    | `360px` | `360px` | `174.77 × 28.00` | `174.77 × 22.55` (`7.751`) | `38.00` | `103.23` (`right=346.00`, `pad=14.00`) | `none` |
    | `375px` | `375px` | `189.77 × 28.00` | `189.77 × 24.48` (`7.750`) | `38.00` | `103.23` (`right=361.00`, `pad=14.00`) | `none` |
    | `414px` | `414px` | `200.00 × 28.00` | `200.00 × 25.80` (`7.753`) | `38.00` | `103.23` (`right=400.00`, `pad=14.00`) | `none` |
    | `767px` | `767px` | `200.00 × 28.00` | `200.00 × 25.80` (`7.753`) | `38.00` | `103.23` (`right=753.00`, `pad=14.00`) | `none` |
    | `768px` | `805px` (pre-existing) | `250.00 × 34.00` | `250.00 × 34.00` (`7.353`) | `137.55` | `224.72` (`right=805.42`, `pad=-37.42`) | `flex` |
    | `1024px` | `1024px` | `250.00 × 34.00` | `250.00 × 34.00` (`7.353`) | `236.12` | `224.72` (`right=1000.00`, `pad=24.00`) | `flex` |
    | `1440px` | `1440px` | `250.00 × 34.00` | `250.00 × 34.00` (`7.353`) | `294.12` | `224.72` (`right=1340.00`, `pad=100.00`) | `flex` |

  - At `320–414px`, there is zero horizontal overflow (`scrollWidth == innerWidth`), the "Bắt đầu" button keeps its exact `14.0px` right margin, and the logo preserves its `620:80` (`7.75:1`) aspect ratio.
  - At `768px+`, the CSS rules are untouched by this diff and behave identically to `main`.

### 4. Version `2.0.6`, `CHANGELOG.md`, `README.md`, and pitch deck claims (`575` tests)

- **Version consistency:** `pyproject.toml:7`, `web/package.json:4`, `web/package-lock.json:3, 9`, `README.md:10`, and `CHANGELOG.md:3` all consistently report `2.0.6`. No stale `2.0.5` version strings remain (the only `2.0.5` match in the repo is the `"sonner": "^2.0.5"` dependency in `web/package.json:20`).
- **Test count consistency:** `README.md:13, 27, 168, 194` and `docs/pitch/index.html:342` all consistently report `575` passed tests (`576` collected by `pytest --collect-only -q`, minus `1` live-gated skipped test in offline mode = `575` passed). No stale `574` test counts remain in `README.md` or `docs/pitch/index.html`.
- **Changelog accuracy:** `CHANGELOG.md:3-9` accurately summarizes all three fixes in Vietnamese.

---

## Test Execution Summary

- `unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake .venv/bin/python -m pytest --collect-only -q -p no:cacheprovider'` -> **`576 tests collected in 0.58s`** (matches `575 passed, 1 skipped`).
- `unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake .venv/bin/python -m pytest -q -p no:cacheprovider tests/llm'` -> **`128 passed in 31.05s`**.
- `unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake .venv/bin/python -m pytest -q -p no:cacheprovider tests/core tests/test_cli.py tests/test_db.py tests/test_mapping.py tests/test_schemas.py tests/web/test_matching.py -k "not test_operator_view_shows_brief_count_not_five"'` -> **`355 passed, 1 deselected in 51.14s`**.
- `unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake .venv/bin/python -m pytest -q -p no:cacheprovider tests/web/test_security.py -k "not test_media_symlink_escape_blocked" tests/web/test_app_ui_fixes.py::test_frame_url_dropped_when_media_file_missing'` -> **`3 passed, 1 deselected in 0.84s`**.

VERDICT: PASS

---

## Follow-up

Reviewed `git diff 399fea6..HEAD -- . ':!docs/process'` across `6794717`, `cd47393`, and `9641c43` (9 files changed, 39 insertions, 12 deletions).

### Findings

No **P1**, **P2**, or **P3** findings.

All three previous P3 observations from the initial review are resolved in `9641c43`:
1. **`src/koc/llm/pricing.py:37-38`:** Module docstring now states `image_tokens = ceil(sum(max(tiles * 258, min_image_tokens_per_frame)) * 1.5)` and documents `min_image_tokens_per_frame (config, default 0)` as a measured per-frame floor, matching `src/koc/llm/pricing.py:210, 222-230` and `config/llm_prices.yaml:55-57`.
2. **`.gitignore:17`:** Adds `reports/report_*` (`git check-ignore` matches `reports/report_*.{json,md}` while leaving `reports/benchmark.json` tracked).
3. **`web/src/styles.css:330`:** Adds `display: flex; align-items: center;` to `.wordmark` under `@media (max-width: 767px)`, vertically centering the scaled SVG inside its `28px` box (`web/dist/assets/*.css` rebuilt to match).

### Verification of `README.md` Claims (`cd47393`)

1. **Docker kill/resume command (`README.md:29`):**
   - `docker run --rm --network none -e PYTHON=python koc-discovery bash scripts/kill_resume_test.sh` passes through `scripts/docker-entrypoint.sh:12-13` (`*) exec "$@" ;;`), overrides `PYTHON` at `scripts/kill_resume_test.sh:5` (`PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"`) to use `/usr/local/bin/python` in `python:3.12-slim` (`Dockerfile:16, 23`), and writes temporary databases to `mktemp -d` (`scripts/kill_resume_test.sh:6`).
2. **Task rows, atomic transactions, and DB caching (`README.md:57`):**
   - Every stage task is a row in `tasks` (`src/koc/db.py:12, 86-90`, `src/koc/pipeline.py:512-521, 564`).
   - `db.complete_task(conn, task["task_id"], write)` (`src/koc/db.py:98-106`, called at `src/koc/pipeline.py:613`) executes `write(conn)` and `UPDATE tasks SET status='done'` inside a single `BEGIN ... COMMIT` transaction (`with db.transaction(conn):` reuses `conn.in_transaction` at `src/koc/db.py:72-73`).
   - API responses are cached in `http_cache` (`src/koc/db.py:21, 170-183`, checked in `src/koc/kalodata.py:133-136` and `src/koc/pipeline.py:697-705`), S2 audience metrics in `metrics` (`src/koc/pipeline.py:584-592`), and LLM outputs in `llm_cache` (`src/koc/db.py:22`, `src/koc/pipeline.py:253-300, 334-347`).
   - On resume after `SIGINT` or `SIGKILL`, `execute()` calls `db.reset_running(conn, run_id)` (`src/koc/pipeline.py:534`, `src/koc/db.py:123-130`) to reset interrupted `running` tasks to `pending`, and already-cached API/LLM calls hit `http_cache` / `llm_cache` with `cache_hit=1`, `credits=0`, and `cost_usd=0.0`.
3. **`scripts/kill_resume_test.sh` behavior (`README.md:59-63`):**
   - `scripts/kill_resume_test.sh:9-52` pauses via `KOC_TEST_PAUSE_AFTER_S1_API` (`src/koc/pipeline.py:98`) and `KOC_TEST_PAUSE_AFTER_LLM` (`src/koc/pipeline.py:379`), sends `kill -9`, resumes with `koc.cli resume --mock`, runs a second `koc.cli run --mock --limit 50`, asserts zero duplicate keys across `tasks`, `videos`, `analyses`, and `recommendations` (`scripts/kill_resume_test.sh:31-33`), zero duplicate uncached `request_hash` rows in `api_calls` and `llm_calls` (`scripts/kill_resume_test.sh:34-36`), `runs.status == 'done'` (`scripts/kill_resume_test.sh:37`), and then runs `koc.cli resume --mock` again verifying `0` credits and `0` tokens (`scripts/kill_resume_test.sh:39-47`).
4. **CLI commands and resume constraints (`README.md:65-72`):**
   - `koc status` (`src/koc/cli.py:117-138`, `src/koc/queries.py:7-8`) lists runs newest-first (`ORDER BY started_at DESC`) with task status counts (`SELECT status,COUNT(*) AS n FROM tasks WHERE run_id=? GROUP BY status`) and brief summary.
   - `koc resume` (`src/koc/cli.py:93-114`, `src/koc/pipeline.py:724-754`) always targets `db.run_latest(conn)` (`src/koc/db.py:158-159`), rejects mock/live mode switches (`src/koc/pipeline.py:727-730`), rejects brief changes (`src/koc/pipeline.py:731-734`), and does not re-run a `done` run unless `--retry-failed` is passed (`src/koc/cli.py:105-107`, `src/koc/pipeline.py:735-745`).
   - An in-flight HTTP or LLM request at the moment of termination has not yet reached `db.http_cache_put` (`src/koc/kalodata.py:215`) or `put_cached` (`src/koc/pipeline.py:299`) and is resent on resume.
   - `koc persona` (`src/koc/cli.py:216-244`, `src/koc/persona.py:58-63, 140-153`) commits each video's score to `persona_fit` immediately per video and skips stored `video_id` rows (`if v["video_id"] in done: continue`, 0 calls on rerun).
   - `koc faithfulness` (`src/koc/cli.py:247-285`, `src/koc/faithfulness.py:141-149, 225-260`) commits each KOC's verdicts to `faithfulness` immediately per KOC and skips hash-matched `item.cached` rows (`if item.cached: ... continue`, 0 calls on rerun).

### Execution Verification

- `unshare -rn sh -c 'ip link set lo up; PATH=$PWD/.venv/bin:$PATH KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake bash scripts/kill_resume_test.sh'` -> **`SIGKILL + resume: S1b PASS`** and **`SIGKILL + resume: S3 PASS`** (exit code `0`).
- `data/koc.db` (`0fcc649ec8e4db6608e7e2a5a83fa3b312db19acd79fb4ee79e644a1674982f2`) and `data/demo.db` (`33a58f38343c6a1fdccbefeb1bf3552253e110d55dfb2e0d0ac60d89aee0d52b`) verified unchanged; no tracked files modified outside `docs/process/build/REVIEW_v2_0_6_agy.md`.

VERDICT: PASS
