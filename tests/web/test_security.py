"""v2 item 6: local-only web hardening."""
import sqlite3

from fastapi.testclient import TestClient

from koc.web.__main__ import host_warning
from koc.web.app import create_app


def test_default_host_is_loopback_and_silent(monkeypatch):
    import sys
    from koc.web import __main__ as m
    seen = {}
    monkeypatch.setattr(m.uvicorn, "run", lambda app, host, port, log_level: seen.update(host=host))
    monkeypatch.setattr(sys, "argv", ["koc.web", "--db", ":memory:"])
    m.main()
    assert seen["host"] == "127.0.0.1"
    assert host_warning("127.0.0.1") is None and host_warning("localhost") is None


def test_public_bind_prints_vietnamese_warning(monkeypatch, capsys):
    import sys
    from koc.web import __main__ as m
    monkeypatch.setattr(m.uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["koc.web", "--host", "0.0.0.0"])
    m.main()
    err = capsys.readouterr().err
    assert "CẢNH BÁO BẢO MẬT" in err and "KHÔNG có đăng nhập" in err


def test_media_symlink_escape_blocked(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    (media / "link.txt").symlink_to(secret)
    (media / "ok.txt").write_text("fine")
    db = tmp_path / "x.db"
    sqlite3.connect(db).close()
    client = TestClient(create_app(db_path=str(db), media_dir=str(media)))
    assert client.get("/media/ok.txt").status_code == 200
    assert client.get("/media/link.txt").status_code == 403
    assert client.get("/media//etc/passwd").status_code in (403, 404)
