Overall FAIL

- **P2 OPEN — [video_select.py:49](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/video_select.py:49):** Unaccented brief `sua tam` misses `Sữa tắm hương hoa`. Production probe analyzes three shampoos instead. Allow accent folding when either word lacks accents.
- **Both r2 findings CLOSED:** mixed-accent sunscreen beats shampoo; fresh production reruns reuse all 17 analyses with **zero analyzer calls** at three changed budgets.
- **r1 checks hold:** `nâng cơ` and `chống nâng` score zero. Identity, prompt and preview probes pass.
- Arbitrary nested budgets cannot bypass tested cache identities. Search is finite, without a hard cap.
- Offline suite: **482 passed, 1 skipped**, exit 0 with temporary asyncio workaround. Ordinary invocation times out, exit 124.

Source and tests unchanged. [Full report and command results](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/docs/build/REVIEW_v2_video_rerank_r3.md).