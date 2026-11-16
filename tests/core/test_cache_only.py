import socket

import pytest
from typer.testing import CliRunner

from koc import db
from koc.cli import app
from koc.kalodata import KalodataClient
from koc.pipeline import _cached_call, resume, start
from koc.types import BrandBrief, CacheOnlyMiss


def _forbid_network(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("network attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)


def _top5(conn, run_id):
    return [tuple(row) for row in conn.execute(
        "SELECT creator_id,rank FROM recommendations WHERE run_id=? ORDER BY rank", (run_id,))]


def test_client_cache_miss_raises_without_transport_call(tmp_path):
    conn = db.connect(tmp_path / "c.db")
    db.init_db(conn)
    calls = []
    client = KalodataClient(conn, "run", "key", transport=lambda *a: calls.append(a) or {"data": []}, cache_only=True)
    with pytest.raises(CacheOnlyMiss, match="chỉ-cache"):
        client.creator_rank(page_size=100)
    assert calls == []
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 0


def test_client_cache_hit_is_served_free_in_cache_only(tmp_path):
    conn = db.connect(tmp_path / "c.db")
    db.init_db(conn)
    calls = []
    live = KalodataClient(conn, "r1", "key", transport=lambda *a: calls.append(a) or {"data": [1]})
    live.creator_rank(page_size=100)
    only = KalodataClient(conn, "r2", "key", transport=lambda *a: calls.append(a) or {"data": []}, cache_only=True)
    assert only.creator_rank(page_size=100) == {"data": [1]}
    assert len(calls) == 1
    assert conn.execute("SELECT SUM(credits) FROM api_calls WHERE run_id='r2'").fetchone()[0] == 0


def test_llm_cache_miss_raises_without_calling_provider(tmp_path):
    conn = db.connect(tmp_path / "l.db")
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    brief = BrandBrief(product_vi="kem chống nắng", audience_vi="Nữ", budget_vnd=1)
    called = []
    with pytest.raises(CacheOnlyMiss):
        _cached_call(conn, run_id, "content", "hash", "content_v3", "m", brief, lambda *a, **k: called.append(1), cache_only=True)
    assert called == []
    assert conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 0


def test_real_mode_cache_miss_blocks_run_without_network(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KALODATA_API_KEY", "should-not-be-used")
    _forbid_network(monkeypatch)
    conn = db.connect(tmp_path / "k.db")
    db.init_db(conn)
    run_id = start(conn, limit=5, cache_only=True)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    task = conn.execute("SELECT status,error FROM tasks WHERE run_id=? AND stage='S0'", (run_id,)).fetchone()
    assert task["status"] == "blocked" and "chỉ-cache" in task["error"]
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 0


def test_mock_cache_miss_blocks_run(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "m.db")
    db.init_db(conn)
    run_id = start(conn, limit=5, mock=True, cache_only=True)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()[0] == "blocked"
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0


def test_cache_only_rerun_of_mock_run_costs_nothing_and_keeps_top5(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "r.db")
    db.init_db(conn)
    first = start(conn, limit=20, mock=True)
    assert len(_top5(conn, first)) == 5
    _forbid_network(monkeypatch)
    second = start(conn, limit=20, mock=True, cache_only=True)
    assert conn.execute("SELECT status FROM runs WHERE run_id=?", (second,)).fetchone()[0] == "done"
    assert _top5(conn, second) == _top5(conn, first)
    assert conn.execute("SELECT COALESCE(SUM(credits),0) FROM api_calls WHERE run_id=?", (second,)).fetchone()[0] == 0
    assert conn.execute("SELECT COALESCE(SUM(input_tokens+output_tokens),0) FROM llm_calls WHERE run_id=?", (second,)).fetchone()[0] == 0
    assert conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM llm_calls WHERE run_id=?", (second,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM api_calls WHERE run_id=? AND cache_hit=0", (second,)).fetchone()[0] == 0


def test_resume_keeps_cache_only_from_run_params(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)
    conn = db.connect(tmp_path / "s.db")
    db.init_db(conn)
    start(conn, limit=5, mock=True, cache_only=True)
    resume(conn, mock=True)
    assert conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0


def test_cli_run_accepts_cache_only_flag(tmp_path, monkeypatch):
    import koc.cli as cli
    seen = {}
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    monkeypatch.setattr(cli, "start", lambda *_a, **kw: seen.update(kw) or "rid")
    result = CliRunner().invoke(app, ["run", "--limit", "5", "--cache-only"])
    assert result.exit_code == 0, result.output
    assert seen["cache_only"] is True
