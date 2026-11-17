# VERDICT: brand platform (TEST gate, fix round 6)

Verifier: Claude Opus 5.5. The builder (Codex/OpenAI) is a different provider. Date: 2026-11-16.
Branch `ui-test/react-pick-ui-library` at `2ef8347`, built against `docs/process/build/FIX_round6.md`. This file is the only repo file changed.

All proof is in `/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/verifier2/`, written `$V` below.
Earlier rounds are archived in `$V/r2_out/` to `$V/r6_out/`. Everything directly in `$V/` is from this run.

Setup:
- Fresh fixture on port 8790.
- Fresh copy of the real DB at `$V/real.db` (chmod 444, opened with `mode=ro`). A second copy, `$V/real_rw.db`, was served on port 8791.
- Port 8792 served the empty DB, then `fx_nos2`, then `fx_lingender`. All servers were stopped.
- Fixture variants:
  - `fx_missing`: Linh loses the 25-34 row.
  - `fx_lingender`: Linh loses all age rows; the other creators keep theirs.
  - `fx_genderonly`: nobody has age rows.
  - `fx_nos2`: Linh loses the S2 score.
- Scripts: `ui.py`, `coh.py`, `edge.py`, `ax0.py`, `toast.py`, `api_probe.py`, `age.py`, `a1b.py`, `nos2.py`, `lg.py`.

## Criteria

| # | Verdict | Proof |
|---|---|---|
| 1 | PASS | Invalid submit: 4 inline errors. Valid submit: results and the toast. Both widths, both DBs. The API returns 422 for invalid inputs. |
| 2 | PASS | Fixture: 5 picks, under budget, distinct MCNs. Real DB: 5 picks, and count 10 gives 10 (`probe_*.txt`). `pytest`: 90 passed. |
| 3 | PASS | 0 banned words on brand pages. |
| 4 | PASS (R1 fixed) | `fx_nos2`, results row for Linh: "Khán giả \| Chưa phân tích", badge "**Một phần**" (`nos2.py`). Matching gives `audience=None`, `confidence=Một phần`, fit 85.33 (86.53 with S2). The real results page shows "Chưa phân tích" 11 times. |
| 5 | PASS | PDFs are A4 with 2 pages; 0 matches for nav or button text. |
| 6 | PASS | Partial-handle search opens the creator on both DBs. |
| 7 | PASS | 375 px: dialog + Vaul with results underneath. 1440 px: a page. |
| 8 | PASS | Ops totals equal `queries.run_costs`. |
| 9 | PASS | Listed libraries only. |
| 10 | PASS | `pytest`: 90 passed. Build: exit 0. Lint: exit 0. |
| 11 | PASS | No snake_case words except creator handles. No `dd-dd` hyphen ranges remain in results, KOC or proposal text on either DB (`grep` over `text_*.txt`). |
| 12 | PASS | 0 serious axe issues on all pages, edge pages, the 0-pick page, the age form, the toast (8/8 clean samples) and the palette. The `/koc` hit in `ui.py` is the fading toast again. |
| 13 | UNPROVEN | Needs Lystiger's sign-off. |
| 14 | PASS | CTAs work. The sample link is hidden on the empty DB. Stats match SQL. |
| 15 | PASS | With reduced motion: no animation and scrollWidth 375. |
| 16 | PASS | `/chien-dich` works, including the empty state. |
| 17 | PASS | The print logo is 145 px wide, and "KOC DISCOVERY" appears once in each PDF. |
| 18 | PASS | Shared header, footer, pills and title block (`coh.json`). Steps 1 / 2 / 3, hidden in print. Searching state shows with motion and is skipped under reduced motion. |
| 19 | PASS | See the A1 re-run below. The picker passes: chips, slider, keys, aria and axe 0. The API accepts contiguous ranges and rejects gaps with 422. Real placeholder rows give audience `None` for all 4 ranges tested and at count 10 (`a1b.py`, `age_out.json`). |

## A1 re-run: fit never rises (`a1b.py`)

| Case | Linh audience | Linh fit |
|---|---|---|
| Baseline, target 25-34 | 60.0 | 81.92 |
| `fx_missing`, target 25-34 | 54.25 | **80.78** |
| Baseline, target 18-34 | 83.0 | 86.53 |
| `fx_missing`, target 18-34 | 81.25 | 86.17 |
| Gender-only creator (`fx_lingender`), target 18-34 | 81.25 | 86.17 |
| Gender-only pool (`fx_genderonly`), target 18-34 | 82.5 | 86.42 |
| No S2 row (`fx_nos2`), target 18-34 | `None` (shown "Chưa phân tích", Một phần) | 85.33 |

## R1-R3

| ID | Status | Proof |
|---|---|---|
| R1 | Fixed | Row 4. The KOC detail API nulls audience metrics when the run has no S2 row (`api.py`). |
| R2 | Fixed | En dashes everywhere checked. Slider ticks read "18–24". |
| R3 | Fixed | The phone header CTA shows "Bắt đầu", with the accessible name "Bắt đầu chiến dịch", which contains the visible text (WCAG 2.5.3). The header is 1 row, 67 px (`coh.json` `headerItems`). |

## New defects

| ID | Severity | Defect |
|---|---|---|
| G1 | Low | A creator with gender data but no age data shows a number that partly comes from the pool-minimum fill: "Khán giả 81" (82.5 female, with age filled at 80), next to the note "Thiếu dữ liệu độ tuổi" and the badge "Đầy đủ" (`lg.py`). The score does not rise, and the note is honest. A reader may still take 81 as fully observed. Optional: show the observed gender value, or add "ước tính" to the number. |

## Overall verdict

**PASS**: no criterion fails. Criterion 13 stays UNPROVEN until Lystiger signs off.
