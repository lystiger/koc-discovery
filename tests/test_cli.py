from typer.testing import CliRunner

from kalodata_intake.cli import app

runner = CliRunner()


def test_collect_dry_run_writes_no_db(tmp_path, raw_file):
    db_path = tmp_path / "intake.db"
    result = runner.invoke(app, [
        "intake", "collect", "--limit-creators", "3", "--videos-per-creator", "2",
        "--dry-run", "--db", str(db_path), "--source-file", str(raw_file),
    ])
    assert result.exit_code == 0, result.output
    assert "planned creator c1" in result.output
    assert "nothing written" in result.output
    assert not db_path.exists()
