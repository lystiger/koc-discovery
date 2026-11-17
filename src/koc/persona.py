"""Persona fit (approach C of docs/eval/COST_EFFICIENCY.md): does the creator in each analysed video match the brief's
target audience by apparent age, style and how they address viewers?

  run's S3 videos (same 3 per KOC as B) --> 8 frames + audio --> model --> score 1-5 per video
  KOC persona = mean of its video scores x 20 (0-100, same scale as S3)
  C final = (45 x S1 + 20 x persona + 35 x S3) / 100; brand-fit gate and budget selection unchanged

The S3 analyses are reused unchanged, so C differs from B only by the persona weight. Results live in table
`persona_fit`; a rerun with stored rows makes 0 calls. Calls are logged with run_id NULL, kind "persona", like the
faithfulness pass, so the run's own reports stay untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from . import db
from .brief import brand_brief, run_brief
from .budget_guard import BudgetGuard
from .config import load_config
from .llm.guard import DATA_NOTICE_VI, fence
from .llm.pricing import estimate_tokens_and_usd, load_pricing_config
from .types import CacheOnlyMiss

PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "persona_v1.md"
PROMPT_VERSION = "persona_v1"
KIND = "persona"
OUTPUT_TOKENS = 600
SCHEMA = """CREATE TABLE IF NOT EXISTS persona_fit (run_id TEXT NOT NULL, video_id TEXT NOT NULL, creator_id TEXT NOT NULL,
model TEXT NOT NULL, prompt_version TEXT NOT NULL, score INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
PRIMARY KEY(run_id,video_id,model,prompt_version))"""



class PersonaPayload(BaseModel):
    video_id: str
    apparent_age_vi: str
    style_vi: str
    audience_signals_vi: str
    score: int = Field(ge=1, le=5)
    rationale_vi: str


def videos(conn, run_id: str, media_dir: Path = Path("data/media")) -> list[dict]:
    """The run's analysed videos (the same picks B used), with their local mp4 path."""
    out = []
    for (cid, handle) in conn.execute("SELECT s.creator_id, c.handle FROM scores s JOIN creators c USING(creator_id) "
                                      "WHERE s.run_id=? AND s.stage='S3' ORDER BY c.handle", (run_id,)):
        for vid, *_ in db.run_analyses(conn, run_id, cid):
            row = conn.execute("SELECT data_json FROM videos WHERE video_id=?", (vid,)).fetchone()
            title = json.loads(row[0]).get("video_title") if row else None
            out.append({"creator_id": cid, "handle": handle, "video_id": vid, "title": title, "mp4": media_dir / f"{vid}.mp4"})
    return out


def stored(conn, run_id: str, model: str) -> dict[str, dict]:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='persona_fit'").fetchone():
        return {}
    rows = conn.execute("SELECT video_id, score, payload_json FROM persona_fit WHERE run_id=? AND model=? AND prompt_version=?",
                        (run_id, model, PROMPT_VERSION)).fetchall()
    return {v: {"score": s, **json.loads(p)} for v, s, p in rows}


def _prompt(video: dict, brief) -> str:
    return PROMPT_FILE.read_text(encoding="utf-8").format(product_vi=brief.product_vi, audience_vi=brief.audience_vi,
                                                          video_id=video["video_id"], title=fence(video["title"], 200))


def estimate(conn, run_id: str, model: str, config_path=None) -> dict:
    """Calls and estimated USD for videos without a stored result (not a bound). Read only, no network."""
    brief = brand_brief(run_brief(conn, run_id, load_config()))
    done = stored(conn, run_id, model)
    todo = [v for v in videos(conn, run_id) if v["video_id"] not in done]
    usd = 0.0
    for v in todo:
        cap = float(load_pricing_config(config_path).get("token_accounting", {}).get("max_analyzed_seconds", 90))
        _, c = estimate_tokens_and_usd(n_frames=8, audio_s=cap, est_output_tokens=OUTPUT_TOKENS, config_path=config_path,
                                       text_parts=[_prompt(v, brief), DATA_NOTICE_VI], response_schema=PersonaPayload,
                                       has_audio=True, model=model)
        usd += c
    missing = [v["video_id"] for v in todo if not v["mp4"].exists()]
    # An estimate, not a bound: image tiles depend on frame sizes known only after preprocessing.
    # "usd_with_retries" allows the one schema retry per video that _call permits.
    return {"calls": len(todo), "usd": usd, "usd_with_retries": 2 * usd, "stored": len(done), "missing_media": missing}


def _call(video: dict, brief, client, guard, config_path) -> PersonaPayload:
    from .llm.gemini import create_part_from_audio, create_part_from_image
    from .llm.media import preprocess_video
    work = Path("data/media/frames") / video["video_id"]
    work.mkdir(parents=True, exist_ok=True)
    media = preprocess_video(str(video["mp4"]), str(work), n_frames=8)
    contents: list[object] = [_prompt(video, brief), DATA_NOTICE_VI]
    for frame in media["frames"]:
        contents += [f"Frame at {frame['t_s']}s:", create_part_from_image(frame["path"])]
    audio = media.get("audio_path")
    has_audio = bool(audio) and Path(audio).is_file() and Path(audio).stat().st_size > 0
    if has_audio:
        contents += ["Full video audio:", create_part_from_audio(Path(audio))]
    model = getattr(client, "model", None)
    errors: list[str] = []
    for _ in range(2):
        call = contents + ([f"Lần trước không hợp lệ: {'; '.join(errors)}. Trả về đúng một JSON hợp lệ."] if errors else [])
        est_tokens, est_usd = estimate_tokens_and_usd(
            n_frames=len(media["frames"]), audio_s=float(media["duration_s"]) if has_audio else 0.0,
            est_output_tokens=OUTPUT_TOKENS, config_path=config_path, frame_sizes=[(f["width"], f["height"]) for f in media["frames"]],
            text_parts=[c for c in call if isinstance(c, str)], response_schema=PersonaPayload, has_audio=has_audio, model=model)
        guard.check(est_usd)
        raw, usage = client.generate_json(contents=call, response_schema=PersonaPayload, prompt_version=PROMPT_VERSION,
                                          max_output_tokens=OUTPUT_TOKENS, budget_guard=guard, upper_bound_usd=est_usd,
                                          initial_check_done=True, est_tokens=est_tokens)
        guard.record(usage)
        try:
            payload = PersonaPayload.model_validate_json(raw)
        except Exception as exc:  # JSON or schema error, including score outside 1-5
            errors = [str(exc)[:200]]
            continue
        if payload.video_id != video["video_id"]:
            errors = [f"video_id phải là {video['video_id']}"]
            continue
        return payload
    raise ValueError(f"Kết quả persona không hợp lệ cho video {video['video_id']}: {'; '.join(errors)}")


def evaluate(conn, run_id: str, client=None, *, model: str | None = None, cache_only: bool = False,
             cap_usd: float | None = None, config_path=None) -> dict:
    """Score every analysed video of the run. Stored videos cost 0 calls. Returns per-KOC persona (0-100) and spend."""
    conn.execute(SCHEMA)
    if client is None and not cache_only:
        from .llm.factory import get_llm_client
        client = get_llm_client(model=model, config_path=config_path)
    name = getattr(client, "model", None) or model or load_pricing_config(config_path).get("model", {}).get("id", "cache")
    brief = brand_brief(run_brief(conn, run_id, load_config()))
    done = stored(conn, run_id, name)
    guard = BudgetGuard(conn, cap_usd=cap_usd, run_id=None, kind=KIND)
    spent_before = guard._spent()
    calls = 0
    for v in videos(conn, run_id):
        if v["video_id"] in done:
            continue
        if cache_only:
            raise CacheOnlyMiss(f"persona của video {v['video_id']}")
        if not v["mp4"].exists():
            raise FileNotFoundError(f"Thiếu tệp video {v['mp4']}")
        guard.request_hash = call_tag(run_id, v["video_id"])  # every attempt, failed or not, carries this tag
        payload = _call(v, brief, client, guard, config_path)
        calls += 1
        with db.transaction(conn):
            conn.execute("INSERT OR REPLACE INTO persona_fit VALUES (?,?,?,?,?,?,?,?)",
                         (run_id, v["video_id"], v["creator_id"], name, PROMPT_VERSION, payload.score,
                          payload.model_dump_json(), db.now()))
    return {"per_koc": per_koc(conn, run_id, name), "calls": calls, "usd": guard._spent() - spent_before, "model": name}


def per_koc(conn, run_id: str, model: str) -> dict[str, float]:
    """creator_id -> mean video persona score x 20 (0-100)."""
    rows = conn.execute("SELECT creator_id, AVG(score) FROM persona_fit WHERE run_id=? AND model=? AND prompt_version=? "
                        "GROUP BY creator_id", (run_id, model, PROMPT_VERSION)).fetchall()
    return {cid: avg * 20 for cid, avg in rows}


def coverage(conn, run_id: str, model: str) -> tuple[int, int]:
    """(videos with a stored score, videos the run analysed) for one model and prompt version."""
    want = {v["video_id"] for v in videos(conn, run_id)}
    return len(want & set(stored(conn, run_id, model))), len(want)


def call_tag(run_id: str, video_id: str) -> str:
    return f"{KIND}:{run_id}:{video_id}"


def spend(conn, run_id: str, model: str) -> dict:
    """Cost of every persona call tagged with this run (all attempts, across resumes), for one model.

    Calls made before tagging existed have an empty request_hash and cannot be attributed to a run: they are counted
    separately as "untagged" and `exact` is False when any exist for this model."""
    tagged = conn.execute("SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(latency_ms),0), COUNT(*) FROM llm_calls "
                          "WHERE kind=? AND model=? AND cache_hit=0 AND request_hash LIKE ?",
                          (KIND, model, f"{KIND}:{run_id}:%")).fetchone()
    untagged = conn.execute("SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(latency_ms),0), COUNT(*) FROM llm_calls "
                            "WHERE kind=? AND model=? AND cache_hit=0 AND request_hash=''", (KIND, model)).fetchone()
    return {"usd": tagged[0], "seconds": tagged[1] / 1000, "calls": tagged[2], "exact": untagged[2] == 0,
            "untagged": {"usd": untagged[0], "seconds": untagged[1] / 1000, "calls": untagged[2]}}


def c_final(s1: float, persona: float, s3: float) -> float:
    return (45 * s1 + 20 * persona + 35 * s3) / 100
