"""S3 content-prompt smoke test on a free OpenRouter model: 0 USD, no DB writes, no Kalodata call.

Runs the real koc.llm.content.analyze_video (prompts/content_v3.md without the budget line, 8 JPEG frames + audio,
the ContentAnalysisPayload JSON schema, the same validator and one repair retry) on ONE already downloaded video,
with a :free model instead of the paid one. Only OpenRouter is called (plus the public model list when no model is given).

Modes
  full        frames + audio, the exact input of the paid stage (needs a :free model with image AND audio input)
  --no-audio  frames only: the video is re-muxed without sound, so the prompt takes its "no audio" branch.
              Proves prompt + schema + frames; does NOT prove the audio input path.
  --text-only no media: frame descriptions and speech quotes from a stored content_v3 analysis stand in for the frames.
              Proves only that the current prompt + schema yield valid JSON from text; does NOT prove the model can see
              frames or hear audio, nor the quality of a free model's scores.

Usage (from the repo root, key entered with read -s):
  OPENROUTER_API_KEY=... python scripts/s3_free_smoke.py [--model ID:free] [--video-id ID] [--no-audio | --text-only]
Without --model the script lists :free models from the public OpenRouter catalogue that accept the needed input
and tries up to three of them. Exit 0 and "RESULT PASS" only when a model returned JSON that passed the validator.
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from koc.brief import brand_brief, make_brief  # noqa: E402
from koc.config import load_config  # noqa: E402
from koc.llm import content  # noqa: E402
from koc.llm.factory import get_llm_client  # noqa: E402
from koc.types import VideoInput  # noqa: E402

DEFAULT_VIDEO = "7701594488619191573"  # @meixiuriviu, on-topic sunscreen video, 4.9 MB, already analysed in the live run
CATALOGUE = "https://openrouter.ai/api/v1/models"
BUDGET_WORDS = ("ngân sách", "ngan sach", "budget", "vnd", "30000000", "30.000.000")


class FreeGuard:
    """Refuses any call that reports a cost above zero."""
    total = 0.0

    def check(self, estimated_usd):
        pass

    def record(self, usage):
        self.total += usage.cost_usd
        if usage.cost_usd > 0:
            print(f"STOP: model reported cost {usage.cost_usd} USD", flush=True)
            raise SystemExit(3)


class Spy:
    """Wraps the client and keeps every text part sent, to prove the budget is not in the prompt."""
    def __init__(self, client):
        self.client, self.texts = client, []

    def __getattr__(self, name):
        return getattr(self.client, name)

    def generate_json(self, contents, *args, **kwargs):
        self.texts += [c for c in contents if isinstance(c, str)]
        return self.client.generate_json(contents, *args, **kwargs)


def free_candidates(models, need_audio):
    """Free model ids whose input modalities include image (and audio when need_audio). Pure; takes the catalogue list."""
    need = {"image", "audio"} if need_audio else {"image"}
    found = []
    for model in models:
        modalities = set((model.get("architecture") or {}).get("input_modalities") or [])
        if str(model.get("id", "")).endswith(":free") and need <= modalities:
            found.append(model["id"])
    return found


def build_client(model, tmp):
    cfg = yaml.safe_load((ROOT / "config/llm_prices.yaml").read_text())
    cfg["models"][model] = {"id": model, "name": f"{model} (smoke test)", "provider": "openrouter",
                            "pricing_per_1m": {"input_usd": 0.0, "output_usd": 0.0}}
    # free models think before answering; give them room (still 0 USD)
    cfg["token_accounting"]["default_content_output_tokens"] = 16384
    path = Path(tmp) / "llm_prices.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    return get_llm_client(model=model, config_path=path)


def video_input(video_id, mp4):
    return VideoInput(video_id=video_id, creator_id="smoke", title="kem chống nắng (smoke test)", publish_date=None,
                      views=1000, likes=100, comments=10, shares=5, revenue_vnd=None, mp4_path=str(mp4))


def run_media(client, guard, video_id, mp4, tmp):
    """Real stage path. Returns (ContentAnalysis, prompt text parts)."""
    spy = Spy(client)
    analysis = content.analyze_video(video_input(video_id, mp4), brand_brief(make_brief(load_config())),
                                     budget_guard=guard, client=spy, frames_dir=str(Path(tmp) / "frames"))
    return analysis, spy.texts


def strip_audio(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an", "-c:v", "copy", str(dst)], check=True)
    return dst


def run_text_only(client, guard, video_id, db_path):
    """Prompt + schema check on text: stored frame/speech evidence replaces the media. Returns (payload, validation errors, texts)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    row = conn.execute("SELECT analysis_json FROM analyses WHERE video_id=? AND prompt_version='content_v3' LIMIT 1", (video_id,)).fetchone()
    conn.close()
    if not row:
        raise SystemExit(f"STOP: no stored content_v3 analysis for video {video_id} in {db_path}")
    stored = json.loads(row[0])
    evidence = stored.get("evidence", [])
    duration = max([e.get("end_s") or e["start_s"] for e in evidence] + [1.0]) + 1.0
    brief = brand_brief(make_brief(load_config()))
    prompt = content.PROMPT_FILE.read_text(encoding="utf-8").format(
        product_vi=brief.product_vi, audience_vi=brief.audience_vi, video_id=video_id,
        title="kem chống nắng (smoke test)", views=1000, likes=100, comments=10, shares=5)
    frames = "\n".join(f"- {e['start_s']}s: {e['quote_vi']}" for e in evidence if e["kind"] == "frame")
    speech = "\n".join(f"- {e['start_s']}s: {e['quote_vi']}" for e in evidence if e["kind"] == "speech")
    contents = [prompt, "KIỂM TRA VĂN BẢN: không có ảnh. Mô tả các khung hình thay cho ảnh (dùng đúng mốc thời gian để tạo evidence_id):\n" + frames,
                "Lời nói trong audio (thay cho âm thanh):\n" + (speech or "(không có)")]
    spy = Spy(client)
    raw, usage = spy.generate_json(contents=contents, response_schema=content.ContentAnalysisPayload, prompt_version="content_v3",
                                   max_output_tokens=16384, budget_guard=guard, upper_bound_usd=0.0, initial_check_done=True, est_tokens=sum(len(c.encode()) for c in contents))
    guard.record(usage)
    payload = content.enforce_payload_limits(content.dedupe_payload(content.ContentAnalysisPayload.model_validate_json(raw)))
    return payload, content._validate_payload(payload, video_id, duration, has_audio=bool(speech)), spy.texts


def budget_leaks(texts):
    joined = "\n".join(texts).lower()
    return [word for word in BUDGET_WORDS if word in joined]


def candidates(args):
    if args.model:
        return [args.model]
    models = httpx.get(CATALOGUE, timeout=30).json().get("data", [])
    found = free_candidates(models, need_audio=not args.no_audio)
    print(f"{len(found)} :free model(s) with {'image+audio' if not args.no_audio else 'image'} input: {found[:10]}")
    if not found:
        print("No :free model accepts this input. Re-run with --no-audio (frames only), then --text-only.")
        raise SystemExit(2)
    return found[:3]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="a :free OpenRouter model id")
    parser.add_argument("--video-id", default=DEFAULT_VIDEO)
    parser.add_argument("--media-dir", default="data/media")
    parser.add_argument("--db", default="data/koc.db", help="only for --text-only; opened read-only")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--no-audio", action="store_true")
    mode.add_argument("--text-only", action="store_true")
    args = parser.parse_args(argv)
    if args.model:
        assert args.model.endswith(":free"), "smoke test only runs on :free models"
    label = "text-only" if args.text_only else "frames-only (no audio)" if args.no_audio else "frames + audio"
    mp4 = Path(args.media_dir) / f"{args.video_id}.mp4"
    if not args.text_only and not mp4.exists():
        print(f"STOP: {mp4} missing; run from the repo root or pass --media-dir")
        return 2
    tmp = tempfile.mkdtemp(prefix="s3_smoke_")
    try:
        for model in candidates(args):
            guard = FreeGuard()
            print(f"\n== {model}  mode: {label}  video {args.video_id}")
            try:
                client = build_client(model, tmp)
                if args.text_only:
                    payload, errors, texts = run_text_only(client, guard, args.video_id, args.db)
                    scores = {r.criterion: r.score for r in payload.rubric}
                    evidence_n = len(payload.evidence)
                else:
                    source = strip_audio(mp4, Path(tmp) / "silent.mp4") if args.no_audio else mp4
                    analysis, texts = run_media(client, guard, args.video_id, source, tmp)
                    errors, scores, evidence_n = [], {r.criterion: r.score for r in analysis.rubric}, len(analysis.evidence)
            except SystemExit:
                raise
            except Exception as exc:  # model refused the input, bad JSON after repair, HTTP error
                print(f"  FAIL: {type(exc).__name__}: {str(exc)[:300]}")
                continue
            leaks = budget_leaks(texts)
            print(f"  rubric {scores}\n  evidence {evidence_n}, validator errors {errors}, budget words in prompt {leaks}, cost {guard.total} USD")
            if not errors and not leaks and len(scores) == 7 and evidence_n and guard.total == 0:
                print(f"\nRESULT PASS: {label}, model {model}, cost 0 USD")
                if args.text_only or args.no_audio:
                    print("NOT PROVEN by this run: " + ("frames and audio input." if args.text_only else "audio input."))
                return 0
        print("\nRESULT FAIL: no candidate model produced valid output")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
