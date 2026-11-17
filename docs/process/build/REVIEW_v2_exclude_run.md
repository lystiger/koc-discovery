Overall FAIL

- **P2 — `src/koc/web/matching_api.py:261`, `src/koc/web/api.py:33`, `web/src/ui/pages.tsx:380`: Web exclusion is unreachable.** `CampaignInput` discards `exclude_run_ids`; the required checkbox is absent. Reproduced HTTP POST with `exclude_run_ids=["abc123"]`: HTTP 200, saved input loses exclusions, generated command contains no `--exclude-run`. Wire the field through API and UI; test through HTTP.

- **P2 — `src/koc/pipeline.py:41`: Excludes every recommendation, exceeding V2-2’s top-five rule.** After a supported `--count 10` run, exclusion removes all ten creators, including ranks 6–10. Reproduced: 30 candidates become 20 rather than 25. Select recommendations using `ORDER BY rank LIMIT 5`; cover this case.

Verification:

- Full offline suite: **437 passed, 1 skipped in 77.69s**, exit 0.
- Used `unshare -rn env … python -m pytest -q` with fake `KALODATA_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`.
- Direct run stalled because sandbox blocks `socket.send()`. Successful rerun used `/tmp/koc-review-runtime/sitecustomize.py`, replacing asyncio’s wakeup send with `os.write`.
- Independent probes passed: S1/pick exclusions, union exclusions, changed cache identity, zero-cost plain/repeated reruns, invalid IDs without added run/API/LLM rows, interrupted resume at S0/S1b/S3, shell quoting, Vietnamese errors.
- Live DB copy: 55 S1 creators, previous five absent, zero spend. Final selection remained blocked; live-copy picks are **UNPROVEN**.
- Core tests exercise pipeline behavior. Command-generation test bypasses HTTP, missing the first finding.

Source/tests unchanged. Live `data/koc.db` opened read-only; SHA256 unchanged.