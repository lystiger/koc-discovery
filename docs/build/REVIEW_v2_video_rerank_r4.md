Overall FAIL

- **P2 OPEN — [src/koc/video_select.py:52](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/video_select.py:52):** Symmetric folding promotes unrelated live videos. Brief `chong nang` matches `chồng - Nàng`; `rua mat` matches `rửa mát`. Production S3 probes move these videos from ranks 6/10 into analyzer position 1, marked `on_topic:true`. Brief-first deduplication discards the precise configured spelling. Prefer canonical configured phrases when available.

- **R3 P2 CLOSED:** Production probe for `sua tam` selects `Sữa tắm hương hoa` before higher-revenue shampoos.

Risk is limited but demonstrated: all **37 unchanged config terms** produce zero new matches across **1,652 live videos**. Unaccented versions expose two unrelated titles that change actual selections.

Earlier checks pass:

- `nâng cơ` and `chống nâng`: score zero.
- `kem chong nang cho da dầu`: selected before shampoo.
- Budget-only reruns at 8M, 17M and 55M VND: **27 cache hits each; zero analyzer calls, tokens or USD**. Each starts from a fresh memory clone of the read-only DB copy.

Offline command results under `unshare -rn`, fake keys and `PYTHONPATH=src`:

- Independent production probes: exit **0**, reproducing the findings.
- Full suite with temporary asyncio syscall workaround: **484 passed, 1 skipped**, exit **0**.
- Ordinary full-suite invocation: timeout, exit **124**; sandbox blocks `socket.send()`.
- Source/test diff check: exit **0**, unchanged.

[Full English report, commands and evidence](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/docs/build/REVIEW_v2_video_rerank_r4_independent.md).