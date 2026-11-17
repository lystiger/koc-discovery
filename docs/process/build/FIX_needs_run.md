# Fix: "needs_run" panel (D-B3/D-B4). FRONTEND ONLY

Decisions D-B3, D-B4 in `~/Projects/LysStack/projects/koc-discovery/brief.md`; interface in
`~/Projects/LysStack/projects/koc-discovery/brand-platform/d-b3-interface.md`. Same rules as `BRIEF_brand_platform.md`.
Do not edit any Python file; the core session builds the API.

## API contract (core, agreed 2026-11-16)
When no finished run exists for the form's product type, the campaign result is
`{status: "needs_run", picked: [], warnings: [], run_command: "koc run --dry-run --product-type ... --count N",
run_command_notes: [str]}`. `run_command` always contains ` --dry-run`; the real command is the same string with
` --dry-run` removed. If the CLI pre-check would refuse, the reason is `run_command_notes[0]`.

## Build
1. Results page for `needs_run`: panel "Chưa có dữ liệu KOC cho <loại sản phẩm>" with one plain line: the web does not
   start paid runs; an operator runs the command below. Two steps, each a code block with a copy button (Sonner toast
   "Đã sao chép"): "1. Ước tính chi phí" = `run_command`; "2. Chạy thật" = the command without ` --dry-run`.
   Notes listed under it; if the first note is a refusal, show it as a warning above the steps.
2. "Khác": the command contains `--category-ids "<id>"`; highlight the placeholder and keep the note visible.
3. No proposal link, no budget strip, no KOC list in this state. Campaign list chip: "Chờ chạy dữ liệu".
4. Declare `run_command`, `run_command_notes` and the `needs_run` status in `types.ts`.
5. Tests: Playwright with mocked responses (normal, Khác, refusal note first), copy buttons, axe.

Verify: lint, build, smoke, axe; screenshots at 375/1440 into `docs/process/build/shots/readability/` (`needs_run_*`).
Add evidence rows, commit, stop.
