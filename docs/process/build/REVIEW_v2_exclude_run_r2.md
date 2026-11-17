Overall FAIL

- **P2 OPEN — HTTP ignores exclusions when a matching finished run exists.** `src/koc/web/matching_api.py:285` enters cached matching; `get_pool` at `:171` never applies `exclude_run_ids`. Independent HTTP probe returned `200`, status `ok`, and the same five excluded creators: `1, 10, 11, 12, 13`. Exclusions were saved, but no rerun command appeared. Apply exclusions before matching or return `needs_run` with the exclusion flags. The new HTTP test at `tests/web/test_matching_api.py:145` only covers a missing product type.

- **r1 P2 HTTP field/command wiring — CLOSED.** `src/koc/web/api.py:43` accepts and preserves IDs; `src/koc/web/matching_api.py:261` appends quoted flags. Independent HTTP POST/GET confirmed persistence and command generation for `needs_run`. React checkbox excluded from this review.

- **r1 P2 top-five restriction — CLOSED under clarified V2-2.** `src/koc/pipeline.py:41` resolves all final recommendations. `tests/core/test_exclude_run.py:91` verifies ten picks leave both the next S1 pool and final selection.

Reviewed fixes `89afe86..ab2b7d3` and full diff `0f5c03e..HEAD`. No additional P1/P2 found.

Verification:

```bash
unshare -rn env \
  PYTHONPATH=/tmp/koc-review-runtime:src \
  KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q
```

- **444 passed, 1 skipped in 79.30s; exit 0.**
- Runtime shim replaces asyncio wakeup `socket.send()` with `os.write`; network isolation remains active.
- Independent probe `/tmp/koc-exclude-r2-probe.py`: exit 0; reproduced HTTP defect and verified pipeline exclusion.
- `git diff --check 0f5c03e..HEAD`: exit 0.
- Source/tests unchanged. Live `data/koc.db` never opened for writes; SHA256 unchanged.