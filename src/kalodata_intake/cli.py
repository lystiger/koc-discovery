import importlib.util
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from glob import glob
from pathlib import Path

import typer
from pydantic import ValidationError

from . import db, mapping
from .schemas import Creator, FieldValue, MediaAnalysis, Video, field_values

app = typer.Typer(no_args_is_help=True)
intake = typer.Typer(no_args_is_help=True)
media = typer.Typer(no_args_is_help=True)
app.add_typer(intake, name="intake")
app.add_typer(media, name="media")

RAW_GLOB = "data/raw/*.json"
DB_OPTION = typer.Option("data/intake.db", "--db")


def _open(db_path: str):
    conn = db.connect(db_path)
    db.init_db(conn)
    return conn


def _load(paths: list[str]) -> list[dict]:
    records: list[dict] = []
    for path in paths:
        records.extend(json.loads(Path(path).read_text()))
    return records


def _index(records: list[dict]) -> dict[tuple[str, str], dict]:
    index = {}
    for rec in records:
        if rec.get("type") == "creator":
            index[("creator", mapping.creator_id(rec["fields"]))] = rec
        elif rec.get("type") == "video":
            index[("video", mapping.video_id(rec["fields"]))] = rec
    return index


def _plan(records: list[dict], limit_creators: int, videos_per_creator: int) -> list[tuple[str, str, dict]]:
    creators = [r for r in records if r.get("type") == "creator"][:limit_creators]
    plan = []
    for rec in creators:
        cid = mapping.creator_id(rec["fields"])
        plan.append(("creator", cid, rec))
        videos = [
            r for r in records
            if r.get("type") == "video" and r["fields"].get(mapping.VIDEO_CREATOR_ID_LABEL) == cid
        ][:videos_per_creator]
        plan.extend(("video", mapping.video_id(v["fields"]), v) for v in videos)
    return plan


def _writer(kind: str, rec: dict):
    collected_at = datetime.fromisoformat(rec["collected_at"])
    if kind == "creator":
        creator = mapping.normalize_creator(rec["fields"], rec["source"], rec.get("period"), collected_at)
        return lambda conn: db.upsert_creator(conn, creator)
    video = mapping.normalize_video(rec["fields"], rec["source"], rec.get("period"), collected_at)
    return lambda conn: db.upsert_video(conn, video)


def _process(conn, run_id: str, index: dict) -> None:
    for task in db.next_pending_tasks(conn, run_id):
        db.mark_task(conn, task["task_id"], "running")
        try:
            write = _writer(task["kind"], index[(task["kind"], task["key"])])
            db.complete_task_with(conn, task["task_id"], write)
        except (KeyError, ValueError) as exc:
            db.mark_task(conn, task["task_id"], "failed", error=str(exc))
    if not db.next_pending_tasks(conn, run_id):
        db.finish_run(conn, run_id)


@intake.command("inspect")
def inspect_env() -> None:
    """Print python, ffmpeg, playwright and chromium availability."""
    typer.echo(f"python: {sys.version.split()[0]}")
    typer.echo(f"ffmpeg: {shutil.which('ffmpeg') or 'missing'}")
    typer.echo(f"playwright: {'installed' if importlib.util.find_spec('playwright') else 'missing'}")
    chromium = next((c for c in ("chromium", "chromium-browser", "google-chrome") if shutil.which(c)), None)
    typer.echo(f"chromium: {chromium or 'missing'}")


@intake.command("collect")
def collect(
    limit_creators: int = typer.Option(3, "--limit-creators"),
    videos_per_creator: int = typer.Option(2, "--videos-per-creator"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    db_path: str = DB_OPTION,
    source_file: Path | None = typer.Option(None, "--source-file"),
) -> None:
    """Normalize already-captured raw JSON (no network) and upsert it."""
    paths = [str(source_file)] if source_file else sorted(glob(RAW_GLOB))
    if not paths:
        typer.echo(f"no raw files found under {RAW_GLOB}")
        raise typer.Exit(1)
    records = _load(paths)
    plan = _plan(records, limit_creators, videos_per_creator)
    for kind, key, _ in plan:
        typer.echo(f"planned {kind} {key}")
    if dry_run:
        typer.echo(f"dry run: {len(plan)} tasks, nothing written")
        return
    conn = _open(db_path)
    run_id = db.start_run(conn, {
        "source_files": [str(Path(p).resolve()) for p in paths],
        "limit_creators": limit_creators,
        "videos_per_creator": videos_per_creator,
    })
    for kind, key, _ in plan:
        db.add_task(conn, run_id, kind, key)
    _process(conn, run_id, _index(records))
    typer.echo(f"run {run_id}: {len(plan)} tasks processed")


@intake.command("resume")
def resume(db_path: str = DB_OPTION) -> None:
    """Reset interrupted tasks in the latest run and process pending ones."""
    conn = _open(db_path)
    run = db.latest_run(conn)
    if run is None:
        typer.echo("no runs found")
        raise typer.Exit(1)
    db.reset_running(conn, run["run_id"])
    records = _load(json.loads(run["params"])["source_files"])
    _process(conn, run["run_id"], _index(records))
    typer.echo(f"resumed run {run['run_id']}")


@intake.command("validate")
def validate(db_path: str = DB_OPTION) -> None:
    """Re-validate stored rows against the schemas and count field statuses."""
    conn = _open(db_path)
    counts: dict[str, Counter] = defaultdict(Counter)
    invalid = 0
    for table, model in (("creators", Creator), ("videos", Video)):
        for row in conn.execute(f"SELECT data FROM {table}").fetchall():
            try:
                entity = model.model_validate_json(row["data"])
            except ValidationError as exc:
                invalid += 1
                typer.echo(f"invalid {table} row: {exc.errors()[0]['msg']}")
                continue
            for field, fv in field_values(entity).items():
                counts[f"{table}.{field}"][fv.status] += 1
    for key in sorted(counts):
        summary = " ".join(f"{s}={n}" for s, n in sorted(counts[key].items()))
        typer.echo(f"{key}: {summary}")
    typer.echo(f"invalid rows: {invalid}")


@media.command("test")
def media_test(
    limit: int = typer.Option(1, "--limit"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    db_path: str = DB_OPTION,
) -> None:
    """Pick videos for a media analysis test. Runs are done by Agy."""
    video_ids: list[str] = []
    if Path(db_path).exists():
        conn = db.connect(db_path)
        video_ids = [
            r["video_id"]
            for r in conn.execute("SELECT video_id FROM videos ORDER BY updated_at LIMIT ?", (limit,))
        ]
    if dry_run:
        for vid in video_ids:
            typer.echo(f"would send {vid}")
        return
    typer.echo("media tests are run by Agy; record results with `media record FILE`")


@media.command("record")
def media_record(file: Path, db_path: str = DB_OPTION) -> None:
    """Validate a MediaAnalysis JSON file with call metadata and store it."""
    payload = json.loads(file.read_text())
    try:
        analysis = MediaAnalysis.model_validate(payload.get("output", payload.get("analysis")))
    except (KeyError, ValidationError) as exc:
        typer.echo(f"invalid media analysis, nothing recorded: {exc}")
        raise typer.Exit(1)
    conn = _open(db_path)
    db.insert_media_test(conn, {
        "video_id": analysis.video_id,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "prompt_version": payload.get("prompt_version"),
        "preprocess": json.dumps(payload.get("preprocess")),
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "latency_ms": payload.get("latency_ms"),
        "est_cost": payload.get("est_cost"),
        "actual_cost": payload.get("actual_cost"),
        "validation_status": "valid",
        "output": analysis.model_dump_json(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    typer.echo(f"recorded media test for {analysis.video_id}")


@app.command("report")
def report(
    db_path: str = DB_OPTION,
    out: Path = typer.Option("reports/feasibility.json", "--out"),
) -> None:
    """Dump coverage, task and media counts to JSON."""
    conn = _open(db_path)

    def count(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]

    coverage: dict[str, dict[str, int]] = defaultdict(dict)
    for r in conn.execute(
        "SELECT entity_type, field, status, COUNT(*) AS n FROM source_evidence "
        "GROUP BY entity_type, field, status"
    ):
        coverage[f"{r['entity_type']}.{r['field']}"][r["status"]] = r["n"]
    data = {
        "creators": count("SELECT COUNT(*) FROM creators"),
        "videos": count("SELECT COUNT(*) FROM videos"),
        "field_status": coverage,
        "tasks": {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM extraction_tasks GROUP BY status")},
        "media_tests": {r["validation_status"]: r["n"] for r in conn.execute(
            "SELECT validation_status, COUNT(*) AS n FROM media_tests GROUP BY validation_status")},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str))
    typer.echo(f"wrote {out}")


if __name__ == "__main__":
    app()
