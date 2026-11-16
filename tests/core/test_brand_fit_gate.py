import json

import pytest

from koc import db
from koc.config import load_config
from koc import queries
from koc.pipeline import _best_five, _s4, _s4_budget_block_reason, start
from koc.stages import brand_fit_gate, excluded_brand_fit
from koc.web.matching_api import get_pool, result_for_campaign

CAMPAIGN = {"followers_min": 0, "followers_max": 10**9, "target": {"gender": "Tất cả", "age_groups": []},
            "count": 5, "budget_vnd": 10**9, "avoid_same_mcn": False, "product_type": "Chống nắng"}
TIERS = [{"min_followers": 0, "max_followers": 10**9, "vnd_per_video": 1_000_000}]


def _set_brand_fit(conn, run_id, creator_id, score):
    for vid, prompt, model, raw in db.run_analyses(conn, run_id, creator_id):
        data = json.loads(raw)
        for item in data["rubric"]:
            if item["criterion"] == "brand_fit":
                item["score"] = score
        conn.execute("UPDATE analyses SET analysis_json=? WHERE video_id=? AND prompt_version=? AND model=?", (json.dumps(data), vid, prompt, model))
    conn.commit()


@pytest.fixture
def mock_run(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "gate.db")
    db.init_db(conn)
    run_id = start(conn, limit=20, mock=True)
    return conn, run_id


def test_mock_analysis_passes_gate(mock_run):
    conn, run_id = mock_run
    assert excluded_brand_fit(conn, run_id) == []
    assert conn.execute("SELECT COUNT(*) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0] == 5
    assert brand_fit_gate(conn, run_id, _best_five(conn, run_id)[0]["id"])["max_brand_fit"] == 3


def test_gate_excludes_below_threshold_and_keeps_threshold(mock_run):
    conn, run_id = mock_run
    ids = [item["id"] for item in _best_five(conn, run_id)]
    _set_brand_fit(conn, run_id, ids[0], 2)
    _set_brand_fit(conn, run_id, ids[1], 3)
    low, keep = brand_fit_gate(conn, run_id, ids[0]), brand_fit_gate(conn, run_id, ids[1])
    assert not low["eligible"] and low["max_brand_fit"] == 2
    assert low["reason_vi"].startswith("Loại vì video không hợp sản phẩm: độ hợp thương hiệu cao nhất 2/5")
    assert keep["eligible"]


def test_gate_uses_best_video_not_average(mock_run):
    conn, run_id = mock_run
    creator_id = _best_five(conn, run_id)[0]["id"]
    rows = db.run_analyses(conn, run_id, creator_id)
    assert len(rows) >= 2
    vid, prompt, model, raw = rows[0]
    data = json.loads(raw)
    for item in data["rubric"]:
        if item["criterion"] == "brand_fit":
            item["score"] = 1
    conn.execute("UPDATE analyses SET analysis_json=? WHERE video_id=? AND prompt_version=? AND model=?", (json.dumps(data), vid, prompt, model))
    assert brand_fit_gate(conn, run_id, creator_id)["eligible"]


def test_threshold_comes_from_config(mock_run):
    conn, run_id = mock_run
    creator_id = _best_five(conn, run_id)[0]["id"]
    config = load_config()
    assert config["scoring"]["s4"]["min_brand_fit"] == 3
    config["scoring"]["s4"]["min_brand_fit"] = 4
    assert not brand_fit_gate(conn, run_id, creator_id, config)["eligible"]
    config["scoring"]["s4"]["min_brand_fit"] = 3
    assert brand_fit_gate(conn, run_id, creator_id, config)["eligible"]


def test_excluded_creator_never_in_picks_or_s4_output(mock_run):
    conn, run_id = mock_run
    gone = _best_five(conn, run_id)[0]["id"]
    _set_brand_fit(conn, run_id, gone, 2)
    assert gone not in {item["id"] for item in _best_five(conn, run_id)}
    _s4(conn, run_id, mock=True)(conn)
    rows = {r[0] for r in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}
    assert gone not in rows and len(rows) == 5
    assert [e["id"] for e in excluded_brand_fit(conn, run_id)] == [gone]


def test_too_few_eligible_blocked_reason_counts_dropped(mock_run):
    conn, run_id = mock_run
    for item in _best_five(conn, run_id)[:2]:
        _set_brand_fit(conn, run_id, item["id"], 1)
    reason = _s4_budget_block_reason(conn, run_id, 5)
    assert "Đã loại 2 KOC vì video không hợp sản phẩm" in reason
    assert "Lựa chọn: (1)" in reason


def test_web_pool_applies_gate(mock_run):
    conn, run_id = mock_run
    pool, _ = get_pool(conn, CAMPAIGN, TIERS)
    gone = pool[0]["creator_id"]
    _set_brand_fit(conn, run_id, gone, 2)
    pool, _ = get_pool(conn, CAMPAIGN, TIERS)
    assert gone not in {c["creator_id"] for c in pool}
    result = result_for_campaign(conn, CAMPAIGN, TIERS)
    assert gone not in {c["creator_id"] for c in result["picked"] + result["alternates"]}
    assert gone in {e["id"] for e in result["brand_fit_excluded"]}


def test_no_analysed_video_is_not_eligible(mock_run):
    conn, run_id = mock_run
    s1_only = conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S1' AND creator_id NOT IN (SELECT creator_id FROM scores WHERE run_id=? AND stage='S3')", (run_id, run_id)).fetchone()[0]
    gate = brand_fit_gate(conn, run_id, s1_only)
    assert not gate["eligible"] and gate["max_brand_fit"] is None
    assert gate["reason_vi"] == "Loại vì chưa có video được phân tích để kiểm tra độ hợp sản phẩm."
    pool, _ = get_pool(conn, CAMPAIGN, TIERS)
    assert s1_only not in {c["creator_id"] for c in pool}
    assert s1_only in {e["id"] for e in excluded_brand_fit(conn, run_id, stage="S1")}
    # S4 keeps its own S3-score requirement: S1-only creators are not S4 candidates or counted as dropped.
    assert s1_only not in {e["id"] for e in excluded_brand_fit(conn, run_id)}


def test_web_gate_covers_creator_without_s3_score(mock_run):
    conn, run_id = mock_run
    gone = _best_five(conn, run_id)[0]["id"]
    _set_brand_fit(conn, run_id, gone, 2)
    conn.execute("DELETE FROM scores WHERE run_id=? AND creator_id=? AND stage='S3'", (run_id, gone))
    conn.commit()
    assert not brand_fit_gate(conn, run_id, gone)["eligible"]
    pool, _ = get_pool(conn, CAMPAIGN, TIERS)
    assert gone not in {c["creator_id"] for c in pool}
    result = result_for_campaign(conn, {**CAMPAIGN, "count": 1}, TIERS)
    assert gone not in {c["creator_id"] for c in result["picked"]}
    assert gone in {e["id"] for e in result["brand_fit_excluded"]}


def test_pool_is_only_eligible_creators_and_refusal_counts_them(mock_run):
    conn, run_id = mock_run
    eligible = {c["creator_id"] for c in get_pool(conn, CAMPAIGN, TIERS)[0]}
    assert eligible == {r[0] for r in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S3'", (run_id,))}
    result = result_for_campaign(conn, {**CAMPAIGN, "count": len(eligible) + 1}, TIERS)
    assert len(result["picked"]) <= len(eligible)


def test_s4_rewrite_replaces_recommendation_set_atomically(mock_run):
    conn, run_id = mock_run
    old = {r[0] for r in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}
    gone = _best_five(conn, run_id)[0]["id"]
    _set_brand_fit(conn, run_id, gone, 2)
    _s4(conn, run_id, mock=True)(conn)
    new = {r[0] for r in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=?", (run_id,))}
    assert len(new) == 5 and gone not in new and old != new
    assert {r[0] for r in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S4'", (run_id,))} == new
    total = conn.execute("SELECT SUM(est_cost_vnd) FROM recommendations WHERE run_id=?", (run_id,)).fetchone()[0]
    assert total == json.loads(conn.execute("SELECT params_json FROM runs WHERE run_id=?", (run_id,)).fetchone()[0])["s4"]["total_vnd"]


def test_stored_proposal_and_run_view_filter_failing_pick(mock_run):
    from koc.web import adapter
    conn, run_id = mock_run
    gone = {r[0] for r in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=? ORDER BY rank LIMIT 1", (run_id,))}.pop()
    _set_brand_fit(conn, run_id, gone, 2)
    assert gone not in {row["creator_id"] for row in queries.top5(conn, run_id)}
    data = adapter.get_top5_with_details(conn, run_id)
    assert gone not in {card["creator_id"] for card in data["cards"]}
    assert [e["id"] for e in data["brand_fit_excluded"]] == [gone]
    assert "độ hợp thương hiệu cao nhất 2/5" in data["brand_fit_excluded"][0]["reason_vi"]
    proposal = adapter.get_run_proposal(conn, run_id)
    assert gone not in {pick["creator_id"] for pick in proposal["picks"]}


def test_excluded_carry_video_brand_fit(mock_run):
    from koc.web import adapter
    conn, run_id = mock_run
    gone = {r[0] for r in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=? ORDER BY rank LIMIT 1", (run_id,))}.pop()
    _set_brand_fit(conn, run_id, gone, 2)
    proposal = adapter.get_run_proposal(conn, run_id)
    item = next(e for e in proposal["brand_fit_excluded"] if e["id"] == gone)
    assert item["videos"] and all(v["brand_fit"] == 2 and v["video_id"] for v in item["videos"])
    result = result_for_campaign(conn, CAMPAIGN, TIERS)
    assert all("videos" in e and "nickname" in e for e in result["brand_fit_excluded"])


def test_picks_carry_all_analysed_video_ids(mock_run):
    from koc.web import adapter
    conn, run_id = mock_run
    proposal = adapter.get_run_proposal(conn, run_id)
    result = result_for_campaign(conn, CAMPAIGN, TIERS)
    for creator in result["picked"]:
        expected = [row[0] for row in db.run_analyses(conn, run_id, creator["creator_id"])]
        assert expected and creator["analysed_video_ids"] == expected
    assert proposal["picks"]
