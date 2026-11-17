Overall PASS

## Findings

### P1
None.

### P2
None.

### P3

1. **LLM-written "audience unverified" caveats are not filtered from judge sentences** — [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L108-L109), [reasons.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/llm/reasons.py#L59-L61)
   - **Failure scenario**: `load_items` filters `caveats_vi` by exact string inequality `t != AUDIENCE_MISSING_CAVEAT_VI` (`"Chưa xác minh hồ sơ khán giả (gói Kalodata không có dữ liệu khán giả); cần xác nhận trực tiếp với creator."`). However, rule 5 of [reasons_v4.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/prompts/reasons_v4.md#L41-L42) requires the S4 model itself to write an audience-unverified caveat when audience data is missing. On all 5 KOCs of live run `0e555cac95fb4fb49168410e40ea92d5` (and all 5 of `7372009b22764b339fbcf0f3efb4bc4e`), the model wrote its own phrasing (e.g. `"Hồ sơ khán giả của KOC chưa được xác minh do dữ liệu Kalodata không có thông tin nhân khẩu học..."`). Because that phrasing does not match `AUDIENCE_MISSING_CAVEAT_VI` (or `_states_audience_unverified`, which checks `"chưa xác minh"` rather than `"chưa được xác minh"`), the caveat remains in `item.sentences` while `item.evidence` has no audience metric ID, so a strict judge grades the mandatory disclaimer as `unsupported` or `partly`.

2. **Prompt template substitution and untrusted text delimiters are soft/sequential (crafted-only)** — [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L95-L98), [faithfulness_v1.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/prompts/faithfulness_v1.md#L5-L17)
   - **Failure scenario**: [faithfulness_v1.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/prompts/faithfulness_v1.md#L5) instructs the judge to treat `BẰNG CHỨNG` and `CÂU CẦN CHẤM` as data rather than instructions, and `build_schema(n)` + `_validate` constrain output structure to `n` indexed verdicts. However, `_build_prompt` does not strip newlines or wrap untrusted `quote_vi` / reason strings in structural delimiters (such as XML tags or code fences), and chains `.replace("{{EVIDENCE}}", evidence).replace("{{SENTENCES}}", sentences)`. A crafted video quote containing `\n- [metric:...]` or the literal placeholder `{{SENTENCES}}` can inject lines into the evidence block.

3. **`_metric_line` does not bind `creator_id` or reject `null` metric values (crafted-only)** — [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L68-L75)
   - **Failure scenario**: Normal S4 recommendations validate `cited_evidence_ids` against `_get_valid_evidence_ids(c)`. If a crafted or manually edited `recommendations.rec_json` cites `metric:<other_creator_id>:<name>` or a metric whose stored JSON value is `null`, `_metric_line` resolves `(parts[1], parts[2])` without checking `parts[1] == row[0]` (`creator_id`) or `json.loads(row[0]) is not None`.

4. **`stored_summary` does not cross-check current `recommendations` rows or `request_hash` after post-hoc S4 edits** — [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L230-L239)
   - **Failure scenario**: `stored_summary(conn, run_id)` selects the latest `(model, prompt_version)` in `faithfulness` for `run_id` and averages all rows for that pair. If `recommendations` for `run_id` were later regenerated without re-running `koc faithfulness --run <id>`, `stored_summary` would return the prior `faithfulness` rows until `koc faithfulness` is run again.

---

## Checklist Verification

- **Judge sees only cited & resolved evidence (no more, no less)**: Verified in [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L78-L87) and [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L112-L118). `load_items` resolves only `eid in rec.cited_evidence_ids` against `db.run_analyses(conn, run_id, creator_id)` (including only the cited `Evidence` item and rubric entries whose `evidence_ids` reference `eid`) and `_metric_line`. On run `0e555cac95fb4fb49168410e40ea92d5`, all 5 KOCs resolve 8/8, 11/11, 9/9, 10/10, and 8/8 cited evidence IDs with 0 uncited items leaked.
- **Reasons citing no evidence are unsupported**: Verified in [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L219-L220) and tested in [test_faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/tests/core/test_faithfulness.py#L87-L94). When `item.evidence` is empty, every sentence gets `verdict: "unsupported"` (`why: NO_EVIDENCE_WHY`, score `0.0`) with 0 LLM calls.
- **Scoring math (`partly = 0.5`, per-KOC share, run mean)**: Verified in [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L31) and [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L133-L138). `MARKS = {"supported": 1.0, "partly": 0.5, "unsupported": 0.0}`; `score_of` computes the arithmetic mean over sentence verdicts; `run_score` computes the arithmetic mean over KOC scores (or `None` when empty).
- **Strict JSON schema validation and repair**: Verified in [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L45-L54) and [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L159-L191). `build_schema(n)` enforces `additionalProperties: False`, required fields, `verdict` enum `["supported", "partly", "unsupported"]`, and `minItems == maxItems == n`. `_validate` enforces `[v.index for v in payload.verdicts] == list(range(n))`. `_grade` retries once with error feedback and raises `ValueError` if the second attempt fails.
- **Caching (rerun = 0 calls) & cache key coverage**: Verified in [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L90-L92) and [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L120-L124). `_hash` hashes `{"v": PROMPT_VERSION, "model": model, "sentences": sentences, "evidence": evidence}` with `sort_keys=True`. Matching `request_hash` in table `faithfulness` returns cached verdicts with 0 calls.
- **`BudgetGuard` / USD cap enforced before each call**: Verified in [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L176-L182) and [faithfulness.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/faithfulness.py#L211). Every attempt in `_grade` (initial and repair) estimates upper-bound tokens and USD via `estimate_tokens_and_usd`, calls `guard.check(est_usd)` before `client.generate_json`, passes `budget_guard=guard` for transport retries, and calls `guard.record(usage)` afterward.
- **Judge calls logged in `llm_calls` with `run_id = NULL` (S4 isolation, 5 USD cap inclusion, operator visibility)**:
  - *S4 cost isolation*: Both [report.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/report.py#L45) ([line 146](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/report.py#L146)) and [benchmark.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/benchmark.py#L112) ([lines 275-277](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/benchmark.py#L275-L277)) query `llm_calls WHERE run_id=?`, which excludes `run_id IS NULL`. (Had `run_id` been non-null, `report.py:160` would have folded `kind='faithfulness'` into S4 and `benchmark.py:117` would have raised `KeyError: 'faithfulness'`).
  - *5 USD cap inclusion*: [budget_guard.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/budget_guard.py#L24) sums `SELECT COALESCE(SUM(cost_usd),0) FROM llm_calls` across the entire table regardless of `run_id`, so judge calls count toward the global 5 USD cap in [llm_caps.yaml](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/config/llm_caps.yaml#L1).
  - *Operator visibility*: The spend is printed by `koc faithfulness` on the grading run (`chi phí: ... USD` in [cli.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/cli.py#L252)) and by the `llm_calls` delta in [RUNBOOK_v2_faithfulness.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/docs/build/RUNBOOK_v2_faithfulness.md#L45-L48). Because `run_id` is `NULL` and `benchmark.py` only reports `excluded_api_calls` (not `excluded_llm_calls`), historical faithfulness call costs are not shown in `docs/BENCHMARK.md`, `koc status`, or cached reruns (`--cache-only` prints `0.000000 USD`), remaining inspectable via `SELECT * FROM llm_calls WHERE kind='faithfulness'`.
- **Benchmark output & `estimate.py` per-KOC units**: Verified in [benchmark.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/benchmark.py#L334-L336), [benchmark_render.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/benchmark_render.py#L119-L123), and [estimate.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/src/koc/estimate.py#L35-L45). `result["faithfulness"]` and section `## 10. Độ trung thực của lý do S4` are emitted only when `stored_summary` is non-None, and `units_success` / `units_total` are unchanged.
- **`:free` smoke script**: Verified in [faithfulness_free_smoke.py](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/scripts/faithfulness_free_smoke.py#L23-L65). Refuses models not ending in `:free`, backs up `file:data/koc.db?mode=ro` to a temp dir, wraps the client in `CostSpy` raising `SystemExit(3)` on any `usage.cost_usd > 0`, and verifies the second pass makes 0 calls.
- **Runbook bash blocks**: Verified in [RUNBOOK_v2_faithfulness.md](file:///home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a59bc3b045147544a/docs/build/RUNBOOK_v2_faithfulness.md#L11-L51). Both blocks run inside subshells with `set -euo pipefail`, pass `bash -n`, back up `data/koc.db` via `sqlite3 -readonly` first, read `OPENROUTER_API_KEY` silently with `read -r -s -p`, and in Block 2 run `--dry-run` and require typing `yes` before any DB write or paid call.

---

## Command Results

1. **Offline `--dry-run` on read-only DB backup (`/tmp/faith.db`) for run `0e555cac95fb4fb49168410e40ea92d5`**:
   ```text
   $ sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db '.backup /tmp/faith.db'
   $ KOC_DB=/tmp/faith.db PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m koc.cli faithfulness --run 0e555cac95fb4fb49168410e40ea92d5 --dry-run
   Ước tính chấm độ trung thực, mô hình google/gemini-3.8-flash: 5 lượt gọi (đã lưu 0, không có bằng chứng 0), tối đa 31542 token đầu vào, tối đa 0.0492 USD. Chạy thử: không gọi mạng.
   ```
   Post-check on `/tmp/faith.db`: `SELECT name FROM sqlite_master WHERE type='table' AND name='faithfulness'` returned empty (table not created by `--dry-run`).

2. **Runbook syntax check (`bash -n` on both blocks in `docs/process/build/RUNBOOK_v2_faithfulness.md`)**:
   ```text
   Found 2 bash blocks
   Block 1 bash -n exit=0 stderr=''
   Block 2 bash -n exit=0 stderr=''
   ```

3. **Full pytest suite (offline under `unshare -rn`)**:
   ```text
   $ unshare -rn sh -c 'ip link set lo up; PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q'
   524 passed, 1 skipped in 92.65s (0:01:32)
   ```
