# Media Feasibility Findings: Video 7705660238917143816

## 1. Executive Summary
Evaluation of media processing feasibility on local video `7705660238917143816.mp4` (24.57 s, 576x1024, H.264/AAC) and its thumbnail `7705660238917143816.cover.png`. Visual feature extraction and schema-compliant structured analysis succeeded completely. Scene-change frame extraction failed due to static camera staging, and audio transcription was blocked by the absence of local ASR tooling under strict no-install constraints.

---

## 2. Command Execution & Wall Time

| Step | Operation | Command | Wall Time | Exit Code | Result |
|---|---|---|---|---|---|
| 1a | Stream & format probe | `ffprobe -hide_banner -show_error -show_format -show_streams data/raw/media/7705660238917143816.mp4` | 146.89 ms | 0 | 2 streams (aac audio, h264 video), duration 24.57s |
| 1b | Cover inspection | `identify data/raw/media/7705660238917143816.cover.png` | 73.44 ms | 0 | JPEG 1080x1920 sRGB (JPEG inside .png filename) |
| 2a | Regular frame extraction | `ffmpeg -y -i data/raw/media/7705660238917143816.mp4 -vf 'fps=0.5,scale=360:-1' docs/process/agy/work/frames/frame_%03d.jpg` | 538.09 ms | 0 | 12 frames (360x640) generated |
| 2b | Scene-change extraction | `ffmpeg -y -i data/raw/media/7705660238917143816.mp4 -vf 'select=gt(scene,0.3),scale=360:-1' -fps_mode vfr docs/process/agy/work/scene_frames/scene_%03d.jpg` | 511.76 ms | 234 | 0 frames (max scene score = 0.0358 < 0.3) |
| 3a | Audio extraction | `ffmpeg -y -i data/raw/media/7705660238917143816.mp4 -vn -ar 16000 -ac 1 docs/process/agy/work/audio_16k.wav` | 216.34 ms | 0 | 16 kHz mono WAV (767 KiB, 24.54s) |
| 3b | Subtitle probe | `ffprobe -v error -select_streams s -show_entries stream=index,codec_name -of default=noprint_wrappers=1 data/raw/media/7705660238917143816.mp4` | 146.49 ms | 0 | No subtitle/caption streams exist |

---

## 3. What Worked
- **Metadata Probing**: Fast, reliable ffprobe extraction of codec details, dimensions, frame rates, and durations.
- **Uniform Frame Sampling**: Fast extraction (538 ms) of 12 evenly-spaced 360x640 JPEG frames (`fps=0.5`).
- **Visual Inspection & OCR**: High-clarity visual inspection of all frames. Identified live commerce setting ("Mega Chanhbeauty"), host, assistants, and product variants (Downy Passion red pouch and Downy Gentle/Floral blue pouch).
- **On-Screen Vietnamese Text Extraction**: Exact on-screen Vietnamese text banner identified: `"Mua 2 tính xiền 1"` (static throughout 0.0s–24.57s).
- **JSON Validation**: `docs/process/agy/media_analysis_7705660238917143816.json` strictly adheres to `media_analysis.schema.json`.

---

## 4. What Failed / Limitations
- **Scene-Change Extraction (`select='gt(scene,0.3)'`)**: Failed with exit code 234 (no frames selected). The video is a single, uninterrupted tripod shot without camera cuts or scene transitions. The maximum frame-to-frame scene score across all 737 frames is only `0.035789`, far below the 0.3 threshold.
- **Audio Speech Transcription**: BLOCKED. The MP4 container lacks subtitle/caption streams. No local speech-to-text binary (`whisper`, `faster-whisper`, `vosk`) is installed, and package installations/network calls were prohibited by task rules. Speech guessing was explicitly prohibited.
- **Thumbnail Extension Discrepancy**: `data/raw/media/7705660238917143816.cover.png` is an ISO JPEG file (JFIF standard 1.01) rather than a true PNG file.

---

## 5. Frame Count & Image Token Estimates
- **Frames Inspected**: 12 frames (1 frame every 2.0 s, 360x640 resolution).
- **Per-Image Token Assumption**: 258 tokens per image (standard Gemini vision model tiling for single-tile images where resolution ≤ 768px on the longest dimension).
- **Total Image Tokens (12 frames)**: `12 * 258 = 3,096 tokens`.
- *(Reference at 1 fps verification: 25 frames * 258 = 6,450 tokens)*.

---

## 6. Audio Usability Assessment
- **File Integrity**: Usable audio stream extracted cleanly to 16 kHz mono WAV (`docs/process/agy/work/audio_16k.wav`, 785,452 bytes).
- **Transcription Feasibility**: UNUSABLE in the current offline environment without preinstalled ASR tools or native audio API ingestion. No embedded captions exist.

---

## 7. Confidence & Verification Status per MediaAnalysis Field

| Field | Value | Confidence | Verification Status | Evidence / Notes |
|---|---|---|---|---|
| `video_id` | `"7705660238917143816"` | 100% | **VERIFIED** | Matches input filename and ffprobe format metadata. |
| `opening_hook` | `"Mua 2 tính xiền 1"` (0.0s–3.0s) | 95% | **VERIFIED** | Host signals promotion with hand gestures while text banner is prominently displayed. |
| `product_appearances` | Downy Passion & Floral refill pouches (0.0s–24.57s) | 100% | **VERIFIED** | Both pouches remain in foreground on desk throughout all frames. |
| `product_demonstration` | `present: false` | 100% | **VERIFIED** | Pouches remain sealed and static on desk; no pouring, washing, or fabric testing occurs. |
| `claims` (on_screen) | `"Mua 2 tính xiền 1"` (0.0s) | 100% | **VERIFIED** | Exact Vietnamese text overlay visible continuously on screen. |
| `claims` (spoken) | None listed (empty) | N/A | **BLOCKED / UNVERIFIED** | Spoken audio cannot be transcribed locally; guessing prohibited. |
| `call_to_action` | `null` | 90% | **VERIFIED (Visual)** / **UNVERIFIED (Spoken)** | No visual CTA overlay (e.g., cart icon or click text); spoken CTA unverified. |
| `notes` | Livestream context, static shot description | 100% | **VERIFIED** | Corroborated across all 12 inspected frames. |
