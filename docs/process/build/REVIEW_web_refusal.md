Overall FAIL

Independent review of `8fbef7e..69d6bcd2dea6e5d584a6ef07461590f8ec95b0d1` on `worktree-agent-a8ca40e33ea886ecc`, 2026-11-16. Two P2 correctness findings. No P1 findings.

1. **P2: Web campaign costs omit the pipeline's three-video multiplier.**

   Location: `src/koc/web/matching_api.py:138`, consumed at `src/koc/web/matching_api.py:176` and `src/koc/web/matching_api.py:188`. The new minimum-budget option uses those costs at `src/koc/web/matching.py:107`. Compare `src/koc/pipeline.py:317` and `src/koc/pipeline.py:320`.

   `_estimated_cost()` returns one `vnd_per_video`. The pipeline's `_rate()` returns `vnd_per_video * 3`. The configured rates are 1,000,000, 2,500,000, and 5,000,000 VND per video in `config/rate_card.yaml:4` through line 12.

   Reproduction: Create a temporary database with one scored creator at 20,000 followers. Submit a campaign with count 1 and budget 1,000,000 VND. The endpoint returns `status="ok"`, one creator, `total_cost_vnd=1000000`, and `leftover_vnd=0`. `_rate(20000)` returns `3000000` for the same creator. The web approves a plan that exceeds that budget under the pipeline's pricing model.

   A second reproduction uses one scored creator at 150,000 followers and budget 1,000,000 VND. The refusal advertises `min_budget_for_count={"budget_vnd":5000000}`. `_rate(150000)` returns `15000000`. Increasing the budget to the web's advertised minimum still does not cover the pipeline's recommendation. Totals, leftover, and alternative costs inherit the same discrepancy.

   The pricing discrepancy predates this diff, but the new refusal options expose it as a minimum-budget recommendation. This is P2 under the requested pricing-consistency criterion. Use the same three-video rate model for web selections and all options.

2. **P2: Supported follower ranges outside the rate card hide an available cheaper band.**

   Location: `src/koc/web/matching_api.py:207` through line 209. Compare the nearest-tier fallback at `src/koc/web/matching_api.py:133` through line 138 and the unrestricted upper follower bound at `src/koc/web/api.py:38`.

   Reproduction: Create a temporary database with two scored creators, at 500,000 and 20,000 followers. Submit count 1, budget 3,000,000 VND, and follower range 400,000 through 600,000. The endpoint refuses with these options:

   ```json
   {
     "max_count_within_budget": null,
     "min_budget_for_count": {"budget_vnd": 5000000},
     "cheaper_follower_band": null
   }
   ```

   Resubmit the same campaign with follower range 10,000 through 49,999. The endpoint returns `status="ok"`, exactly one creator, and `total_cost_vnd=1000000`. The cheaper option is valid, costs less than the original 5,000,000 VND minimum, and fits the budget. It remains affordable at 3,000,000 VND after correcting finding 1.

   `_cheaper_band()` returns early because no configured tier overlaps the original range. However, `get_pool()` supports that range and prices its creator using the nearest tier. The UI hides a valid recovery choice because the API returns null. Derive the comparison cost using the same fallback as creator pricing before searching cheaper tiers.

Verification used only temporary synthetic databases. No production database was opened or copied. Source files and tests were not modified.

The full suite completed with **368 passed, 1 skipped in 74.83s**. The skipped test was `tests/web/test_api.py::test_real_run_copy_proposal_totals_and_evidence`, because its optional real-run copy was absent. The command was:

```bash
KOC_REVIEW_POLL_LOOP=1 PYTHONDONTWRITEBYTECODE=1 \
PYTEST_ADDOPTS='-p no:cacheprovider' \
PYTHONPATH=/tmp/koc-refusal-review:src \
/home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

`/tmp/koc-refusal-review/sitecustomize.py` blocked socket connections and DNS resolution. It also rejected SQLite connections to the production database and preserved those guards in Python subprocesses. Bytecode and pytest cache writes were disabled.

The first suite attempt stalled at the first TestClient request. A separate minimal request reproduced the stall. Its traceback showed the event-loop thread in `selectors.select` and the caller waiting in AnyIO's `run_sync_from_thread`. The temporary `KOC_REVIEW_POLL_LOOP` workaround limits selector waits to 10 ms. With that workaround, the minimal request and the full suite completed. This changes only test-process scheduling. The suite without this workaround remains UNPROVEN in this sandbox.

Additional executed checks:

- An independent exhaustive-combination oracle passed 800 deterministic cases. It covered N=1, empty pools, pools smaller than N, MCN conflicts, both MCN settings, and pools exceeding the top-15 cutoff. Successful results had exactly N creators, correct totals, and nonnegative leftover. Refusals had no picks. Maximum-count and minimum-budget options matched the oracle.
- Real `POST /api/campaigns` and `GET /api/campaigns/{id}` calls preserved results across storage. All 78 offered options exercised by the probe resubmitted successfully with the advertised count and cost. The probe covered several follower ranges, budgets, counts, and MCN settings. Finding 2 concerns a missing option, rather than an offered option that fails.
- A separate top-15 case used 15 higher-ranked creators sharing one MCN and a lower-ranked creator from another MCN. Matching refused N=2 and returned a maximum count of 1 with no minimum-budget option. Options respected the same top-15 restriction as selection.
- Existing exact-budget tests passed, including zero leftover. Legacy normalization retained the singular warning, added its warnings list, defaulted missing status to `ok`, and computed leftover from the stored input budget without mutating the original result. Legacy rows intentionally remain `ok` under the requested compatibility rule.
- The response contract matches `ui/readability:docs/process/build/FIX_budget_refuse.md` at `633bdececa5b6094bef2c2db5cbdab6d44551bd0`. Refusals contain `status`, `picks=[]`, `warnings`, and all three nullable options. They also retain `picked=[]` for existing consumers. Successful responses retain the existing `picked` field and add `status`, `budget_vnd`, and `leftover_vnd`. The singular option keys `follower_min` and `follower_max` match the contract. Browser rendering of the separate frontend work was not tested.

Reproduction scripts and captured output from this review are available locally:

```text
/tmp/koc-refusal-review/sitecustomize.py
/tmp/koc-refusal-review/probe.py
/tmp/koc-refusal-review/probe-poll.log
/tmp/koc-refusal-review/edge_probe.py
/tmp/koc-refusal-review/edge-probe.log
/tmp/koc-refusal-review/full-suite-poll.log
```

The probes run with the same environment as the suite, replacing `-m pytest -q tests` with the script path. Each probe creates its own database under `/tmp`.
