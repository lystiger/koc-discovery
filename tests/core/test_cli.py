import pytest
from typer.testing import CliRunner

from koc.cli import app
from koc.cli import save_category_ids
from koc import db


def test_dry_run_does_not_open_database_or_network(tmp_path, monkeypatch, stable_test_config):
    import socket

    db_path = tmp_path / "never.db"
    monkeypatch.setenv("KOC_DB", str(db_path))
    monkeypatch.setattr(socket.socket, "connect", lambda *_: (_ for _ in ()).throw(AssertionError("network attempted")))
    result = CliRunner().invoke(app, ["run", "--limit", "5", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "5" in result.output
    assert "S0+S1 dự kiến: tối đa 1.1" in result.output
    assert "Tín dụng S2 dự kiến: tối đa 5.0" in result.output
    assert not db_path.exists()


def test_category_keyword_saves_matching_ids(tmp_path):
    config = tmp_path / "scoring.yaml"
    config.write_text("s0:\n  category_ids: []\n")
    rows = [{"category_id": "1", "category_name": "Skincare"}, {"category_id": "2", "category_name": "Fashion"}]
    result = save_category_ids(rows, "skin", config)
    assert [row["category_id"] for row in result] == ["1"]
    assert "category_ids:\n  - '1'" in config.read_text()


def test_status_reports_budget_block_reason(tmp_path, monkeypatch):
    db_path = tmp_path / "status.db"
    import koc.cli as cli
    monkeypatch.setattr(cli, "DB_PATH", db_path)
    conn = db.connect(db_path)
    db.init_db(conn)
    run_id = db.create_run(conn, {})
    task_id = db.add_task(conn, run_id, "S3", "c1")
    db.block_task(conn, task_id, "Hạn mức LLM 1.00 USD đã bị vượt.")
    db.finish_run(conn, run_id, "blocked")
    conn.close()

    result = CliRunner().invoke(app, ["status"])

    assert result.exit_code == 0
    assert "lý do: Hạn mức LLM 1.00 USD đã bị vượt." in result.output


def test_categories_prints_kalodata_error_and_exits(tmp_path, monkeypatch):
    import koc.cli as cli

    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "categories.db")

    class FailingClient:
        def __init__(self, *_):
            pass

        def category_rank(self, **_):
            raise RuntimeError("Kalodata từ chối category/rank (501 VALIDATION): denied")

    monkeypatch.setattr("koc.kalodata.KalodataClient", FailingClient)
    result = CliRunner().invoke(app, ["categories", "--keyword", "skin"])
    assert result.exit_code == 1
    assert "Kalodata từ chối category/rank (501 VALIDATION): denied" in result.output


def test_run_prints_kalodata_error_and_exits(tmp_path, monkeypatch):
    import koc.cli as cli

    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "run.db")
    monkeypatch.setattr(cli, "start", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("Kalodata từ chối creator/rank (501 VALIDATION): denied")
    ))
    result = CliRunner().invoke(app, ["run", "--limit", "1"])
    assert result.exit_code == 1
    assert "Kalodata từ chối creator/rank (501 VALIDATION): denied" in result.output


@pytest.mark.parametrize("command", ["resume", "audience"])
def test_resume_commands_print_runtime_error_without_traceback(tmp_path, monkeypatch, command):
    import koc.cli as cli

    monkeypatch.setattr(cli, "DB_PATH", tmp_path / f"{command}.db")
    conn = db.connect(cli.DB_PATH)
    db.init_db(conn)
    conn.close()
    monkeypatch.setattr(cli, "resume_pipeline", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Kalodata failed")))

    result = CliRunner().invoke(app, [command])
    assert result.exit_code == 1
    assert "Kalodata failed" in result.output
    assert "Traceback" not in result.output
