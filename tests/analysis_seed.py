from koc import db
from koc.types import ContentAnalysis, Evidence, RubricScore, Usage

CRITERIA = ("hook", "product_clarity", "demonstration", "claim_quality", "cta", "brand_fit", "production_quality")


def seed_brand_fit(conn, creator_id, score=5, video_id=None, prompt_version="content_v3"):
    """Give a synthetic creator one analysed video with rubric brand_fit=score, so the real D-B7 gate sees evidence.

    Fixtures that write S1/S2/S3 scores by hand have no pipeline-made analyses; call this after the scores.
    The row is a valid ContentAnalysis, so S4 can read it.
    """
    video_id = video_id or f"{creator_id}-seed-video"
    usage = Usage(provider="gemini", model="seed-model", prompt_version=prompt_version, input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0)
    evidence = Evidence(evidence_id=f"{video_id}@1.0s", video_id=video_id, start_s=1, end_s=None, kind="speech", quote_vi="x", frame_path=None)
    rubric = [RubricScore(criterion=name, score=score if name == "brand_fit" else 3, rationale_vi="x", evidence_ids=[evidence.evidence_id]) for name in CRITERIA]
    analysis = ContentAnalysis(video_id=video_id, transcript_vi=None, rubric=rubric, risks_vi=[], evidence=[evidence], usage=usage)
    db.upsert_video(conn, video_id, creator_id, {"video_id": video_id})
    with db.transaction(conn):
        conn.execute("INSERT OR REPLACE INTO analyses VALUES (?,?,?,?)", (video_id, prompt_version, "seed-model", analysis.model_dump_json()))
    return video_id
