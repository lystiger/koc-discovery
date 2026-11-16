import json

import pytest
from typer.testing import CliRunner

import koc.cli as cli
from koc import db
from koc.brief import make_brief
from koc.pipeline import start


@pytest.fixture
def conn(tmp_path, monkeypatch, stable_test_config):
    monkeypatch.chdir(tmp_path)  # mock media goes to ./data/media
    c = db.connect(tmp_path / "x.db")
    db.init_db(c)
    return c


def _picks(conn, run_id):
    return [row[0] for row in conn.execute("SELECT creator_id FROM recommendations WHERE run_id=? ORDER BY rank", (run_id,))]


def _pool(conn, run_id):
    return {row[0] for row in conn.execute("SELECT creator_id FROM scores WHERE run_id=? AND stage='S1'", (run_id,))}


def _brief(config):
    return make_brief(config, category_ids=["111"], count=5, budget=30_000_000)


def test_excluded_picks_leave_pool_and_picks(conn, stable_test_config):
    first = start(conn, limit=20, mock=True, brief=_brief(stable_test_config))
    old = _picks(conn, first)
    assert len(old) == 5
    second = start(conn, limit=20, mock=True, brief=_brief(stable_test_config), exclude_run_ids=[first])
    assert not set(old) & _pool(conn, second)
    assert not set(old) & set(_picks(conn, second))
    assert len(_picks(conn, second)) == 5
    params = json.loads(conn.execute("SELECT params_json FROM runs WHERE run_id=?", (second,)).fetchone()[0])
    assert params["exclude"] == {"run_ids": [first], "creator_ids": sorted(old)}


def test_exclusion_set_changes_picks_vs_plain_rerun(conn, stable_test_config):
    first = start(conn, limit=20, mock=True, brief=_brief(stable_test_config))
    plain = start(conn, limit=20, mock=True, brief=_brief(stable_test_config))
    excluded = start(conn, limit=20, mock=True, brief=_brief(stable_test_config), exclude_run_ids=[first])
    assert _picks(conn, plain) == _picks(conn, first)
    assert set(_picks(conn, excluded)).isdisjoint(_picks(conn, first))


def test_two_runs_excluded_together(conn, stable_test_config):
    a = start(conn, limit=30, mock=True, brief=_brief(stable_test_config))
    b = start(conn, limit=30, mock=True, brief=_brief(stable_test_config), exclude_run_ids=[a])
    c = start(conn, limit=30, mock=True, brief=_brief(stable_test_config), exclude_run_ids=[a, b])
    assert set(_picks(conn, c)).isdisjoint(_picks(conn, a) + _picks(conn, b))


def test_unknown_run_fails_early_with_zero_spend(conn, stable_test_config):
    with pytest.raises(RuntimeError, match="Không tìm thấy lượt chạy nope"):
        start(conn, limit=20, mock=True, brief=_brief(stable_test_config), exclude_run_ids=["nope"])
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 0


def test_run_without_picks_fails_early(conn, stable_test_config):
    empty = db.create_run(conn, {})
    with pytest.raises(RuntimeError, match="chưa có KOC nào được đề xuất"):
        start(conn, limit=20, mock=True, brief=_brief(stable_test_config), exclude_run_ids=[empty])
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_cli_reports_exclusion_in_vietnamese(conn, tmp_path, monkeypatch, stable_test_config):
    first = start(conn, limit=20, mock=True, brief=_brief(stable_test_config))
    conn.close()
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "x.db")
    result = CliRunner().invoke(cli.app, ["run", "--limit", "20", "--mock", "--category-ids", "111", "--exclude-run", first])
    assert result.exit_code == 0, result.output
    assert f"Đã loại 5 KOC đã đề xuất ở lần chạy {first}" in result.output


def test_cli_unknown_run_exits_with_vietnamese_error(conn, tmp_path, monkeypatch):
    conn.close()
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "x.db")
    result = CliRunner().invoke(cli.app, ["run", "--limit", "20", "--mock", "--category-ids", "111", "--exclude-run", "nope"])
    assert result.exit_code == 1
    assert "Không tìm thấy lượt chạy nope" in result.output


def test_count_10_run_excludes_all_ten_picks(conn, stable_test_config):
    brief = make_brief(stable_test_config, category_ids=["111"], count=10, budget=60_000_000)
    first = start(conn, limit=30, mock=True, brief=brief)
    old = _picks(conn, first)
    assert len(old) == 10
    second = start(conn, limit=30, mock=True, brief=brief, exclude_run_ids=[first])
    assert len(_pool(conn, first)) - len(_pool(conn, second)) == 10
    assert set(old).isdisjoint(_pool(conn, second)) and set(old).isdisjoint(_picks(conn, second))


def test_resume_keeps_exclusion(conn, stable_test_config):
    from koc.pipeline import resume
    first = start(conn, limit=20, mock=True, brief=_brief(stable_test_config))
    second = start(conn, limit=20, mock=True, brief=_brief(stable_test_config), exclude_run_ids=[first])
    conn.execute("DELETE FROM recommendations WHERE run_id=?", (second,))
    conn.execute("UPDATE tasks SET status='pending' WHERE run_id=? AND stage='S4'", (second,))
    conn.execute("UPDATE runs SET status='blocked' WHERE run_id=?", (second,))
    conn.commit()
    assert resume(conn, mock=True) == second
    assert set(_picks(conn, second)).isdisjoint(_picks(conn, first)) and len(_picks(conn, second)) == 5
