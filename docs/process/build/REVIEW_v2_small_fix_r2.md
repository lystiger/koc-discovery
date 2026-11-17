Overall FAIL

Reviewed `bcc4803..24dbfe7`. One P2 remains open. No additional P1/P2 found.

- **P2-1 — FAIL, partially fixed.** [faithfulness.py:39](src/koc/faithfulness.py:39) still drops “Hồ sơ khán giả đã được xác minh, doanh thu chưa được xác minh.” Reproduction inflated Lưu ý from **0.5 to 1.0**. Tie missing verification specifically to audience information. Original round-1 example now passes.
- **P2-2 — PASS.** [faithfulness.py:147](src/koc/faithfulness.py:147) preserves reasons and verdict mapping. Reproduction: four sentences, four correctly mapped verdicts; expected/actual reason score **0.666667**.
- **P2-3 — PASS.** [guard.py:82](src/koc/llm/guard.py:82) detects transcript-only injection through `_cached_call`; one warning, zero provider calls/tokens/USD.
- **P3 duplicate warnings — PASS.** [guard.py:87](src/koc/llm/guard.py:87) replaces the old warning. Original reproduction returns one warning across repeated reads.
- **P3 cache regression coverage — PARTIAL.** [test_injection.py:180](tests/llm/test_injection.py:180) adds S3 integration coverage. S4 integration, zero usage, and cache immutability assertions remain absent. Independent reproductions verified those behaviors.

Command results:

- Read-only backup and cache-only CLI: **exit 0**. Exact Lý do **0.875**, Lưu ý **0.10**, **0 calls, USD 0**.
- All **five audience caveats excluded**; live verdict mapping correct.
- Detector: **zero hits** across **906 nonempty titles** from 941 rows, **52 transcripts**, and remaining checked text.
- Focused pytest: **55 passed**.
- Offline non-web suite: **405 passed, 1 deselected**.
- Requested full suite: **UNPROVEN**. Hung at `test_operator_view_shows_brief_count_not_five` inside TestClient/AnyIO; interrupted, exit **130**. Bounded diagnostic exited **124**. Network setup reported `Cannot open netlink socket: Operation not permitted`.
- Benchmark sections 1–9, non-faithfulness fields, and estimates unchanged.
- Source/tests untouched. Live DB timestamp unchanged; schema and all **15 tables** match backup.

Evidence: [over-match reproduction](/tmp/sf2-overmatch.log), [live checks](/tmp/sf2-checks.log), [cache checks](/tmp/sf2-cache.log), [suite diagnostic](/tmp/sf2-suite-diagnostic.log).