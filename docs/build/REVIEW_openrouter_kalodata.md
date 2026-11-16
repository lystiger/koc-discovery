# Independent review: OpenRouter and Kalodata

Date: 2026-11-15. Reviewed HEAD `7bdc0a5`, OpenRouter `58bf245`, Kalodata `f3d33b8` and `cf3e6da`, amendment A2, and `EVIDENCE_openrouter.md`.

**Overall: FAIL — three P2 findings; no P1 findings.** No implementation changes. Existing `config/scoring.yaml` modification left untouched. No network or live API calls; probes used fake keys, mocked transports, in-memory SQLite, and a socket-connect rejection guard.

## Findings

- **P2 — Mixed Kalodata retries return an error as data.** `src/koc/kalodata.py:133`, `:172`, `:189`: the four-iteration loop shares HTTP and logical retry attempts. Mock sequence HTTP 503, then three HTTP 200 `success:false/code:2017` responses returns the last failure dictionary after delays `[1, 15, 60, 180]`, instead of raising `KalodataRateLimited`. Credits remain zero and cache stays empty, but downstream code can consume the failure as an empty result and miss blocked-run handling. Separate retry counters from loop termination, and always raise on exhaustion.
- **P2 — HTTP 429 fails runs instead of blocking them.** `src/koc/kalodata.py:155`, `:160`; `src/koc/pipeline.py:353`, `:369`: exhausted HTTP 429 raises generic `RuntimeError`. An S0 execution probe produces run/task `failed/failed`; the equivalent logical RATE_LIMIT produces `blocked/blocked`. Raise `KalodataRateLimited` for exhausted HTTP 429 so the same block/resume path applies.
- **P2 — OpenRouter transport retries bypass the budget gate.** `src/koc/llm/openrouter.py:183`, `:185`; `src/koc/llm/reasons.py:169`, `:171`: a real `write_reasons` caller with mocked HTTP 503, 503, 200 produces `check, http, http, http, record`. The second and third HTTP calls have no fresh budget check. Put each outbound attempt behind a guard check; preserve accounting for potentially billed ambiguous transport failures. Repair calls themselves do recheck correctly.

## Per-item verdicts

| Item | Verdict | Evidence |
| --- | --- | --- |
| Endpoint, JPEG data URIs, MP3 input_audio | PASS | `src/koc/llm/openrouter.py:82`, `:87`, `:178`; `src/koc/llm/gemini.py:40`; `src/koc/llm/media.py:159`. Mocked request-shape test passes. |
| Strict JSON schema, reasoning off, usage requested, output cap | PASS | `src/koc/llm/openrouter.py:145`, `:165`, `:166`, `:168`. Confirms outgoing contract fields, not upstream enforcement. |
| Usage tokens, audio/image detail, provider cost and fallback | PASS | `src/koc/llm/openrouter.py:240`, `:246`, `:253`, `:263`. Tests cover detailed usage and fallback: 10,000 input + 2,000 output tokens costs $0.016500. Provider cost is rounded to six decimals (`:272`). |
| Budget check before initial and repair calls | PASS | `src/koc/llm/content.py:259`, `:267`; `src/koc/llm/reasons.py:169`, `:177`. Content repair test and independent reasons repair probe produce `check, http, record, check, http, record`. Refusal test sends zero HTTP requests. |
| Budget check before every HTTP attempt | FAIL | P2 above; retry probe sends three requests behind one check. |
| Proven multimodal budget upper bound | FAIL — UNPROVEN | `src/koc/llm/pricing.py:54` explicitly marks OpenRouter image/audio token rates UNVERIFIED. Mock tests cannot establish an upstream mathematical bound. Evidence document's “provable” claim exceeds available evidence; verify rates or adopt an independently justified bound. |
| Key never logged by reviewed provider/script paths | PASS | `src/koc/llm/openrouter.py:65`, `:190`, `:195`, `:216`; `scripts/llm_check.py:28`, `:58`. Provider does not print response bodies or network exception text. Existing repr/error and script sanitization tests pass. Scope excludes external logging hooks. |
| OpenRouter 402 / 429 / 5xx handling | PASS | `src/koc/llm/openrouter.py:195`, `:197`, `:208`. Tests prove immediate 402 failure and three total attempts for exhausted 429/503. Numeric Retry-After honored; otherwise 0.5/1-second backoff. Budget retry gap assessed separately. |
| `scripts/llm_check.py` safety | PASS | `scripts/llm_check.py:43`, `:47`, `:58`: bounded 50-token request, sanitized failures, no response/key printing. Mocked success/failure tests pass. Limitation: `:49` prints OK without validating returned JSON; independent invalid-JSON probe returns exit 0/OK. “One-shot” means one client invocation, potentially three HTTP attempts. |
| Gemini remains selectable; default OpenRouter/model pinning | PASS | `src/koc/llm/factory.py:26`; `src/koc/llm/openrouter.py:55`, `:134`. Provider-selection and unpriced-model tests pass. Current default model IDs distinguish provider cache entries (`src/koc/budget_guard.py:61`). |
| Kalodata success:false and HTTP errors never cached | PASS | `src/koc/kalodata.py:152`, `:177`, `:185`. Independent logical failure and HTTP 429 probes each leave cache empty. Mixed-retry failure is also uncached but incorrectly returned. |
| Zero credits on handled failures | PASS | `src/koc/db.py:161`; `src/koc/kalodata.py:156`, `:171`, `:182`. Independent logical, mixed, and HTTP 429 probes each report total credits 0. |
| Logical RATE_LIMIT retry delays | PASS for homogeneous failures | `src/koc/kalodata.py:15`, `:167`. Tests verify recovery and four exhausted attempts with delays 15/60/180 seconds. Mixed failures FAIL as above. |
| Two-second pacing across endpoints | PASS within one client | `src/koc/kalodata.py:99`; `config/pipeline.yaml:7`. Fake-clock test verifies exactly 2.0 seconds between creator/detail and video/url. State is per client, not a cross-process limiter. |
| Logical RATE_LIMIT blocked status and resume | PASS | `src/koc/pipeline.py:353`, `:377`, `:427`; `tests/core/test_d2_pipeline.py:214`. Suite verifies blocked stage tasks, pending downstream task, then successful resume. Independent S0 transport probe confirms blocked/blocked. HTTP 429 FAIL as above. |

## Verification

Required command:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q tests/llm tests/core
105 passed in 18.55s
```

Additional inline Python probes used `httpx.MockTransport`, injected Kalodata transports, patched sleeps, and in-memory databases. Decisive outputs:

```text
mixed: returned {success: false, code: 2017, errorCategory: RATE_LIMIT}; credits=0; cache=0
logical failure: RuntimeError; credits=0; cache=0
HTTP 429: RuntimeError; credits=0; cache=0
budget_retry_events: ['check', 'http', 'http', 'http', 'record']
repair_events: ['check', 'http', 'record', 'check', 'http', 'record']
health_invalid_json: 0 OK
http429 run=failed task=failed
logical2017 run=blocked task=blocked
```

The green suite does not cover the three P2 counterexamples. Overall PASS requires resolving them and establishing the contractual multimodal budget bound.
