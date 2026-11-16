Overall PASS

Reviewed `bcc4803..3e93a73`. **P2-1 fixed; no P1/P2 open.**

- Original sentence and no-comma variant remain graded. All **48 other-subject checks passed**; legacy verdict mapping and scores stayed correct. [Evidence](/tmp/sf3-integration.log)
- **P3 — [faithfulness.py:41](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/src/koc/faithfulness.py:41):** Crafted “Hồ sơ khán giả doanh thu chưa xác minh.” still over-matches. Tighten subject matching.
- **P3 — [faithfulness.py:38](/home/lystiger/Projects/KOC-Discovery/.claude/worktrees/agent-ab5c588fde60ae2d6/src/koc/faithfulness.py:38):** “Không có dữ liệu về khán giả.” is missed. Add direct missing-data wording. [Adversarial results](/tmp/sf3-audit.log)

Command results:

- Read-only backup and cache-only CLI: **exit 0**, exact Lý do **0.875**, Lưu ý **0.10**, **0 calls/USD**.
- Live run: **10 audience caveats excluded**, **6 other caveats retained**; all five KOCs’ verdicts aligned.
- Offline non-web suite: **406 passed, 1 deselected**.
- Requested full suite: **UNPROVEN**, stalled; interrupted, exit **130**. Bounded diagnostics reproduced the same TestClient/AnyIO hang at [HEAD](/tmp/sf3-head-web.log) and [bcc4803](/tmp/sf3-base-web.log); exit **137**. Loopback setup reported `Operation not permitted`.
- S3/S4 cache checks passed: repeated warnings stable, zero provider calls/tokens/USD, cache rows unchanged.
- Benchmark sections 1–9, non-faithfulness fields, projections, and estimates unchanged.

Source/tests untouched. Live DB accessed read-only; schema and all **15 tables** match backup.