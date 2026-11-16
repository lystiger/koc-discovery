"""scripts/s3_pending_videos.py must leave the --db file byte-identical (cache-hit logging goes to an in-memory copy)."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from koc import db
from koc.kalodata import KalodataClient

REPO = Path(__file__).resolve().parents[2]


def test_db_file_unchanged_after_run(tmp_path, monkeypatch, capsys):
    path = tmp_path / "fixture.db"
    conn = db.connect(path)
    db.init_db(conn)
    conn.execute("INSERT INTO runs VALUES ('r1','2026-01-01T00:00:00','', 'done', ?)", (json.dumps({}),))
    conn.execute("INSERT INTO tasks VALUES ('t1','r1','S3','c1','pending',0,NULL,'2026-01-01T00:00:00')")
    conn.commit()
    KalodataClient(conn, run_id=None, cache_only=True)  # same client class the script uses
    body = {"region": "VN", "language": "vi-VN", "currency": "VND", "date_range": "last30Day", "creator_id": "c1",
            "sort_field": {"field": "revenue", "type": "DESC"}, "page_size": 100, "page_number": 1}
    db.http_cache_put(conn, db.cache_key("video/rank", body), "video/rank", {"data": []})
    conn.commit()
    conn.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location("s3_pending_videos", REPO / "scripts" / "s3_pending_videos.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", ["x", "--db", str(path), "--run-id", "r1", "--media-dir", str(tmp_path)])
    module.main()
    assert "videos picked: 0" in capsys.readouterr().out
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
