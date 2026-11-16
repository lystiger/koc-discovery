"""Faithfulness check of S4 reasons (v2 item 5, A7): a second model grades each reason sentence against ONLY the
evidence the recommendation cites. RAGAS-style, no library.

  recommendation --> sentences (reasons_vi = strengths, caveats_vi = weaknesses)
  cited ids ------> evidence text (metrics, quotes, frame notes, rubric scores)
  judge call -----> verdict per sentence: supported 1 / partly 0.5 / unsupported 0
  "Lý do" score = mean of marks of reasons_vi only (the headline); "Lưu ý" score = mean of marks of caveats_vi.
  Run score = mean of KOC scores. Audience-unverified caveats are system statements: never graded, never scored.

Results live in table `faithfulness`, keyed by a hash of (prompt, judge model, sentences, evidence text): a rerun with
unchanged inputs makes 0 calls. A recommendation citing no resolvable evidence is unsupported without a call.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from . import db
from .llm.guard import fold
from .budget_guard import BudgetGuard
from .llm.gemini import GeminiClient
from .llm.pricing import estimate_tokens_and_usd, load_pricing_config
from .types import CacheOnlyMiss, ContentAnalysis, Recommendation

PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "faithfulness_v1.md"
PROMPT_VERSION = "faithfulness_v1"
KIND = "faithfulness"
MARKS = {"supported": 1.0, "partly": 0.5, "unsupported": 0.0}
NO_EVIDENCE_WHY = "Đề xuất không trích dẫn bằng chứng nào tra cứu được."


_AUD = r"(ho so khan gia|nhan khau hoc|do tuoi|gioi tinh|(thong tin|du lieu) (ve )?khan gia)"
_W = r"( [a-z0-9]+){0,2} "  # at most two filler words, so another subject (doanh thu, ty le chuyen doi) breaks the match
_MISSING = r"(chua (duoc )?xac minh|(khong|chua) (co|cung cap) (thong tin|du lieu))"
_AUD_UNVERIFIED = [re.compile(_MISSING + r"( ve)?" + _W.rstrip() + " " + _AUD), re.compile(_AUD + _W.rstrip() + " " + _MISSING)]


def is_audience_unverified_caveat(text: str) -> bool:
    """Heuristic: some comma-free span says the audience profile (demographics, age, gender) itself is unverified or
    has no data. Spans split on , . ; and 'nhung'; a different subject between the terms breaks the match."""
    return any(r.search(c) for c in re.split(r"[.,;]| nhung ", fold(text)) for r in _AUD_UNVERIFIED)


class Verdict(BaseModel):
    index: int
    verdict: Literal["supported", "partly", "unsupported"]
    why: str


class JudgePayload(BaseModel):
    verdicts: list[Verdict]


def build_schema(n: int) -> dict:
    """Strict JSON schema for one judge call: exactly n verdicts."""
    schema = JudgePayload.model_json_schema()
    verdict = schema["$defs"]["Verdict"]
    verdict["additionalProperties"] = False
    verdict["required"] = ["index", "verdict", "why"]
    schema["additionalProperties"] = False
    schema["required"] = ["verdicts"]
    schema["properties"]["verdicts"].update({"minItems": n, "maxItems": n})
    return schema


@dataclass
class Item:
    creator_id: str
    handle: str
    sentences: list[tuple[str, str]]  # (kind "strength"|"weakness", text)
    evidence: list[str]  # resolved evidence lines
    prompt: str = ""
    request_hash: str = ""
    n_reasons: int = 0  # sentences[:n_reasons] are reasons_vi, the rest are caveats_vi
    cached: dict | None = field(default=None, repr=False)


def _metric_line(conn, evidence_id: str) -> str | None:
    parts = evidence_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "metric":
        return None
    row = conn.execute("SELECT value FROM metrics WHERE creator_id=? AND name=? ORDER BY collected_at DESC LIMIT 1", (parts[1], parts[2])).fetchone()
    if row is None:
        return None
    return f"[{evidence_id}] chỉ số {parts[2]} = {json.loads(row[0])}"


def _video_lines(analyses: list[ContentAnalysis]) -> dict[str, str]:
    lines = {}
    for a in analyses:
        for e in a.evidence:
            line = f"[{e.evidence_id}] video {a.video_id}, {e.kind} tại {e.start_s}s: {e.quote_vi}"
            rubric = [f"{r.criterion}={r.score}/5 ({r.rationale_vi})" for r in a.rubric if e.evidence_id in r.evidence_ids]
            if rubric:
                line += " | điểm rubric: " + "; ".join(rubric)
            lines[e.evidence_id] = line
    return lines


def _hash(model: str, sentences, evidence) -> str:
    blob = json.dumps({"v": PROMPT_VERSION, "model": model, "sentences": sentences, "evidence": evidence}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _build_prompt(item: Item) -> str:
    evidence = "\n".join(f"- {line}" for line in item.evidence) or "(không có bằng chứng)"
    sentences = "\n".join(f"{i}. [{kind}] {text}" for i, (kind, text) in enumerate(item.sentences))
    return PROMPT_FILE.read_text(encoding="utf-8").replace("{{EVIDENCE}}", evidence).replace("{{SENTENCES}}", sentences)


def load_items(conn, run_id: str, model: str) -> list[Item]:
    """One Item per recommendation of the run, with evidence resolved from the DB (read only)."""
    from .llm.reasons import AUDIENCE_MISSING_CAVEAT_VI
    rows = conn.execute("SELECT r.creator_id,r.rec_json,c.handle FROM recommendations r LEFT JOIN creators c ON c.creator_id=r.creator_id WHERE r.run_id=? ORDER BY r.rank", (run_id,)).fetchall()
    items = []
    for row in rows:
        rec = Recommendation.model_validate_json(row[1])
        # "audience unverified" caveats are system statements, not claims about evidence: not graded, not scored
        keep = [t for t in rec.caveats_vi if not is_audience_unverified_caveat(t)]
        sentences = [("strength", t) for t in rec.reasons_vi] + [("weakness", t) for t in keep]
        # older runs graded with only the exact caveat string excluded; their stored verdicts line up with this list
        legacy = [("strength", t) for t in rec.reasons_vi] + [("weakness", t) for t in rec.caveats_vi if t != AUDIENCE_MISSING_CAVEAT_VI]
        if not sentences and not legacy:
            continue
        analyses = [ContentAnalysis.model_validate_json(r[3]) for r in db.run_analyses(conn, run_id, row[0])]
        video = _video_lines(analyses)
        evidence = []
        for eid in rec.cited_evidence_ids:
            line = video.get(eid) or _metric_line(conn, eid)
            if line:
                evidence.append(line)
        item = Item(row[0], row[2] or row[0], sentences, evidence, n_reasons=len(rec.reasons_vi))
        item.request_hash = _hash(model, item.sentences, item.evidence)
        item.prompt = _build_prompt(item)
        stored = conn.execute("SELECT request_hash,score,verdicts_json FROM faithfulness WHERE run_id=? AND creator_id=? AND model=? AND prompt_version=?", (run_id, row[0], model, PROMPT_VERSION)).fetchone() if _has_table(conn) else None
        if stored and stored[0] == item.request_hash:
            item.cached = {"score": stored[1], "verdicts": json.loads(stored[2])}
        elif stored and stored[0] == _hash(model, legacy, item.evidence):
            # 0 calls: drop the verdicts of audience-unverified caveats and renumber; the rest stay valid
            old = json.loads(stored[2])
            kept = [v for n, (v, (_, t)) in enumerate(zip(old, legacy)) if n < item.n_reasons or not is_audience_unverified_caveat(t)]  # only caveats are ever dropped
            item.cached = {"score": stored[1], "verdicts": [{**v, "index": i} for i, v in enumerate(kept)]}
        items.append(item)
    return items


def _has_table(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='faithfulness'").fetchone() is not None


def score_of(verdicts: list[dict]) -> float:
    return sum(MARKS[v["verdict"]] for v in verdicts) / len(verdicts) if verdicts else 0.0


def split_scores(verdicts: list[dict], n_reasons: int) -> tuple[float | None, float | None]:
    """(Lý do, Lưu ý) scores from stored verdicts; None for a part with no sentences. Recomputing costs 0 calls."""
    r, c = verdicts[:n_reasons], verdicts[n_reasons:]
    return (score_of(r) if r else None, score_of(c) if c else None)


def run_score(scores: list[float | None]) -> float | None:
    scores = [x for x in scores if x is not None]
    return sum(scores) / len(scores) if scores else None


def _output_tokens(cfg: dict, n: int) -> int:
    return int(cfg.get("token_accounting", {}).get("default_faithfulness_output_tokens", 800 + 60 * n))


def estimate(items: list[Item], client_model: str, config_path=None) -> dict:
    """Calls, tokens and USD upper bound for the items that are not cached and have evidence."""
    cfg = load_pricing_config(config_path)
    calls = tokens = 0
    usd = 0.0
    for item in items:
        if item.cached or not item.evidence:
            continue
        t, c = estimate_tokens_and_usd(est_output_tokens=_output_tokens(cfg, len(item.sentences)), config_path=config_path, text_parts=[item.prompt],
                                       response_schema=build_schema(len(item.sentences)), has_audio=False, model=client_model)
        calls, tokens, usd = calls + 1, tokens + t, usd + c
    return {"calls": calls, "input_tokens": tokens, "usd": usd, "cached": sum(1 for i in items if i.cached), "no_evidence": sum(1 for i in items if not i.cached and not i.evidence)}


def _validate(payload: JudgePayload, n: int) -> list[str]:
    errors = []
    if [v.index for v in payload.verdicts] != list(range(n)):
        errors.append(f"index phải là 0..{n - 1} theo thứ tự, mỗi câu đúng một phán quyết")
    return errors


def _grade(item: Item, client, guard, config_path) -> list[dict]:
    cfg = load_pricing_config(config_path)
    n = len(item.sentences)
    schema_arg = JudgePayload if isinstance(client, GeminiClient) else build_schema(n)
    model = getattr(client, "model", None)
    errors: list[str] = []
    for attempt in range(2):
        contents = [item.prompt]
        if errors:
            contents.append("Lần trước không hợp lệ: " + "; ".join(errors) + f". Trả về đúng {n} phán quyết, index 0..{n - 1}.")
        est_tokens, est_usd = estimate_tokens_and_usd(est_output_tokens=_output_tokens(cfg, n), config_path=config_path, text_parts=contents,
                                                      response_schema=schema_arg if isinstance(schema_arg, dict) else build_schema(n), has_audio=False, model=model)
        guard.check(est_usd)
        raw, usage = client.generate_json(contents=contents, response_schema=schema_arg, prompt_version=PROMPT_VERSION,
                                          max_output_tokens=_output_tokens(cfg, n), budget_guard=guard, upper_bound_usd=est_usd,
                                          initial_check_done=True, est_tokens=est_tokens)
        guard.record(usage)
        try:
            payload = JudgePayload.model_validate_json(raw)
        except Exception as exc:  # schema or JSON syntax error
            errors = [f"JSON/schema lỗi: {str(exc)[:200]}"]
            continue
        errors = _validate(payload, n)
        if not errors:
            return [v.model_dump() for v in payload.verdicts]
    raise ValueError(f"Phán quyết của mô hình chấm không hợp lệ cho {item.creator_id}: {'; '.join(errors)}")


def _store(conn, run_id, item: Item, model: str, verdicts: list[dict]) -> float:
    score = split_scores(verdicts, item.n_reasons)[0]
    score = score_of(verdicts) if score is None else score
    with db.transaction(conn):
        conn.execute("INSERT INTO faithfulness(run_id,creator_id,model,prompt_version,request_hash,score,verdicts_json,created_at) VALUES (?,?,?,?,?,?,?,?) "
                     "ON CONFLICT(run_id,creator_id,model,prompt_version) DO UPDATE SET request_hash=excluded.request_hash,score=excluded.score,verdicts_json=excluded.verdicts_json,created_at=excluded.created_at",
                     (run_id, item.creator_id, model, PROMPT_VERSION, item.request_hash, score, json.dumps(verdicts, ensure_ascii=False), db.now()))
    return score


def evaluate(conn, run_id: str, client=None, *, model: str | None = None, cache_only: bool = False, cap_usd: float | None = None, config_path=None) -> dict:
    """Grade every recommendation of the run. Cached items cost 0 calls. Returns {"items": [...], "score": float|None, "calls": int, "usd": float}."""
    db.init_db(conn)
    if client is None and not cache_only:
        from .llm.factory import get_llm_client
        client = get_llm_client(model=model, config_path=config_path)
    judge = getattr(client, "model", None) or model or load_pricing_config(config_path).get("model", {}).get("id", "cache")
    items = load_items(conn, run_id, judge)
    guard = BudgetGuard(conn, cap_usd=cap_usd, run_id=None, kind=KIND)  # run_id None: keeps S3/S4 run reports and benchmark untouched
    spent_before = guard._spent()
    calls = 0
    results = []
    for item in items:
        if item.cached:
            v = item.cached["verdicts"]
            results.append((item, v, split_scores(v, item.n_reasons)[0]))  # recomputed from stored verdicts: 0 calls
            continue
        if not item.evidence:
            verdicts = [{"index": i, "verdict": "unsupported", "why": NO_EVIDENCE_WHY} for i in range(len(item.sentences))]
        elif cache_only:
            raise CacheOnlyMiss(f"độ trung thực của {item.creator_id}")
        else:
            verdicts = _grade(item, client, guard, config_path)
            calls += 1
        results.append((item, verdicts, _store(conn, run_id, item, judge, verdicts)))
    caveat = run_score([split_scores(v, i.n_reasons)[1] for i, v, _ in results])
    return {"items": results, "score": run_score([s for _, _, s in results]), "caveat_score": caveat, "calls": calls, "usd": guard._spent() - spent_before, "model": judge}


def stored_summary(conn, run_id: str) -> dict | None:
    """Latest stored faithfulness result of the run for the benchmark, or None when never graded."""
    if not _has_table(conn):
        return None
    first = conn.execute("SELECT model,prompt_version FROM faithfulness WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,)).fetchone()
    if first is None:
        return None
    items = [i for i in load_items(conn, run_id, first[0]) if i.cached]  # hash-matched rows only; scores recomputed from verdicts
    split = {i.creator_id: split_scores(i.cached["verdicts"], i.n_reasons) for i in items}
    return {"model": first[0], "prompt_version": first[1], "run_score": run_score([r for r, _ in split.values()]),
            "caveat_score": run_score([c for _, c in split.values()]), "kocs": len(split),
            "per_koc": {k: r for k, (r, _) in sorted(split.items()) if r is not None},
            "per_koc_caveats": {k: c for k, (_, c) in sorted(split.items()) if c is not None}}
