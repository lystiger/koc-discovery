# Independent budget review — round 4

Date: 2026-11-15. Reviewer: Codex / OpenAI.
HEAD: `e875b843ad7ffd7a3ae08ce2b37fba24d6a571b1`, including LLM fix `1968d1a` and core fix `d68fdd5`.

**Overall: PASS. R2-1 closed for the requested budget counterexamples. No confirmed P1/P2 remains open in this scope.**

Offline, budget closure only. Re-read round 3 and current implementation; independently ran Python-stdin probes using real SQLite, public `write_reasons`/`GeminiClient`, and mocked generation. Only this report was created.

| Item | Verdict | Evidence |
|---|---|---|
| Schema overhead | PASS | Same sample: 3039 prompt UTF-8 bytes, 513 schema bytes. Actual checked estimate is now `$0.005814`, including schema and 200 overhead tokens; without schema it is `$0.005429`. With round-3 initial spend `$4.9945285`, public `write_reasons` raises before generation: **0 calls**, ledger unchanged. Schema reaches estimation in `src/koc/llm/reasons.py:165` and `src/koc/llm/content.py:247`; accounting in `src/koc/llm/pricing.py:245`. |
| Arbitrary model | PASS | `arbitrary-unpriced-model` raises `ValueError` at construction. Mutating an accepted client's model to that ID also raises before generation; **0 SDK calls**. Model validation: `src/koc/llm/gemini.py:62`, `src/koc/llm/gemini.py:87`; usage pricing receives the sent model. |
| Overspend logging | PASS | Replayed round-3 conditional usage: initial `$4.9945285`, checked `$0.005279`, actual `$0.005664`. `record` raises, but ledger retains **2 rows, total `$5.000192500000001`**. Separate below-cap estimate breach (`$0.5` checked, `$0.6` actual, `$1` cap) also raises and retains its row. Insert commits before either rejection: `src/koc/budget_guard.py:26`. |
| Pipeline stop at cap | PASS | Independent execution probe starts with `$1` logged at `$1` cap and a `$0.1` next-call estimate. Two S3 tasks and one S4 task become `blocked`, all with retries `0`; run becomes `blocked`; **0 generation dispatches**. Used real task advancement, timing, and SQLite; mocked stage bodies and external client. Handler: `src/koc/pipeline.py:344`. |
| Resume after raising cap | PASS | Raised that probe's cap to `$2`; public `resume` retains run ID, executes `c1`, `c2`, then S4, and ends with **3 done tasks, cleared errors, run done**. Resume: `src/koc/pipeline.py:412`. Requested suite additionally covers the initially-over-cap case. |

Requested gate, with bytecode writes disabled:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q tests/llm tests/core
81 passed in 11.28s
```

Skipped `tests/web`. No network or real Gemini calls.

Limits: synthetic schema usage is not a measured tokenizer result. Live prices, service tokenization, media accounting, and the universal validity of the fixed overhead margin remain **UNPROVEN** offline. PASS covers the reproduced defects and local stop/resume behavior, not a universal service-cost guarantee. `max_call_upper_bound_usd` is exported and tested, but core does not call it; actual LLM callers check each request directly.
