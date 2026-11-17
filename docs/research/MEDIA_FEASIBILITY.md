# Media Feasibility

Scope: one video, `7705660238917143816` (24.57 s, 576x1024, h264 + aac, 30 fps). Sandbox, no network. Sources: `docs/process/agy/MEDIA_FINDINGS.md`, `docs/process/agy/media_analysis_7705660238917143816.json`, `docs/research/FACTS.md` (Media test).

## Summary

| Capability | Status | Evidence |
|---|---|---|
| Probe metadata | Works (147 ms) | MEDIA_FINDINGS 1a |
| Uniform frames (fps=0.5, 360x640) | Works: 12 frames in 538 ms | MEDIA_FINDINGS 2a |
| Scene-change frames | 0 frames (max score 0.0358 < 0.3). Static shot | MEDIA_FINDINGS 2b |
| Audio extract (16 kHz mono WAV) | Works (216 ms) | MEDIA_FINDINGS 3a |
| Embedded captions | None | MEDIA_FINDINGS 3b |
| Vietnamese speech transcription | BLOCKED | Below |
| Agy structured analysis | Valid against schema; recorded | `media record`, media_tests row 1 |
| Token / cost capture | Not captured | Below |

## Agy analysis result (video 7705660238917143816)

| Field | Agy output | Orchestrator check | Verdict |
|---|---|---|---|
| `opening_hook` | "Mua 2 tính xiền 1", 0.0-3.0 s | On-screen text correct | VERIFIED (frames) |
| `product_appearances` | Downy Passion (red) and light-blue Downy pouches, 0-24.57 s | Pouches visible, correct variants in checked frames. Full-clip 0-24.57 s span is Agy's assertion | PARTIALLY VERIFIED (4 of 12 frames checked: 1, 4, 8, 12) |
| `product_demonstration` | `present: false` | Agy says pouches "static, untouched". Host holds them in frames 4 and 12 | ERROR: "static" claim wrong. `present: false` UNVERIFIED for the frames not checked |
| `claims` (on_screen) | "Mua 2 tính xiền 1" as on-screen claim, 0.0 s | Text correct in checked frames. "Shown across the clip" is Agy's assertion | PARTIALLY VERIFIED (4 of 12 frames checked: 1, 4, 8, 12) |
| `claims` (spoken) | none | Speech exists (Agy note). Not transcribed | BLOCKED |
| `call_to_action` | `null` | No visual CTA seen in checked frames. Spoken CTA unknown | Visual: VERIFIED for checked frames. Spoken: BLOCKED |
| `notes` | Live backdrop "Mega Chanhbeauty", static shot | Backdrop correct | VERIFIED |

Note: MEDIA_FINDINGS section 7 marks the pouch "sealed and static" claim VERIFIED. The frame check contradicts it. Treat that row as wrong.

Frame times (derived from fps=0.5, frame n at (n-1) x 2 s): frame 1 = 0 s, frame 4 = 6 s, frame 8 = 14 s, frame 12 = 22 s.

## Vietnamese ASR status

| Attempt | Result | Source |
|---|---|---|
| `voxtype transcribe --engine parakeet` (parakeet-tdt-0.6b-v3) | English gibberish. Vietnamese unsupported | FACTS line 59 |
| `voxtype transcribe --engine whisper` | `whisper-cli not found` | FACTS line 59 |
| local `ggml-base.en` | English-only model | FACTS line 59 |
| faster-whisper `small` model download | HF 429 from huggingface.co. Pending HF login | FACTS line 70 (2026-11-14 install log) |
| Agy transcription | Did not transcribe audio (guessing prohibited) | MEDIA_FINDINGS section 4 |

Result: BLOCKED. No Vietnamese transcript exists. Spoken claims, spoken CTA and spoken content are unknown.

## Cover image

`7705660238917143816.cover.png` is a JPEG, 1080x1920 sRGB (JFIF 1.01). Extension is wrong. Load it as JPEG (MEDIA_FINDINGS 1b).

## Cost and tokens

- Tokens, latency, est/actual cost: NOT captured. Agy run log files were lost after the run (exit code 1). `media_tests` row has `input_tokens`, `output_tokens`, `latency_ms`, `est_cost`, `actual_cost` all NULL.
- Agy estimate: 258 tokens/image x 12 = 3,096 image tokens. Agy assumption, UNVERIFIED.
- Reference at 1 fps: 25 frames x 258 = 6,450 (MEDIA_FINDINGS section 5; same assumption).

## Recorded artifacts

- `docs/process/agy/media_analysis_7705660238917143816.json` (validates against `docs/process/agy/media_analysis.schema.json`).
- Stored: `kalodata media record` -> `media_tests` (provider `agy`, model `gemini-3.8-flash-high`, prompt `v1`, validation `valid`).
- Prompt: `docs/process/agy/PROMPT_v1.md`.

## Conclusion

Frames and structured visual analysis: usable for a shortlist, with a manual spot check. Spoken content: BLOCKED until a Vietnamese ASR runs. Token cost: unmeasured, so inference cost per video is UNVERIFIED.
