import json

from .config import load_config
from .stages import brand_fit_gate


def list_runs(conn):
    return [dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY started_at DESC")]


def get_run(conn, run_id: str):
    row = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return dict(row) if row else None


def top5(conn, run_id: str):
    config = load_config()
    run = get_run(conn, run_id)
    brief = (json.loads(run["params_json"]).get("brief") if run else None) or {}
    limit = brief.get("count", 5) if isinstance(brief, dict) else 5
    rows = conn.execute("SELECT * FROM recommendations WHERE run_id=? ORDER BY rank", (run_id,)).fetchall()
    # D-B7 at read time: a stored pick that fails the brand_fit gate is never served.
    rows = [row for row in rows if brand_fit_gate(conn, run_id, row["creator_id"], config)["eligible"]][:limit]
    return [{**dict(row), "recommendation": json.loads(row["rec_json"])} for row in rows]


def creator_detail(conn, run_id: str, creator_id: str):
    creator = conn.execute("SELECT * FROM creators WHERE creator_id=?", (creator_id,)).fetchone()
    if not creator:
        return None
    return {
        "creator": dict(creator),
        "metrics": [dict(row) for row in conn.execute("SELECT * FROM metrics WHERE creator_id=? ORDER BY name", (creator_id,))],
        "scores": [dict(row) for row in conn.execute("SELECT * FROM scores WHERE run_id=? AND creator_id=?", (run_id, creator_id))],
    }


def run_costs(conn, run_id: str):
    api = conn.execute("SELECT COALESCE(SUM(credits),0),COALESCE(SUM(latency_ms),0) FROM api_calls WHERE run_id=?", (run_id,)).fetchone()
    llm = conn.execute("SELECT COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0),COALESCE(SUM(cost_usd),0) FROM llm_calls WHERE run_id=?", (run_id,)).fetchone()
    return {"credits": api[0], "api_latency_ms": api[1], "input_tokens": llm[0], "output_tokens": llm[1], "cost_usd": llm[2]}
