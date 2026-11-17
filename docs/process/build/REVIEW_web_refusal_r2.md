Overall PASS

Independent review, round 2, of `947e388..2291a8d82267da5c76dde1579f8bfa93f333bb86` on `worktree-agent-a8ca40e33ea886ecc`, 2026-11-16. No open P1/P2 correctness findings. Both P2 findings in `docs/process/build/REVIEW_web_refusal.md` are CLOSED.

1. **CLOSED — P2: Web campaign costs omit the pipeline's three-video multiplier.**

   Locations: `src/koc/pricing.py:1`, `src/koc/pricing.py:14`, `src/koc/pipeline.py:320`, and `src/koc/web/matching_api.py:138`.

   Re-ran the original synthetic-database reproduction through `POST /api/campaigns`, with a completed legacy run and one scored creator at 20,000 followers. Count 1 and budget 1,000,000 VND now return `status="refused"`, no picks, and `min_budget_for_count={"budget_vnd":3000000}`. Resubmitting at 3,000,000 VND returns `status="ok"`, exactly one creator, total 3,000,000 VND, and zero leftover. With one creator at 150,000 followers and budget 1,000,000 VND, the minimum is now 15,000,000 VND; resubmitting that minimum succeeds. Both costs equal `pipeline._rate()` and `creator_cost()`.

2. **CLOSED — P2: Supported follower ranges outside the rate card hide an available cheaper band.**

   Location: `src/koc/web/matching_api.py:219`.

   Re-ran the original reproduction with scored creators at 500,000 and 20,000 followers. Count 1, budget 3,000,000 VND, and follower range 400,000–600,000 now return `status="refused"` and these options:

   ```json
   {
     "max_count_within_budget": null,
     "min_budget_for_count": {"budget_vnd": 15000000},
     "cheaper_follower_band": {
       "follower_min": 10000,
       "follower_max": 49999,
       "cost_vnd": 3000000
     }
   }
   ```

   Resubmitting the cheaper follower range succeeds with exactly one creator at the advertised 3,000,000 VND.

Backward compatibility was verified against an isolated backup of the production database. The original was accessed only by this command:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-review-r2/production.db'
chmod 444 /tmp/koc-review-r2/production.db
```

Direct compatibility probes opened the backup with `mode=ro&immutable=1`. Its SHA-256 is `a8a4f7c10ba666f21ebe544e582fe663466bcadc82d28461ba6a407d9fc07a76`. Cache-only execution used an in-memory derivative; campaign POSTs used a separate disposable database copied from the read-only backup. No source files or existing reports were modified.

For run `7372009b22764b339fbcf0f3efb4bc4e`, `_best_five()` at both `947e388` and HEAD exactly matched the stored S4 ranks and costs:

```text
rank  creator_id           cost_vnd
1     7485602050560148487   3000000
2     7234931025289217051   3000000
3     7594293671543079957   7500000
4     7450735628620760071   7500000
5     6730533371858437121   7500000
Total                     28500000
```

The real `_s4()` code generated identical five LLM cache keys at both revisions. The read-only probe intercepted only `_cached_call()` to capture each generated key and load its cached Recommendation without writing cache-hit logs. Each key also matched the production snapshot's `run_results`/`llm_calls` record. Both probe JSON files have SHA-256 `c5f7e38ecf499e10bfee59cfc7a62d10e316a4f1e2dbfd7599a8958ea5b0ea2e`. Direct read-only connections reported zero changes. A separate unmodified `_s4(cache_only=True)` call and its returned writer completed on the in-memory derivative, retaining the 28,500,000 VND total.

`POST /api/campaigns` on the disposable production-copy derivative, with product type `Chống nắng`, budget 30,000,000 VND, count 5, and default follower/target/MCN settings, returned `status="ok"`, the same five creators in the same order, total 28,500,000 VND, and leftover 1,500,000 VND. Its `run_id` was `7372009b22764b339fbcf0f3efb4bc4e`; GET of the stored campaign returned the identical result.

Additional executed checks:

- Shared pricing: tested followers 0, 5,000, 9,999, 10,000, 49,999, 50,000, 99,999, 100,000, 300,000, 300,001, 500,000, and 1,000,000,000. `creator_cost()`, `pipeline._rate()`, web `_estimated_cost()`, and adapter finalist estimates agreed and remained positive. S4 minimum-budget options agreed with those costs. CLI precheck rejected 2,999,999 VND and accepted 3,000,000 VND for one creator. The shared three-video multiplier also serves `brief.cheapest_tier()` and `brief.s4_options()` (`src/koc/brief.py:42`, `src/koc/brief.py:81`); the adapter retains stored recommendation costs and uses `creator_cost()` for new estimates (`src/koc/web/adapter.py:299`).
- Product isolation: a completed Serum run remained the only pool used for Serum after adding a newer completed Chống nắng run and a newer unfinished Serum run. A request for Trang điểm returned `needs_run`, no picks, and no run ID. The suite also verified that runs without a stored product type count as Chống nắng, and unfinished runs do not satisfy the completed-run requirement (`src/koc/web/matching_api.py:142`, `src/koc/web/matching_api.py:278`).
- Generated commands: all 270 combinations of six product types, three genders, and 15 contiguous age selections passed the real Typer CLI parser. Captured CLI briefs matched product type, category IDs, gender, age bounds, budget, and count. This includes 55+ mapping to 55–99 and `Tất cả` mapping to `tat-ca`. Khác used the literal `<id>` category placeholder and its replacement note. Budget precheck notes matched the real CLI refusal; custom follower ranges produced the explicit pipeline-filter note (`src/koc/web/matching_api.py:239`).
- Shell quoting: four product-spec payloads covered apostrophes, command substitution, backticks, semicolons, newlines, double quotes, backslashes, and an option-looking `--mock` value. POSIX-shell tokenization preserved each product value literally, the CLI accepted it, and the injection sentinel was never created.
- Legacy normalization: a stored row without status loaded as `ok`, retained its original picks and singular warning, added the warnings list, and computed leftover from stored input budget. The stored JSON and caller's original dictionary stayed unchanged (`src/koc/web/matching_api.py:269`, `src/koc/web/api.py:289`).
- Refusal and option regression checks: an exhaustive-combination oracle passed 800 deterministic cases covering empty pools, N=1, shortages, MCN conflicts, both MCN settings, and pools exceeding 15 creators. Successful plans contained exactly N creators within budget; refusals contained no picks, a warnings list, all three nullable options, zero cost, and full budget as leftover. Maximum-count and minimum-budget options matched the oracle. Across 200 real campaign requests, all 123 advertised options resubmitted successfully with the advertised count and cost. A separate 16-creator case confirmed that options respect the same top-15 and MCN restrictions as selection (`src/koc/web/matching.py:72`).

The full suite completed with **418 passed in 87.06s**, with no skips. This included the production-copy integration test, enabled explicitly through `KOC_REAL_RUN_COPY`:

```bash
KOC_REVIEW_POLL_LOOP=1 PYTHONDONTWRITEBYTECODE=1 \
PYTEST_ADDOPTS='-p no:cacheprovider' \
KOC_REAL_RUN_COPY=/tmp/koc-review-r2/production.db \
PYTHONPATH=/tmp/koc-review-r2:src \
/home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

`/tmp/koc-review-r2/sitecustomize.py` blocked socket connections, datagram sends, and DNS resolution. It rejected Python SQLite access to the original database and preserved these guards when subprocesses supplied replacement environments. Guard probes confirmed blocked networking in the parent and an explicit-environment child. Bytecode and pytest cache writes were disabled. The suite used the previous review's sandbox scheduling workaround: selector waits were capped at 10 ms by the external `sitecustomize.py`. Execution without this scheduling workaround remains UNPROVEN in this sandbox; no repository code was changed for it.

Reproduction scripts and captured evidence are available locally:

```text
/tmp/koc-review-r2/sitecustomize.py
/tmp/koc-review-r2/probe.py
/tmp/koc-review-r2/probe.log
/tmp/koc-review-r2/edges.py
/tmp/koc-review-r2/edges.log
/tmp/koc-review-r2/compat.py
/tmp/koc-review-r2/compat-base.json
/tmp/koc-review-r2/compat-head.json
/tmp/koc-review-r2/compat-base.log
/tmp/koc-review-r2/compat-head.log
/tmp/koc-review-r2/full-suite-guarded.log
```

Run the probes with the suite's guarded environment, replacing `-m pytest -q tests` with the script path. `compat.py` takes a label (`base` or `head`); the baseline uses the archived `947e388` source at `/tmp/koc-review-r2/base` and its `src` on PYTHONPATH. `edges.py` also reads the previous review's `/tmp/koc-refusal-review/probe.py` to rerun its independent oracle. The backup hash remained unchanged after all checks. Final repository status contained only the new `docs/process/build/REVIEW_web_refusal_r2.md` report.
