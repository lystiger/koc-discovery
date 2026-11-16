import math
import os
from pathlib import Path

import typer
import yaml

from . import db
from .brief import check_brief, make_brief, run_brief, vnd
from .config import load_config
from .estimate import estimate_lines_vi, estimate_run
from .pipeline import leftover_line, resume as resume_pipeline, run_exclusions, start
from .stages import excluded_brand_fit
from .queries import list_runs


app = typer.Typer(no_args_is_help=True)
DB_PATH = Path(os.getenv("KOC_DB", "data/koc.db"))


def save_category_ids(rows, keyword, config_path):
    matches = [row for row in rows if keyword.casefold() in str(row.get("category_name", "")).casefold()]
    if not matches:
        return []
    config = yaml.safe_load(config_path.read_text())
    config["s0"]["category_ids"] = [str(row["category_id"]) for row in matches]
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    return matches


def _category_ids(value):
    return None if value is None else [part.strip() for part in value.split(",") if part.strip()]


@app.command()
def run(limit: int = typer.Option(200, "--limit", min=1),
        product: str = typer.Option(None, "--product", help="Sản phẩm (mặc định: kem chống nắng); cũng là từ khóa khi không có danh mục."),
        product_type: str = typer.Option(None, "--product-type", help="Loại sản phẩm của web (Chống nắng, Dưỡng ẩm, Serum, Làm sạch, Trang điểm, Khác); điền --category-ids từ config/product_categories.yaml."),
        category_ids: str = typer.Option(None, "--category-ids", help="ID danh mục Kalodata, ngăn bằng dấu phẩy (mặc định: config s0.category_ids)."),
        gender: str = typer.Option(None, "--gender", help="nu, nam hoặc tat-ca (mặc định nu)."),
        age_min: int = typer.Option(None, "--age-min", help="Tuổi nhỏ nhất của khán giả (mặc định 18)."),
        age_max: int = typer.Option(None, "--age-max", help="Tuổi lớn nhất của khán giả (mặc định 30)."),
        budget: int = typer.Option(None, "--budget", help="Ngân sách VND (mặc định 30000000)."),
        count: int = typer.Option(None, "--count", help="Số KOC cần chọn (mặc định 5)."),
        exclude_run: list[str] = typer.Option(None, "--exclude-run", help="ID lượt chạy trước; loại các KOC đã được đề xuất ở lượt đó (lặp lại được)."),
        dry_run: bool = typer.Option(False, "--dry-run"), mock: bool = typer.Option(False, "--mock"), cache_only: bool = typer.Option(False, "--cache-only", help="Chỉ dùng dữ liệu đã lưu; không gọi mạng, không tốn tín dụng/token.")):
    config = load_config()
    brief = make_brief(config, product=product, product_type=product_type, category_ids=_category_ids(category_ids), gender=gender, age_min=age_min, age_max=age_max, budget=budget, count=count)
    if error := check_brief(brief, config):
        typer.echo(error, err=True)
        raise typer.Exit(1)
    if dry_run:
        pages = math.ceil(limit / 100)
        pipeline = load_config()["s1"]
        prices = load_config()["kalodata_prices"]
        s0_s1_credits = pages * 0.1 + min(pipeline["s1a_limit"], limit) * 0.2
        s2_credits = min(pipeline["s2_limit"], pipeline["s1_limit"], limit) * prices["ui_creator_detail_view"]
        s3_candidates = min(pipeline["s1a_limit"], pipeline["s1_limit"], pipeline["s2_limit"], limit)
        s3_credits = s3_candidates * (0.1 + 3 * 0.5)
        categories = ", ".join(brief["category_ids"]) or "chưa cấu hình"
        typer.echo(f"Kế hoạch: S0 tối đa {limit} nhà sáng tạo, S1a lọc còn {pipeline['s1a_limit']}, S1b chấm điểm còn {pipeline['s1_limit']}, S2 còn {pipeline['s2_limit']}, S3 phân tích, S4 chọn {brief['count']}.")
        typer.echo(f"Brief: {brief['product']} · {brief['target']} · {brief['count']} KOC · ngân sách {vnd(brief['budget_vnd'])} VND.")
        typer.echo(f"Danh mục: {categories}.")
        typer.echo(f"Tín dụng S0+S1 dự kiến: tối đa {s0_s1_credits:.1f} (S0 rank + {min(pipeline['s1a_limit'], limit)} × 0.2 cho S1b).")
        typer.echo(f"Tín dụng S2 dự kiến: tối đa {s2_credits:.1f}.")
        typer.echo(f"Tín dụng S3 dự kiến: tối đa {s3_credits:.1f}; tổng toàn pipeline: {s0_s1_credits + s2_credits + s3_credits:.1f}; token LLM: 0 trong chạy thử.")
        if estimate := estimate_run(load_config(), limit, brief["count"]):
            for line in estimate_lines_vi(estimate):
                typer.echo(line)
        else:
            typer.echo("Chưa có reports/benchmark.json nên chưa có ước tính chi phí và thời gian.")
        if not brief["category_ids"]: typer.echo(f"Cảnh báo: chưa cấu hình danh mục; sẽ tìm creator/rank với từ khóa '{brief['product']}'.")
        typer.echo("Chạy thử: không gọi mạng, không ghi dữ liệu.")
        return
    conn = db.connect(DB_PATH)
    db.init_db(conn)
    if not brief["category_ids"]:
        typer.echo(f"Cảnh báo: chưa cấu hình danh mục; đang dùng từ khóa '{brief['product']}' cho creator/rank.")
    try:
        notes = [f"Đã loại {len(run_exclusions(conn, [source])['creator_ids'])} KOC đã đề xuất ở lần chạy {source}." for source in dict.fromkeys(exclude_run or [])]
        for note in notes:
            typer.echo(note)
        run_id = start(conn, limit, mock=mock, cache_only=cache_only, brief=brief, exclude_run_ids=exclude_run)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Đã hoàn tất lượt chạy {run_id}.")
    if leftover := leftover_line(conn, run_id):
        typer.echo(leftover)


@app.command()
def resume(mock: bool = typer.Option(False, "--mock"),
           product: str = typer.Option(None, "--product"), product_type: str = typer.Option(None, "--product-type"), category_ids: str = typer.Option(None, "--category-ids"),
           gender: str = typer.Option(None, "--gender"), age_min: int = typer.Option(None, "--age-min"),
           age_max: int = typer.Option(None, "--age-max"), budget: int = typer.Option(None, "--budget"), count: int = typer.Option(None, "--count"),
           retry_failed: bool = typer.Option(False, "--retry-failed", help="Thử lại creator S3 bị loại của lượt chạy đã hoàn tất (tốn phí, chọn lại S4).")):
    if not DB_PATH.exists():
        typer.echo("Chưa có cơ sở dữ liệu.")
        raise typer.Exit(1)
    conn = db.connect(DB_PATH)
    db.init_db(conn)
    given = {"product": product, "product_type": product_type, "category_ids": _category_ids(category_ids), "gender": gender, "age_min": age_min, "age_max": age_max, "budget_vnd": budget, "count": count}
    latest = db.run_latest(conn)
    if latest is not None and latest["status"] == "done" and not retry_failed and all(value is None for value in given.values()):
        typer.echo(f"Lượt chạy {latest['run_id']} đã hoàn tất; không có gì để tiếp tục. Dùng --retry-failed để thử lại các creator bị loại.")
        return
    try:
        run_id = resume_pipeline(conn, mock=mock if mock else None, retry_failed=retry_failed, brief=given)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Đã tiếp tục lượt chạy {run_id}.")


@app.command()
def status():
    if not DB_PATH.exists():
        typer.echo("Chưa có lượt chạy.")
        return
    conn = db.connect(DB_PATH)
    db.init_db(conn)
    runs = list_runs(conn)
    if not runs:
        typer.echo("Chưa có lượt chạy.")
        return
    for item in runs:
        counts = {row["status"]: row["n"] for row in conn.execute("SELECT status,COUNT(*) AS n FROM tasks WHERE run_id=? GROUP BY status", (item["run_id"],))}
        reason = conn.execute("SELECT error FROM tasks WHERE run_id=? AND (status='blocked' OR error LIKE 'blocked:%') AND error IS NOT NULL LIMIT 1", (item["run_id"],)).fetchone()
        why = f" · lý do: {reason[0]}" if reason else ""
        brief = run_brief(conn, item["run_id"], load_config())
        text = f" · brief: {brief['product']}, {brief['target']}, {brief['count']} KOC, {vnd(brief['budget_vnd'])} VND"
        typer.echo(f"{item['run_id']} · {item['status']} · tác vụ: {counts}{why}{text}")
        if leftover := leftover_line(conn, item["run_id"]):
            typer.echo(f"  {leftover}")
        for gone in excluded_brand_fit(conn, item["run_id"]):
            typer.echo(f"  {gone['handle']}: {gone['reason_vi']}")


@app.command()
def categories(keyword: str = typer.Option(..., "--keyword")):
    """Tìm danh mục Kalodata và lưu ID khớp vào cấu hình."""
    conn = db.connect(DB_PATH)
    db.init_db(conn)
    from .kalodata import KalodataClient
    client = KalodataClient(conn)
    data = []
    for page_number in range(1, 20):
        try:
            response = client.category_rank(page_size=100, page_number=page_number)
        except RuntimeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        rows = response.get("data", response) if isinstance(response, dict) else response
        data.extend(rows or [])
        if len(rows or []) < 100:
            break
    config_path = Path(__file__).resolve().parents[2] / "config/scoring.yaml"
    matches = save_category_ids(data, keyword, config_path)
    if not matches:
        typer.echo("Không tìm thấy danh mục khớp từ khóa.")
        return
    for row in matches:
        typer.echo(f"{row['category_id']}\t{row['category_name']}")


@app.command()
def audience():
    """Tiếp tục chụp dữ liệu đối tượng từ phiên Kalodata đã đăng nhập."""
    if not DB_PATH.exists():
        typer.echo("Chưa có lượt chạy.")
        raise typer.Exit(1)
    conn = db.connect(DB_PATH)
    db.init_db(conn)
    try:
        run_id = resume_pipeline(conn)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Đã tiếp tục thu thập đối tượng cho lượt chạy {run_id}.")


@app.command()
def report(run: str = typer.Option(..., "--run")):
    from .report import write_benchmark
    conn = db.connect(DB_PATH)
    db.init_db(conn)
    result = write_benchmark(conn, run)
    typer.echo(f"Đã ghi reports/benchmark.json và docs/BENCHMARK.md cho lượt chạy {run} ({result['candidates']['finalists']} ứng viên vào S4).")


@app.command()
def benchmark(run: str = typer.Option(..., "--run"), scaling_run: str = typer.Option(None, "--scaling-run", help="Lượt chạy mô phỏng dùng cho mục mở rộng 50 ứng viên."),
              out_dir: Path = typer.Option(Path("."), "--out-dir")):
    """Ghi reports/benchmark.json và docs/BENCHMARK.md từ cơ sở dữ liệu (chỉ đọc)."""
    import json
    from . import benchmark as bench
    from .benchmark_render import render_markdown
    if not DB_PATH.exists():
        typer.echo("Chưa có cơ sở dữ liệu.", err=True)
        raise typer.Exit(1)
    conn = db.connect(DB_PATH)
    try:
        result = bench.build(conn, run, scaling_run)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    (out_dir / "reports").mkdir(parents=True, exist_ok=True)
    (out_dir / "docs").mkdir(parents=True, exist_ok=True)
    (out_dir / "reports/benchmark.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (out_dir / "docs/BENCHMARK.md").write_text(render_markdown(result))
    typer.echo(f"Đã ghi reports/benchmark.json và docs/BENCHMARK.md cho lượt chạy {run}: thành công {result['totals_success']['credits']:.2f} tín dụng, tổng thực chi {result['totals_total']['credits']:.2f} tín dụng.")


@app.command()
def faithfulness(run: str = typer.Option(..., "--run"),
                 model: str = typer.Option(None, "--model", help="Mô hình chấm (mặc định: cùng họ mô hình rẻ với S4)."),
                 cache_only: bool = typer.Option(False, "--cache-only", help="Chỉ dùng kết quả đã lưu; không gọi mạng."),
                 dry_run: bool = typer.Option(False, "--dry-run", help="Chỉ ước tính số lượt gọi, token và USD; không gọi mạng.")):
    """Chấm độ trung thực của lý do S4: mỗi câu có được bằng chứng đã trích dẫn chống đỡ không."""
    from . import faithfulness as fa
    from .llm.pricing import load_pricing_config
    from .types import BudgetExceeded, CacheOnlyMiss
    if not DB_PATH.exists():
        typer.echo("Chưa có cơ sở dữ liệu.", err=True)
        raise typer.Exit(1)
    conn = db.connect(DB_PATH)
    judge = model or load_pricing_config().get("model", {}).get("id")
    if dry_run:  # read only: never creates the table or a call
        items = fa.load_items(conn, run, judge)
        if not items:
            typer.echo(f"Lượt chạy {run} chưa có đề xuất S4.", err=True)
            raise typer.Exit(1)
        e = fa.estimate(items, judge)
        typer.echo(f"Ước tính chấm độ trung thực, mô hình {judge}: {e['calls']} lượt gọi (đã lưu {e['cached']}, không có bằng chứng {e['no_evidence']}), tối đa {e['input_tokens']} token đầu vào, tối đa {e['usd']:.4f} USD. Chạy thử: không gọi mạng.")
        return
    try:
        out = fa.evaluate(conn, run, model=model, cache_only=cache_only)
    except (CacheOnlyMiss, BudgetExceeded, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if not out["items"]:
        typer.echo(f"Lượt chạy {run} chưa có đề xuất S4.", err=True)
        raise typer.Exit(1)
    glyph = {"supported": "đủ cơ sở", "partly": "một phần", "unsupported": "không có cơ sở"}
    typer.echo(f"{'KOC':<24}{'Lý do':>7}{'Lưu ý':>7}  Câu / phán quyết (lý do trước, rồi lưu ý; bỏ qua lưu ý về khán giả chưa xác minh)")
    for item, verdicts, score in out["items"]:
        caveat = fa.split_scores(verdicts, item.n_reasons)[1]
        typer.echo(f"{item.handle:<24}{score:>7.2f}{('-' if caveat is None else format(caveat, '.2f')):>7}  " + ", ".join(f"{i + 1}:{glyph[v['verdict']]}" for i, v in enumerate(verdicts)))
        for (kind, text), v in zip(item.sentences, verdicts):
            if v["verdict"] != "supported":
                typer.echo(f"    - {glyph[v['verdict']]}: {text[:90]} ({v['why']})")
    cav = "-" if out["caveat_score"] is None else f"{out['caveat_score']:.2f}"
    typer.echo(f"Điểm trung thực của lượt chạy (Lý do): {out['score']:.2f} / 1 ({len(out['items'])} KOC, mô hình {out['model']}). Điểm Lưu ý (không tính lưu ý khán giả chưa xác minh): {cav}. Số lượt gọi: {out['calls']}; chi phí: {out['usd']:.6f} USD.")


if __name__ == "__main__":
    app()
