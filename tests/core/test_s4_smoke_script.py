import shutil

import pytest
import subprocess
import sys
from pathlib import Path

from koc import db
from tests.analysis_seed import seed_brand_fit

REPO = Path(__file__).resolve().parents[2]


def test_s4_smoke_script_exits_nonzero_on_fail(tmp_path):
    """F6: an empty synthetic DB gives no recommendations: the script prints FAIL and exits 1."""
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / "config" / "llm_prices.yaml", tmp_path / "config" / "llm_prices.yaml")
    conn = db.connect(tmp_path / "data" / "koc.db")
    db.init_db(conn)
    conn.close()
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "s4_free_smoke.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "OPENROUTER_API_KEY": "sk-or-fake", "PYTHONPATH": str(REPO / "src")},
    )
    assert "RESULT FAIL" in result.stdout, result.stderr
    assert result.returncode == 1


def test_s4_smoke_script_passes_on_nonempty_synthetic_db_with_mocked_transport(tmp_path, monkeypatch, capsys):
    """R2-F6: with candidates the script must reach RESULT PASS and exit 0 (its adapter drops cache_only)."""
    import json
    import re
    import runpy

    import httpx

    import koc.llm.factory as factory

    run_id = "7372009b22764b339fbcf0f3efb4bc4e"
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    shutil.copy(REPO / "config" / "llm_prices.yaml", tmp_path / "config" / "llm_prices.yaml")
    conn = db.connect(tmp_path / "data" / "koc.db")
    db.init_db(conn)
    conn.execute("INSERT INTO runs VALUES (?,?,NULL,'done',?)", (run_id, "2026-01-01", json.dumps({"limit": 5})))
    for i, audience in enumerate([(71.0, 20.0, 30.0), (72.0, 21.0, 31.0), (73.0, 22.0, 32.0), (74.0, 23.0, 33.0), (75.0, 24.0, 34.0)]):
        creator_id = f"c{i}"
        db.upsert_creator(conn, creator_id, creator_id, {"creator_followers": 30000})
        for stage, score in (("S1", 80), ("S2", 50), ("S3", 60)):
            db.upsert_score(conn, run_id, creator_id, stage, score, {})
        seed_brand_fit(conn, creator_id)
        for name, value in zip(("female_pct", "age_18_24_pct", "age_25_34_pct"), audience):
            db.upsert_metric(conn, creator_id, name, value, "test")
        db.upsert_metric(conn, creator_id, "video_gpm", 1000, "test")
    conn.commit()
    conn.close()

    def handler(request: httpx.Request) -> httpx.Response:
        creator_id = re.search(r"metric:(\w+):video_gpm", request.content.decode()).group(1)
        content = {"creator_id": creator_id, "reasons_vi": ["Doanh thu dưỡng da tốt.", "Chi phí hợp lý.", "Video có bằng chứng sản phẩm."],
                   "cited_evidence_ids": [f"metric:{creator_id}:video_gpm"], "caveats_vi": []}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.0}})

    real_factory = factory.get_llm_client
    monkeypatch.setattr(factory, "get_llm_client", lambda *a, **kw: real_factory(*a, http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kw))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    import koc.pipeline as pipeline
    monkeypatch.setattr(pipeline, "_cached_call", pipeline._cached_call)  # the script replaces it; restore at teardown
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["s4_free_smoke.py"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(REPO / "scripts" / "s4_free_smoke.py"), run_name="__main__")
    assert exit_info.value.code == 0
    assert "RESULT PASS: 5 recommendations" in capsys.readouterr().out
