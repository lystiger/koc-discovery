"""scripts/s3_free_smoke.py offline: mocked OpenRouter transport, a generated 3 s video, no network."""
import importlib.util
import json
import re
import sqlite3
import subprocess
from pathlib import Path

import httpx
import pytest

import koc.llm.factory as factory

REPO = Path(__file__).resolve().parents[2]
VIDEO_ID = "7701594488619191573"
CRITERIA = ["hook", "product_clarity", "demonstration", "claim_quality", "cta", "brand_fit", "production_quality"]


def _load():
    spec = importlib.util.spec_from_file_location("s3_free_smoke", REPO / "scripts" / "s3_free_smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _video(path: Path):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=360x640:rate=10", "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "32k", str(path)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


COST = [0.0]


def _transport(seen, speech=True):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        evidence = [{"evidence_id": f"{VIDEO_ID}@0.5", "video_id": VIDEO_ID, "start_s": 0.5, "end_s": 1.0, "kind": "frame", "quote_vi": "Cận cảnh tuýp kem chống nắng."}]
        content = {"video_id": VIDEO_ID, "risks_vi": [], "evidence": evidence,
                   "rubric": [{"criterion": c, "score": 3, "rationale_vi": "Tạm ổn.", "evidence_ids": [f"{VIDEO_ID}@0.5"]} for c in CRITERIA]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": COST[0]}})
    return httpx.MockTransport(handler)


@pytest.fixture
def smoke(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    seen = []
    real = factory.get_llm_client
    monkeypatch.setattr(factory, "get_llm_client", lambda *a, **kw: real(*a, http_client=httpx.Client(transport=_transport(seen)), **kw))
    module = _load()
    monkeypatch.setattr(module, "get_llm_client", factory.get_llm_client)
    media = tmp_path / "media"
    media.mkdir()
    _video(media / f"{VIDEO_ID}.mp4")
    return module, seen, media


def test_catalogue_filter_needs_image_and_audio_for_the_full_mode():
    module = _load()
    models = [{"id": "a/x:free", "architecture": {"input_modalities": ["text", "image", "audio"]}},
              {"id": "b/y:free", "architecture": {"input_modalities": ["text", "image"]}},
              {"id": "c/z", "architecture": {"input_modalities": ["text", "image", "audio"]}},
              {"id": "d/w:free", "architecture": {}}]
    assert module.free_candidates(models, need_audio=True) == ["a/x:free"]
    assert module.free_candidates(models, need_audio=False) == ["a/x:free", "b/y:free"]


def test_full_mode_sends_frames_and_audio_without_budget_and_passes(smoke, capsys):
    module, seen, media = smoke
    assert module.main(["--model", "x/y:free", "--video-id", VIDEO_ID, "--media-dir", str(media)]) == 0
    out = capsys.readouterr().out
    assert "RESULT PASS: frames + audio" in out and "NOT PROVEN" not in out
    kinds = [p["type"] for p in seen[0]["messages"][-1]["content"]]
    assert kinds.count("image_url") == 8 and kinds.count("input_audio") == 1
    assert not module.budget_leaks([p["text"] for p in seen[0]["messages"][-1]["content"] if p["type"] == "text"])


def test_no_audio_mode_sends_no_audio_part_and_says_what_is_unproven(smoke, capsys):
    module, seen, media = smoke
    assert module.main(["--model", "x/y:free", "--video-id", VIDEO_ID, "--media-dir", str(media), "--no-audio"]) == 0
    out = capsys.readouterr().out
    assert "NOT PROVEN by this run: audio input." in out
    assert "input_audio" not in [p["type"] for p in seen[0]["messages"][-1]["content"]]


def test_text_only_mode_uses_stored_evidence_and_never_opens_the_db_for_writing(smoke, capsys, tmp_path):
    module, seen, media = smoke
    db = tmp_path / "koc.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE analyses (video_id TEXT, prompt_version TEXT, model TEXT, analysis_json TEXT)")
    stored = {"evidence": [{"start_s": 0.5, "end_s": 1.0, "kind": "frame", "quote_vi": "Tuýp kem trên bàn."},
                           {"start_s": 2.0, "end_s": 3.0, "kind": "speech", "quote_vi": "Kem này nhẹ da."}]}
    conn.execute("INSERT INTO analyses VALUES (?,?,?,?)", (VIDEO_ID, "content_v3", "m", json.dumps(stored)))
    conn.commit()
    conn.close()
    assert module.main(["--model", "x/y:free", "--video-id", VIDEO_ID, "--text-only", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "NOT PROVEN by this run: frames and audio input." in out
    sent = json.dumps(seen[0], ensure_ascii=False)
    assert "Tuýp kem trên bàn." in sent and "image_url" not in sent
    assert not re.search(r"ngân sách|budget", sent, re.I)


def test_paid_model_is_refused():
    module = _load()
    with pytest.raises(AssertionError):
        module.main(["--model", "google/gemini-3.8-flash"])


def test_nonzero_cost_stops_with_exit_code_3(smoke, capsys, monkeypatch):
    module, seen, media = smoke
    COST[0] = 0.01
    try:
        with pytest.raises(SystemExit) as exc:
            module.main(["--model", "x/y:free", "--video-id", VIDEO_ID, "--media-dir", str(media)])
    finally:
        COST[0] = 0.0
    assert exc.value.code == 3
    assert "STOP: model reported cost" in capsys.readouterr().out
