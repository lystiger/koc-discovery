"""v2 item 4: S3 picks on-topic videos; budget_vnd is out of the content prompt and its cache key."""
import json
from pathlib import Path

import pytest

from koc import db, pipeline
from koc.config import load_config
from koc.types import BrandBrief
from koc.video_select import fold_text, select_videos

BRIEF = {"product": "kem chống nắng", "product_type": "Chống nắng"}


def _v(vid, title, revenue, **extra):
    return {"video_id": vid, "video_title": title, "revenue": revenue, **extra}


def _ids(picked):
    return [v["video_id"] for v, _ in picked]


def test_fold_text_strips_diacritics_case_and_d_stroke():
    assert fold_text("Kem CHỐNG NẮNG Đẹp đà") == "kem chong nang dep da"
    assert fold_text("Kem chống nắng") == fold_text("kem chong nang")
    assert fold_text(None) == ""


def test_on_topic_outranks_higher_revenue_off_topic():
    videos = [_v("shampoo", "Dầu gội thảo dược siêu mượt", 900), _v("sun", "Review kem chống nắng SPF50", 10),
              _v("deal", "Deal sốc cuối tuần", 800), _v("sun2", "Xịt chống nắng cho da dầu", 20)]
    picked = select_videos(videos, BRIEF, load_config(), n=3)
    assert _ids(picked)[:2] == ["sun", "sun2"]  # "sun" matches more terms (kem chống nắng, chống nắng, spf)
    assert [info["on_topic"] for _, info in picked] == [True, True, False]
    assert _ids(picked)[2] == "shampoo"  # fill by revenue


def test_diacritic_free_title_matches_and_matched_terms_are_stored():
    picked = select_videos([_v("a", "kem chong nang spf 50 cho da dau", 5)], BRIEF, load_config(), n=3)
    info = picked[0][1]
    assert info["on_topic"] is True and info["score"] > 0
    assert "chống nắng" in info["matched_terms"] and "spf" in info["matched_terms"]


def test_ties_break_by_revenue_and_hashtag_compound_matches():
    videos = [_v("lo", "Chống nắng mùa hè", 10), _v("hi", "Chống nắng mùa hè", 99), _v("tag", "Mới về #kemchongnang", 1)]
    picked = select_videos(videos, BRIEF, load_config(), n=3)
    assert all(info["on_topic"] for _, info in picked)
    assert _ids(picked).index("hi") < _ids(picked).index("lo")


def test_fewer_than_n_on_topic_fills_by_revenue_and_marks_off_topic():
    videos = [_v("x", "Dầu gội", 50), _v("sun", "Kem chống nắng", 1), _v("y", "Mì tôm", 70), _v("z", "Áo thun", 60)]
    picked = select_videos(videos, BRIEF, load_config(), n=3)
    assert _ids(picked) == ["sun", "y", "z"]
    assert [info["on_topic"] for _, info in picked] == [True, False, False]
    assert picked[1][1]["score"] == 0 and picked[1][1]["matched_terms"] == []


def test_attached_product_name_counts_when_present():
    picked = select_videos([_v("a", "Review hot", 1, product_name="Kem chống nắng Anessa")], BRIEF, load_config(), n=3)
    assert picked[0][1]["on_topic"] is True


def test_other_product_type_uses_brief_product_only():
    brief = {"product": "Sữa tắm", "product_type": "Khác"}
    picked = select_videos([_v("a", "Sữa tắm hương hoa", 1), _v("b", "Kem chống nắng", 99)], brief, load_config(), n=3)
    assert _ids(picked) == ["a", "b"]
    assert [i["on_topic"] for _, i in picked] == [True, False]


def test_no_videos_returns_empty():
    assert select_videos([], BRIEF, load_config(), n=3) == []


# --- budget out of the content prompt and cache key ---

def test_content_prompt_has_no_budget():
    text = (Path(__file__).resolve().parents[2] / "prompts" / "content_v3.md").read_text(encoding="utf-8")
    assert "budget_vnd" not in text and "Ngân sách" not in text


def test_analyze_video_sends_no_budget_in_prompt(monkeypatch, tmp_path):
    from koc.llm import content
    from koc.types import VideoInput
    seen = {}
    monkeypatch.setattr(content, "preprocess_video", lambda *a, **k: {"frames": [], "duration_s": 1, "audio_path": None})

    class Stop(Exception):
        pass

    class Guard:
        def check(self, *_a, **_k): pass
        def record(self, *_a, **_k): pass

    class Client:
        config_path = None
        def __getattr__(self, name):
            def call(contents=None, *a, **k):
                seen["prompt"] = str(contents)
                raise Stop
            return call

    brief = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ", budget_vnd=12345678)
    video = VideoInput(video_id="v", creator_id="c", title="t", publish_date=None, views=1, likes=1, comments=1, shares=1, revenue_vnd=1, mp4_path=str(tmp_path / "v.mp4"))
    with pytest.raises(Stop):
        content.analyze_video(video, brief, budget_guard=Guard(), client=Client())
    assert "prompt" in seen and "kem chống nắng" in seen["prompt"]
    assert "12345678" not in seen["prompt"] and "Ngân sách" not in seen["prompt"]


def test_budget_only_change_costs_zero_new_llm_calls(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "b.db")
    db.init_db(conn)
    db.upsert_creator(conn, "c1", "c1", {"creator_followers": 30000})

    class Client:
        def video_rank(self, creator_id, **_k):
            return {"data": [_v("v1", "Kem chống nắng", 5), _v("v2", "Dầu gội", 9)]}
        def video_url(self, vid):
            return {"data": {"video_url": "mock://x"}}

    def run(budget):
        brief = {**pipeline.run_brief(conn, "none", stable_test_config), "budget_vnd": budget}
        run_id = db.create_run(conn, {"brief": brief})
        write = pipeline._s3_creator(conn, run_id, Client(), "c1", mock=True, media_dir=tmp_path / "media")
        with db.transaction(conn):
            write(conn)
        return run_id

    run(30_000_000)
    paid_first = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE cache_hit=0").fetchone()[0]
    second = run(7_000_000)
    assert paid_first == 2
    assert conn.execute("SELECT COUNT(*) FROM llm_calls WHERE cache_hit=0").fetchone()[0] == paid_first
    assert conn.execute("SELECT COUNT(*) FROM llm_calls WHERE run_id=? AND cache_hit=1", (second,)).fetchone()[0] == 2


def test_real_cache_key_ignores_budget_and_legacy_rows_are_reused(tmp_path):
    from koc.budget_guard import llm_cache_key, put_cached
    from koc.pipeline import _cached_call, _content_key, _fake_analysis
    from koc.types import VideoInput
    conn = db.connect(tmp_path / "k.db")
    db.init_db(conn)
    a = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ", budget_vnd=30_000_000)
    b = a.model_copy(update={"budget_vnd": 5_000_000})
    item = VideoInput(video_id="v1", creator_id="c", title="t", publish_date=None, views=1, likes=1, comments=1, shares=1, revenue_vnd=1, mp4_path="x")
    calls = []

    def fn(video, brief, budget_guard=None, **_k):
        calls.append(brief.budget_vnd)
        return _fake_analysis(video)

    _cached_call(conn, db.create_run(conn, {}), "content", "H", "content_v3", "m", a, fn, item, a)
    _cached_call(conn, db.create_run(conn, {}), "content", "H", "content_v3", "m", b, fn, item, b)
    assert calls == [30_000_000]  # budget-only change: cache hit, function not called
    legacy = llm_cache_key("H2", "content_v3", "m", a.model_dump())  # key as built before this change
    res = _fake_analysis(item)
    put_cached(conn, legacy, res.model_dump(mode="json"), res.usage.model_dump(mode="json"), None)
    run3 = db.create_run(conn, {"brief": {"budget_vnd": 30_000_000}})
    _cached_call(conn, run3, "content", "H2", "content_v3", "m", a, fn, item, a)
    assert calls == [30_000_000]  # legacy row reused, no new call
    new_key = _content_key("H2", "content_v3", "m", a, "v1")
    assert conn.execute("SELECT COUNT(*) FROM llm_cache WHERE request_hash=?", (new_key,)).fetchone()[0] == 1


def test_s3_breakdown_stores_selection_reason(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "r.db")
    db.init_db(conn)
    db.upsert_creator(conn, "c1", "c1", {"creator_followers": 30000})
    rows = [_v("v1", "Kem chống nắng SPF50", 5), _v("v2", "Dầu gội", 9), _v("v3", "Mì tôm", 8), _v("v4", "Áo", 7)]

    class Client:
        def video_rank(self, creator_id, **_k): return {"data": rows}
        def video_url(self, vid): return {"data": {"video_url": "mock://x"}}

    run_id = db.create_run(conn, {})
    write = pipeline._s3_creator(conn, run_id, Client(), "c1", mock=True, media_dir=tmp_path / "media")
    with db.transaction(conn):
        write(conn)
    bd = json.loads(conn.execute("SELECT breakdown_json FROM scores WHERE run_id=? AND stage='S3'", (run_id,)).fetchone()[0])
    assert bd["video_ids"] == ["v1", "v2", "v3"]
    sel = bd["video_selection"]
    assert [s["video_id"] for s in sel] == ["v1", "v2", "v3"]
    assert sel[0]["on_topic"] is True and sel[0]["score"] > 0 and "spf" in sel[0]["matched_terms"]
    assert sel[1]["on_topic"] is False and sel[1]["matched_terms"] == []


# --- review r1 ---

def test_scattered_words_and_accent_lookalikes_do_not_match():
    off = _v("a", "Kem dưỡng chống lão hóa, nâng cơ", 999)
    sun = _v("b", "Kem chống nắng SPF50", 1)
    picked = select_videos([off, sun], BRIEF, load_config(), n=3)
    assert _ids(picked) == ["b", "a"]
    assert [i["on_topic"] for _, i in picked] == [True, False]
    assert select_videos([_v("c", "Chống lão hóa, nắng đẹp", 1)], BRIEF, load_config())[0][1]["on_topic"] is False


def test_unaccented_title_is_matched_folded():
    info = select_videos([_v("a", "kem chong nang spf50", 1)], BRIEF, load_config())[0][1]
    assert info["on_topic"] is True and "kem chống nắng" in info["matched_terms"] and "spf" in info["matched_terms"]


def test_hashtag_glued_term_still_matches_in_accented_title():
    assert select_videos([_v("a", "Mới về #kemchongnang", 1)], BRIEF, load_config())[0][1]["on_topic"] is True


def test_attached_product_prefilter_does_not_hide_on_topic_video(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "p.db")
    db.init_db(conn)
    db.upsert_creator(conn, "c1", "c1", {"creator_followers": 30000, "top3_product_ids": ["P1"]})
    rows = [_v("shampoo", "Dầu gội", 99, product_id="P1"), _v("sun", "Kem chống nắng", 1, product_id="P9")]

    class Client:
        def video_rank(self, creator_id, **_k): return {"data": rows}
        def video_url(self, vid): return {"data": {"video_url": "mock://x"}}

    run_id = db.create_run(conn, {})
    write = pipeline._s3_creator(conn, run_id, Client(), "c1", mock=True, media_dir=tmp_path / "media")
    with db.transaction(conn):
        write(conn)
    bd = json.loads(conn.execute("SELECT breakdown_json FROM scores WHERE run_id=? AND stage='S3'", (run_id,)).fetchone()[0])
    assert bd["video_ids"] == ["sun", "shampoo"]
    assert [s["on_topic"] for s in bd["video_selection"]] == [True, False]


def _vi(vid):
    from koc.types import VideoInput
    return VideoInput(video_id=vid, creator_id="c", title="t", publish_date=None, views=1, likes=1, comments=1, shares=1, revenue_vnd=1, mp4_path="x")


def test_identical_media_under_two_video_ids_never_shares_an_analysis(tmp_path):
    from koc.budget_guard import llm_cache_key, put_cached
    from koc.pipeline import _cached_call, _fake_analysis
    conn = db.connect(tmp_path / "ids.db")
    db.init_db(conn)
    a = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ", budget_vnd=30_000_000)
    b = a.model_copy(update={"budget_vnd": 5_000_000})
    legacy_result = _fake_analysis(_vi("v1"))
    put_cached(conn, llm_cache_key("SAME", "content_v3", "m", a.model_dump()), legacy_result.model_dump(mode="json"), legacy_result.usage.model_dump(mode="json"))
    run1 = db.create_run(conn, {"brief": {"budget_vnd": 30_000_000}})
    calls = []

    def fn(video, brief, budget_guard=None, **_k):
        calls.append(video.video_id)
        return _fake_analysis(video)

    # legacy row of v1 is not adopted for v2 (even with another budget); v2 pays once, then is cached
    r2 = _cached_call(conn, run1, "content", "SAME", "content_v3", "m", b, fn, _vi("v2"), b)
    assert r2.video_id == "v2" and calls == ["v2"]
    _cached_call(conn, db.create_run(conn, {}), "content", "SAME", "content_v3", "m", a, fn, _vi("v2"), a)
    assert calls == ["v2"]
    # v1 itself still reuses its legacy row, whatever the budget
    r1 = _cached_call(conn, db.create_run(conn, {}), "content", "SAME", "content_v3", "m", b, fn, _vi("v1"), b)
    assert r1.video_id == "v1" and calls == ["v2"]


def test_preview_counts_unrelated_model_analysis_as_needing_payment(tmp_path):
    import importlib.util
    from koc.brief import brand_brief
    from koc.budget_guard import llm_cache_key, put_cached
    from koc.pipeline import _fake_analysis
    spec = importlib.util.spec_from_file_location("s3_rerank_preview", Path(__file__).resolve().parents[2] / "scripts" / "s3_rerank_preview.py")
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    conn = db.connect(tmp_path / "pv.db")
    db.init_db(conn)
    brief = {"product": "kem chống nắng", "product_type": "Chống nắng", "target": "Nữ, 18-30 tuổi", "budget_vnd": 30_000_000}
    (tmp_path / "v1.mp4").write_bytes(b"bytes")
    import hashlib
    h = hashlib.sha256(b"bytes").hexdigest()
    res = _fake_analysis(_vi("v1"))
    # analysis produced by an unrelated model: the table row exists, the production cache identity does not
    conn.execute("INSERT INTO analyses VALUES (?,?,?,?)", ("v1", "content_v3", "other-model", res.model_dump_json()))
    put_cached(conn, llm_cache_key(h, "content_v3", "other-model", brand_brief(brief).model_dump()), res.model_dump(mode="json"), res.usage.model_dump(mode="json"))
    assert preview.needs_payment(conn, brief, "v1", tmp_path, "gemini-3.8-flash") is True
    assert preview.needs_payment(conn, brief, "v1", tmp_path, "other-model") is False  # legacy row, same model
    assert preview.needs_payment(conn, brief, "v9", tmp_path, "other-model") is True  # no downloaded file
