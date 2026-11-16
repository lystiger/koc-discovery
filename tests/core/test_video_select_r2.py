"""Review r2 of v2 item 4: per-word accent handling and legacy adoption across every stored budget."""
from koc import db
from koc.config import load_config
from koc.types import BrandBrief
from koc.video_select import select_videos

from tests.core.test_video_select import BRIEF, _ids, _v, _vi


def test_mixed_accent_title_matches_per_word_but_lookalikes_still_fail():
    cfg = load_config()
    mixed = select_videos([_v("a", "kem chong nang cho da dầu", 1)], BRIEF, cfg)[0][1]
    assert mixed["on_topic"] is True and "kem chống nắng" in mixed["matched_terms"]
    picked = select_videos([_v("shampoo", "Dầu gội cho da dầu", 999), _v("sun", "kem chong nang cho da dầu", 1)], BRIEF, cfg)
    assert _ids(picked) == ["sun", "shampoo"]
    assert select_videos([_v("n", "kem dưỡng chống lão hóa, nâng cơ", 1)], BRIEF, cfg)[0][1]["on_topic"] is False
    assert select_videos([_v("n", "chống nâng", 1)], BRIEF, cfg)[0][1]["on_topic"] is False


def test_legacy_row_keyed_with_budget_stored_only_under_s4_is_reused_at_a_different_budget(tmp_path):
    from koc.budget_guard import llm_cache_key, put_cached
    from koc.pipeline import _cached_call, _fake_analysis
    conn = db.connect(tmp_path / "s4.db")
    db.init_db(conn)
    old = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ", budget_vnd=30_000_000)
    res = _fake_analysis(_vi("v1"))
    put_cached(conn, llm_cache_key("H", "content_v3", "m", old.model_dump()), res.model_dump(mode="json"), res.usage.model_dump(mode="json"))
    db.create_run(conn, {"s4": {"budget_vnd": 30_000_000, "total_vnd": 1}})  # the live run: no params.brief
    new = old.model_copy(update={"budget_vnd": 8_000_000})
    calls = []

    def fn(video, brief, budget_guard=None, **_k):
        calls.append(video.video_id)
        return _fake_analysis(video)

    run_id = db.create_run(conn, {"brief": {"budget_vnd": 8_000_000}})
    got = _cached_call(conn, run_id, "content", "H", "content_v3", "m", new, fn, _vi("v1"), new)
    assert got.video_id == "v1" and calls == []
