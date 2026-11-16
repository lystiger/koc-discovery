#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

run_case() {
  local stage="$1"
  local database="$TMP/$stage.db"
  local marker="$TMP/$stage.ready"
  local pause_variable="KOC_TEST_PAUSE_AFTER_S1_API"
  [[ "$stage" == "S3" ]] && pause_variable="KOC_TEST_PAUSE_AFTER_LLM"
  env KOC_DB="$database" KOC_TEST_STAGE_MARKER="$marker" "$pause_variable=1" \
    PYTHONPATH="$ROOT/src" "$PYTHON" -m koc.cli run --mock --limit 50 &
  local pid=$!
  for _ in $(seq 1 500); do
    [[ -f "$marker" ]] && break
    kill -0 "$pid" 2>/dev/null || { wait "$pid"; return 1; }
    sleep 0.02
  done
  [[ -f "$marker" ]] || { kill -9 "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; echo "Không tới giai đoạn $stage" >&2; return 1; }
  kill -9 "$pid"
  wait "$pid" 2>/dev/null || true
  KOC_DB="$database" PYTHONPATH="$ROOT/src" "$PYTHON" -m koc.cli resume --mock
  KOC_DB="$database" PYTHONPATH="$ROOT/src" "$PYTHON" -m koc.cli run --mock --limit 50
  KOC_DB="$database" PYTHONPATH="$ROOT/src" "$PYTHON" - "$database" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
for table, column in (("tasks", "task_id"), ("videos", "video_id"), ("analyses", "video_id || prompt_version || model"), ("recommendations", "run_id || creator_id")):
    total, unique = c.execute(f"SELECT COUNT(*),COUNT(DISTINCT {column}) FROM {table}").fetchone()
    assert total == unique, (table, total, unique)
for table, key in (("api_calls", "request_hash"), ("llm_calls", "request_hash")):
    duplicates = c.execute(f"SELECT 1 FROM {table} WHERE cache_hit=0 GROUP BY {key} HAVING COUNT(*)>1 LIMIT 1").fetchone()
    assert duplicates is None, (table, duplicates)
assert c.execute("SELECT status FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()[0] == "done"
PY
  KOC_DB="$database" PYTHONPATH="$ROOT/src" "$PYTHON" -m koc.cli resume --mock
  KOC_DB="$database" PYTHONPATH="$ROOT/src" "$PYTHON" - "$database" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
assert c.execute("SELECT COALESCE(SUM(credits),0) FROM api_calls").fetchone()[0] == 0
assert c.execute("SELECT COALESCE(SUM(input_tokens+output_tokens),0) FROM llm_calls").fetchone()[0] == 0
run_id = c.execute("SELECT run_id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()[0]
assert c.execute("SELECT COUNT(*) FROM llm_calls WHERE run_id=? AND cache_hit=0", (run_id,)).fetchone()[0] == 0
PY
  echo "SIGKILL + resume: $stage PASS"
}

run_case S1b
run_case S3
