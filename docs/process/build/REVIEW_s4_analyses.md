Overall FAIL

Independent review of `6fb40f4..6d329452d4e1d9bce40b9f5dd92b0ecaff7d97d3` on `worktree-agent-a60cac7fdfbf5f6b5`.
Two P2 correctness regressions. No P1 findings. Source files were not modified.

## Findings

### P2: Legacy databases with retained content crash the benchmark command

Location: `src/koc/db.py:226`, reached through `src/koc/benchmark.py:54` and `src/koc/benchmark.py:88`.

`run_analyses()` queries `run_results` without checking whether the table exists. The benchmark explicitly supports older databases without this table and does not run schema migrations. Any retained S3 video now reaches the unconditional query and raises `sqlite3.OperationalError: no such table: run_results`. This happens with or without `video_ids` in the S3 breakdown.

Reproduction: run F1 in the script below. A current-prompt analysis, an S3 score, and a paid ledger entry are sufficient. Drop `run_results`, enable SQLite read-only queries, then call `aggregate()`. The existing legacy-schema test passes because its fixture has no retained analyses and never enters the selector's video loop (`tests/core/test_r5_findings.py:97`).

Also reproduced through `CliRunner` against a temporary legacy database. `koc benchmark --run <id> --out-dir <temporary-directory>` exits 1 with the exception above. Replacing only the benchmark module with its `6fb40f4` implementation exits 0 and reports 0.50 successful credits. Baseline aggregation on the same read-only fixture succeeds with 100 successful input tokens.

Fix: treat an absent `run_results` table as missing selection metadata and use the fallback without migrating the database.

### P2: Applying the current-prompt selector to historical accounting erases successful spend

Location: `src/koc/benchmark.py:54`, `src/koc/benchmark.py:88`; filtering occurs at `src/koc/db.py:223` and `src/koc/db.py:230`.

A completed real run can legitimately retain only `content_v1`, `content_v2`, or `content_v2_repair`, without `run_results` rows or S3 `video_ids`. These analyses are the run's final results, not superseded rows from a later rescore. The new selector returns no analyses because it accepts only `content_v3` variants for real runs. Consequently, `_retained()` becomes empty and `_exact()` reports exact attribution even though provenance is unknown.

Reproduction: run F2 below with each historical prompt. For one retained video, its paid analysis, and its download, baseline reports successful spend of 0.50 credits, 100 input tokens, 10 output tokens, and USD 0.01. HEAD reports zero successful spend, moves all those amounts into `waste`, and sets `success_estimated=False`. Total actual spend remains correct. The successful-path ledger, waste totals, and attribution status are wrong. Historical detail pages also lose the retained rubric and evidence.

Fix: preserve historical retained subjects and historical prompt/model attribution in benchmark accounting. Do not infer that a historical run retained nothing because it has no current-prompt analysis. Keep unknown provenance marked as estimated.

## Reproduction script

Run this Python script from the checkout with `PYTHONPATH` containing `src` and the external socket-blocking `sitecustomize.py`. It uses only synthetic in-memory databases.

```python
import json
import sqlite3
from koc import db
from koc.benchmark import aggregate


def fixture(prompt):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    run = db.create_run(c, {"mock": False, "limit": 1})
    db.upsert_creator(c, "c", "c", {})
    db.upsert_video(c, "v", "c", {})
    db.upsert_score(c, run, "c", "S3", 60, {})
    c.execute("INSERT INTO analyses VALUES (?,?,?,?)", ("v", prompt, "m", "{}"))
    c.execute(
        "INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES (?,?,?,?)",
        ("h", json.dumps({"video_id": "v"}), json.dumps({"prompt_version": prompt}), "t"),
    )
    c.execute(
        "INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,"
        "input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run, "content", "h", "m", prompt, 100, 10, 1, .01, 0, "t"),
    )
    db.add_api_call(
        c, run, "video/url", db.cache_key("video/url", {"video_id": "v"}),
        "200", .5, 1, False,
    )
    c.commit()
    return c, run


c, run = fixture("content_v3")
c.execute("DROP TABLE run_results")
c.commit()
c.execute("PRAGMA query_only=ON")
try:
    aggregate(c, run)
except sqlite3.OperationalError as exc:
    print("F1:", exc)

for prompt in ("content_v1", "content_v2", "content_v2_repair"):
    c, run = fixture(prompt)
    result = aggregate(c, run)
    print("F2:", prompt, "success=", result["totals_success"],
          "waste=", result["waste"], "estimated=", result["success_estimated"])
```

Observed decisive output:

```text
F1: no such table: run_results
F2: content_v2 success= {'calls': 0, 'cache_hits': 0, 'credits': 0.0, 'tokens_in': 0, 'tokens_out': 0, 'usd': 0.0, 'wall_time_ms': 0} waste= {'credits': 0.5, 'tokens_in': 100, 'tokens_out': 10, 'usd': 0.01} estimated= False
```

## Verification

Full suite command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/koc-s4-review-offline:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q -p no:cacheprovider tests
```

Result: **276 passed in 56.68s**, exit 0. The unadjusted attempt stalled at the first TestClient request because this sandbox denies even local `socketpair().send()` with `PermissionError: [Errno 1] Operation not permitted`. The external `sitecustomize.py` blocks socket connections, DNS, and datagram sends. It also caps selector waits at 10 ms so asyncio sees work queued by other threads despite denied wakeup writes. No repository or dependency code was changed for this accommodation. The first stalled attempt was interrupted. Network access remained blocked throughout the completed run.

Additional synthetic checks passed:

- Repair fallback, configured-model preference over a later row from another model, and exact `run_results` prompt/model selection.
- S3 `video_ids` restrict the selected videos. Missing IDs use the creator's videos. Empty IDs and creators without analyses return an empty list.
- Mock fallback selects `content_v1` with model `mock` when that is the available mock analysis.
- Actual `_s3_creator()` writes, `run_analyses()` results, and captured `_s4()` summaries agree in real and mock modes. The persisted S3 score equals the score recomputed from those selected rubrics.
- Existing web tests, benchmark tests, and the complete suite pass under the offline setup.

All three added S4 tests were also run with only `_s4` replaced in memory by its function definition from `6fb40f4`. Result: **3 failed, 6 deselected in 0.25s**. Each failure is the intended stale-analysis assertion, not an import or setup error. The same tests pass in HEAD's full suite. The new helper's `video_ids` argument is unused, so those tests do not themselves exercise video subsets, multiple models, mock selection, or missing legacy tables.

Local evidence files are `/tmp/koc-s4-review-offline/full-suite-poll.log`, `old-tests.log`, `probe.log`, and `minimal_repro.py`. All fixtures were synthetic. The production `data/koc.db` was never opened.

## Existing web limitation outside the findings

`get_creator_full_detail()` still loads the creator's earliest three videos (`src/koc/web/adapter.py:329`), then attaches only the run-selected analyses. With three older videos preceding three current S3 videos, the selector correctly returns the current videos, but the page displays the older videos with empty rubrics and evidence. Reproduced output was `S3 selected=['new0', 'new1', 'new2']`, `detail videos=['old0', 'old1', 'old2']`, and rubric counts `[0, 0, 0]`. The baseline already used the same earliest-three query and displayed the wrong video set, so this is not counted as a new P2 regression. The detail page still does not fully honor the run's video subset.
