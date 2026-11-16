from datetime import datetime, timedelta, timezone

from koc import db
from koc.config import load_config
from koc.kalodata import KalodataClient

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def clock(monkeypatch, moment):
    monkeypatch.setattr(db, "now", lambda: moment.isoformat())


def make(tmp_path, calls):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    client = KalodataClient(conn, "r", "key", transport=lambda *a: calls.append(a[0]) or {"data": [len(calls)]}, sleep=lambda *_: None)
    client._min_interval = 0
    return conn, client


def test_default_ttl_is_seven_days():
    assert load_config()["s1"]["cache_ttl_days"] == 7


def test_fresh_rank_detail_video_rank_are_served_from_cache(tmp_path, monkeypatch):
    calls = []
    clock(monkeypatch, T0)
    conn, client = make(tmp_path, calls)
    client.creator_rank(page_size=100)
    client.creator_detail("c1")
    client.video_rank("c1")
    clock(monkeypatch, T0 + timedelta(days=6, hours=23))
    client.creator_rank(page_size=100)
    client.creator_detail("c1")
    client.video_rank("c1")
    assert len(calls) == 3


def test_stale_rows_are_refetched_and_replaced(tmp_path, monkeypatch):
    calls = []
    clock(monkeypatch, T0)
    conn, client = make(tmp_path, calls)
    client.creator_rank(page_size=100)
    client.creator_detail("c1")
    client.video_rank("c1")
    clock(monkeypatch, T0 + timedelta(days=7, seconds=1))
    assert client.creator_rank(page_size=100) == {"data": [4]}
    client.creator_detail("c1")
    client.video_rank("c1")
    assert len(calls) == 6
    # refreshed row is fresh again: no further call
    client.creator_rank(page_size=100)
    assert len(calls) == 6
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 3


def test_cache_only_serves_stale_rows_free(tmp_path, monkeypatch):
    calls = []
    clock(monkeypatch, T0)
    conn, client = make(tmp_path, calls)
    client.creator_rank(page_size=100)
    clock(monkeypatch, T0 + timedelta(days=60))
    only = KalodataClient(conn, "r2", "key", transport=lambda *a: calls.append(a) or {}, cache_only=True)
    assert only.creator_rank(page_size=100) == {"data": [1]}
    assert len(calls) == 1


def test_video_url_never_expires(tmp_path, monkeypatch):
    calls = []
    clock(monkeypatch, T0)
    conn, client = make(tmp_path, calls)
    client.video_url("v1")
    clock(monkeypatch, T0 + timedelta(days=400))
    client.video_url("v1")
    assert len(calls) == 1


def test_llm_cache_never_expires(tmp_path, monkeypatch):
    from koc.budget_guard import get_cached, put_cached
    conn = db.connect(tmp_path / "l.db")
    db.init_db(conn)
    clock(monkeypatch, T0)
    put_cached(conn, "k", {"x": 1}, {"tokens": 1})
    clock(monkeypatch, T0 + timedelta(days=400))
    assert get_cached(conn, "k") == ({"x": 1}, {"tokens": 1})
