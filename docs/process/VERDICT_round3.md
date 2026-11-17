# Phase 0 independent TEST review — round 3

Reviewed 2026-11-15 at `de4a34b`. **Overall: FAIL (A5).** No network used. Only `docs/process/VERDICT.md` created by this review.

| Criterion | Verdict | Evidence |
|---|---|---|
| A1 | PASS | `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/pytest -q`: **22 passed in 0.03s**. |
| A2–A4, A6–A8 | PASS (carried over) | `docs/process/VERDICT_round2.md`. Inspected `git diff f59fc38..HEAD`: only `docs/research/FACTS.md:65` and capture-script argument forwarding changed (3 insertions, 2 deletions). Normalization, DB, CLI, fixtures, immutable reports and media metadata remain unchanged. No regression found; tests pass. This is a scope-based carryover, not a repeat of every round-2 audit. |
| A5 | FAIL | All ten answers use allowed status labels and cite evidence, but documentation consistency still fails as detailed below. |

## Both round-2 fixes confirmed

- **Visit-cap reconciliation: PASS.** `docs/research/FACTS.md:65` now identifies the same trial account and observed 10-detail-visits/day cap, consistent with `docs/research/FACTS.md:13`, `README.md:70` and `docs/research/FEASIBILITY.md:113`. Paid-plan relief remains explicitly unverified in FACTS.
- **Custom CDP endpoint: PASS.** `scripts/capture_creator.py:99-100` parses and forwards `--cdp`. Offline execution of the actual entry-point AST with a recording replacement for `main` passed three cases: defaults, custom endpoint with `--videos`, and reversed option order. No browser connection or output file was needed. README usage (`:40`) and script docstring (`:6`) now match.

## A5 evidence coverage

Read README, every `docs/*.md`, both script docstrings and implementations, and referenced reports/code.

| Questions | Traceability result |
|---|---|
| Q1–Q3 | `docs/research/feasibility.json`, sample exports, FACTS Methods 2–3/API probe and DATA_DICTIONARY parity table support field availability and rounded-versus-precise values. Independently checked immutable API evidence: six HTTP-200/success records, 31 fields each. Audience claim is scoped to the three-creator sample. |
| Q4 | FACTS Method 5 and capture-script URL construction support six derived TikTok links and one downloaded MP4; URL resolution and API video download remain unverified. |
| Q5–Q6 | Media report/analysis JSON and FACTS media/ASR entries support preprocessing, blocked transcription, missing fields and disclosed visual-analysis error. Historical provenance/status statements are explicitly superseded by FACTS `:72`; FEASIBILITY and MEDIA_FEASIBILITY explicitly reject the old static-pouch claim. |
| Q7 | FACTS Methods 1–5 and scripts support the methods inventory. Terms and bulk-use entitlement remain unverified. |
| Q8 | FACTS `:61-62`, immutable API records and media reports support the observed seven-call run and unmeasured inference cost. Script docstring contradicts the call total (finding 1). |
| Q9 | FACTS resume entry, `tests/test_db.py:39,56`, `db.py` and CLI support the qualified answer, including absent crash harness and no failed-task retry. |
| Q10 | Scoped GO, unmeasured duration/throughput and trial arithmetic are disclosed. Paid-plan relief is asserted beyond the evidence (finding 2). |

## Required fixes

1. **Correct API call-count documentation.** `scripts/api_probe.py:1` advertises a hard cap of six calls (~0.6 credit), contradicting `README.md:55`, FACTS `:61` and FEASIBILITY `:92` (seven observed calls). `MAX_CALLS` limits only the probe loop (`:49-58`); discovery (`:31-37,47`) adds requests. Offline execution with mocked HTTP and file writes confirmed **one discovery + six probes = seven**. Document six probe calls plus discovery: zero discovery calls with an explicit header, one in the observed run, up to six candidate attempts otherwise. Clarify README's seven-call statement as the observed/first-candidate case. No live API test is required.
2. **Qualify paid-plan relief.** `docs/research/FEASIBILITY.md:113` says “A paid plan would change this,” while revised `docs/research/FACTS.md:65` explicitly says whether paid membership lifts the cap is UNVERIFIED. Mark the effect on the cap unverified, alongside price; do not present relief as established.

Both requested fixes pass, but A5 requires consistency across the full documentation surface. The remaining contradictions prevent an overall PASS.
