Overall PASS

Reviewed `v2/video-rerank` at `e93d2d0`: incremental `059e3bc..HEAD` and complete `d1d1409..HEAD`, against r5’s canonical-accent rule and plan item 4/A4. **No P1/P2 remain open.** Source and tests unchanged.

**P3 — Mixed-accent hashtags can lose valid matches.** [src/koc/video_select.py:96](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/video_select.py:96) checks whether the entire hashtag lacks accents. Consequently, `#kemchongnắng` and `#kemchongnangchodaDầu` both score zero for sunscreen. Production `_s3_creator(mock=False)` probes supply one such sunscreen video and three higher-revenue shampoos:

| Revision | Analyzer receives |
|---|---|
| `059e3bc` | Sunscreen, shampoo0, shampoo1 |
| HEAD | shampoo0, shampoo1, shampoo2 |

Apply canonical accent comparison to the matched phrase’s constituent words, without letting accented suffixes disable matching. Preserve rejection of r5’s lookalikes. **Crafted-only P3:** no corresponding mismatch appeared in the live corpus. [Reproducer](/tmp/koc-r6-mixed-hashtag.py), [output](/tmp/koc-r6-mixed-hashtag.log).

**R5 P2 closed.** Recreated `/tmp/koc-r5-canonical.py` against `/tmp/r6.db`, changing its assertions to require closure. For `#chồngnàng`, `#chốngnâng` and `#rửamát`, production S3 now analyzes all three legitimate on-topic alternatives. The unrelated revenue-999 video is excluded.

**Live corpus and earlier regressions pass.**

- Fresh corpus: **1,752 rows, 1,652 unique videos, 1,412 distinct titles**.
- Independent canonical oracle: **zero differences across 37 configured terms × 1,652 videos**.
- All 37 unaccented configured briefs retain canonical configured spellings and strict matching.
- R4’s live `chồng - Nàng` and `rửa mát` videos score zero and remain excluded from analyzer calls.
- `sua tam` still selects accented body wash. Mixed-accent sunscreen prose still outranks shampoo. `nâng cơ` and `chống nâng` remain off-topic.

**Budget-only reruns: zero analyzer calls.** Separate in-memory clones of the fresh read-only copy tested budgets **8M, 17M and 55M VND**. Each reused **27 analyses**, with **0 analyzer calls, 0 paid calls, 0 tokens and USD 0**. The analyzer raises if invoked.

These checks hold video candidates fixed to isolate budget changes. Intentional reranking separately yields **17 reusable analyses and 10 misses**, unchanged across budgets. Budget remains absent from the content prompt and current content cache key.

**A4 holdout:** Rio selects sunscreen videos `7695457484974099730`, `7698027306689809671` and `7701751823807466759`; shampoo selections are excluded. For creator `7234931025289217051`, none of the 100 inspected cached titles establishes a sunscreen alternative. Its three deals remain explicitly off-topic. The conditional holdout’s video-content portion remains **UNPROVEN**.

**Commands and results.** Fresh copy:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/r6.db'
chmod 444 /tmp/r6.db
```

All Python executions used `unshare -rn`, `PYTHONPATH=src`, and fake Kalodata, Gemini, OpenRouter and Google keys.

| Command/artifact | Result |
|---|---|
| `/tmp/koc-r6-canonical.py` | Exit 0; canonical corpus checks and r5 closure pass |
| `/tmp/koc-video-r6-independent.py` | Exit 0; adapted r4 corpus, production, holdout and budget probes pass |
| `/tmp/koc-r6-mixed-hashtag.py` | Exit 0; P3 reproduced |
| `scripts/s3_rerank_preview.py --db /tmp/r6.db --media-dir /home/lystiger/Projects/KOC-Discovery/data/media` | Exit 0; 9 creators, 5 changed selections, 10 analysis misses |
| `timeout 140 …/python -m pytest -q` | Exit 124; stalls after 50 tests |
| `timeout 180 …/python /tmp/koc-offline-suite.py` | Exit 0; **496 passed, 1 skipped in 87.66s** |
| Tracked source/test/config/prompt/script diffs, staged and unstaged | Exit 0; unchanged |

The temporary suite wrapper replaces only asyncio’s socket wakeup with `os.write()`. Independent verification confirms `socket.send()` raises `EPERM`, while `os.write()` succeeds. No tests were modified or additionally skipped. Ordinary invocation remains **UNPROVEN in this sandbox**.

The copy rejects writes; its SHA256 remained:

```text
0bb5d3eb4204c60f4e878f418d8165b31fa5fe033f91fd252c7f94a95e4c304c
```

Evidence: [canonical results](/tmp/koc-r6-canonical.log), [production and budget results](/tmp/koc-video-r6-independent.log), [preview](/tmp/koc-r6-preview.log), [complete suite](/tmp/koc-r6-suite-workaround.log).