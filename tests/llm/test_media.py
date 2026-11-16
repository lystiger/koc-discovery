from pathlib import Path
import hashlib
import subprocess
import pytest

from koc.llm.media import preprocess_video, _calculate_frame_timestamps, get_jpeg_dimensions


def _create_test_video(path: Path, duration_s: float = 3.0, width: int = 360, height: int = 640) -> Path:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size={width}x{height}:rate=10",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_s}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "32k",
        str(path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return path


def test_preprocess_video_generated_file(tmp_path: Path):
    video_path = tmp_path / "test_video.mp4"
    _create_test_video(video_path, duration_s=3.0, width=360, height=640)

    out_dir = str(tmp_path / "media_out")
    result = preprocess_video(str(video_path), out_dir, n_frames=8)

    # 1. Structure
    assert isinstance(result, dict)
    assert "frames" in result
    assert "audio_path" in result
    assert "duration_s" in result
    assert "sha256" in result

    # 2. Duration and SHA256
    assert isinstance(result["duration_s"], float)
    assert 2.9 <= result["duration_s"] <= 3.1

    expected_sha256 = hashlib.sha256(video_path.read_bytes()).hexdigest()
    assert result["sha256"] == expected_sha256

    # 3. Audio file
    audio_path = Path(result["audio_path"])
    assert audio_path.is_file()
    assert audio_path.stat().st_size > 0
    assert audio_path.name == "audio_16k.mp3"

    # 4. Frames count and hook frame
    frames = result["frames"]
    assert len(frames) == 8

    # Hook frame at 0.5s
    assert pytest.approx(frames[0]["t_s"], abs=0.01) == 0.5

    # Check timestamps are strictly increasing and < duration
    timestamps = [f["t_s"] for f in frames]
    assert all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))
    assert all(t < result["duration_s"] for t in timestamps)

    # Check images exist, width is 360px, naming follows f_<t_ms>.jpg
    for f in frames:
        frame_file = Path(f["path"])
        assert frame_file.is_file()
        assert frame_file.stat().st_size > 0
        t_ms = int(round(f["t_s"] * 1000))
        assert frame_file.name == f"f_{t_ms}.jpg"
        w, h = get_jpeg_dimensions(frame_file)
        assert w == 360
        assert h == 640
        assert f["width"] == 360
        assert f["height"] == 640


def test_calculate_frame_timestamps_short_video_hook():
    # 2.0s video with 8 frames: hook must stay 0.5s (Finding 8)
    ts_2s = _calculate_frame_timestamps(2.0, 8)
    assert len(ts_2s) == 8
    assert ts_2s[0] == 0.5
    assert all(ts_2s[i] < ts_2s[i + 1] for i in range(len(ts_2s) - 1))
    assert ts_2s[-1] < 2.0

    # Short video (0.4s) shorter than 0.5s: fallback halfway
    ts_short = _calculate_frame_timestamps(0.4, 8)
    assert len(ts_short) == 8
    assert ts_short[0] == 0.2
    assert all(ts_short[i] < ts_short[i + 1] for i in range(len(ts_short) - 1))
    assert ts_short[-1] < 0.4

    # 10s video with 8 frames
    ts_10s = _calculate_frame_timestamps(10.0, 8)
    assert len(ts_10s) == 8
    assert ts_10s[0] == 0.5
    assert all(ts_10s[i] < ts_10s[i + 1] for i in range(len(ts_10s) - 1))
    assert ts_10s[-1] < 10.0

    # 1 frame
    assert _calculate_frame_timestamps(3.0, 1) == [0.5]
    assert _calculate_frame_timestamps(0.3, 1) == [0.15]

    # 0 frames
    assert _calculate_frame_timestamps(3.0, 0) == []


def test_preprocess_video_no_audio_stream(tmp_path: Path):
    """R2-3: Video without audio stream extracts frames but returns audio_path=None without error."""
    video_path = tmp_path / "silent_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2.0:size=360x640:rate=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    out_dir = str(tmp_path / "silent_out")
    result = preprocess_video(str(video_path), out_dir, n_frames=8)

    assert result["audio_path"] is None
    assert len(result["frames"]) == 8
    assert pytest.approx(result["duration_s"], abs=0.1) == 2.0
    for f in result["frames"]:
        assert Path(f["path"]).is_file()


def test_preprocess_video_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        preprocess_video(str(tmp_path / "non_existent.mp4"), str(tmp_path))


def test_preprocess_video_clips_to_max_analyzed_seconds(tmp_path: Path):
    """Long video fixture (> 90s): clips audio with ffmpeg -t <= 90s, samples frames <= 90s, keeps 0.5s hook."""
    video_path = tmp_path / "long_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=100:size=360x640:rate=1",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=100",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "32k",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    out_dir = str(tmp_path / "long_out")
    result = preprocess_video(str(video_path), out_dir, n_frames=8)

    # 1. Duration reported is clipped to <= 90s
    assert result["duration_s"] <= 90.0
    assert pytest.approx(result["duration_s"], abs=0.1) == 90.0

    # 2. Audio duration measured with ffprobe is <= 90s
    audio_path = result["audio_path"]
    assert audio_path is not None
    assert Path(audio_path).is_file()
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    audio_dur = float(subprocess.check_output(probe_cmd, text=True).strip())
    assert audio_dur <= 90.1
    assert audio_dur >= 89.9

    # 3. Frames sampled within the 90s window and hook frame kept at 0.5s
    frames = result["frames"]
    assert len(frames) == 8
    assert pytest.approx(frames[0]["t_s"], abs=0.01) == 0.5
    for f in frames:
        assert f["t_s"] <= 90.0

