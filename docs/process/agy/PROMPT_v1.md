# Agy media feasibility task (prompt v1)
You are Agy, media feasibility tester. Work ONLY on local files. Do NOT make any network request, do NOT open URLs, do NOT install packages.
Input dir: data/raw/media/ (video 7705660238917143816.mp4, 24.6 s, 576x1024 h264+aac, plus its cover.png). Source: downloaded from Kalodata's in-page player.
Output dir: docs/process/agy/ (create files only there; you may also write temp files under docs/process/agy/work/).

Steps, record command + wall time for each:
1. ffprobe the mp4; confirm the thumbnail opens (identify size).
2. Extract representative frames with ffmpeg (1 frame every 2 s, scaled to 360 px wide) to docs/process/agy/work/frames/. Also try scene-change frames (select='gt(scene,0.3)').
3. Extract audio to 16 kHz mono wav. Check if any caption/subtitle stream exists. State whether you can transcribe the audio yourself (Vietnamese speech); if you cannot, say so. Do NOT guess speech.
4. Look at the frames (and audio if you can) and produce a MediaAnalysis JSON that validates against docs/process/agy/media_analysis.schema.json: opening hook, product appearances, product demonstration, spoken or on-screen claims (quote on-screen Vietnamese text exactly), call to action, timestamps in seconds. Use null/empty lists where evidence is absent. Do not infer sales or performance from visuals.
   Write it as docs/process/agy/media_analysis_7705660238917143816.json with this wrapper:
   {"analysis": <MediaAnalysis>, "provider": "agy", "model": "gemini-3.8-flash-high", "prompt_version": "v1", "preprocess": {...ffmpeg settings, frame count...}, "input_tokens": null, "output_tokens": null, "latency_ms": null, "est_cost": null, "actual_cost": null}
5. Write docs/process/agy/MEDIA_FINDINGS.md (short): what worked, what failed, frame count, image token estimate for the frames you looked at (state your per-image token assumption), whether audio was usable, confidence per MediaAnalysis field, and what you could NOT verify. Mark each claim VERIFIED / PARTIALLY VERIFIED / UNVERIFIED / BLOCKED.
Finish with a 5-line summary.
