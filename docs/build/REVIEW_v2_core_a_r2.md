Overall PASS

Reviewed `090efbb..4c2e318` and `0f5c03e..4c2e318`. No open P1/P2 findings in core track A.

- **P2 r1 — CLOSED:** [src/koc/estimate.py:36](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a9619bb0f6162a6dc/src/koc/estimate.py:36) uses published units. Independent multiplication by stage counts `(200, 200, 60, 10, 10, 5)` gives **27.611111–29.377778 credits**, **$0.478810–1.460518**, **441,769–1,286,591 tokens**, and **46.236 minutes** before the ±25% band. Display correctly rounds to **27.6–29.4 credits / $0.48–1.46 / 35–58 minutes**. Reducing `s2_limit` to 5 changes S2 **10.7→5.4 minutes** and S3 **29.3→14.6 minutes**.
- **P3 r1 — CLOSED:** [docs/ARCHITECTURE.md:110](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a9619bb0f6162a6dc/docs/ARCHITECTURE.md:110) documents seven-day TTL, permanent caches, paid stale refetches, and free `--cache-only` replay.
- **P3 new — OPEN:** [README.md:132](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a9619bb0f6162a6dc/README.md:132) and [docs/ARCHITECTURE.md:109](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-a9619bb0f6162a6dc/docs/ARCHITECTURE.md:109) still claim dry-run lacks USD/time and prints “S2 còn 15”. Update these stale descriptions.

Command results:

```text
unshare -rn python -m pytest -q
443 passed, 1 skipped in 137.70s

git diff --check 0f5c03e..HEAD
exit 0

git diff --quiet -- src tests
exit 0
```

Suite used venv Python, fake API keys, a production-database audit guard, and an external selector polling cap for the sandbox’s TestClient wakeup issue.

Independent probes passed: TTL boundary/refetch/cap enforcement, API estimate parity for counts 1/5/10, missing-benchmark `null`, valid seeded analyses, and preserved existing assertions. Synthetic replay preserved picks at **0 credits / 0 tokens** when fresh or stale with `--cache-only`; ordinary stale replay spent **1.9 credits**.

React panel rendering remains **UNPROVEN** under this core-track review. Source/tests unchanged; production `data/koc.db` access blocked.

[Suite log](/tmp/koc-core-a-r2-independent/suite.log) · [Independent probes](/tmp/koc-core-a-r2-independent/probes.log) · [Replay log](/tmp/koc-core-a-r2-independent/rerun.log)