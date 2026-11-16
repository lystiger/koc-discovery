Overall FAIL

Reviewed `d1d1409..fbd2b98` on `v2/video-rerank`. Four P2 findings remain open. No source or tests modified.

**Findings**

- **P2 — Scattered words create Vietnamese false positives.** [src/koc/video_select.py:42](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/video_select.py:42): `Kem dưỡng chống lão hóa, nâng cơ` matches both `kem chống nắng` and `chống nắng`. Folding makes `nâng` equal `nắng`; unordered token matching joins unrelated words. Probe selected this off-topic video over actual sunscreen when revenue was higher. Match complete phrases with boundaries, while preserving supported hashtag matching.

- **P2 — Existing product filter defeats reranking.** [src/koc/pipeline.py:328](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/pipeline.py:328): `attached or videos` excludes videos outside the creator’s historical top products before topic scoring. Production-path probe supplied attached shampoo plus unattached sunscreen. Stored selection contained only shampoo, marked off-topic. Rank all candidates by brief relevance.

- **P2 — Legacy adoption can return another video’s analysis.** [src/koc/pipeline.py:225](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/src/koc/pipeline.py:225): identical media bytes under different video IDs share the media hash. Adoption never checks the requested video ID. Reproduced with a legacy `v1` row and a different-budget request for `v2`:
  ```text
  d1d1409 requested=v2 returned=v2 stub_calls=1
  HEAD    requested=v2 returned=v1 stub_calls=0
  ```
  Returned analysis and evidence still identify `v1`. Validate video identity before adoption and cache reuse.

- **P2 — Preview undercounts analyses requiring payment.** [scripts/s3_rerank_preview.py:45](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/scripts/s3_rerank_preview.py:45): any `content_v3` analysis marks a video reusable, regardless of model, brief or usable cache entry. Synthetic DB containing only an unrelated-model analysis produced:
  ```text
  preview: new paid analyses needed ... 0 video(s)
  actual cache lookup: CacheOnlyMiss
  ```
  Check availability using production cache identity and legacy lookup rules.

- **P3 — Prompt test passes without inspecting a prompt.** [tests/core/test_video_select.py:102](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/tests/core/test_video_select.py:102): `budget_guard=None` raises `AttributeError` before the client captures anything. Broad `pytest.raises(Exception)` accepts it; the empty-string assertion passes. Probe confirmed `captured=False`. Supply a guard, require the intended sentinel exception, and assert capture occurred.

**Live holdout**

Executed:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  '.backup /tmp/koc-video-review.db'

unshare -rn sh -c 'PYTHONPATH=src /home/lystiger/Projects/KOC-Discovery/.venv/bin/python scripts/s3_rerank_preview.py --db /tmp/koc-video-review.db'
```

- **Rio PASS:** selected `7695457484974099730`, `7698027306689809671`, `7701751823807466759`; sunscreen titles replace all three shampoo videos.
- **7234931025289217051 UNPROVEN:** still selects Roopy, Kato Kato and Charmix deals. All 100 cached titles score zero. Available metadata does not establish an on-topic alternative, so the conditional holdout cannot receive PASS.
- Preview reports 9 creators, 5 changed selections, and 10 videos needing analysis. Payment count has the limitation above.
- Audited execution: **0 network attempts, 0 write opens, four SELECT statements**. Copy and live DB SHA256 hashes remained unchanged.

**Other checks**

- Folding handles `Đ/đ`, tone marks, NFC and NFD. `chống` alone correctly remains off-topic.
- Off-topic fills carry `on_topic:false`, score zero and empty terms. Selection metadata persists in `breakdown_json`.
- Budget is absent from the content prompt and content key. Production `_s3_creator(mock=False)` with a stubbed analyzer reused both results after a budget-only change: **0 additional analyzer calls, 2 cache hits**.
- Legacy lookup preserves media hash, prompt-version label, model key, product and audience. Changed values correctly miss. It intentionally reuses older budget-bearing `content_v3` prompts.
- Adoption itself spends nothing. Search is finite: current budget plus distinct budgets stored in runs; no fixed maximum. An undiscoverable legacy budget misses and allows the caller’s normal paid path. `cache_only=True` prevents that payment.
- Smoke-test restoration is legitimate: [tests/core/test_s4_smoke_script.py:71](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-abf5439f8360b5add/tests/core/test_s4_smoke_script.py:71) registers `_cached_call` for teardown restoration after the script replaces it.

**Test results**

Focused offline run: **15 passed**.

The ordinary full-suite command hung after 50 tests because sandbox restrictions block asyncio’s socket wakeup. Probe confirmed `socket.send()` raises `EPERM`; `os.write()` succeeds.

Full suite completed under `unshare -rn`, fake keys and `PYTHONPATH=src`, using `/tmp/koc-offline-suite.py` solely to replace that wakeup syscall. Repository source and tests remained unchanged:

```text
474 passed, 1 skipped in 88.11s
```

The unmodified full-suite invocation remains **UNPROVEN in this sandbox**.