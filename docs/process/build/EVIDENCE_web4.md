# KOC Discovery web4 audit fixes

## Audit mapping

| Finding | Fix |
|---|---|
| F1 | `runs_list.html` labels cells for a stacked mobile card layout. Theme A remains selected by default. |
| F2 | `top5.html` keeps theme B's comparison table inside its scroll box and shows a mobile scroll cue. |
| F3 | Corrected fixture evidence IDs. The web test follows every fragment link from each themed recommendation page to its target page and checks the target ID. |
| F4 | Dashboard Gemini cost now reads as an estimate in USD. |
| F5 | Each mock video now has distinct transcript, rubric evidence, and risk text. Captions identify frames as mock placeholders and do not claim they show transcript content. |
| F6 | The run list shows the mock banner when it contains mock runs. |
| F7 | Booking fee notes link to the creator's booking fee record. |
| F8 | Evidence links now number citations across each recommendation card and keep distinct accessible labels. |
| F9 | Kalodata credit usage and cap now include the `credit` unit. |
| F10 | Zero task errors use muted text. Nonzero counts use the error color. |
| F11 | Dashboard stage labels now use Vietnamese names without English duplicates. |
| F12 | Removed calibration values because the fixture has no sample size for a useful caveat. |
| F13 | Dashboard decimals, scores, and timestamps use Vietnamese decimal commas. |
| F14 | Replaced audience-fit overclaim with the observed age range and campaign range. |
| F15 | Replaced the GPM trend claim with the unitless revenue trend slope and its limits. |
| F16 | Follower count no longer claims national reach. |
| F17 | Replaced flattering medical authority language with the transcript topic. |
| F18 | Audience age statement now says the data does not measure purchasing power. |
| F19 | Fixture frames are neutral gray placeholders with a mock label. Alt text says they are not real video frames. |
| F20 | Evidence identifiers and metric sources wrap inside their cells. |
| F21 | Profile frames use centered `object-fit: cover` cropping. |
| F22 | Dashboard stat values stay on one line at narrow widths. |
| F23 | The score denominator uses a nonwrapping span. |
| F24 | Audience terms and values now live in a definition list. |
| F25 | Removed the internal creator ID from the visible profile details. |
| F26 | Removed inline `Lưu ý:` labels from warning text. |
| F27 | Replaced title dashes and age-range dashes with punctuation or `đến`. |
| F28 | Expanded `KCN` to `kem chống nắng` in fixture titles. |
| F29 | Corrected mismatched timestamp IDs and display timestamps with one decimal convention. |

## Checks

- Added a test for every fragment link on the recommendation page in themes a, b, and c.
- Added a fixture test for distinct transcripts, rubric data, and risks across three videos, plus the mock flag.
- `pytest -q tests/web` could not run in this environment: `/usr/bin/python: No module named pytest`.
- Pytest and FastAPI are missing from this environment, so runtime route checks could not run.
- 375 px and desktop screenshots remain for the orchestrator to capture. Responsive screenshots are UNPROVEN here.

## Design choices

UI Pro Max returned Data-Dense Dashboard for the analytics tool. The patch uses its in-frame table scroll cue. Theme A stays the default. It uses Georgia, system-ui, and ui-monospace with palette `#f5f3ee`, `#fbfaf7`, `#24231f`, and `#785b2e`.
