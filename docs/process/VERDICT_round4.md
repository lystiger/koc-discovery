# Phase 0 independent TEST review — round 4

Reviewed offline at `9f7caa1953574be024a3540be26e1809b23fbc4e`. **Overall: FAIL (A5).** Only `docs/process/VERDICT.md` created. No network used.

| Criterion | Verdict | Evidence |
|---|---|---|
| A1 | PASS | `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/pytest -q`: **22 passed in 0.04s**. |
| A2 | PASS | Carried over from rounds 2–3: normalized data and provenance unchanged. |
| A3 | PASS | Carried over: DB, checkpoint and resume implementation unchanged. |
| A4 | PASS | Carried over: CLI and dry-run implementation unchanged. Documentation defects below do not invalidate earlier behavioral checks. |
| A5 | FAIL | Exhaustive documentation sweep completed; required corrections below. |
| A6 | PASS | Carried over: required artifacts remain present; report and exports unchanged. |
| A7 | PASS | Carried over: diff contains only three documentation lines, without credentials or contact data. |
| A8 | PASS | Carried over: media artifacts, metadata and cost disclosures unchanged. |

Carryover basis: inspected complete `git diff de4a34b..HEAD`: only `README.md:55`, `docs/research/FEASIBILITY.md:113`, and the module docstring at `scripts/api_probe.py:1` changed. Earlier evidence: `docs/process/VERDICT_round2.md` and `docs/process/VERDICT_round3.md`.

## Round-3 fixes confirmed

1. **PASS — call count.** `README.md:55` and `scripts/api_probe.py:1` now distinguish six probe calls from zero discovery calls with an explicit header, otherwise one to six discovery attempts. This matches `api_probe.py:22-23,31-37,44-58`. The observed seven-call run remains supported by `docs/research/FACTS.md:61-62` and six saved HTTP-200/success responses, each containing 31 fields.
2. **PASS — paid-plan relief.** `docs/research/FEASIBILITY.md:113` now marks both relief from the visit cap and paid-plan price UNVERIFIED, consistent with `docs/research/FACTS.md:65`.

## A5 sweep and all required fixes

Read every line of `README.md`, all six `docs/*.md`, both complete `scripts/*.py` (including every docstring), and `docs/research/feasibility.json` including all ten conclusions. Cross-checked CLI code, immutable API evidence and media reports/analysis. All ten answers have allowed status labels and evidence references. Historical provenance/status statements are explicitly superseded by FACTS line 72; the static-pouch error is explicitly rejected. These are not additional failures.

1. **Remove the unconditional no-overwrite guarantee.** `README.md:56`, `scripts/api_probe.py:6-7`, and `docs/research/FACTS.md:71` promise a new file per run. `api_probe.py:42` uses second-resolution timestamps; lines 70 and 72 open with `"w"`. Offline execution of actual `main()` twice with a fixed clock, mocked HTTP and an in-memory file sink produced two writes to **`reports/api_probe_20261115T000000Z.json`, mode `w`**. Same-second runs can overwrite. Qualify documentation or provide collision-safe writes; preserve the historical evidence file.
2. **Correct CLI behavior descriptions.** `README.md:29` says ordinary `kalodata media test` lists videos. Actual invocation against the populated DB (six videos) exited 0 and printed only `media tests are run by Agy; record results with \`media record FILE\``. Only `--dry-run` lists IDs (`cli.py:176-180`). Also `README.md:33` says every command opening a DB creates tables, but this command calls `db.connect` directly and queries without `init_db` (`cli.py:170-175`). Document both exceptions. Product behavior need not change.
3. **Limit visual verification claims to checked frames.** `docs/research/MEDIA_FEASIBILITY.md:23` presents appearances over **0–24.57 s** as VERIFIED using only frames 1, 4, 8 and 12. Line 25 similarly marks text “shown across the clip” VERIFIED. `docs/research/FACTS.md:57` supports four spot checks; `docs/research/FEASIBILITY.md:70` explicitly marks the other eight frames UNVERIFIED. Distinguish Agy's full-clip assertions from independently verified sampled observations, or supply a complete check. Keep the existing pouch-error disclosure and qualified CTA finding.
4. **Correct API cost-control guidance.** `docs/research/RISKS.md:22` recommends `--dry-run` for API cost overrun. `scripts/api_probe.py:41-79` has no dry-run argument handling and sends requests regardless of that token. CLI dry-runs cover offline intake/media selection (`cli.py:102,111-113,176-179`), not API calls. Remove or explicitly scope this advice; describe the actual probe/discovery caps now documented in README.

`docs/research/feasibility.json` conclusions remain consistent with the qualified feasibility answers; no additional required correction found there. No live API, browser capture, ASR or scale claims were re-tested.
