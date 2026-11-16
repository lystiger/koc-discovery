Overall PASS

Independent review, round 2, of `5b84b88..bb319dbe711bc862beaf3ac335f566271beff311` on `worktree-agent-a60cac7fdfbf5f6b5`.
No open P1/P2 correctness findings in the requested scope. Source files were not modified.

## Findings

### F1 CLOSED: Legacy databases with retained content no longer crash the benchmark command

Re-ran the original F1 fixture from `REVIEW_s4_analyses.md`: one retained `content_v3` analysis, an S3 score, a paid LLM ledger entry, and a paid video download; drop `run_results` and query read-only. Also re-ran the original extended reproduction with both `{}` and `{"video_ids": ["v"]}` S3 breakdowns on temporary databases opened with SQLite `mode=ro`.

Both aggregations now match the `6fb40f4` implementation exactly. Successful spend is 0.50 credits, 100 input tokens, 10 output tokens, and USD 0.01. `koc benchmark --run <id> --out-dir <temporary-directory>` exits 0 for both fixtures. Database SHA-256 hashes are unchanged after the CLI calls.

`src/koc/db.py:224` checks whether `run_results` exists before the query at line 230. Direct `run_analyses()` calls against both read-only legacy fixtures also return the retained video. Benchmark accounting no longer depends on this selector.

### F2 CLOSED: Historical accounting preserves successful spend and estimated attribution

Re-ran the original F2 fixture separately for `content_v1`, `content_v2`, and `content_v2_repair`, with no selection rows or S3 video IDs. Each result matches `6fb40f4` exactly:

```text
success={'calls': 2, 'cache_hits': 0, 'credits': 0.5, 'tokens_in': 100,
         'tokens_out': 10, 'usd': 0.01, 'wall_time_ms': 0}
waste={'credits': 0.0, 'tokens_in': 0, 'tokens_out': 0, 'usd': 0.0}
success_estimated=True
```

`git diff --exit-code 6fb40f4 HEAD -- src/koc/benchmark.py` exits 0: the benchmark module is restored exactly. The baseline module used for execution also has the same SHA-256 as the git object. Additional historical fixtures with valid seven-criterion analyses retain all seven rubric entries on the detail page; `run_analyses()` returns each historical prompt through its newest-row fallback (`src/koc/db.py:238`).

### Detail-page video subset CLOSED: The page displays the videos selected by S3

Re-ran the original web reproduction unchanged in substance: insert `old0`, `old1`, `old2` before `new0`, `new1`, `new2`; give all six valid current-prompt analyses; list only the three new videos in S3 and record their selected results. This reproduces the original ordering hazard even when the old videos also have current-prompt analyses.

```text
S3 selected=['new0', 'new1', 'new2']
detail videos=['new0', 'new1', 'new2']
API videos=['new0', 'new1', 'new2']
displayed rubric counts=[7, 7, 7]
displayed evidence counts=[1, 1, 1]
```

`src/koc/web/adapter.py:388` selects video rows from the run-selected analyses before applying the three-video limit. `src/koc/web/api.py:131` uses the same selection and order. The earlier web limitation is closed for its exact reproduction.

## Reproduction script

The original report's exact minimal F1/F2 script was copied to `/tmp/koc-s4-review-r2-offline/minimal_repro.py` and run under the external socket blocker. F1 returned normally; all three F2 prompts produced the successful totals above. The following assertion wrapper reuses that original fixture and makes both closure checks explicit:

```python
import runpy
from koc import db
from koc.benchmark import aggregate

fixture = runpy.run_path(
    "/tmp/koc-s4-review-r2-offline/minimal_repro.py"
)["fixture"]

c, run = fixture("content_v3")
c.execute("DROP TABLE run_results")
c.commit()
c.execute("PRAGMA query_only=ON")
assert aggregate(c, run)["totals_success"]["tokens_in"] == 100
assert [a[0] for a in db.run_analyses(c, run, "c")] == ["v"]
print("F1 CLOSED")

for prompt in ("content_v1", "content_v2", "content_v2_repair"):
    c, run = fixture(prompt)
    result = aggregate(c, run)
    success = result["totals_success"]
    assert (success["credits"], success["tokens_in"],
            success["tokens_out"], success["usd"]) == (.5, 100, 10, .01)
    assert all(value == 0 for value in result["waste"].values())
    assert result["success_estimated"] is True
    print("F2 CLOSED:", prompt)
```

The extended reproductions and assertions are in `/tmp/koc-s4-review-r2-offline/probe.py`; additional web checks are in `web_extra.py` in that directory. Both exit 0. The extended script preserves the previous review's seed, analysis, ledger, and S3/S4 probe functions, and checks the corrected outcomes instead of expecting failures.

## Verification

Full suite command, with only bytecode/cache suppression and the external offline bootstrap added:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/koc-s4-review-r2-offline:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python \
  -m pytest -q -p no:cacheprovider tests
```

Result: **317 passed in 76.78s (0:01:16)**, exit 0.

The external `/tmp/koc-s4-review-r2-offline/sitecustomize.py` blocks socket connections, DNS resolution, and datagram sends. It retains the previous review's 10 ms selector polling accommodation for this sandbox's denied local socket wakeups. Direct calls to the patched connection and DNS functions confirm that the blocker is active. No network access or dependency changes were used.

Additional regression checks passed:

- Exact `run_results` prompt/model selection overrides current-prompt and later rows from other models. A missing referenced analysis falls through without crashing.
- `content_v3_repair` fallback and configured-model preference beat a later current-prompt row from another model. An explicitly changed model configuration was also tested.
- With no current-prompt or selected result, the newest historical row is returned. Explicit S3 video IDs preserve listed historical rows; absent IDs retain the implemented filtering of historical-only videos when stronger matches exist (`tests/core/test_run_analyses.py:56`).
- Explicit empty S3 video IDs and creators without analyses return no selected analyses. Mock fallback and exact selection work.
- Actual `_s3_creator()` writes, selected analyses, and captured `_s4()` summaries agree in real and mock modes. Recomputed rubric scores equal the persisted S3 score, 60.0 in both fixtures. Paid/provider calls were stubbed.
- Top-five cards use the selected video's frame. Detail/API payloads retain the selected rubric and evidence even when a newer analysis from another prompt/model exists for the same video.
- `_evidence_target_exists(..., run_id)` rejects both videos outside the run subset and evidence from a superseded prompt/model of the same video. Selected evidence and existing creator metric evidence remain valid. `_reason()` and API reason links filter excluded video evidence (`src/koc/web/matching_api.py:109`, `src/koc/web/api.py:170`).

Evidence: `/tmp/koc-s4-review-r2-offline/full-suite.log`, `probe.log`, and `web-extra.log`. All review fixtures were synthetic. The production `/home/lystiger/Projects/KOC-Discovery/data/koc.db` was never opened or copied. Before report creation, `git status --porcelain=v1` was empty and `git diff --check` passed. The only repository artifact added by this review is this report.
