import json
import sqlite3
import uuid

from koc.db import now


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS campaigns ("
        "campaign_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
        "input_json TEXT NOT NULL, result_json TEXT NOT NULL)"
    )
    conn.commit()


def save(conn: sqlite3.Connection, campaign_input: dict, result: dict) -> dict:
    campaign = {
        "campaign_id": uuid.uuid4().hex,
        "created_at": now(),
        "input": campaign_input,
        "result": result,
    }
    conn.execute(
        "INSERT INTO campaigns VALUES (?, ?, ?, ?)",
        (
            campaign["campaign_id"],
            campaign["created_at"],
            json.dumps(campaign_input, ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
        ),
    )
    conn.commit()
    return campaign


def get(conn: sqlite3.Connection, campaign_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM campaigns WHERE campaign_id=?", (campaign_id,)).fetchone()
    if not row:
        return None
    return {
        "campaign_id": row["campaign_id"],
        "created_at": row["created_at"],
        "input": json.loads(row["input_json"]),
        "result": json.loads(row["result_json"]),
    }


def list_all(conn: sqlite3.Connection) -> list[dict]:
    return [
        {
            "campaign_id": row["campaign_id"],
            "created_at": row["created_at"],
            "input": json.loads(row["input_json"]),
            "picked_count": len(json.loads(row["result_json"]).get("picked", [])),
        }
        for row in conn.execute("SELECT * FROM campaigns ORDER BY rowid DESC")
    ]
