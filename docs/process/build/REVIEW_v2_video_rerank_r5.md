Overall FAIL

Reviewed `v2/video-rerank` at `ca71ffd`: `60b9276..HEAD` and complete `d1d1409..HEAD`, against the orchestrator rule and plan item 4/A4. Source and tests unchanged.

**P2 OPEN — [src/koc/video_select.py:93](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/video_select.py:93): hashtag matching bypasses canonical accent checks.**

The hashtag fallback always folds accented text, regardless of `_Term.loose`. Consequently:

| Configured canonical term | Incorrectly accepted hashtag |
|---|---|
| `chống nắng` | `#chồngnàng` |
| `chống nắng` | `#chốngnâng` |
| `rửa mặt` | `#rửamát` |

Each produces `score:1`, `on_topic:true`.

Independent production probes execute `_s3_creator(mock=False)` with fixture media and a recording analyzer. Each creator has three valid on-topic videos, revenue 3/2/1, plus one unrelated hashtag video, revenue 999.

All three probes select `[unrelated, on0, on1]`, dropping `on2`. This violates A4 even when three on-topic alternatives exist. These are crafted reproductions; no corresponding violation appeared in the live corpus.

Apply canonical accent checks to hashtag matching. Preserve unaccented hashtag support and restrict loose matching to fallback brief terms.

Evidence: [probe script](/tmp/koc-r5-canonical.py), [complete output](/tmp/koc-r5-canonical.log).

No additional P1/P2 or P3 findings.

**R4 finding closed for both live examples.**

Fresh-copy production probes compare `60b9276` with HEAD using each creator’s complete cached candidate set:

| Brief | Live video | HEAD result |
|---|---|---|
| `chong nang` / `Chống nắng` | `7702522628208168200`, “chồng - Nàng” | Score 0; off-topic; excluded from analyzer calls |
| `rua mat` / `Làm sạch` | `7691582703367376149`, “rửa mát” | Score 0; off-topic; excluded from analyzer calls |

Both were selected first at `60b9276`.

The live corpus contains **1,752 rows, 1,652 unique videos and 1,412 distinct titles**. An independent canonical matcher found **zero differences across all 37 configured terms and 1,652 videos**. All 37 configured phrases supplied as unaccented briefs retained their category’s canonical spellings and strict matching.

**Requested regression probes pass.**

| Case | Production result |
|---|---|
| `sua tam`, type `Khác` | `Sữa tắm hương hoa` selected before higher-revenue shampoos |
| `kem dưỡng chống lão hóa, nâng cơ` | Score 0; excluded |
| `chống nâng` without hashtag | Score 0; excluded |
| `kem chong nang cho da dầu` | Score 2; selected before shampoos |

Configured spelling wins deduplication. Accented brief products remain eligible terms.

**Budget-only reruns pass: zero analyzer calls.**

Each attempt starts from a separate in-memory clone of the untouched read-only copy. The analyzer raises if invoked.

| Changed budget | Cache hits | Analyzer calls | New tokens | USD |
|---|---:|---:|---:|---:|
| 8,000,000 VND | 27 | 0 | 0 | 0 |
| 17,000,000 VND | 27 | 0 | 0 | 0 |
| 55,000,000 VND | 27 | 0 | 0 | 0 |

These probes hold the previously analyzed video set fixed, replaying the old revenue selection. They isolate budget changes from intentional reselection.

For the newly reranked selection, production cache lookup consistently reports **17 reusable analyses and 10 misses**, independent of budget. Budget is absent from the content prompt and content cache key.

**Live A4 holdout results.**

- **Rio PASS:** selected `7695457484974099730`, `7698027306689809671`, `7701751823807466759`; all describe sunscreen. Shampoo selections are excluded.
- **Creator `7234931025289217051`:** inspected all 100 cached titles; none establishes a sunscreen alternative. Three deals remain selected, explicitly off-topic. The conditional requirement cannot be established from this metadata; video contents remain **UNPROVEN**.

**Commands and results.**

Fresh copy:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/r5.db'
chmod 444 /tmp/r5.db
```

Exit **0**. Opening with `mode=ro` rejects writes. SHA256 remained unchanged:

```text
0bb5d3eb4204c60f4e878f418d8165b31fa5fe033f91fd252c7f94a95e4c304c
```

All probe and suite executions used `unshare -rn`, fake provider keys and `PYTHONPATH=src`.

| Command/artifact | Result |
|---|---|
| `/tmp/koc-video-r5-independent.py` | Exit 0; live collisions, regression cases and budget checks reproduced |
| `/tmp/koc-r5-canonical.py` | Exit 0; corpus checks complete; open hashtag defect reproduced |
| `scripts/s3_rerank_preview.py --db /tmp/r5.db --media-dir /home/lystiger/Projects/KOC-Discovery/data/media` | Exit 0; 9 creators, 5 changed selections, 10 analysis misses |
| Ordinary `timeout 130 …/python -m pytest -q` | Exit 124; stalled after 50 tests |
| `timeout 180 …/python /tmp/koc-offline-suite.py` | Exit 0; **488 passed, 1 skipped in 112.76s** |
| `git diff --exit-code -- src tests config prompts scripts` | Exit 0; unchanged |

The temporary suite wrapper replaces only asyncio’s socket wakeup with `os.write()`. No repository tests were changed or additionally skipped. Independent syscall verification confirmed `socket.send()` raises `EPERM`, while `os.write()` succeeds. The ordinary suite invocation remains **UNPROVEN in this sandbox**.

Logs: [production probes](/tmp/koc-video-r5-independent.log), [preview](/tmp/koc-r5-preview.log), [ordinary suite](/tmp/koc-r5-suite-plain.log), [complete workaround suite](/tmp/koc-r5-suite-workaround.log). Existing untracked r5 report was left untouched.