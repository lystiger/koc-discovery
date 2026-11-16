# DEV brief: real run proposal page (B24, R11, AC20)

Same rules as `BRIEF_brand_platform.md` and `BRIEF_integration.md` (no network or paid calls, DB copy only in
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/integration/`).
Read spec R11 / AC20 and B24 in `~/Projects/LysStack/projects/koc-discovery/brand-platform/`.

1. API (`src/koc/web/api.py`, data via `koc.web.adapter`, no rescoring):
   `GET /api/runs/latest`, `GET /api/runs/{run_id}/proposal` (picks, cost, budget, reasons, caveats, score parts,
   evidence counts), `GET /api/runs/{run_id}/creators/{creator_id}` (evidence: metric rows, video timestamps,
   quotes, frame URLs `/media/frames/<video_id>/`). Placeholder audience: core text only, no numbers. Tests on the
   fixture DB and a real-run-copy test skipped when the copy is absent.
2. React routes `/de-xuat` (latest run) and `/de-xuat/:runId`, `/de-xuat/:runId/koc/:creatorId`. Reuse the results,
   proposal and KOC components (title block, budget strip, score bars, "Xem bằng chứng (n)", step indicator step 3,
   print stylesheet with logo). Title: "Đề xuất KOC cho <i>sản phẩm</i>" from the run's product and target.
3. Clean copy: map metric keys to Vietnamese labels (reuse the label map), strip evidence ids from prose, no run
   ids, timestamps, USD, tokens, stage codes on these pages. Footer link "Vận hành" goes to the Jinja `/runs/<id>`.
4. Landing "Xem một bản đề xuất mẫu" and header "Đề xuất mẫu" open `/de-xuat` (latest real run); fall back to the
   newest campaign proposal, hide when neither exists. Ctrl+K lists the run's KOCs.

Verify: full list, real-run copy: 5 KOCs, 28.500.000 ₫, all evidence links and frames resolve (HTTP 200), banned-word
scan, axe, PDF, screenshots at 375/1440 into `docs/build/shots/integration/` (run_proposal_*, run_koc_*).
Add row 6 (AC20) to `EVIDENCE_integration.md`, commit, stop.
