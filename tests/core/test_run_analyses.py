import json
import sqlite3

from koc import db
from koc.benchmark import aggregate
from koc.web.adapter import get_creator_full_detail
from koc.web.api import _creator_detail


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    return c


def _seed(c, videos, analyses, breakdown=None):
    run = db.create_run(c, {"mock": False, "limit": 1})
    db.upsert_creator(c, "c", "c", {})
    for video_id in videos:
        db.upsert_video(c, video_id, "c", {})
    db.upsert_score(c, run, "c", "S3", 60, breakdown or {})
    for video_id, prompt in analyses:
        c.execute("INSERT INTO analyses VALUES (?,?,?,?)", (video_id, prompt, "google/gemini-3.8-flash", json.dumps({"video_id": video_id, "rubric": [], "evidence": []})))
    c.commit()
    return run


def _ids(c, run):
    return [(a[0], a[1]) for a in db.run_analyses(c, run, "c")]


def test_missing_run_results_table_is_not_a_crash():
    c = _conn()
    run = _seed(c, ["v"], [("v", "content_v3")])
    c.execute("DROP TABLE run_results")
    c.commit()
    c.execute("PRAGMA query_only=ON")
    assert _ids(c, run) == [("v", "content_v3")]


def test_historical_run_falls_back_to_newest_analysis():
    for prompt in ("content_v1", "content_v2", "content_v2_repair"):
        c = _conn()
        run = _seed(c, ["v"], [("v", prompt)])
        assert _ids(c, run) == [("v", prompt)]


def test_current_prompt_beats_newer_stale_row_but_listed_historical_rows_survive():
    c = _conn()
    run = _seed(c, ["v0", "v1"], [("v0", "content_v3"), ("v0", "content_v2"), ("v1", "content_v2")], {"video_ids": ["v0", "v1"]})
    assert _ids(c, run) == [("v0", "content_v3"), ("v1", "content_v2")]


def test_without_video_ids_stale_only_videos_dropped_when_current_exists():
    c = _conn()
    run = _seed(c, ["old0", "new0"], [("old0", "content_v1"), ("new0", "content_v3")])
    assert _ids(c, run) == [("new0", "content_v3")]


def _benchmark_fixture(prompt, drop_run_results=False):
    c = _conn()
    run = _seed(c, ["v"], [])
    c.execute("INSERT INTO analyses VALUES (?,?,?,?)", ("v", prompt, "m", "{}"))
    c.execute("INSERT INTO llm_cache(request_hash,output_json,usage_json,created_at) VALUES (?,?,?,?)", ("h", json.dumps({"video_id": "v"}), json.dumps({"prompt_version": prompt}), "t"))
    c.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (run, "content", "h", "m", prompt, 100, 10, 1, .01, 0, "t"))
    db.add_api_call(c, run, "video/url", db.cache_key("video/url", {"video_id": "v"}), "200", .5, 1, False)
    c.commit()
    if drop_run_results:
        c.execute("DROP TABLE run_results")
        c.commit()
        c.execute("PRAGMA query_only=ON")
    return c, run


def test_benchmark_legacy_schema_with_retained_content():
    c, run = _benchmark_fixture("content_v3", drop_run_results=True)
    assert aggregate(c, run)["totals_success"]["tokens_in"] == 100


def test_benchmark_historical_prompts_keep_successful_spend():
    for prompt in ("content_v1", "content_v2", "content_v2_repair"):
        c, run = _benchmark_fixture(prompt)
        result = aggregate(c, run)
        assert result["totals_success"]["credits"] == 0.5 and result["totals_success"]["tokens_in"] == 100, prompt
        assert result["waste"]["credits"] == 0 and result["success_estimated"], prompt


def test_detail_pages_list_the_videos_s3_selected():
    c = _conn()
    run = _seed(c, [f"old{i}" for i in range(3)] + [f"new{i}" for i in range(3)],
                [(f"old{i}", "content_v1") for i in range(3)] + [(f"new{i}", "content_v3") for i in range(3)],
                {"video_ids": ["new0", "new1", "new2"]})
    db.upsert_score(c, run, "c", "S1", 50, {})
    c.execute("INSERT INTO recommendations(run_id,creator_id,rank,est_cost_vnd,rec_json) VALUES (?,?,?,?,?)", (run, "c", 1, 1, "{}"))
    c.commit()
    web = get_creator_full_detail(c, run, "c")
    assert [v["video_id"] for v in web["videos"]] == ["new0", "new1", "new2"]
    api = _creator_detail(c, "c", run)
    assert [v["video_id"] for v in api["videos"]] == ["new0", "new1", "new2"]
