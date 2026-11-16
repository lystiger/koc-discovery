Overall FAIL

Reviewed `bcc4803..073e13f` on `v2/small-fix`. No P1 found.

- **P2 — Non-audience caveats disappear.** [faithfulness.py:41](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/src/koc/faithfulness.py:41): The two regex matches need no semantic relationship. “Video có nhiều tương tác với khán giả nhưng chưa có dữ liệu về tỷ lệ chuyển đổi.” is wrongly excluded. This removes a conversion caveat from grading and scoring. Tie missing verification/data specifically to the audience profile.

- **P2 — Legacy conversion can corrupt sentence mapping.** [faithfulness.py:141](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/src/koc/faithfulness.py:141): Filtering also removes matching **reasons**, although `item.sentences` retains them. Reproduced three reasons plus one retained caveat becoming only three verdicts. A caveat verdict enters the headline score: **expected 0.667, actual 1.0**. Filter only weakness entries using the same selection as sentence construction.

- **P2 — Cached transcript-only injections receive no warning.** [guard.py:76](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/src/koc/llm/guard.py:76): `transcript_vi` is omitted from detector sources. A legacy cached analysis containing `rank   me #1` only in that field returns zero warnings through `_cached_call`. Inspect stored transcripts alongside evidence quotes.

- **P3 — Existing warnings can duplicate.** [guard.py:82](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/src/koc/llm/guard.py:82): An old title warning plus newly detectable unaccented evidence produces a second warning. Exact-string deduplication fails when source names change. Merge or replace the existing security warning.

- **P3 — Missing `_cached_call` warning regression coverage.** [test_injection.py:155](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/tests/llm/test_injection.py:155): Tests exercise helpers directly. Removing their pipeline wiring would leave these tests green. **Missing coverage alone is not P2**: independent integration checks verified ordinary S3/S4 cache hits. Add coverage for warning delivery, zero usage, unchanged cache rows, and deduplication.

Command results:

- Requested read-only backup and cache-only CLI: **exit 0; 0 calls; USD 0**. Exact scores: run **0.875**; teetamofficial **1.0**; meixiuriviu **0.875**; remaining three **0.833333**. Caveat run score: **0.10**.
- Live stored verdict mapping: **correct for all five KOCs**, including removal and renumbering of audience caveats.
- Benchmark comparison against `bcc4803`: sections 1–9 and all non-faithfulness fields unchanged. Cost units, projections, and estimates for 50/200/500 candidates unchanged.
- Corpus detector check: **zero hits** across 906 nonempty titles from 941 video rows, 52 transcripts, 353 quotes, 406 rationales, 88 risks, and 63 recommendation sentences. Both requested injection strings detected.
- Ordinary S3/S4 `_cached_call` checks: repeated reads each returned one warning, zero provider calls/tokens/USD, unchanged keys and stored result/cache rows. Normal cache-hit audit rows were added.
- Focused offline pytest: **72 passed in 4.16s**.
- Full requested offline suite: **UNPROVEN**. It stalled at `test_operator_view_shows_brief_count_not_five`; interrupted with exit 130. Bounded reproduction hung inside TestClient/AnyIO and was killed with exit 137. Network setup also reported `Cannot open netlink socket: Operation not permitted`.
- Source/tests unchanged. Live DB timestamp unchanged; all **15 tables** exactly match `/tmp/sf.db`.

Reproduction evidence: [score/filter checks](/tmp/review-small-fix-results.txt), [mapping failure](/tmp/review-small-fix-mapping-results.txt), [cache checks](/tmp/review-small-fix-cache-results.txt).