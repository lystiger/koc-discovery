# KOC Discovery visual system

## Approved direction

Use direction A, "Bản đề xuất", selected by Lystiger on 2026-11-15. The three taste mocks are in `design/taste/`; the approved screenshots are `design/taste/shots/a-ban-de-xuat-1440.png` and `design/taste/shots/a-ban-de-xuat-375.png`.

## Tokens and layout

- Warm paper background `#f6f3ee`, white paper surfaces `#fffdfa`, dark green ink `#24312b`, muted ink `#5d6962`, green action `#315f53`, pale green `#dce8e1`, warm border `#e3ddd3`.
- Newsreader for headings and Be Vietnam Pro for body text.
- Editorial ranked rows, thin separators, compact confidence badges, and a budget allocation strip on campaign results and proposals.
- Tabular numerals for scores, followers, costs, and budget totals.
- Keep copy in Vietnamese. Preserve readable wrapping on 375 px screens.

## Search result

The required `ui-ux-pro-max` search for "beauty creator campaign matching platform Vietnamese editorial" returned a generic pink, block-based marketing direction with Inter. That result conflicts with the approved mock, so the picked mock controls colors, type, and page structure.

## Allowed components

Use base-ui for selects and tooltips, cmdk for creator/campaign search, Vaul for the mobile creator sheet, Sonner for form feedback, NumberFlow for score and budget changes, and Recharts for operator charts. Use `clsx` for conditional classes.
