Overall FAIL

- **P2 — [src/koc/estimate.py:35](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a9619bb0f6162a6dc/src/koc/estimate.py:35): Incorrect estimate units.** Code divides stage totals by funnel inputs instead of using published `units_success`/`units_total`. For 200 candidates, it prints **26.0–27.6 credits / $0.43–1.32**; published-unit projections give **27.6–29.4 / $0.48–1.46**. S2 also remains 10.7 minutes when `s2_limit` drops from 10 to 5. Use published units with actual processed-stage counts. CLI and `run_estimate` both inherit this error.

- **P3 — [docs/ARCHITECTURE.md:110](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a9619bb0f6162a6dc/docs/ARCHITECTURE.md:110): Operator documentation contradicts TTL behavior.** It still says Kalodata cache never expires. After seven days, a normal rerun can spend credits. Evidence documents this exception at `docs/build/EVIDENCE_v2_core_a.md:41`; add Vietnamese operator guidance explaining TTL and `--cache-only`.

The rerun choice fits newer A3’s explicit **fresh-run** qualification, narrowing original C6. Synthetic pipeline replay confirmed fresh and stale `--cache-only` reruns preserved picks at **0 credits / 0 tokens**. Plain stale replay spent **1.9 credits**.

Other checks passed: “ước tính” labels, configured S2 text, payload parity and missing-benchmark `null`, exact TTL endpoint scope, permanent analyses/LLM cache, and credit-cap enforcement during refetch. A6 removes the lenient fixture, seeds valid analyses, and preserves existing assertions.

Full offline suite: **441 passed, 1 skipped in 138.31s**, using `unshare -rn`, fake `KALODATA_API_KEY`, `GEMINI_API_KEY`, and `OPENROUTER_API_KEY`. An external selector wakeup cap resolved a TestClient stall. Source/tests remained unchanged; production `data/koc.db` connections were blocked.

[Suite log](/tmp/koc-core-a-review-suite-final.log) · [Independent probes](/tmp/koc-core-a-review-probes.log) · [Rerun replay](/tmp/koc-core-a-review-rerun.log)