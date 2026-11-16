import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from koc import benchmark, benchmark_render, cli, db, faithfulness as fa
from koc.llm.openrouter import OpenRouterClient
from koc.types import BudgetExceeded, CacheOnlyMiss, Recommendation, Usage
from tests.analysis_seed import seed_brand_fit

REPO = Path(__file__).resolve().parents[2]
RUN = "r1"


class Transport:
    """Mocked OpenRouter: counts calls, answers one verdict per numbered sentence in the prompt."""
    def __init__(self, verdicts=None, cost=0.0, bad_first=False):
        self.calls, self.prompts, self.cost, self.verdicts, self.bad_first = 0, [], cost, verdicts, bad_first

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        body = json.loads(request.content)
        prompt = body["messages"][-1]["content"]
        text = prompt if isinstance(prompt, str) else " ".join(p.get("text", "") for p in prompt)
        self.prompts.append(text)
        n = len(re.findall(r"^\d+\. \[(?:strength|weakness)\]", text, re.M))
        marks = self.verdicts or ["supported"] * n
        verdicts = [{"index": i, "verdict": marks[i], "why": "ok"} for i in range(n)]
        if self.bad_first and self.calls == 1:
            verdicts = verdicts[:-1]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"verdicts": verdicts})}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": self.cost}})


def client(transport):
    return OpenRouterClient(api_key="sk-or-fake", http_client=httpx.Client(transport=httpx.MockTransport(transport)))


def rec(creator_id, cited, reasons=None, caveats=None):
    usage = Usage(provider="openrouter", model="m", prompt_version="reasons_v4", input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0)
    return Recommendation(creator_id=creator_id, reasons_vi=reasons or ["GPM video cao.", "Video nêu rõ công dụng.", "Giá hợp lý."],
                          cited_evidence_ids=cited, caveats_vi=caveats or ["Mẫu video nhỏ."], usage=usage)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "koc.db")
    db.init_db(c)
    c.execute("INSERT INTO runs VALUES (?,?,NULL,'done',?)", (RUN, "2026-01-01", json.dumps({})))
    for i, cited in enumerate(([f"metric:c0:video_gpm", "c0-seed-video@1.0s"], ["missing:id"])):
        cid = f"c{i}"
        db.upsert_creator(c, cid, f"@{cid}", {})
        db.upsert_metric(c, cid, "video_gpm", 1234, "test")
        seed_brand_fit(c, cid)
        c.execute("INSERT INTO recommendations VALUES (?,?,?,?,?)", (RUN, cid, i + 1, 1000, rec(cid, cited).model_dump_json()))
    c.commit()
    return c


def test_schema_is_strict_and_fixed_length():
    schema = fa.build_schema(3)
    assert schema["properties"]["verdicts"]["minItems"] == schema["properties"]["verdicts"]["maxItems"] == 3
    assert schema["$defs"]["Verdict"]["properties"]["verdict"]["enum"] == ["supported", "partly", "unsupported"]
    assert schema["additionalProperties"] is False and schema["$defs"]["Verdict"]["additionalProperties"] is False


def test_scoring_math():
    assert fa.score_of([{"verdict": v} for v in ("supported", "partly", "unsupported", "supported")]) == pytest.approx(0.625)
    assert fa.run_score([1.0, 0.5]) == 0.75
    assert fa.run_score([]) is None


def test_evidence_resolved_and_prompt_only_has_cited_evidence(conn):
    items = fa.load_items(conn, RUN, "m")
    first = items[0]
    assert any("video_gpm = 1234" in line for line in first.evidence)
    assert any("c0-seed-video@1.0s" in line and "brand_fit=5/5" in line for line in first.evidence)
    assert "c1-seed-video" not in first.prompt


def test_missing_evidence_is_unsupported_without_a_call(conn):
    t = Transport()
    out = fa.evaluate(conn, RUN, client(t))
    by_creator = {item.creator_id: (verdicts, score) for item, verdicts, score in out["items"]}
    verdicts, score = by_creator["c1"]
    assert score == 0.0 and {v["verdict"] for v in verdicts} == {"unsupported"} and verdicts[0]["why"] == fa.NO_EVIDENCE_WHY
    assert t.calls == 1 and out["calls"] == 1  # only c0 reached the judge
    assert out["score"] == pytest.approx(0.5)  # mean of 1.0 and 0.0


def test_rerun_costs_zero_calls_and_input_change_regrades(conn):
    t = Transport(verdicts=["supported", "partly", "unsupported", "supported"], cost=0.001)
    first = fa.evaluate(conn, RUN, client(t))
    assert first["calls"] == 1 and first["usd"] == pytest.approx(0.001)
    assert first["items"][0][2] == pytest.approx(0.5)  # Lý do only: (1 + .5 + 0) / 3
    again = fa.evaluate(conn, RUN, client(t))
    assert again["calls"] == 0 and t.calls == 1 and again["usd"] == 0 and again["score"] == first["score"]
    conn.execute("UPDATE metrics SET value='999' WHERE creator_id='c0'")
    conn.commit()
    assert fa.evaluate(conn, RUN, client(t))["calls"] == 1
    assert fa.evaluate(conn, RUN, client(Transport()), model="other-model")["calls"] == 0  # client model wins; same key
    n = conn.execute("SELECT COUNT(*) FROM llm_calls WHERE kind='faithfulness'").fetchone()[0]
    assert n == 2  # both paid calls logged in llm_calls with the other stages


def test_cache_only_never_calls_and_raises_on_miss(conn):
    with pytest.raises(CacheOnlyMiss):
        fa.evaluate(conn, RUN, None, cache_only=True)
    t = Transport()
    fa.evaluate(conn, RUN, client(t))
    out = fa.evaluate(conn, RUN, None, cache_only=True, model="google/gemini-3.8-flash")
    assert out["calls"] == 0 and out["score"] == pytest.approx(0.5) and t.calls == 1


def test_invalid_verdict_count_is_retried_once(conn):
    t = Transport(bad_first=True)
    out = fa.evaluate(conn, RUN, client(t))
    assert t.calls == 2 and out["calls"] == 1 and len(out["items"][0][1]) == 4


def test_cost_guard_blocks_before_the_call(conn):
    t = Transport()
    with pytest.raises(BudgetExceeded):
        fa.evaluate(conn, RUN, client(t), cap_usd=1e-9)
    assert t.calls == 0


def test_estimate_counts_uncached_calls_only(conn):
    items = fa.load_items(conn, RUN, "google/gemini-3.8-flash")
    e = fa.estimate(items, "google/gemini-3.8-flash")
    assert e["calls"] == 1 and e["no_evidence"] == 1 and e["usd"] > 0 and e["input_tokens"] > 0


def test_cli_dry_run_cache_only_and_table(conn, tmp_path, monkeypatch):
    path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    monkeypatch.setattr(cli, "DB_PATH", path)
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network attempted")))
    runner = CliRunner()
    dry = runner.invoke(cli.app, ["faithfulness", "--run", RUN, "--dry-run"])
    assert dry.exit_code == 0 and "1 lượt gọi" in dry.output and "USD" in dry.output, dry.output
    assert conn.execute("SELECT COUNT(*) FROM faithfulness").fetchone()[0] == 0
    miss = runner.invoke(cli.app, ["faithfulness", "--run", RUN, "--cache-only"])
    assert miss.exit_code == 1
    t = Transport(verdicts=["supported", "partly", "unsupported", "supported"])
    monkeypatch.undo()
    monkeypatch.setattr(cli, "DB_PATH", path)
    fa.evaluate(conn, RUN, client(t))
    out = runner.invoke(cli.app, ["faithfulness", "--run", RUN, "--cache-only"])
    assert out.exit_code == 0, out.output
    assert "@c0" in out.output and "0.50" in out.output and "một phần" in out.output
    assert "Điểm trung thực của lượt chạy (Lý do): 0.25" in out.output and "Số lượt gọi: 0" in out.output


def test_benchmark_has_faithfulness_only_when_graded(conn):
    result = benchmark.build(conn, RUN)
    assert "faithfulness" not in result
    assert "Độ trung thực" not in benchmark_render.render_markdown(result)
    units = result["units_total"]
    fa.evaluate(conn, RUN, client(Transport()))
    graded = benchmark.build(conn, RUN)
    assert graded["faithfulness"]["run_score"] == pytest.approx(0.5) and graded["faithfulness"]["kocs"] == 2
    assert graded["units_total"] == units and graded["totals_total"] == result["totals_total"]
    assert "## 10. Độ trung thực của lý do S4" in benchmark_render.render_markdown(graded)


def test_free_smoke_script_passes_and_exits_3_on_cost(tmp_path, monkeypatch, capsys, conn):
    import runpy
    import koc.llm.factory as factory
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "config").mkdir(exist_ok=True)
    shutil.copy(REPO / "config" / "llm_prices.yaml", tmp_path / "config" / "llm_prices.yaml")
    conn.commit()
    shutil.copy(Path(conn.execute("PRAGMA database_list").fetchone()[2]), tmp_path / "data" / "koc.db")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    real = factory.get_llm_client
    for cost, code in ((0.0, 0), (0.01, 3)):
        monkeypatch.setattr(factory, "get_llm_client", lambda *a, _c=cost, **kw: real(*a, http_client=httpx.Client(transport=httpx.MockTransport(Transport(cost=_c))), **kw))
        monkeypatch.setattr(sys, "argv", ["faithfulness_free_smoke.py", "baidu/ernie-5.5-flash-preview:free", RUN])
        with pytest.raises(SystemExit) as info:
            runpy.run_path(str(REPO / "scripts" / "faithfulness_free_smoke.py"), run_name="__main__")
        assert info.value.code == code
    assert not (tmp_path / "data" / "koc.db-journal").exists()


# --- v2 small fix: Lý do / Lưu ý split, audience-unverified caveats never graded or scored ---

AUDIENCE_VARIANTS = [
    "Chưa xác minh hồ sơ khán giả (gói Kalodata không có dữ liệu khán giả); cần xác nhận trực tiếp với creator.",
    "Hồ sơ khán giả chưa được xác minh do gói dữ liệu Kalodata không có thông tin nhân khẩu học.",
    "Khong co du lieu nhan khau hoc cua khan gia, chua xac minh.",
]
CITED = ["metric:c0:video_gpm", "c0-seed-video@1.0s"]


def test_audience_unverified_detector_catches_variants_only():
    assert all(fa.is_audience_unverified_caveat(t) for t in AUDIENCE_VARIANTS)
    assert not fa.is_audience_unverified_caveat("Mẫu video nhỏ, chỉ có 3 video.")
    assert not fa.is_audience_unverified_caveat("Khán giả phản hồi tích cực trong bình luận.")
    assert not fa.is_audience_unverified_caveat("Video có nhiều tương tác với khán giả nhưng chưa có dữ liệu về tỷ lệ chuyển đổi.")
    assert not fa.is_audience_unverified_caveat("Chưa xác minh doanh thu thực tế của khán giả mua hàng.")
    assert not fa.is_audience_unverified_caveat("Hồ sơ khán giả đã được xác minh, doanh thu chưa được xác minh.")
    assert not fa.is_audience_unverified_caveat("Hồ sơ khán giả đã xác minh doanh thu chưa xác minh tỷ lệ chuyển đổi.")


def test_split_scores_reasons_vs_caveats():
    v = [{"verdict": x} for x in ["supported", "partly", "supported", "unsupported", "partly"]]
    assert fa.split_scores(v, 3) == (pytest.approx(5 / 6), pytest.approx(0.25))
    assert fa.split_scores(v[:3], 3) == (pytest.approx(5 / 6), None)


def _with_audience_caveat(conn):
    conn.execute("UPDATE recommendations SET rec_json=? WHERE creator_id='c0'",
                 (rec("c0", CITED, caveats=["Mẫu video nhỏ.", AUDIENCE_VARIANTS[1]]).model_dump_json(),))
    conn.commit()


def test_audience_caveat_variant_is_not_sent_to_judge_nor_scored(conn):
    _with_audience_caveat(conn)
    t = Transport(verdicts=["supported", "supported", "supported", "partly"])
    out = fa.evaluate(conn, RUN, client(t))
    assert t.prompts[0].count("[weakness]") == 1 and AUDIENCE_VARIANTS[1] not in t.prompts[0]
    item, verdicts, score = out["items"][0]
    assert score == 1.0 and fa.split_scores(verdicts, item.n_reasons)[1] == 0.5


def test_legacy_stored_verdicts_rescore_with_zero_calls(conn):
    """Rows graded when only the exact audience string was excluded still count: audience verdicts dropped, no regrade."""
    _with_audience_caveat(conn)
    judge = "google/gemini-3.8-flash"
    evidence = fa.load_items(conn, RUN, judge)[0].evidence
    sents = [("strength", t) for t in ["GPM video cao.", "Video nêu rõ công dụng.", "Giá hợp lý."]] + [("weakness", "Mẫu video nhỏ."), ("weakness", AUDIENCE_VARIANTS[1])]
    verdicts = [{"index": i, "verdict": m, "why": "x"} for i, m in enumerate(["supported", "partly", "supported", "unsupported", "unsupported"])]
    conn.execute("INSERT INTO faithfulness VALUES (?,?,?,?,?,?,?,?)",
                 (RUN, "c0", judge, fa.PROMPT_VERSION, fa._hash(judge, sents, evidence), 0.5, json.dumps(verdicts), "t"))
    conn.commit()
    items = [i for i in fa.load_items(conn, RUN, judge) if i.cached]
    assert len(items) == 1
    vs = items[0].cached["verdicts"]
    assert len(vs) == 4 and [v["index"] for v in vs] == [0, 1, 2, 3]
    assert fa.split_scores(vs, 3) == (pytest.approx(5 / 6), 0.0)
    summary = fa.stored_summary(conn, RUN)
    assert summary["per_koc"]["c0"] == pytest.approx(5 / 6) and summary["per_koc_caveats"]["c0"] == 0.0
    assert "Điểm Lưu ý" in benchmark_render.render_markdown(benchmark.build(conn, RUN))


def test_legacy_conversion_never_drops_reasons_and_keeps_index_mapping(conn):
    """3 reasons (one mentions audience data) + 1 retained caveat + 1 audience caveat: only the audience caveat goes."""
    reasons = ["GPM video cao.", "Khán giả chưa xác minh nhưng nội dung rõ; hồ sơ khán giả chưa được xác minh.", "Giá hợp lý."]
    conn.execute("UPDATE recommendations SET rec_json=? WHERE creator_id='c0'",
                 (rec("c0", CITED, reasons=reasons, caveats=["Mẫu video nhỏ.", AUDIENCE_VARIANTS[1]]).model_dump_json(),))
    conn.commit()
    judge = "google/gemini-3.8-flash"
    evidence = fa.load_items(conn, RUN, judge)[0].evidence
    sents = [("strength", t) for t in reasons] + [("weakness", "Mẫu video nhỏ."), ("weakness", AUDIENCE_VARIANTS[1])]
    marks = ["supported", "partly", "unsupported", "supported", "unsupported"]
    verdicts = [{"index": i, "verdict": m, "why": f"w{i}"} for i, m in enumerate(marks)]
    conn.execute("INSERT INTO faithfulness VALUES (?,?,?,?,?,?,?,?)",
                 (RUN, "c0", judge, fa.PROMPT_VERSION, fa._hash(judge, sents, evidence), 0.5, json.dumps(verdicts), "t"))
    conn.commit()
    item = [i for i in fa.load_items(conn, RUN, judge) if i.cached][0]
    vs = item.cached["verdicts"]
    assert [v["why"] for v in vs] == ["w0", "w1", "w2", "w3"] and [v["index"] for v in vs] == [0, 1, 2, 3]
    assert len(item.sentences) == len(vs) == 4 and item.n_reasons == 3
    assert fa.split_scores(vs, 3) == (pytest.approx(0.5), 1.0)
