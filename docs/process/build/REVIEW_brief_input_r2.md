Overall PASS — no open P1/P2 findings. Both prior findings are CLOSED.

Independent round-two review of `65e9be3..5edb3e7ea814b1fceac6d509f71d95f8bb284e14` (`ac0ff51`, `5edb3e7`) on `worktree-agent-a52e3ed613e6eeb40`, 2026-11-16. No source changes or network requests. This report is the only repository file created. Severity follows the requested correctness rubric; visual style is not a blocking criterion.

## Findings

### CLOSED — prior P2: counts above five were silently truncated

Location: `src/koc/queries.py:13`.

Re-ran the exact previous report's script, extracted without changing its Python body. Six scored creators, count six, and an 18,000,000 VND budget now produce six stored recommendations, six query results, six cards, 18,000,000 VND displayed spend, and zero remaining. Stored S4 arithmetic agrees with the view. Status is `done`. The legacy run without a stored brief still returns its original five recommendations.

### CLOSED — prior P3: underfilled S4 omitted recovery options

Locations: `src/koc/pipeline.py:462`, `src/koc/pipeline.py:352`, `src/koc/brief.py:92`.

The same exact script now returns all three numbered options for both shortage cases. Two scored creators against count three offer two KOCs for 6,000,000 VND and the actual 10k–50k follower tier; the unavailable three-creator budget is explicitly marked unavailable. Zero scored creators mark all three alternatives unavailable. Both runs remain `blocked`, with zero stored recommendations. No paid work is attempted by these S4 refusal paths.

### New findings

None within the reviewed scope. No P1/P2 correctness regression was reproduced.

## Offline finding reproduction

The Python body below is identical to the previous report. Only the external guard path changed.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/koc-review-r2/guard:src \
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

Observed output:

```text
scored=6 requested=6 status=done stored=6 returned=6
error= None
s4= {'budget_vnd': 18000000, 'leftover_vnd': 0, 'total_vnd': 18000000}
view_cards=6 view_total=18000000 view_remaining=0
scored=2 requested=3 status=blocked stored=0 returned=0
error= Chưa đủ điểm nội dung để đề xuất: có 2, cần 3. Lựa chọn: (1) giảm còn 2 KOC (tốn 6.000.000 VND); (2) không có (chưa đủ 3 KOC có điểm nội dung để tính ngân sách tối thiểu); (3) nhóm follower rẻ nhất trong danh sách là 10k-50k.
scored=0 requested=1 status=blocked stored=0 returned=0
error= Chưa đủ điểm nội dung để đề xuất: có 0, cần 1. Lựa chọn: (1) không có (không có nhóm nhỏ hơn nào nằm trong ngân sách); (2) không có (chưa đủ 1 KOC có điểm nội dung để tính ngân sách tối thiểu); (3) không có (chưa có KOC nào có điểm nội dung).
```

## Verification evidence

- **D-B5, accepted ages and scoring — PASS.** `src/koc/brief.py:57` accepts inclusive 18–99 and rejects reversed/out-of-bounds ranges. An independent overlap oracle checked all 3,403 valid integer ranges for all three genders: 10,209 matching scores. Only 18–24 and 25–34 contribute when they overlap; ranges without overlap return `None` (`src/koc/stages.py:96`). Compared 125 absent/zero/boundary metric combinations against the base implementation: default scores are unchanged.
- **D-B5, NULL propagation — PASS.** Seven mock pipeline runs covered 18–24, 25–34, 35–44, 45–54, 55–99, 18–99, and 25–44. Each completed with the requested six picks and exactly 18,000,000 VND spend. Each non-overlapping range persisted ten NULL S2 scores. Final scores matched `final_score(S1, None, S3)`, which drops and renormalises the audience weight (`src/koc/stages.py:164`). Both changed adapter conversions (`src/koc/web/adapter.py:178`, `src/koc/web/adapter.py:332`) were exercised through top-list/detail data and HTTP routes; NULL S2 caused no crash.
- **D-B6, offline mapping — PASS.** Read all 19 cached `category/rank` responses from the read-only backup, yielding 1,900 unique categories. Every one of the 20 configured IDs exists and its cached Vietnamese name matches the YAML comment. Inspected the names themselves, including the retained broad sunscreen category and the explicitly empty `Khác` mapping. No category lookup used the network. `Chống nắng` IDs equal the existing default configuration.
- **D-B6, CLI and storage — PASS.** Eleven actual mock CLI runs covered each nonempty mapped product type and explicit IDs for all six types. The stored brief retained `product_type`; explicit `111,222` IDs prevailed over every mapping. Twenty invalid CLI cases covered unknown types, `Khác` without IDs, explicitly blank IDs with a mapped type, and invalid ages, across normal/dry-run/mock/cache-only modes. Patched DB opening and pipeline entry to fail if reached; every case refused with exit 1 first. Locations: `src/koc/brief.py:17`, `src/koc/brief.py:60`, `src/koc/cli.py:45`.
- **Ordering — PASS.** A 23-creator synthetic fixture included positive, zero and NULL S2 values; tied S2/S1 values; and reversed insertion order. Independent sorting matched `_s2_top` and `get_finalists` at the 15-row cutoff. `_advance` queued exactly the expected top ten S3 creator IDs. Ordering is S2 descending, NULL last, then S1 descending, then creator ID (`src/koc/pipeline.py:129`, `src/koc/web/adapter.py:293`). The existing audience-metric eligibility filter remains in effect.
- **Operator brief count — PASS.** All seven age-range runs rendered `/runs/<run_id>` with `6 / 6`, the actual product and target, and a successful JSON proposal route. The prior live run retains count five. Location: `src/koc/web/templates/top5.html:9`.

Probe source and output: `/tmp/koc-review-r2/probes.py`, `/tmp/koc-review-r2/probes.log`. Exact finding script and output: `/tmp/koc-review-r2/exact_repro.py`, `/tmp/koc-review-r2/exact_repro.log`.

### Live-run backward compatibility — PASS

Run: `7372009b22764b339fbcf0f3efb4bc4e`. The original was opened only by SQLite's read-only `.backup` operation:

```bash
sqlite3 -readonly /home/lystiger/Projects/KOC-Discovery/data/koc.db \
  ".backup '/tmp/koc-review-r2/live.db'"
chmod 444 /tmp/koc-review-r2/live.db
```

Backup SHA256: `a8a4f7c10ba666f21ebe544e582fe663466bcadc82d28461ba6a407d9fc07a76`.

All subsequent inspection used this backup. Replay opened it with `mode=ro`, checked `PRAGMA quick_check`, and backed it into a separate in-memory DB for each code version. Base source/config came from `git archive 65e9be3`; HEAD used this checkout. Both `resume()` calls on the already completed run left the entire in-memory SQL dump byte-for-byte unchanged.

The ten eligible S3 creator IDs are unchanged between the stored tasks, base `_s2_top(..., 10)` and HEAD `_s2_top(..., 10)`:

```text
6730533371858437121
6872721641991209985
6976265099049305089
7164572563820250139
7234931025289217051
7288941699803694098
7450735628620760071
7471573167103378440
7485602050560148487
7594293671543079957
```

S1 tie-breaking changes their order because all ten stored S2 scores equal 65; it does not change the set. Creator `7471573167103378440` retains its original `skipped` S3 task. The other nine have S3 scores and were all replayed by both versions.

Stored recommendations, base recomputation and HEAD recomputation agree exactly:

| Rank | Creator ID | Estimated cost (VND) |
| ---: | --- | ---: |
| 1 | 7485602050560148487 | 3,000,000 |
| 2 | 7234931025289217051 | 3,000,000 |
| 3 | 7594293671543079957 | 7,500,000 |
| 4 | 7450735628620760071 | 7,500,000 |
| 5 | 6730533371858437121 | 7,500,000 |
| **Total** | | **28,500,000** |

Budget remains 30,000,000 VND; remaining budget is 1,500,000 VND. Both replayed runs end `done`.

For cache compatibility, reset every originally `done` task to `pending` in each in-memory copy, cleared the S4 selection, and ran `execute(..., cache_only=True)` through S0–S4. Originally skipped S2/S3 tasks stayed skipped. Existing media were read from the original media directory; cache-only mode refuses absent media before writing or downloading anything.

Both versions generated exactly the same ordered `(endpoint/kind, request_hash)` sequences:

| Cache path | Hits in each replay | Misses | Ordered-key manifest SHA256 |
| --- | ---: | ---: | --- |
| API | 141 | 0 | `6207011d5e733fb88b754a0f0693949d57620994f4104cbde649f1dfee482c8d` |
| LLM | 32 | 0 | `7d6f4bef1ba83b6d028079442896c3fcd51708bc5a7702bac824ef93438d207d` |

API hits comprise 131 HTTP-cache requests (2 creator ranks, 60 creator details, 69 video ranks) plus 10 stored S2 audience-metric reads. LLM hits comprise 27 content and 5 reasons requests. Every HTTP/LLM key exists in the corresponding backup cache. Additional billed credits, LLM USD, input tokens and output tokens are all zero. Thus the new brief field, tie-breaking and NULL handling do not change cache keys or paid S3 inputs for this existing run.

This replay preserves the original operator decision to skip one S3 creator. A fresh run that attempts that skipped creator requires uncached work; that existing limitation is not introduced by this range.

Evidence: `/tmp/koc-review-r2/live_replay.py`, `base.json`, `head.json`, `base.log`, `head.log`. The JSON manifests retain the full compared key sequences. Re-run against the prepared base snapshot with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/koc-review-r2/guard:/tmp/koc-review-r2/base/src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python \
  /tmp/koc-review-r2/live_replay.py /tmp/koc-review-r2/base.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/koc-review-r2/guard:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python \
  /tmp/koc-review-r2/live_replay.py /tmp/koc-review-r2/head.json
```

## Full suite and network isolation

Full suite: **340 passed in 97.17s (0:01:37)**, exit code 0. The copied live-run fixture was enabled; no test was skipped. Output: `/tmp/koc-review-r2/suite.log`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
KOC_REVIEW_SELECTOR_POLL=1 \
KOC_REAL_RUN_COPY=/tmp/koc-review-r2/live.db \
PYTEST_ADDOPTS='-p no:cacheprovider' \
PYTHONPATH=/tmp/koc-review-r2/guard:src \
  /home/lystiger/Projects/KOC-Discovery/.venv/bin/python -m pytest -q tests
```

The external socket-blocking `sitecustomize.py` was installed before importing application code or starting tests/replays. The selector timeout adaptation is the same external workaround documented in round one: this sandbox cannot provide the socket wakeup used by in-process TestClient. It changes no application source or dependency. Direct guard probes confirmed blocking of connect, connection creation and DNS. Guard file `/tmp/koc-review-r2/guard/sitecustomize.py`:

```python
import socket

def _blocked(*args, **kwargs):
    raise RuntimeError('REVIEW R2: network blocked by sitecustomize')

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
