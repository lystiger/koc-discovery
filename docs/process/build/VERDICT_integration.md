# VERDICT: core integration + real run page (integration_core.md, AC20)

Auditor: Claude Opus 5.5 (Anthropic), React/brand-platform orchestrator. Builder: Codex gpt-6-luna (OpenAI).
Tested: `037b355` on `ui-test/react-pick-ui-library` (core merge `52870b1` of `feat/koc-mvp@6fb40f4`,
run page `f5e0a64`). Data: fresh read-only `.backup` of `data/koc.db` taken 2026-11-16 after the content_v3
rescore (core session confirmed it done). Server on port 8790, local only.

| # | Must hold | Verdict | Proof |
|---|---|---|---|
| 1 | Core data logic wins; placeholder audience shows only core text, no female/age numbers or citations | PASS | `/api/runs/<run>/creators/<id>` returns `audience_text`; all 5 KOC pages contain "Không có dữ liệu", regex for `(nữ\|tuổi)…%` finds 0 hits on run page and KOC pages at 375 and 1440 |
| 2 | Age slider does not use placeholder age values | PASS | Brand-platform verdict on `2ef8347` (AC19) plus `matching_api.py` now imports `koc.stages.placeholder_audience_creators` (EVIDENCE_integration.md) |
| 3 | Real run: 5 KOCs, total ≤ 30M, Vietnamese reasons and caveats, every cited id resolves | PASS | API picks = `[7485602050560148487 3.000.000, 7234931025289217051 3.000.000, 7594293671543079957 7.500.000, 7450735628620760071 7.500.000, 6730533371858437121 7.500.000]`, total 28.500.000 of 30.000.000, matching the DB copy and the core session's list. Cited ids 7/8/9/5/6 per KOC: all present as DOM anchors; all in-page evidence links resolve after URL decoding; clicks scroll to the target (top 20-24 px). 53 frame URLs fetched: 53 × HTTP 200 |
| 4 | Full suite green | PASS | `pytest -q tests`: 307 passed; `npm run lint` and `npm run build` exit 0 |
| 5 | No network or paid calls | PASS | Audit used the DB copy, local FastAPI and local Chromium only; no `koc run` / `koc resume` |
| AC20 | `/de-xuat/<run>` in the brand design | PASS | No banned words, raw keys, run ids or timestamps in visible text at 375 and 1440; axe 0 serious/critical at both; scrollWidth 375/1440; landing sample link → `/de-xuat` (latest = this run); PDF 3 A4 pages, print logo 145 px wide; Jinja `/runs/<run>`, `/dashboard`, `/creators/<id>` still 200 |

Screenshots and PDF (scratch, not committed): `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/audit/` (`run_1440.png`, `run_375.png`, `koc_1440.png`, `run.pdf`, `audit.json`).

## Defects (non-blocking)
- I1, Medium: KOC page "Lý do phù hợp" and "Lưu ý" end each paragraph with a run of 6-10 small inline links,
  several with the same name ("Khung hình video" ×3). Hard to scan; same class as C2. Group per paragraph
  ("Bằng chứng (n)") or number them.
- I2, Low: KOC metric table shows unitless raw values ("Xu hướng doanh thu 267.245,048", "Tỷ lệ tương tác 0,003").
  Add units or plain-language formatting.
- I3, Low (data, core): reason prose from S4 contains raw numbers ("1.0", "687643.86"). Core's S4 rerun is due; recheck after.
- I4, Low: the run page budget strip is a single bar, not the per-KOC allocation strip of the campaign proposal.

## Overall: PASS
Merge `ui-test/react-pick-ui-library` into `feat/koc-mvp` (B23). Reasons and citations to be re-checked after the
core S4 rerun.
