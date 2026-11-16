"""Media preprocessing using ffmpeg for KOC video analysis."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess


def get_jpeg_dimensions(path: str | Path) -> tuple[int, int]:
    """Read width and height of a JPEG file."""
    p = Path(path)
    if not p.is_file():
        return (0, 0)
    try:
        with p.open("rb") as f:
            data = f.read(2)
            if data != b"\xff\xd8":
                return (0, 0)
            while True:
                marker_bytes = f.read(2)
                if len(marker_bytes) < 2:
                    break
                if marker_bytes[0] != 0xFF:
                    break
                marker = marker_bytes[1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    length = int.from_bytes(f.read(2), "big")
                    sof_data = f.read(5)
                    h = int.from_bytes(sof_data[1:3], "big")
                    w = int.from_bytes(sof_data[3:5], "big")
                    return (w, h)
                elif marker in (0xD8, 0xD9, 0x00):
                    continue
                else:
                    length = int.from_bytes(f.read(2), "big")
                    if length < 2:
                        break
                    f.seek(length - 2, 1)
    except Exception:
        pass
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            str(p),
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        w_str, h_str = out.split("x")
        return (int(w_str), int(h_str))
    except Exception:
        return (360, 640)


def _compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _has_audio_stream(path: Path) -> bool:
    """Check if the video file contains at least one audio stream."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0 and "audio" in res.stdout.strip()


def _get_video_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


def _calculate_frame_timestamps(duration_s: float, n_frames: int) -> list[float]:
    if n_frames <= 0:
        return []
    if duration_s <= 0.0:
        return [0.0] * n_frames

    # Hook frame at 0.5s if video is longer than 0.5s; otherwise fallback
    t_hook = 0.5 if duration_s > 0.5 else round(duration_s / 2.0, 2)
    if n_frames == 1:
        return [t_hook]

    timestamps = [t_hook]
    rem = n_frames - 1
    step = (duration_s - t_hook) / (rem + 1)
    for i in range(1, rem + 1):
        t = round(t_hook + i * step, 2)
        if t <= timestamps[-1]:
            t = round(timestamps[-1] + 0.01, 2)
        if t >= duration_s:
            t = round(duration_s - 0.01 * (rem - i + 1), 2)
        timestamps.append(t)

    return timestamps


def _get_default_max_analyzed_seconds(config_path: str | Path | None = None) -> float:
    try:
        from koc.llm.pricing import load_pricing_config
        cfg = load_pricing_config(config_path)
        return float(cfg.get("token_accounting", {}).get("max_analyzed_seconds", 90))
    except Exception:
        return 90.0


def preprocess_video(
    mp4_path: str,
    out_dir: str,
    n_frames: int = 8,
    max_analyzed_seconds: float | None = None,
    config_path: str | Path | None = None,
) -> dict:
    """Preprocess MP4 video using ffmpeg:
    - Analyzes at most max_analyzed_seconds (default from config/llm_prices.yaml or 90).
    - Extracts n_frames within that window (first at 0.5s for hook if duration > 0.5s), 360 px wide JPEG.
    - Extracts 16 kHz mono audio clipped with ffmpeg -t (mp3 format, 32 kbps).
    - Computes sha256 and duration.

    Returns:
        dict: {"frames": [{"path": str, "t_s": float, "width": int, "height": int}], "audio_path": str, "duration_s": float, "raw_duration_s": float, "sha256": str}
    """
    video_file = Path(mp4_path)
    if not video_file.is_file():
        raise FileNotFoundError(f"Video file not found: {mp4_path}")

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sha256_hex = _compute_sha256(video_file)
    raw_duration_s = _get_video_duration(video_file)

    if max_analyzed_seconds is None:
        max_analyzed_seconds = _get_default_max_analyzed_seconds(config_path)

    if max_analyzed_seconds is not None and max_analyzed_seconds > 0:
        analyzed_duration_s = min(raw_duration_s, float(max_analyzed_seconds))
    else:
        analyzed_duration_s = raw_duration_s

    timestamps = _calculate_frame_timestamps(analyzed_duration_s, n_frames)

    frames = []
    for i, t in enumerate(timestamps):
        t_ms = int(round(t * 1000))
        frame_filename = f"f_{t_ms}.jpg"
        frame_path = output_dir / frame_filename
        # ffmpeg: scale to 360px wide, keep aspect ratio (-2 ensures even height)
        cmd_frame = [
            "ffmpeg",
            "-y",
            "-ss", str(t),
            "-i", str(video_file),
            "-vframes", "1",
            "-vf", "scale=360:-2",
            "-q:v", "3",
            str(frame_path),
        ]
        subprocess.run(cmd_frame, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        w, h = get_jpeg_dimensions(frame_path)
        frames.append({"path": str(frame_path), "t_s": t, "width": w, "height": h})

    # Audio extraction: 16 kHz mono mp3 clipped to analyzed_duration_s (only if video contains an audio stream)
    audio_path: str | None = None
    if _has_audio_stream(video_file):
        extracted_audio = output_dir / "audio_16k.mp3"
        cmd_audio = [
            "ffmpeg",
            "-y",
            "-i", str(video_file),
            "-t", str(analyzed_duration_s),
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            "-b:a", "32k",
            str(extracted_audio),
        ]
        subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        audio_path = str(extracted_audio)

    return {
        "frames": frames,
        "audio_path": audio_path,
        "duration_s": round(analyzed_duration_s, 2),
        "raw_duration_s": round(raw_duration_s, 2),
        "sha256": sha256_hex,
    }
