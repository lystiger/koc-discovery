import pytest

from koc import db
from koc.kalodata import CreditCounter, KalodataClient, KalodataNotReady, KalodataRateLimited, strip_contacts


def test_cache_hit_costs_zero_credits_and_strips_contact(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "cache.db")
    db.init_db(conn)
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *a: {
        "data": {"creator_id": "c1", "creator_contact_email": "secret", "creator_followers": "50000"}
    }, sleep=lambda _: None)
    first = client.creator_detail("c1", need_extra=True)
    second = client.creator_detail("c1", need_extra=True)
    assert "creator_contact_email" not in first["data"]
    assert first == second
    assert conn.execute("SELECT SUM(credits) FROM api_calls").fetchone()[0] == pytest.approx(.1)
    assert conn.execute("SELECT cache_hit FROM api_calls ORDER BY id DESC LIMIT 1").fetchone()[0] == 1


def test_credit_counter_refuses_before_transport(tmp_path):
    conn = db.connect(tmp_path / "cap.db")
    db.init_db(conn)
    called = False

    def transport(*_):
        nonlocal called
        called = True
        return {"data": []}

    client = KalodataClient(conn, run_id="r1", api_key="x", transport=transport, credit_cap=.1)
    client.creator_detail("c1")
    with pytest.raises(CreditCounter.CapExceeded):
        client.video_url("v1")
    assert called
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 1


def test_strip_contacts_recurses():
    assert strip_contacts({"nested": [{"creator_contact_zalo": "x", "ok": 1}]}) == {"nested": [{"ok": 1}]}


def test_retries_server_errors_three_times_then_logs_success(tmp_path):
    conn = db.connect(tmp_path / "retry.db")
    db.init_db(conn)
    responses = iter([(503, {}), (500, {}), (200, {"data": []})])
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: next(responses), sleep=delays.append)
    assert client.creator_detail("c1") == {"data": []}
    assert delays[0] == 1
    assert delays[-1] == pytest.approx(2, abs=.05)
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 3
    assert conn.execute("SELECT SUM(credits) FROM api_calls").fetchone()[0] == pytest.approx(.1)


@pytest.mark.parametrize(("response", "message"), [
    ((401, {}), "Xác thực Kalodata thất bại (401)."),
    ((400, {}), "Yêu cầu Kalodata thất bại (400)."),
    ((500, {}), "Yêu cầu Kalodata thất bại (500)."),
])
def test_request_errors_are_in_vietnamese(tmp_path, response, message):
    conn = db.connect(tmp_path / "errors.db")
    db.init_db(conn)
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: response, sleep=lambda _: None)
    with pytest.raises(RuntimeError, match=message.replace("(", r"\(").replace(")", r"\)")):
        client.creator_detail("c1")


def test_category_rank_uses_cached_category_endpoint(tmp_path):
    conn = db.connect(tmp_path / "categories.db")
    db.init_db(conn)
    seen = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda endpoint, body, _: (seen.append((endpoint, body)) or {"data": [{"category_id": "1", "category_name": "Skincare"}]}))
    assert client.category_rank()["data"][0]["category_name"] == "Skincare"
    client.category_rank()
    assert seen[0][0] == "category/rank"
    assert seen[0][1]["category_level"] == 3
    assert conn.execute("SELECT cache_hit FROM api_calls ORDER BY id DESC LIMIT 1").fetchone()[0] == 1


def test_api_error_is_not_cached_and_costs_zero_credits(tmp_path):
    conn = db.connect(tmp_path / "api-error.db")
    db.init_db(conn)
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: {
        "success": False, "code": "501", "errorCategory": "VALIDATION",
        "message": "The key is not allowed",
    })

    for _ in range(2):
        with pytest.raises(RuntimeError, match=r"Kalodata từ chối creator/rank \(501 VALIDATION\): The key is not allowed"):
            client.creator_rank(page_size=1)

    calls = conn.execute("SELECT status,credits,cache_hit FROM api_calls ORDER BY id").fetchall()
    assert [tuple(row) for row in calls] == [("api_error:501", 0, 0), ("api_error:501", 0, 0)]
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_rate_limit_retries_then_succeeds_without_caching_or_charging(tmp_path):
    conn = db.connect(tmp_path / "rate-limit-retry.db")
    db.init_db(conn)
    responses = iter([
        {"success": False, "code": "2017", "errorCategory": "RATE_LIMIT", "message": "Try again later"},
        {"data": []},
    ])
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: next(responses), sleep=delays.append)

    assert client.creator_detail("c1") == {"data": []}
    assert [delay for delay in delays if delay in (15, 60, 180)] == [15]
    calls = conn.execute("SELECT status,credits,cache_hit FROM api_calls ORDER BY id").fetchall()
    assert [tuple(row) for row in calls] == [("api_error:2017", 0, 0), ("200", pytest.approx(.1), 0)]
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 1


def test_rate_limit_exhaustion_raises_after_three_delays(tmp_path):
    conn = db.connect(tmp_path / "rate-limit-exhausted.db")
    db.init_db(conn)
    response = {"success": False, "code": "2017", "errorCategory": "RATE_LIMIT", "message": "Try again later"}
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: response, sleep=delays.append)

    with pytest.raises(KalodataRateLimited, match="Kalodata giới hạn lưu lượng"):
        client.creator_detail("c1")

    assert [delay for delay in delays if delay in (15, 60, 180)] == [15, 60, 180]
    assert conn.execute("SELECT COUNT(*) FROM api_calls WHERE credits=0 AND cache_hit=0").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_mixed_http_and_logical_retries_never_return_rate_limit_as_data(tmp_path):
    conn = db.connect(tmp_path / "mixed-rate-limit.db")
    db.init_db(conn)
    responses = iter([
        (503, {}),
        {"success": False, "code": "2017", "errorCategory": "RATE_LIMIT"},
        {"success": False, "code": "2017", "errorCategory": "RATE_LIMIT"},
        {"success": False, "code": "2017", "errorCategory": "RATE_LIMIT"},
    ])
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: next(responses), sleep=delays.append)
    client._pace = lambda _endpoint: None

    with pytest.raises(KalodataRateLimited):
        client.creator_detail("c1")

    assert delays == [1, 15, 60, 180]
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_exhausted_http_429_raises_rate_limited(tmp_path):
    conn = db.connect(tmp_path / "http-429.db")
    db.init_db(conn)
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: (429, {}), sleep=delays.append)
    client._pace = lambda _endpoint: None

    with pytest.raises(KalodataRateLimited):
        client.creator_detail("c1")

    assert delays == [1, 2]
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_minimum_interval_applies_across_endpoints(tmp_path, monkeypatch):
    import koc.kalodata as kalodata

    conn = db.connect(tmp_path / "pace.db")
    db.init_db(conn)
    clock = {"now": 0.0}
    delays = []
    monkeypatch.setattr(kalodata.time, "monotonic", lambda: clock["now"])
    def sleep(delay):
        delays.append(delay)
        clock["now"] += delay

    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: {"data": []}, sleep=sleep)
    client.creator_detail("c1")
    client.video_url("v1")

    assert delays == [2.0]


def test_success_true_response_is_cached(tmp_path):
    conn = db.connect(tmp_path / "api-success.db")
    db.init_db(conn)
    calls = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: (
        calls.append(1) or {"success": True, "data": []}
    ))

    assert client.creator_rank(page_size=1) == {"success": True, "data": []}
    assert client.creator_rank(page_size=1) == {"success": True, "data": []}
    assert len(calls) == 1


def test_not_found_is_cached_as_empty_answer_without_credits(tmp_path):
    conn = db.connect(tmp_path / "not-found.db")
    db.init_db(conn)
    calls = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: (
        calls.append(1) or {"success": False, "code": None, "message": "Video Not Found"}
    ))

    assert client.video_rank("c1") == {"data": [], "not_found": True}
    assert client.video_rank("c1") == {"data": [], "not_found": True}
    assert len(calls) == 1
    row = conn.execute("SELECT status,credits FROM api_calls WHERE cache_hit=0").fetchone()
    assert tuple(row) == ("not_found", 0)
    assert conn.execute("SELECT SUM(credits) FROM api_calls").fetchone()[0] == 0


def test_video_url_not_ready_retries_without_billing_or_cache(tmp_path):
    conn = db.connect(tmp_path / "video-not-ready.db")
    db.init_db(conn)
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: {
        "success": False, "code": "1054", "message": "Video is being fetched, please try again"
    }, sleep=delays.append)
    client._pace = lambda _endpoint: None

    with pytest.raises(KalodataNotReady, match="Video Kalodata chưa sẵn sàng"):
        client.video_url("v1")

    assert delays == [30, 60, 120]
    assert [tuple(row) for row in conn.execute("SELECT status,credits,cache_hit FROM api_calls")] == [
        ("api_error:1054", 0, 0), ("api_error:1054", 0, 0), ("api_error:1054", 0, 0), ("api_error:1054", 0, 0)
    ]
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


@pytest.mark.parametrize(("endpoint", "response"), [
    ("video/rank", {"success": False, "code": "AUTH_ERROR", "errorCategory": "AUTH", "message": "API key not found"}),
    ("video/rank", {"success": False, "code": None, "errorCategory": "VALIDATION", "message": "Video not found"}),
    ("creator/detail", {"success": False, "code": None, "errorCategory": None, "message": "Creator not found"}),
    ("category/rank", {"success": False, "code": None, "errorCategory": None, "message": "Category not found"}),
])
def test_non_video_not_found_errors_are_not_cached(tmp_path, endpoint, response):
    conn = db.connect(tmp_path / "not-found-error.db")
    db.init_db(conn)
    calls = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: (calls.append(1) or response))
    request = {
        "video/rank": lambda: client.video_rank("c1"),
        "creator/detail": lambda: client.creator_detail("c1"),
        "category/rank": client.category_rank,
    }[endpoint]

    for _ in range(2):
        with pytest.raises(RuntimeError, match="Kalodata từ chối"):
            request()

    assert len(calls) == 2
    assert conn.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_mixed_http_error_then_1054_ends_in_not_ready(tmp_path):
    """F3: HTTP 500 followed by three 1054 responses must end in KalodataNotReady, not a generic RuntimeError."""
    conn = db.connect(tmp_path / "mixed.db")
    db.init_db(conn)
    responses = iter([(500, {})] + [(200, {"success": False, "code": "1054", "message": "Video being fetched"})] * 3)
    delays = []
    client = KalodataClient(conn, run_id="r1", api_key="x", transport=lambda *_: next(responses), sleep=delays.append)
    client._pace = lambda _endpoint: None

    with pytest.raises(KalodataNotReady):
        client.video_url("v1")

    assert delays == [1, 30, 60]  # last attempt of the shared budget does not sleep
    assert conn.execute("SELECT COALESCE(SUM(credits),0) FROM api_calls").fetchone()[0] == 0
