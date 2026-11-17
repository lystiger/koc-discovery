Overall FAIL

Reviewed branch `v2/video-rerank`, HEAD `18727db`, fix `f78c9e1..HEAD`, and complete diff `d1d1409..HEAD` against item 4 and A4 in `~/Projects/LysStack/projects/koc-discovery/v2_plan.md`. One new P2 remains open. The r3 P2 is closed. Source and tests were not modified.

**P2 OPEN — Symmetric folding promotes unrelated live videos for unaccented briefs.** `src/koc/video_select.py:52`, with `src/koc/video_select.py:36` retaining the unaccented brief ahead of its fold-equivalent configured phrase.

The new comparison accepts accented title words whenever the corresponding brief word is unaccented. The brief-first deduplication then removes the more precise configured spelling. This affects legitimate briefs with an explicit product type, using the actual phrases in `config/video_topics.yaml:8` and `config/video_topics.yaml:35`:

| Brief / product type | Live video | Title evidence | Before fix | HEAD |
|---|---|---|---|---|
| `chong nang` / `Chống nắng` | `7702522628208168200`, creator `7608428399555970055` | `Má chồng - Nàng dâu nhà em ko Drama...` | Score 0; rank 6; not analyzed | Score 1; rank 1; analyzed; `on_topic:true` |
| `rua mat` / `Làm sạch` | `7691582703367376149`, creator `6966250772758561794` | `Hướng dẫn tắm rửa mát lạnh x2 với chai sữa tắm gội CM24 2in1...` | Score 0; rank 10; not analyzed | Score 1; rank 1; analyzed; `on_topic:true` |

Both probes use the creator's complete ten cached candidates and the real configuration. They execute `_s3_creator(mock=False)` and persist its selection breakdown in temporary SQLite databases. A recording analyzer replaces the paid provider; fixture media prevents downloads. Replaying the selector from `f78c9e1` excludes both videos from the three analyzer calls. HEAD calls the analyzer for each unrelated video first. These are demonstrated paid-selection changes, not merely possible word collisions. No clearly on-topic alternative is established for either ten-video candidate set; the demonstrated defects are false relevance labels and changed selection priority.

Prefer the configured accented spelling when a brief phrase folds to that known phrase. Preserve the `sua tam` behavior for products outside the configured vocabulary. Verify both live collisions alongside the existing accent cases before closing this finding.

**Risk assessment using real inputs.** The fresh live DB contains 1,752 cached video/rank rows, 1,652 unique video IDs and 1,412 distinct titles. Comparing all 37 configured phrases against those videos produces **zero additional matches** from this fix when the phrases retain their configured spelling. Individual words such as `kem` can newly match `kèm` or `kém`, but their complete configured phrases produce no additions in this corpus.

Repeating the comparison with each configured phrase supplied as an unaccented brief produces seven additional term/video pairs across five videos. Manual inspection identifies the two unrelated examples above; the other three titles describe sunscreen or moisturizer with spelling differences. The observed scope is small and concentrated in unaccented briefs. It is still P2 because normal supported inputs change actual S3 selections and incorrectly classify unrelated videos. These corpus counts are not an estimated production error rate.

**R3 P2 CLOSED — `sua tam` now selects accented body wash.** Production `_s3_creator(mock=False)` receives three higher-revenue shampoos plus `Sữa tắm hương hoa`. At `f78c9e1`, the recording analyzer receives the three shampoos. At HEAD it receives body wash first, then two shampoos; body wash has score 1, `on_topic:true`, matched term `sua tam`.

**Earlier cases rechecked.**

| Case | Independent result |
|---|---|
| `kem dưỡng chống lão hóa, nâng cơ` | Score 0; remains off-topic for accented sunscreen brief |
| `chống nâng` | Score 0; remains off-topic for accented sunscreen brief |
| `kem chong nang cho da dầu` | Score 2; analyzed before higher-revenue shampoos |
| Budget-only change to 8M, 17M, 55M VND | Each fresh attempt: 27 cache hits, zero analyzer calls, zero paid rows, zero tokens, USD 0 |
| New reranked selection at those budgets | Read-only production cache lookup: 17 reusable, 10 misses for newly selected videos, unchanged across budgets |
| Identical-media IDs, unrelated-model preview, captured budget-free prompt | Existing regression tests pass in the complete suite |

For budget verification, the disk copy is opened with SQLite `mode=ro`. Each attempt starts from a separate in-memory backup of that same copy, before any legacy adoption. Production cache bookkeeping writes only to memory. Each creator receives the cached revenue-top-three candidates to isolate the budget change from the intentional video reselection. Historical S3 breakdowns do not contain `video_ids`, so these are replays of the old revenue rule rather than a claim of reading recorded selections. The analyzer raises if called; all 27 existing analyses are reused at each changed budget. Read-only availability checks for the newly reranked 27 videos run directly against the untouched disk copy.

**A4 live holdout.** Rio (`7450735628620760071`) has four title-matched candidates. The selected videos are `7695457484974099730`, `7698027306689809671`, `7701751823807466759`; all three describe sunscreen. The old shampoo selections are excluded. For `7234931025289217051`, all 100 cached titles were inspected: none establishes a sunscreen video. The selector still fills with Roopy, Kato Kato and Charmix deals, all marked off-topic. The conditional requirement “when an on-topic video exists” is not established there; actual video contents remain UNPROVEN.

**Commands and results.** Commands run from the reviewed worktree. Temporary probe scripts and logs are outside repository source and tests.

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-r4-fresh.db'
chmod 444 /tmp/koc-r4-fresh.db
git show f78c9e1:src/koc/video_select.py > /tmp/koc-r4-before.py

unshare -rn sh -c 'PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake GOOGLE_API_KEY=fake /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -u /tmp/koc-video-r4-independent.py'
# Exit 0. ALL_PROBES_PASS means all stated observations were reproduced,
# including the new P2; it does not mean the product passes review.

unshare -rn sh -c 'PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake /home/lystiger/Projects/KOC-Discovery/.venv/bin/python scripts/s3_rerank_preview.py --db /tmp/koc-r4-fresh.db --media-dir /home/lystiger/Projects/KOC-Discovery/data/media'
# Exit 0. 9 creators, 5 changed selections, 10 new analysis misses.

unshare -rn sh -c 'PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake GOOGLE_API_KEY=fake timeout 150 /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q'
# Exit 124. Hangs after 50 tests; unmodified full-suite invocation UNPROVEN here.

unshare -rn sh -c 'PYTHONPATH=src KALODATA_API_KEY=fake GEMINI_API_KEY=fake OPENROUTER_API_KEY=fake GOOGLE_API_KEY=fake timeout 180 /home/lystiger/Projects/KOC-Discovery/.venv/bin/python /tmp/koc-offline-suite.py'
# Exit 0. 484 passed, 1 skipped in 89.03s.

git diff --exit-code -- src tests config prompts scripts
# Exit 0. Review changed no tracked source, tests, configuration, prompts or scripts.
```

The temporary suite wrapper changes only asyncio's socket wakeup implementation from `socket.send()` to `os.write()` and runs `pytest -q` through `runpy`. An independent socketpair probe inside `unshare -rn` confirms `socket.send()` raises `PermissionError: [Errno 1] Operation not permitted`, while `os.write()` writes one byte. The wrapper does not skip tests or alter repository files. The ordinary invocation remains unverified in this sandbox despite the complete passing workaround run.

The read-only copy rejects `CREATE TABLE` with `attempt to write a readonly database`. Its SHA256 remains `0bb5d3eb4204c60f4e878f418d8165b31fa5fe033f91fd252c7f94a95e4c304c` after all probes. No live provider was called by the independent probes.

Evidence: `/tmp/koc-video-r4-independent.py`, `/tmp/koc-video-r4-independent.log`, `/tmp/koc-video-r4-preview.log`, `/tmp/koc-r4-suite-plain.log`, `/tmp/koc-r4-suite-workaround.log`, `/tmp/koc-offline-suite.py`.

No additional P1 or P3 findings. Existing untracked `docs/process/build/REVIEW_v2_video_rerank_r4.md` was left untouched; this separately named report records this independent review.
