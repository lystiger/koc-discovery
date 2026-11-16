import json
import time

import pytest

from koc import db
from koc.types import BudgetExceeded, ProviderAccountError
from koc.pipeline import _advance, _cached_call, capture_audience, execute, start
from koc.report import benchmark, spearman, write_benchmark
from koc.stages import audience_score, parse_audience_text
from koc.types import BrandBrief, Usage
from tests.analysis_seed import seed_brand_fit


def _seed_s4_inputs(conn, run_id, creator_ids):
    for creator_id in creator_ids:
        db.upsert_score(conn, run_id, creator_id, "S1", 80, {})
        db.upsert_score(conn, run_id, creator_id, "S2", 80, {})
        seed_brand_fit(conn, creator_id)
        conn.execute("INSERT INTO metrics(creator_id,name,value,collected_at) VALUES (?,?,?,?)", (creator_id, "female_pct", "70", db.now()))
    conn.commit()


def test_audience_parser_strips_private_use_glyphs_and_scores_target_segments():
    result = parse_audience_text("Female\n70%\nAge\n18-24\n30%\n25-34\n40%\n35-44\n20%\nTop 5 Locations\ue000")
    assert result == {"female_pct": 70.0, "age_18_24_pct": 30.0, "age_25_34_pct": 40.0}
    assert audience_score(result) == 70.0


def test_audience_parser_accepts_vietnamese_labels():
    assert parse_audience_text("Nữ\n70%\nĐộ tuổi\n18-24\n30%\n25-34\n40%") == {
        "female_pct": 70.0, "age_18_24_pct": 30.0, "age_25_34_pct": 40.0,
    }


def test_supervised_capture_waits_and_rejects_access_limit():
    class Page:
        url = ""
        def goto(self, url): self.url = url
        def wait_for_timeout(self, _): pass
        def inner_text(self, _): return "Female\n70%\nAge\n18-24\n20%\nTop 5 Locations"

    pauses = []
    result, source, _ = capture_audience(Page(), "creator-1", time.monotonic() - 1, sleep=pauses.append)
    assert pauses and pauses[0] >= 3.9
    assert result["female_pct"] == 70
    assert source.endswith("id=creator-1")

    class Denied(Page):
        def inner_text(self, _): return "Trial accounts are allowed"

    try:
        capture_audience(Denied(), "creator-2")
    except PermissionError:
        pass
    else:
        raise AssertionError("access-limit page must stop capture")


def test_mock_run_is_resumable_cached_and_writes_five_recommendations(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "koc.db")
    db.init_db(conn)
    run_id = start(conn, limit=20, mock=True)
    before = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
              for table in ("tasks", "videos", "analyses", "recommendations", "llm_calls", "api_calls")}
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S1'", (run_id,)).fetchone()[0] == 20
    assert conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S3'", (run_id,)).fetchone()[0] == 15
    from koc.pipeline import _best_five
    for creator_id in ("1", "2", "3", "4", "5", "6"):
        row = conn.execute("SELECT data_json FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
        profile = json.loads(row[0]); profile["mcn_id"] = "shared-mcn"
        db.upsert_creator(conn, creator_id, f"koc{creator_id}", profile)
    picks = _best_five(conn, run_id)
    assert sum(item["profile"].get("mcn_id") == "shared-mcn" for item in picks) <= 1
    assert len(picks) == 5

    second_run = start(conn, limit=20, mock=True)
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (second_run,)).fetchone()[0] == 5
    assert conn.execute("SELECT SUM(input_tokens+output_tokens) FROM llm_calls WHERE run_id=?", (second_run,)).fetchone()[0] == 0
    assert conn.execute("SELECT SUM(cost_usd) FROM llm_calls WHERE run_id=?", (second_run,)).fetchone()[0] == 0
    assert conn.execute("SELECT SUM(cache_hit) FROM llm_calls WHERE run_id=?", (second_run,)).fetchone()[0] > 0

    report = benchmark(conn, second_run)
    assert report["candidates"] == {"input": 20, "finalists": 15, "recommended": 5}
    assert report["stages"]["S3"]["candidates_out"] == 15
    assert report["projection_500"]["candidates"] == 500
    write_benchmark(conn, second_run)
    assert (tmp_path / "reports/benchmark.json").exists()
    assert "Ước tính cho 500 ứng viên" in (tmp_path / "docs/BENCHMARK.md").read_text()

    from koc.pipeline import resume
    completed = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                 for table in before}
    resume(conn, mock=True)
    after = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
             for table in before}
    assert after == completed
    assert spearman([1, 2, 3], [1, 2, 3]) == 1.0
    assert spearman([1], [1]) is None


def test_mock_run_writes_s2_metrics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "mock.db")
    db.init_db(conn)
    run_id = start(conn, limit=20, mock=True)
    names = {row[0] for row in conn.execute(
        "SELECT DISTINCT name FROM metrics WHERE name IN ('female_pct','age_18_24_pct','age_25_34_pct')"
    )}
    assert names == {"female_pct", "age_18_24_pct", "age_25_34_pct"}
    assert conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S2'", (run_id,)).fetchone()[0] > 0


def test_page_path_creates_audience_tasks_and_writes_metrics(tmp_path, monkeypatch):
    import koc.pipeline as pipeline

    conn = db.connect(tmp_path / "page.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 1, "mock": False})
    db.upsert_creator(conn, "c1", "creator", {"creator_followers": 30000})
    db.upsert_score(conn, run_id, "c1", "S1", 50, {})
    db.add_task(conn, run_id, "S1b", "c1")
    conn.execute("UPDATE tasks SET status='done' WHERE task_id=?", (f"{run_id}:S1b:c1",))
    conn.commit()
    page = object()
    _advance(conn, run_id, None, 1, page, False, None)
    tasks = conn.execute("SELECT stage,key FROM tasks WHERE run_id=? AND stage='S2'", (run_id,)).fetchall()
    assert [(row["stage"], row["key"]) for row in tasks] == [("S2", "c1")]

    class FakePage:
        def goto(self, _url): pass
        def wait_for_timeout(self, _delay): pass
        def inner_text(self, _selector): return "Female\n70%\nAge\n18-24\n30%\n25-34\n40%\nTop 5 Locations"

    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    execute(conn, run_id, object(), 1, page=FakePage(), media_dir=tmp_path / "media")
    names = {row[0] for row in conn.execute(
        "SELECT name FROM metrics WHERE creator_id='c1' AND name IN ('female_pct','age_18_24_pct','age_25_34_pct')"
    )}
    assert names == {"female_pct", "age_18_24_pct", "age_25_34_pct"}


def test_successful_s2_views_keep_charges_and_enforce_cumulative_cap(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline
    from koc.kalodata import CreditCounter

    conn = db.connect(tmp_path / "s2-credit-cap.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    db.add_task(conn, run_id, "S2", "c1")
    db.add_task(conn, run_id, "S2", "c2")

    class Client:
        counter = CreditCounter(conn, cap=1)

    class Page:
        def goto(self, _url): pass
        def wait_for_timeout(self, _delay): pass
        def inner_text(self, _selector): return "Female\n70%\nAge\n18-24\n30%\n25-34\n40%\nTop 5 Locations"

    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, Client(), 1, page=Page(), media_dir=tmp_path / "media")

    assert conn.execute("SELECT SUM(credits) FROM api_calls").fetchone()[0] == 1
    assert [tuple(row) for row in conn.execute("SELECT status,credits FROM api_calls ORDER BY id")] == [("200", 1)]
    assert [tuple(row) for row in conn.execute("SELECT key,status FROM tasks ORDER BY rowid")] == [("c1", "done"), ("c2", "blocked")]


def test_empty_s2_capture_blocks_run_keeps_charge_and_stops_after_first_page(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline
    from koc.kalodata import CreditCounter

    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "empty-s2.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    db.add_task(conn, run_id, "S2", "c1")
    db.add_task(conn, run_id, "S2", "c2")

    class Client:
        counter = CreditCounter(conn, cap=1)

    class Page:
        visits = 0
        def goto(self, _url): self.visits += 1
        def wait_for_timeout(self, _delay): pass
        def inner_text(self, _selector): return "Audience demographics unavailable"

    page = Page()
    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, Client(), 1, page=page, media_dir=tmp_path / "media")

    assert page.visits == 1
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    assert tuple(conn.execute("SELECT key,status,error FROM tasks ORDER BY rowid").fetchone()) == (
        "c1", "blocked", "Không đọc được dữ liệu khán giả từ trang Kalodata; đã dừng để tránh lưu điểm sai."
    )
    assert conn.execute("SELECT status,credits FROM api_calls").fetchone()[:] == ("capture_empty", 1)
    assert conn.execute("SELECT status FROM tasks WHERE key='c2'").fetchone()[0] == "pending"
    assert conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM scores WHERE stage='S2'").fetchone()[0] == 0


def test_s3_not_ready_blocks_only_creator_and_continues_to_score_threshold(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline
    from koc.kalodata import KalodataNotReady

    stable_test_config["s1"]["recommendation_count"] = 2
    conn = db.connect(tmp_path / "s3-not-ready.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    for creator_id in ("c1", "c2", "c3"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.add_task(conn, run_id, "S3", creator_id)
    _seed_s4_inputs(conn, run_id, ("c1", "c2", "c3"))

    def s3(conn, run_id, _client, creator_id, *_args):
        if creator_id == "c1":
            raise KalodataNotReady()
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    monkeypatch.setattr(pipeline, "_s3_creator", s3)
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, object(), 1, media_dir=tmp_path / "media")

    assert [tuple(row) for row in conn.execute("SELECT key,status,error FROM tasks WHERE stage='S3' ORDER BY rowid")] == [
        ("c1", "blocked", "blocked: video Kalodata chưa sẵn sàng"),
        ("c2", "done", None), ("c3", "done", None),
    ]
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"
    assert db.get_task(conn, f"{run_id}:S4:select")["status"] == "done"


def test_provider_account_error_stops_s3_and_resume_retries_pending_creator(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline
    from koc import llm
    from koc.llm import content
    from koc.llm.openrouter import OpenRouterClient
    import httpx

    stable_test_config["s1"]["recommendation_count"] = 1
    conn = db.connect(tmp_path / "provider-account.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 1})
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.add_task(conn, run_id, "S3", creator_id)
    _seed_s4_inputs(conn, run_id, ("c1", "c2"))

    class Client:
        def __init__(self): self.video_urls = []
        def video_rank(self, creator_id, **_kwargs):
            return {"data": [{"video_id": f"{creator_id}-v1", "revenue": 1}]}
        def video_url(self, video_id):
            self.video_urls.append(video_id)
            db.add_api_call(conn, run_id, "video/url", video_id, "200", 0.5, 0, False)
            return {"data": {"video_url": "mock://video"}}

    client = Client()
    transport = httpx.MockTransport(lambda _request: httpx.Response(402, json={"error": {"message": "requires at least $0.50 in balance for audio"}}))
    llm_client = OpenRouterClient(api_key="test-key", http_client=httpx.Client(transport=transport))
    monkeypatch.setattr(content, "get_llm_client", lambda: llm_client)
    monkeypatch.setattr(pipeline, "KalodataClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr(content, "preprocess_video", lambda *_args, **_kwargs: {"frames": [], "duration_s": 1, "audio_path": None})
    def download(c, vid, target, _mock=False, **_kwargs):
        c.video_url(vid)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"video")
        return str(target)
    monkeypatch.setattr(pipeline, "_download_video", download)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    pipeline.execute(conn, run_id, client, 1, media_dir=tmp_path / "media")

    assert client.video_urls == ["c1-v1"]
    assert conn.execute("SELECT SUM(credits) FROM api_calls WHERE endpoint='video/url'").fetchone()[0] == 0.5
    assert tuple(conn.execute("SELECT status,error FROM tasks WHERE key='c1'").fetchone()) == (
        "pending", "blocked: tài khoản LLM (nạp tiền/khóa API)"
    )
    assert conn.execute("SELECT status FROM tasks WHERE key='c2'").fetchone()[0] == "pending"
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"

    monkeypatch.setattr(llm, "analyze_video", lambda video, brief, **_kw: pipeline._fake_analysis(video))
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    pipeline.resume(conn)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"
    assert conn.execute("SELECT COUNT(*) FROM tasks WHERE stage='S3' AND status='done'").fetchone()[0] == 2


def test_s2_raw_capture_is_saved_with_contact_lines_removed(tmp_path):
    from koc.pipeline import capture_audience

    class Page:
        def goto(self, _url): pass
        def wait_for_timeout(self, _delay): pass
        def inner_text(self, _selector):
            return "Female\n70%\nEmail: creator@example.com\nPhone: +84 912 345 678\nZalo: @creator\nAge\n18-24\n30%"

    raw_path = tmp_path / "raw.txt"
    capture_audience(Page(), "creator-1", raw_path=raw_path)
    raw = raw_path.read_text()
    assert "Female\n70%" in raw and "Age\n18-24\n30%" in raw
    assert "@example.com" not in raw and "912 345 678" not in raw and "Zalo" not in raw


def test_s2_runtime_limit_skips_queued_tasks_and_s3_excludes_empty_audience(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline
    from koc.kalodata import CreditCounter

    conn = db.connect(tmp_path / "s2-limit.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    for creator_id in ("c1", "c2"):
        db.add_task(conn, run_id, "S2", creator_id)

    class Client:
        counter = CreditCounter(conn, cap=5)

    class Page:
        def goto(self, _url): pass
        def wait_for_timeout(self, _delay): pass
        def inner_text(self, _selector): return "Female\n70%\nAge\n18-24\n30%"

    real_load_config = pipeline.load_config
    monkeypatch.setattr(pipeline, "load_config", lambda: {**real_load_config(), "s1": {"s1a_limit": 1, "s1_limit": 1, "s2_limit": 1}})
    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, Client(), 1, page=Page(), media_dir=tmp_path / "media")
    assert [tuple(row) for row in conn.execute("SELECT key,status,error FROM tasks ORDER BY rowid")] == [
        ("c1", "done", None), ("c2", "skipped", "vượt s2_limit")
    ]

    db.upsert_metric(conn, "c1", "female_pct", 70, "source")
    db.upsert_score(conn, run_id, "c1", "S2", 70, {})
    db.add_task(conn, run_id, "S2", "c3")
    conn.execute("UPDATE tasks SET status='done' WHERE task_id=?", (f"{run_id}:S2:c3",))
    db.upsert_metric(conn, "c3", "female_pct", None, "source")
    db.upsert_score(conn, run_id, "c3", "S2", 0, {})
    _advance(conn, run_id, Client(), 1, Page(), False, tmp_path / "media")
    assert [row[0] for row in conn.execute("SELECT key FROM tasks WHERE stage='S3'")] == ["c1"]


def test_cached_llm_call_logs_zero_tokens_and_cost(tmp_path):
    from koc.budget_guard import llm_cache_key, put_cached

    conn = db.connect(tmp_path / "cache.db")
    db.init_db(conn)
    brief = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ", budget_vnd=30000000)
    usage = Usage(provider="gemini", model="gemini-test", prompt_version="content_v1", input_tokens=1500,
                  output_tokens=300, latency_ms=500, cost_usd=0.00225, audio_tokens=120, image_tokens=8)
    output = {"video_id": "v1", "transcript_vi": None, "rubric": [], "risks_vi": [], "evidence": [],
              "usage": usage.model_dump(mode="json")}
    key = llm_cache_key("media-hash", "content_v1", "gemini-test", brief.model_dump())
    put_cached(conn, key, output, usage.model_dump(mode="json"))
    run_id = db.create_run(conn, {})
    result = _cached_call(conn, run_id, "content", "media-hash", "content_v1", "gemini-test", brief,
                          lambda *_args, **_kwargs: None)
    assert result.usage.input_tokens == result.usage.output_tokens == 0
    assert result.usage.audio_tokens == result.usage.image_tokens == 0
    row = conn.execute("SELECT input_tokens,output_tokens,cost_usd FROM llm_calls WHERE run_id=?", (run_id,)).fetchone()
    assert tuple(row) == (0, 0, 0.0)


def test_s3_passes_frames_directory_to_llm(tmp_path, monkeypatch):
    from koc import llm
    from koc.pipeline import _s3_creator
    conn = db.connect(tmp_path / "frames.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    db.upsert_creator(conn, "c1", "creator", {"creator_followers": 30000})
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "v1.mp4").write_bytes(b"video")
    received = {}

    class Client:
        def video_rank(self, *_args, **_kwargs):
            return [{"video_id": "v1", "views": 100}]

    def fake_analyze(video, brief, *, budget_guard, frames_dir):
        received["frames_dir"] = frames_dir
        return pipeline._fake_analysis(video)

    import koc.pipeline as pipeline
    monkeypatch.setattr(llm, "analyze_video", fake_analyze)
    _s3_creator(conn, run_id, Client(), "c1", media_dir=media_dir)
    assert received["frames_dir"] == "data/media/frames"


def test_s1b_scores_creator_without_videos(tmp_path):
    from koc.pipeline import _s1

    conn = db.connect(tmp_path / "empty-videos-s1.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    db.upsert_creator(conn, "c1", "creator", {"creator_followers": 30000})

    class Client:
        def creator_detail(self, *_args, **_kwargs): return {"data": {}}
        def video_rank(self, *_args, **_kwargs): return {"data": [], "not_found": True}

    _s1(conn, run_id, Client(), "c1")(conn)
    assert conn.execute("SELECT score FROM scores WHERE run_id=? AND stage='S1'", (run_id,)).fetchone()[0] is not None
    assert conn.execute("SELECT value FROM metrics WHERE creator_id='c1' AND name='engagement_per_view'").fetchone()[0] == "null"


def test_s3_zero_videos_records_null_score_and_caveat(tmp_path):
    from koc.pipeline import _best_five, _s3_creator

    conn = db.connect(tmp_path / "empty-videos-s3.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    db.upsert_creator(conn, "c1", "creator", {})

    class Client:
        def video_rank(self, *_args, **_kwargs): return {"data": [], "not_found": True}

    _s3_creator(conn, run_id, Client(), "c1", media_dir=tmp_path / "media")(conn)
    score, breakdown = conn.execute("SELECT score,breakdown_json FROM scores WHERE run_id=? AND stage='S3'", (run_id,)).fetchone()
    assert score is None
    assert json.loads(breakdown)["caveat_vi"] == "Không tìm thấy video để phân tích nội dung."
    db.upsert_creator(conn, "c1", "creator", {"creator_followers": 30000})
    db.upsert_score(conn, run_id, "c1", "S1", 100, {})
    db.upsert_score(conn, run_id, "c1", "S2", 100, {})
    assert _best_five(conn, run_id) == []


def test_budget_stop_blocks_s3_s4_and_resume_retries_when_cap_rises(tmp_path, monkeypatch):
    import koc.pipeline as pipeline

    conn = db.connect(tmp_path / "budget-pipeline.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 1})
    db.add_task(conn, run_id, "S3", "c1")
    db.add_task(conn, run_id, "S3", "c2")
    db.add_task(conn, run_id, "S4", "select")
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
    _seed_s4_inputs(conn, run_id, ("c1", "c2"))
    conn.execute("INSERT INTO llm_calls(run_id,kind,request_hash,model,prompt_version,input_tokens,output_tokens,latency_ms,cost_usd,cache_hit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (run_id, "content", "", "model-x", "v1", 1, 1, 1, 1.1, 0, db.now()))
    conn.commit()
    cap = {"value": 1}
    from koc.budget_guard import BudgetGuard
    real_load_config = pipeline.load_config
    monkeypatch.setattr(pipeline, "load_config", lambda: {**real_load_config(), "s1": {**real_load_config()["s1"], "recommendation_count": 2}})

    def run_s3(_conn, _run_id, _client, creator_id, *_args, **_kwargs):
        BudgetGuard(conn, cap_usd=cap["value"], run_id=run_id).check(.1)
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_s3_creator", run_s3)
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    pipeline.execute(conn, run_id, object(), 1)

    tasks = conn.execute("SELECT stage,status,error,retries FROM tasks WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
    assert [(row[0], row[1], row[3]) for row in tasks] == [
        ("S3", "blocked", 0), ("S3", "blocked", 0), ("S4", "blocked", 0),
    ]
    assert all("Hạn mức" in row[2] for row in tasks)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"

    cap["value"] = 2
    pipeline.resume(conn)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"
    assert conn.execute("SELECT COUNT(*) FROM tasks WHERE run_id=? AND status='done'", (run_id,)).fetchone()[0] == 3


def test_rate_limit_blocks_stage_and_resume_continues(tmp_path, monkeypatch):
    import koc.pipeline as pipeline
    from koc.kalodata import KalodataRateLimited

    conn = db.connect(tmp_path / "rate-limit-pipeline.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 1})
    db.add_task(conn, run_id, "S3", "c1")
    db.add_task(conn, run_id, "S3", "c2")
    db.add_task(conn, run_id, "S4", "select")
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
    _seed_s4_inputs(conn, run_id, ("c1", "c2"))
    should_block = {"value": True}
    real_load_config = pipeline.load_config
    monkeypatch.setattr(pipeline, "load_config", lambda: {**real_load_config(), "s1": {**real_load_config()["s1"], "recommendation_count": 2}})

    def run_s3(_conn, _run_id, _client, creator_id, *_args, **_kwargs):
        if should_block["value"]:
            raise KalodataRateLimited()
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_s3_creator", run_s3)
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    pipeline.execute(conn, run_id, object(), 1)

    tasks = conn.execute("SELECT stage,status,error FROM tasks WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
    assert [(row[0], row[1]) for row in tasks] == [("S3", "blocked"), ("S3", "blocked"), ("S4", "pending")]
    assert all(row[2] == "blocked: Kalodata giới hạn lưu lượng" for row in tasks[:2])
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"

    should_block["value"] = False
    pipeline.resume(conn)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"
    assert conn.execute("SELECT COUNT(*) FROM tasks WHERE run_id=? AND status='done'", (run_id,)).fetchone()[0] == 3


def test_exhausted_http_429_blocks_run(tmp_path):
    from koc.kalodata import KalodataClient

    conn = db.connect(tmp_path / "http-429-pipeline.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 1})
    db.add_task(conn, run_id, "S0", "candidates")
    client = KalodataClient(conn, run_id=run_id, api_key="x", transport=lambda *_: (429, {}), sleep=lambda _: None)

    execute(conn, run_id, client, 1)

    task = conn.execute("SELECT status,error FROM tasks WHERE run_id=?", (run_id,)).fetchone()
    assert tuple(task) == ("blocked", "blocked: Kalodata giới hạn lưu lượng")
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"


def test_projection_500_scales_funnel_from_config_and_measured_units(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "projection.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"limit": 20})
    for endpoint, credits in (("creator/rank", 0.1), ("creator/detail", 0.2), ("video/url", 0.5)):
        db.add_api_call(conn, run_id, endpoint, endpoint, "200", credits, 0, False)
    for kind, tokens_in, tokens_out, cost in (("content", 1000, 200, 0.01), ("reasons", 100, 50, 0.002)):
        usage = Usage(provider="gemini", model="test", prompt_version="v1", input_tokens=tokens_in,
                      output_tokens=tokens_out, latency_ms=0, cost_usd=cost)
        db.add_llm_call(conn, run_id, kind, kind, usage, False)
    projection = benchmark(conn, run_id)["projection_500"]["stages"]
    assert projection["S0"]["credits"] == pytest.approx(0.5)
    assert projection["S1b"]["credits"] == pytest.approx(30)
    assert projection["S3"]["credits"] == pytest.approx(57)
    assert projection["S3"]["tokens_in"] == 114000
    assert projection["S3"]["tokens_out"] == 22800
    assert projection["S3"]["usd"] == pytest.approx(1.14)
    assert projection["S4"]["usd"] == pytest.approx(0.01)


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError])
def test_s3_llm_failure_fails_task_and_continues_to_s4(tmp_path, monkeypatch, stable_test_config, error_type):
    import koc.pipeline as pipeline

    stable_test_config["s1"]["recommendation_count"] = 1
    conn = db.connect(tmp_path / "s3-llm-failure.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.add_task(conn, run_id, "S3", creator_id)
    _seed_s4_inputs(conn, run_id, ("c1", "c2"))

    def s3(_conn, _run_id, _client, creator_id, *_args):
        if creator_id == "c1":
            raise pipeline.S3AnalysisError("bad JSON " + "x" * 600) from error_type("bad JSON " + "x" * 600)
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    s4_statuses = []
    def s4(_conn, _run_id, *_args):
        s4_statuses.extend(row[0] for row in conn.execute(
            "SELECT status FROM tasks WHERE run_id=? AND stage='S3' ORDER BY rowid", (run_id,)
        ))
        return lambda _c: None

    monkeypatch.setattr(pipeline, "_s3_creator", s3)
    monkeypatch.setattr(pipeline, "_s4", s4)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, object(), 1, media_dir=tmp_path / "media")

    failed = db.get_task(conn, f"{run_id}:S3:c1")
    assert failed["status"] == "failed"
    assert failed["error"].startswith(f"{error_type.__name__}: bad JSON ")
    assert len(failed["error"]) == 500
    assert db.get_task(conn, f"{run_id}:S3:c2")["status"] == "done"
    assert s4_statuses == ["failed", "done"]
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"


def test_s3_failed_attempt_keeps_paid_llm_usage_logged(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline
    from koc.budget_guard import BudgetGuard

    stable_test_config["s1"]["recommendation_count"] = 1
    conn = db.connect(tmp_path / "s3-paid-failure.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.add_task(conn, run_id, "S3", creator_id)

    def s3(_conn, _run_id, _client, creator_id, *_args):
        if creator_id == "c1":
            BudgetGuard(conn, run_id=run_id).record(Usage(
                provider="gemini", model="gemini-test", prompt_version="content_v1",
                input_tokens=10, output_tokens=5, latency_ms=20, cost_usd=0.02,
            ))
            raise pipeline.S3AnalysisError("truncated JSON") from ValueError("truncated JSON")
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    monkeypatch.setattr(pipeline, "_s3_creator", s3)
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, object(), 1, media_dir=tmp_path / "media")

    assert tuple(conn.execute(
        "SELECT kind,input_tokens,output_tokens,cost_usd FROM llm_calls WHERE run_id=?", (run_id,)
    ).fetchone()) == ("content", 10, 5, 0.02)


def test_s3_failure_below_recommendation_threshold_blocks_run_with_reason(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline

    stable_test_config["s1"]["recommendation_count"] = 2
    conn = db.connect(tmp_path / "s3-insufficient.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.add_task(conn, run_id, "S3", creator_id)
    seed_brand_fit(conn, "c2")  # c1's S3 fails, c2's succeeds and has its analysis

    def s3(_conn, _run_id, _client, creator_id, *_args):
        if creator_id == "c1":
            raise pipeline.S3AnalysisError("truncated JSON") from ValueError("truncated JSON")
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    monkeypatch.setattr(pipeline, "_s3_creator", s3)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, object(), 1, media_dir=tmp_path / "media")

    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    blocked = db.get_task(conn, f"{run_id}:S4:select")
    assert blocked["status"] == "blocked"
    assert "Chưa đủ điểm nội dung" in blocked["error"]
    assert "có 1, cần 2" in blocked["error"]


def test_infeasible_s4_budget_blocks_and_resume_recommends_after_cheaper_candidates(tmp_path, monkeypatch, stable_test_config):
    import koc.pipeline as pipeline

    conn = db.connect(tmp_path / "s4-budget.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {"mock": True})
    for creator_id, followers in [("expensive", 100000), *((f"c{i}", 50000) for i in range(1, 5)), ("cheap", 30000)]:
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": followers})
        for stage, score in (("S1", 80), ("S2", 80), ("S3", 80)):
            db.upsert_score(conn, run_id, creator_id, stage, score, {})
        seed_brand_fit(conn, creator_id)
        conn.execute("INSERT INTO metrics(creator_id,name,value,collected_at) VALUES (?,?,?,?)", (creator_id, "female_pct", "70", db.now()))
    db.add_task(conn, run_id, "S4", "select")
    conn.commit()
    monkeypatch.setattr(pipeline, "_advance", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)

    pipeline.execute(conn, run_id, object(), 1, mock=True)

    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    assert db.get_task(conn, f"{run_id}:S4:select")["status"] == "blocked"
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM llm_calls WHERE run_id=? AND kind='reasons'", (run_id,)).fetchone()[0] == 0
    assert "6 KOC có điểm nội dung" in db.get_task(conn, f"{run_id}:S4:select")["error"]
    assert "33.000.000 VND" in db.get_task(conn, f"{run_id}:S4:select")["error"]

    for i in range(1, 6):
        creator_id = f"new{i}"
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        for stage, score in (("S1", 80), ("S2", 80), ("S3", 80)):
            db.upsert_score(conn, run_id, creator_id, stage, score, {})
        seed_brand_fit(conn, creator_id)
        conn.execute("INSERT INTO metrics(creator_id,name,value,collected_at) VALUES (?,?,?,?)", (creator_id, "female_pct", "70", db.now()))
    conn.commit()
    pipeline.resume(conn, mock=True)

    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "done"
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 5


def test_s3_creator_wraps_only_llm_analysis_errors(tmp_path, monkeypatch):
    import koc.pipeline as pipeline

    conn = db.connect(tmp_path / "s3-wrap.db")
    db.init_db(conn)
    db.upsert_creator(conn, "c1", "creator", {"creator_followers": 30000})
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    class Client:
        def video_rank(self, *_args, **_kwargs):
            return {"data": [{"video_id": "v1", "revenue": 10}]}

    monkeypatch.setattr(pipeline, "_download_video", lambda *_args, **_kwargs: str(video_path))
    def fail_llm(*_args, **_kwargs):
        raise RuntimeError("Gemini generation failed")
    monkeypatch.setattr(pipeline, "_cached_call", fail_llm)

    with pytest.raises(pipeline.S3AnalysisError, match="Gemini generation failed") as caught:
        pipeline._s3_creator(conn, "run", Client(), "c1", media_dir=tmp_path / "media")
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_mixed_http_error_and_1054_blocks_creator_and_run_continues(tmp_path, monkeypatch, stable_test_config):
    """F3: HTTP 500 then three 1054 must block c1 (KalodataNotReady) and still process c2."""
    import koc.pipeline as pipeline
    from koc.kalodata import KalodataClient

    stable_test_config["s1"]["recommendation_count"] = 1
    conn = db.connect(tmp_path / "f3.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    for creator_id in ("c1", "c2"):
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        db.add_task(conn, run_id, "S3", creator_id)
    _seed_s4_inputs(conn, run_id, ("c1", "c2"))
    responses = iter([(500, {})] + [(200, {"success": False, "code": "1054", "message": "Video being fetched"})] * 3
                     + [(200, {"data": {"video_url": "x"}})])
    client = KalodataClient(conn, run_id=run_id, api_key="x", transport=lambda *_: next(responses), sleep=lambda _s: None)
    client._pace = lambda _endpoint: None

    def s3(_conn, _run_id, kclient, creator_id, *_args):
        kclient.video_url(f"v-{creator_id}")
        return lambda c: db.upsert_score(c, run_id, creator_id, "S3", 80, {})

    monkeypatch.setattr(pipeline, "_s3_creator", s3)
    monkeypatch.setattr(pipeline, "_s4", lambda *_args: lambda _c: None)
    monkeypatch.setattr(pipeline, "_record_stage_time", lambda *_args: None)
    pipeline.execute(conn, run_id, client, 1, media_dir=tmp_path / "media")

    assert [tuple(row) for row in conn.execute("SELECT key,status FROM tasks WHERE stage='S3' ORDER BY rowid")] == [
        ("c1", "blocked"), ("c2", "done"),
    ]
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] != "failed"


def _done_run_with_failed_s3(conn):
    run_id = db.create_run(conn, {"mock": True})
    for creator_id in ("c1", "c2"):
        db.add_task(conn, run_id, "S3", creator_id)
    db.add_task(conn, run_id, "S4", "select")
    db.upsert_score(conn, run_id, "c2", "S4", 70, {})
    conn.execute("INSERT INTO recommendations(run_id,creator_id,rank,est_cost_vnd,rec_json) VALUES (?,?,?,?,?)", (run_id, "c2", 1, 1, "{}"))
    conn.commit()
    db.fail_task(conn, f"{run_id}:S3:c1", "ValueError: bad")
    for task_id in (f"{run_id}:S3:c2", f"{run_id}:S4:select"):
        conn.execute("UPDATE tasks SET status='done' WHERE task_id=?", (task_id,))
    conn.commit()
    db.finish_run(conn, run_id, "done")
    return run_id


def test_resume_of_done_run_is_noop_and_retry_failed_invalidates_s4(tmp_path, monkeypatch):
    """F2: plain resume of a done run changes nothing and makes no calls; --retry-failed is explicit and re-selects S4."""
    import koc.pipeline as pipeline

    conn = db.connect(tmp_path / "f2.db")
    db.init_db(conn)
    run_id = _done_run_with_failed_s3(conn)
    executed = []
    monkeypatch.setattr(pipeline, "execute", lambda *args, **kwargs: executed.append(1))

    assert pipeline.resume(conn, mock=True) == run_id
    assert not executed
    assert db.get_task(conn, f"{run_id}:S3:c1")["status"] == "failed"
    assert db.get_task(conn, f"{run_id}:S4:select")["status"] == "done"

    pipeline.resume(conn, mock=True, retry_failed=True)
    assert executed
    assert db.get_task(conn, f"{run_id}:S3:c1")["status"] == "pending"
    assert db.get_task(conn, f"{run_id}:S4:select")["status"] == "pending"
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM scores WHERE run_id=? AND stage='S4'", (run_id,)).fetchone()[0] == 0


def test_cli_resume_done_run_prints_message_and_skips_pipeline(tmp_path, monkeypatch):
    import koc.cli as cli
    from typer.testing import CliRunner

    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "f2cli.db")
    conn = db.connect(cli.DB_PATH)
    db.init_db(conn)
    run_id = _done_run_with_failed_s3(conn)
    conn.close()
    calls = []
    monkeypatch.setattr(cli, "resume_pipeline", lambda *_a, **kw: calls.append(kw) or run_id)

    result = CliRunner().invoke(cli.app, ["resume"])
    assert result.exit_code == 0 and "đã hoàn tất" in result.output and not calls
    result = CliRunner().invoke(cli.app, ["resume", "--retry-failed"])
    assert result.exit_code == 0 and calls[0]["retry_failed"] is True
