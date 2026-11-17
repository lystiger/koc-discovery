Overall FAIL

Two P2 findings remain open:

- **P2 OPEN — [video_select.py:61](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/video_select.py:61):** `kem chong nang cho da dầu` scores zero because `dầu` disables folding across the entire title. Probe selects shampoo. At `e08344b`, sunscreen wins.
- **P2 OPEN — [pipeline.py:226](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/pipeline.py:226):** first budget-only rerun misses all 27 existing legacy analyses. Historical budget lives under `s4.budget_vnd`, which adoption ignores. Production probe invokes the analyzer stub again.

All r1 findings are **CLOSED**, independently probed:

| Finding | Result |
|---|---|
| `nâng cơ` false positive | Scores zero; sunscreen wins |
| Attached shampoo hides unattached sunscreen | Sunscreen selected first |
| Identical-media v1/v2 cache collision | Correct IDs; v2 analyzed once, then cached |
| Unrelated-model preview undercount | Preview reports 1; production raises `CacheOnlyMiss` |
| Vacuous prompt test | Prompt captured; product present; budget absent |

Fresh read-only preview: **17 reusable analyses, 10 misses**. At original budget, all 27 old selections adopt successfully with zero analyzer calls.

Holdout: **Rio PASS**. Inspected all 100 titles for `7234931025289217051`; none identifies sunscreen. Conditional clause **N/A**.

Offline suite with fake keys and `PYTHONPATH=src`: **480 passed, 1 skipped**, exit 0, using temporary asyncio workaround. Unmodified invocation timed out, exit 124.

Source and tests unchanged. [Full report, commands, and evidence](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/docs/build/REVIEW_v2_video_rerank_r2.md).