Overall FAIL — one P2 correctness bug; one P3 requirement gap.

Independent review of `8fbef7e..65e9be39973174635125ace666b51e316e1810ea` on `worktree-agent-a52e3ed613e6eeb40`, 2026-11-16. No source changes. No network requests. The production database was copied as a file to `/tmp/koc-review-brief-live/koc.db`; SQLite opened only copies.

## Findings

### P2 — Counts above five are silently truncated by the core recommendation query

Location: `src/koc/queries.py:14`; newly exposed by variable selection size at `src/koc/pipeline.py:343`.

`--count 6` is valid and S4 can commit six recommendations, but `queries.top5()` still applies `LIMIT 5`. The core read interface therefore returns a smaller recommendation than the stored brief requests. Its existing consumer also computes spend and leftover from this incomplete list: six 3,000,000 VND creators on an 18,000,000 VND brief produce five displayed cards, 15,000,000 VND spend, and 3,000,000 VND remaining. The committed `params_json.s4` correctly says 18,000,000 VND spent and zero remaining. This is an observable count and spend discrepancy, not a naming/style issue. The responsible query is outside the excluded `web/` ownership scope.

Fix: return the complete committed selection in rank order; remove the fixed five-row cap or derive the cap from the run brief. Keep the legacy five-creator result unchanged.

Reproduction: run the shared offline script below. Its first case prints:

```text
scored=6 requested=6 status=done stored=6 returned=5
s4={'budget_vnd': 18000000, 'leftover_vnd': 0, 'total_vnd': 18000000}
view_cards=5 view_total=15000000 view_remaining=3000000
```

### P3 — Underfilled S4 bypasses the three recovery options

Location: `src/koc/pipeline.py:458`.

When fewer creators have S3 scores than the requested count, execution blocks before `_s4_budget_block_reason()` runs. Two scored 3,000,000 VND creators against a three-creator, 9,000,000 VND brief produce only `Chưa đủ điểm nội dung để đề xuất: có 2, cần 3.` The refusal omits the feasible two-creator/6,000,000 VND alternative and the actual cheapest follower band. Zero scored creators take the same branch and omit all three option slots instead of explicitly reporting unavailable alternatives. Status remains `blocked`, no recommendations are written, and no paid calls occur; this omission is nonblocking under the requested correctness rubric.

Fix: route this refusal through the scored-creator options formatter, retaining the insufficient-score explanation and explicitly marking impossible alternatives unavailable.

Reproduction: the second and third cases below print these errors without `Lựa chọn`:

```text
Chưa đủ điểm nội dung để đề xuất: có 2, cần 3.
Chưa đủ điểm nội dung để đề xuất: có 0, cần 1.
```

## Offline finding reproduction

Run from the reviewed checkout. The external socket guard described below must remain on `PYTHONPATH`.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/koc-review-brief-guard:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python - <<'PY'
import json
from koc import db, pipeline, queries
from koc.brief import make_brief
from koc.config import load_config
from koc.web.adapter import get_top5_with_details

def case(scored, count, budget):
    conn = db.connect(':memory:')
    db.init_db(conn)
    brief = make_brief(load_config(), count=count, budget=budget)
    run_id = db.create_run(conn, {'mock': True, 'brief': brief})
    for index in range(scored):
        creator_id = f'c{index}'
        db.upsert_creator(conn, creator_id, creator_id,
                          {'creator_followers': 30000})
        for stage in ('S1', 'S2', 'S3'):
            db.upsert_score(conn, run_id, creator_id, stage, 80, {})
        db.upsert_metric(conn, creator_id, 'female_pct', 70, 'review')
    task_id = db.add_task(conn, run_id, 'S4', 'select')
    pipeline.execute(conn, run_id, object(), mock=True)
    run = conn.execute('SELECT * FROM runs WHERE run_id=?',
                       (run_id,)).fetchone()
    stored = conn.execute('SELECT COUNT(*) FROM recommendations WHERE run_id=?',
                          (run_id,)).fetchone()[0]
    print(f"scored={scored} requested={count} status={run['status']} "
          f"stored={stored} returned={len(queries.top5(conn, run_id))}")
    print('error=', db.get_task(conn, task_id)['error'])
    if stored:
        print('s4=', json.loads(run['params_json'])['s4'])
        view = get_top5_with_details(conn, run_id)
        print(f"view_cards={len(view['cards'])} "
              f"view_total={view['total_estimated_cost_vnd']} "
              f"view_remaining={view['budget_remaining_vnd']}")

case(6, 6, 18000000)
case(2, 3, 9000000)
case(0, 1, 3000000)
PY
```

## Verification evidence

- **Default compatibility:** loaded the exact base pipeline and scoring source with `git show 8fbef7e:...`, without modifying the checkout. Separate default mock runs each completed with five identical recommendations, 81 identical HTTP request hashes, and 35 identical LLM cache keys. Default audience scores also matched for 125 combinations of absent/zero/boundary metrics.
- **Existing live run:** the copied latest live run, `7372009b22764b339fbcf0f3efb4bc4e`, is already `done` and has no stored brief. Calling `resume()` left its entire SQL dump unchanged. On separate copies, base and HEAD replayed S0, all 60 S1b inputs, nine scored S3 creators, and S4 in cache-only mode. Each produced 131 HTTP cache hits and 32 LLM cache hits with byte-identical request hashes, zero misses, zero billed credits, and zero input/output tokens. Original media files were only read. Evidence: `/tmp/koc-review-brief-live-keys-all.log` and `/tmp/koc-review-brief-live-keys.py`.
- **Precheck ordering:** 28 CLI refusal cases covered normal, dry-run, mock, and cache-only modes. DB opening and pipeline entry were patched to fail if reached; neither was reached. Invalid `pipeline.start()` also refused before run creation or client construction. Checks included count above the actual limit of 10 and budgets one VND below the cheapest-tier threshold.
- **Resume immutability:** all seven options were changed individually across legacy/new briefs, running/done runs, and retry/no-retry: 56 refusals. Client creation/execution were forbidden during these checks, and SQL dumps stayed unchanged. Explicit unchanged values were accepted.
- **S4 arithmetic:** 3,739 infeasible option cases matched an independent subset-enumeration oracle, including repeated/absent MCN IDs, no creators, count one, count equal to available creators, exact-budget boundaries, and insufficient MCN diversity. Actual S4 execution additionally verified exact-budget success at counts one and six, budget and MCN blocking, no silent reduction, no over-budget writes, and correct stored leftover. The missing-options branch is the P3 finding above.
- **S2 audience:** verified `nam`, `tat-ca`, individual age bands, an age range overlapping both bands, absent female data, and the run-specific score writer. For metrics female=70%, ages 18–24=30%, 25–34=40%, male/25–34 scores 35 and all-genders/25–34 scores 40.
- **Literal scan:** searched `src/koc`, excluding `web/` and `api.py`, for the product string, all common 30-million spellings, and standalone `5`. The active recommendation-count leak is `queries.py:14` (P2). Other matches are brief defaults, CLI default-help text, comments, mock video data, timing constants, rubric/reason limits, or numbered text; no other live product/budget input remains hard-coded there.
- Focused probe scripts and output: `/tmp/koc-review-brief-probes.py`, `/tmp/koc-review-brief-probes.log`.

## Full suite and network isolation

Suite result: **328 passed in 97.91s (0:01:37)**, exit code 0, including the copied live-run fixture. The sandbox selector adaptation below was required; the unadapted full-suite attempt did not complete.

The requested full suite initially hung entering the first web test after 276 passing dots. A minimal `socket.socketpair()` followed by `send()` reproduced `PermissionError: [Errno 1] Operation not permitted` in this sandbox. An independent AnyIO blocking-portal callback also hung. A traceback located TestClient waiting for a cross-thread callback while the event-loop selector slept. This is an execution-environment limitation, not a finding against this diff.

The external `/tmp/koc-review-brief-guard/sitecustomize.py` blocks `socket.socket.connect`, `connect_ex`, `sendto`, `socket.create_connection`, and DNS resolution. Its optional selector timeout cap allows in-process TestClient callbacks to progress without socket wakeups. No application source or dependency was changed. Guard contents:

```python
import socket

def _blocked(*args, **kwargs):
    raise RuntimeError('REVIEW: network blocked by sitecustomize')

socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.socket.sendto = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked

import os
if os.environ.get('KOC_REVIEW_SELECTOR_POLL') == '1':
    import selectors
    _select = selectors.DefaultSelector.select
    def _bounded_select(self, timeout=None):
        return _select(self, 0.02 if timeout is None else min(timeout, 0.02))
    selectors.DefaultSelector.select = _bounded_select
```

Full-suite command, including the copied live-run fixture:

```bash
PYTHONDONTWRITEBYTECODE=1 \
KOC_REVIEW_SELECTOR_POLL=1 \
KOC_REAL_RUN_COPY=/tmp/koc-review-brief-live/koc.db \
PYTEST_ADDOPTS='-p no:cacheprovider' \
PYTHONPATH=/tmp/koc-review-brief-guard:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

Output: `/tmp/koc-review-brief-suite-poll.log`. The unmodified-selector attempt is recorded in `/tmp/koc-review-brief-suite.log`; the diagnostic traceback is in `/tmp/koc-review-brief-hang2.log`.
