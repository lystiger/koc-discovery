Overall PASS

- **P2 r3 CLOSED** at [matching_api.py:310](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abad2461e6efd9021/src/koc/web/matching_api.py:310). Independent HTTP probe: two creators, 15M VND budget, 30M minimum, exclusion outside band. Result remains `refused`, preserving warnings and all options.
- Same probe reproduces r3 on `821b55e`; passes on HEAD.
- No new P1/P2/P3 findings. No P1/P2 open.
- Full suite under `unshare -rn`, fake keys: **447 passed, 1 skipped; exit 0**.
- Independent HTTP and pipeline probes: **exit 0**. Source/tests unchanged. Live DB never opened for writes; SHA256 unchanged.

[Full report and commands](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abad2461e6efd9021/docs/build/REVIEW_v2_exclude_run_r4.md). React checkbox remains separate web scope.