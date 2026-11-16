"""Regression tests: dashboard with every task status, and frames stored under frames/<video_id>/."""
import json
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from koc.web.app import create_app
from koc.web.adapter import media_web_url
from tests.web.fixtures.seed import seed_fixture_db

RUN = "run_mock_beauty_01"
CREATOR = "c_linh_01"


@pytest.fixture
def env(tmp_path):
    db_file = tmp_path / "fixture.db"
    media_dir = tmp_path / "data" / "media"
    seed_fixture_db(db_path=db_file, media_dir=media_dir)
    conn = sqlite3.connect(db_file)
    for status in ("skipped", "blocked"):
        conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,0,NULL,'2026-01-01')", (f"{RUN}:S2:{status}", RUN, "S2", status, status))
    # Real-run layout: <media_dir>/frames/<video_id>/f_<t_ms>.jpg referenced by a repo-relative path.
    for video_id, blob in conn.execute("SELECT video_id,analysis_json FROM analyses").fetchall():
        analysis = json.loads(blob)
        for index, evidence in enumerate(analysis.get("evidence", [])):
            if evidence.get("frame_path"):
                frame = media_dir / "frames" / video_id / f"f_{500 + index * 1000}.jpg"
                frame.parent.mkdir(parents=True, exist_ok=True)
                frame.write_bytes(Path(evidence["frame_path"]).read_bytes())
                evidence["frame_path"] = f"data/media/frames/{video_id}/{frame.name}"
        conn.execute("UPDATE analyses SET analysis_json=? WHERE video_id=?", (json.dumps(analysis), video_id))
    params = json.loads(conn.execute("SELECT params_json FROM runs WHERE run_id=?", (RUN,)).fetchone()[0])
    params["mock"] = False  # mock runs show placeholders instead of frames
    conn.execute("UPDATE runs SET params_json=? WHERE run_id=?", (json.dumps(params), RUN))
    conn.execute("UPDATE analyses SET prompt_version='content_v3'")  # a real run reads the current S3 prompt
    conn.commit()
    conn.close()
    return TestClient(create_app(db_path=str(db_file), media_dir=str(media_dir)))


def test_dashboard_handles_every_task_status(env):
    response = env.get(f"/runs/{RUN}/dashboard")
    assert response.status_code == 200
    assert "Bỏ qua" in response.text and "Bị chặn" in response.text


def test_media_web_url_keeps_video_folder():
    assert media_web_url("data/media/frames/123/f_500.jpg") == "/media/frames/123/f_500.jpg"
    assert media_web_url("/abs/path/data/media/frames/123/f_500.jpg") == "/media/frames/123/f_500.jpg"
    assert media_web_url("/tmp/media/flat.jpg") == "/media/flat.jpg"


def test_detail_page_frame_urls_include_video_folder_and_are_served(env):
    page = env.get(f"/runs/{RUN}/creators/{CREATOR}")
    assert page.status_code == 200
    urls = set(re.findall(r'src="(/media/frames/[^"]+)"', page.text))
    assert urls and all(re.fullmatch(r"/media/frames/[^/]+/f_\d+\.jpg", url) for url in urls)
    for url in urls:
        served = env.get(url)
        assert served.status_code == 200 and served.headers["content-type"].startswith("image/")
