import json

from koc import db
from tests.analysis_seed import seed_brand_fit
from koc.pipeline import _best_five, _s4
from koc.stages import audience_is_placeholder, final_score, run_audience_is_placeholder

AUDIENCE_NAMES = ("female_pct", "age_18_24_pct", "age_25_34_pct")


def _seed(conn, tuples, analyses=True):
    run_id = db.create_run(conn, {})
    for index, values in enumerate(tuples):
        creator_id = f"c{index}"
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.upsert_score(conn, run_id, creator_id, "S1", 80, {})
        db.upsert_score(conn, run_id, creator_id, "S2", 50, {})
        db.upsert_score(conn, run_id, creator_id, "S3", 60, {})
        if analyses:
            seed_brand_fit(conn, creator_id)
        for name, value in zip(AUDIENCE_NAMES, values):
            db.upsert_metric(conn, creator_id, name, value, "test")
        db.upsert_metric(conn, creator_id, "video_gpm", 1000, "test")
    return run_id


def test_detection_rule():
    same = (55.0, 20.0, 30.0)
    assert audience_is_placeholder([same, same, same])
    assert not audience_is_placeholder([same, same])  # fewer than 3 creators
    assert not audience_is_placeholder([same, same, (56.0, 20.0, 30.0)])
    assert not audience_is_placeholder([(None, None, None)] * 4)
    assert audience_is_placeholder([(60.0, 30.5, 39.5)])  # known signature


def test_identical_distributions_are_placeholder_and_renormalised(tmp_path):
    conn = db.connect(tmp_path / "ph.db")
    db.init_db(conn)
    run_id = _seed(conn, [(60.0, 30.5, 39.5)] * 3)
    assert run_audience_is_placeholder(conn, run_id)
    rows = _best_five(conn, run_id)
    assert rows and all(item["scores"]["S2"] is None for item in rows)
    assert all(abs(item["final"] - (.45 * 80 + .35 * 60) / .80) < 1e-9 for item in rows)
    _s4(conn, run_id, mock=True)(conn)
    rec = json.loads(conn.execute("SELECT rec_json FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0])
    assert not any("Tệp người xem" in reason for reason in rec["reasons_vi"])
    assert any("Kalodata" in caveat for caveat in rec["caveats_vi"])
    assert not any(name in cited for cited in rec["cited_evidence_ids"] for name in AUDIENCE_NAMES)
    breakdown = conn.execute("SELECT breakdown_json FROM scores WHERE stage='S4' LIMIT 1").fetchone()[0]
    assert json.loads(breakdown)["audience"] is None


def test_candidate_summary_has_no_audience_metrics(tmp_path, monkeypatch):
    import koc.pipeline as pipeline
    conn = db.connect(tmp_path / "ph2.db")
    db.init_db(conn)
    run_id = _seed(conn, [(60.0, 30.5, 39.5)] * 3)
    seen = []
    real = pipeline.CandidateSummary
    monkeypatch.setattr(pipeline, "CandidateSummary", lambda **kw: seen.append(kw) or real(**kw))
    _s4(conn, run_id, mock=True)
    assert seen
    for kw in seen:
        assert kw["audience_score"] is None
        assert not set(AUDIENCE_NAMES) & set(kw["metrics"])
        assert not set(AUDIENCE_NAMES) & set(kw["metric_evidence_ids"])
        assert "video_gpm" in kw["metrics"]


def test_distinct_distributions_keep_original_weights(tmp_path):
    conn = db.connect(tmp_path / "real.db")
    db.init_db(conn)
    run_id = _seed(conn, [(60.0, 30.0, 40.0), (70.0, 25.0, 35.0), (80.0, 20.0, 30.0)])
    assert not run_audience_is_placeholder(conn, run_id)
    rows = _best_five(conn, run_id)
    assert rows and all(item["scores"]["S2"] == 50 for item in rows)
    assert all(abs(item["final"] - (.45 * 80 + .20 * 50 + .35 * 60)) < 1e-9 for item in rows)
    assert abs(final_score(80, 50, 60) - 67.0) < 1e-9


MIXED = [(60.0, 30.5, 39.5), (71.0, 20.0, 30.0), (72.0, 20.0, 30.0), (73.0, 20.0, 30.0), (74.0, 20.0, 30.0)]


def test_known_sample_capture_is_placeholder_per_creator_even_when_others_differ(tmp_path, monkeypatch):
    """F4: c0 holds the known sample signature, others are distinct real captures; only c0 loses audience."""
    import koc.pipeline as pipeline
    from koc.stages import placeholder_audience_creators

    conn = db.connect(tmp_path / "mixed.db")
    db.init_db(conn)
    run_id = _seed(conn, MIXED)
    assert not run_audience_is_placeholder(conn, run_id)  # run-level rule alone does not fire
    assert placeholder_audience_creators(conn, run_id) == {"c0"}

    rows = {item["id"]: item for item in _best_five(conn, run_id)}
    assert rows["c0"]["scores"]["S2"] is None
    assert abs(rows["c0"]["final"] - (.45 * 80 + .35 * 60) / .80) < 1e-9
    assert all(rows[f"c{i}"]["scores"]["S2"] == 50 for i in range(1, 5))
    assert all(abs(rows[f"c{i}"]["final"] - (.45 * 80 + .20 * 50 + .35 * 60)) < 1e-9 for i in range(1, 5))

    seen = {}
    real = pipeline.CandidateSummary
    monkeypatch.setattr(pipeline, "CandidateSummary", lambda **kw: seen.__setitem__(kw["creator_id"], kw) or real(**kw))
    _s4(conn, run_id, mock=True)(conn)
    assert seen["c0"]["audience_score"] is None
    assert not set(AUDIENCE_NAMES) & set(seen["c0"]["metrics"])
    assert not set(AUDIENCE_NAMES) & set(seen["c0"]["metric_evidence_ids"])
    assert seen["c1"]["audience_score"] == 50
    assert set(AUDIENCE_NAMES) <= set(seen["c1"]["metrics"])
    breakdowns = {row[0]: json.loads(row[1]) for row in conn.execute("SELECT creator_id,breakdown_json FROM scores WHERE stage='S4'")}
    assert breakdowns["c0"]["audience"] is None and breakdowns["c1"]["audience"] == 50


def test_web_adapter_follows_per_creator_placeholder_rule(tmp_path):
    from koc.web.adapter import get_creator_full_detail, get_finalists

    conn = db.connect(tmp_path / "mixed-web.db")
    db.init_db(conn)
    run_id = _seed(conn, MIXED)
    placeholder = get_creator_full_detail(conn, run_id, "c0")
    real = get_creator_full_detail(conn, run_id, "c1")
    assert placeholder["audience"]["placeholder"] is True
    assert placeholder["scores"]["audience"] is None
    assert not any(m["name"] in AUDIENCE_NAMES for m in placeholder["metrics"] if "name" in m)
    assert real["audience"]["placeholder"] is False
    assert real["scores"]["audience"] == 50
    finals = {row["creator_id"]: row for row in get_finalists(conn, run_id, set())}
    assert finals["c0"]["final_score"] == round((.45 * 80 + .35 * 60) / .80, 1)
    assert finals["c1"]["final_score"] == round(.45 * 80 + .20 * 50 + .35 * 60, 1)


class _StopBeforeLLM(Exception):
    pass


def _analysis(video_id, prompt_version):
    from koc.types import ContentAnalysis, Evidence, RubricScore, Usage
    usage = Usage(provider="gemini", model="google/gemini-3.8-flash", prompt_version=prompt_version, input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0)
    evidence = [Evidence(evidence_id=f"{video_id}@{prompt_version}", video_id=video_id, start_s=1, end_s=None, kind="speech", quote_vi="x", frame_path=None)]
    rubric = [RubricScore(criterion=name, score=3, rationale_vi="x", evidence_ids=[evidence[0].evidence_id]) for name in ("hook", "product_clarity", "demonstration", "claim_quality", "cta", "brand_fit", "production_quality")]
    return ContentAnalysis(video_id=video_id, transcript_vi=None, rubric=rubric, risks_vi=[], evidence=evidence, usage=usage)


def _s4_analyses(tmp_path, monkeypatch, rows, results=(), video_ids=None):
    """Prompt versions of the analyses S4 would send for creator c0 (non-mock, LLM call stubbed out)."""
    import koc.pipeline as pipeline
    conn = db.connect(tmp_path / "sel.db")
    db.init_db(conn)
    run_id = _seed(conn, [(60.0, 30.5, 39.5)] * 3, analyses=False)  # the test seeds its own analyses for c0
    for n in range(3):
        db.upsert_video(conn, f"v{n}", "c0", {}, "x.mp4")
    for video_id, prompt in rows:
        conn.execute("INSERT INTO analyses VALUES (?,?,?,?)", (video_id, prompt, "google/gemini-3.8-flash", _analysis(video_id, prompt).model_dump_json()))
    for video_id, prompt in results:
        conn.execute("INSERT INTO run_results(run_id,kind,subject,model,prompt_version) VALUES (?,'content',?,?,?)", (run_id, video_id, "google/gemini-3.8-flash", prompt))
    conn.commit()
    seen = {}
    real = pipeline.CandidateSummary

    def spy(**kw):
        summary = real(**kw)
        seen[kw["creator_id"]] = summary
        return summary

    def stop(*args, **kwargs):
        raise _StopBeforeLLM

    monkeypatch.setattr(pipeline, "CandidateSummary", spy)
    monkeypatch.setattr(pipeline, "_cached_call", stop)
    try:
        _s4(conn, run_id, mock=False)
    except _StopBeforeLLM:
        pass
    return sorted((a.video_id, a.usage.prompt_version) for a in seen["c0"].analyses)


def test_s4_drops_stale_analyses_without_run_results(tmp_path, monkeypatch):
    rows = [(f"v{n}", p) for n in range(3) for p in ("content_v1", "content_v2", "content_v3")]
    assert _s4_analyses(tmp_path, monkeypatch, rows) == [(f"v{n}", "content_v3") for n in range(3)]


def test_s4_keeps_repair_analysis_and_drops_stale(tmp_path, monkeypatch):
    rows = [("v0", "content_v2"), ("v0", "content_v3_repair"), ("v1", "content_v1"), ("v1", "content_v3"), ("v2", "content_v2_repair"), ("v2", "content_v3")]
    assert _s4_analyses(tmp_path, monkeypatch, rows) == [("v0", "content_v3_repair"), ("v1", "content_v3"), ("v2", "content_v3")]


def test_s4_uses_run_results_pick(tmp_path, monkeypatch):
    rows = [("v0", "content_v1"), ("v0", "content_v3"), ("v1", "content_v3"), ("v1", "content_v3_repair")]
    got = _s4_analyses(tmp_path, monkeypatch, rows, results=[("v0", "content_v3"), ("v1", "content_v3_repair")])
    assert got == [("v0", "content_v3"), ("v1", "content_v3_repair")]
