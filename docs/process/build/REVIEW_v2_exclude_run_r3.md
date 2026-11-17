Overall FAIL

- **P2 OPEN — Budget refusal options become invisible.** [matching_api.py:310](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abad2461e6efd9021/src/koc/web/matching_api.py:310) converts every exclusion-related refusal to `needs_run`, including budget failures with enough candidates. Independent HTTP probe: two creators, 15M VND budget, 30M minimum. Adding exclusions outside the follower band changes `refused` to `needs_run` and clears warnings. Options remain in JSON, but [pages.tsx:380](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abad2461e6efd9021/web/src/ui/pages.tsx:380) never displays them. Violates D-B1. Preserve budget refusals or render their warnings and options.

- **r2 P2 cached exclusion finding — CLOSED.** Independent HTTP POST/GET changed picks from `c0,c1` to `c2,c3`. Excluded creators appeared in neither picks nor alternates. Repeated IDs and combined exclusions passed.

For genuine cached-pool shortages, `needs_run` is consistent with D-B4: empty picks, no paid launch, and a dry-run command preserving exclusion flags. Budget refusals still require usable options.

Verification:

- Full suite under `unshare -rn`, fake keys: **446 passed, 1 skipped; exit 0**.
- Independent HTTP probe: **exit 0**; no new runs, tasks, API calls, or LLM calls.
- Diff checks passed. Source/tests unchanged.
- Live DB never opened for writes; SHA256 unchanged.
- Browser verification **UNPROVEN**: Chromium hit sandbox `setsockopt` denial. UI finding follows current source.

No other P1/P2 found.

[Full round-3 report](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abad2461e6efd9021/docs/build/REVIEW_v2_exclude_run_r3.md)