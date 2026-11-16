"""FastAPI server application for KOC Discovery Web UI.

Server-rendered using Jinja2 templates, serving 3 core business views:
1. Top 5 KOC recommendations with score breakdowns & budget optimizer
2. Creator deep-dive with metrics, audience demographics, video frames & rubric
3. Performance and operations dashboard (funnel, tasks, costs, caps, calibration)
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from koc.web.api import router as api_router

from koc import db
from koc.web import adapter
from koc.web.charts import bar_chart, bullet_chart, funnel_chart, scatter_chart, score_chart


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def format_vnd_filter(value: Any) -> str:
    try:
        val = int(float(value))
        formatted = f"{val:,}".replace(",", ".")
        return f"{formatted} ₫"
    except (ValueError, TypeError):
        return f"{value} ₫"


def format_number_filter(value: Any) -> str:
    try:
        val = int(float(value))
        return f"{val:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


def format_percent_filter(value: Any) -> str:
    try:
        val = float(value)
        return f"{val:.1f}%".replace(".", ",")
    except (ValueError, TypeError):
        return f"{value}%"


def format_score_filter(value: Any) -> str:
    try:
        val = float(value)
        return f"{val:.1f}".replace(".", ",")
    except (ValueError, TypeError):
        return str(value)


def format_decimal_filter(value: Any) -> str:
    try:
        return f"{float(value):.1f}".replace(".", ",")
    except (ValueError, TypeError):
        return str(value)


def format_usd_filter(value: Any) -> str:
    try:
        formatted = f"{float(value):.4f}".rstrip("0").rstrip(".")
        if "." not in formatted:
            formatted += ".00"
        elif len(formatted.partition(".")[2]) == 1:
            formatted += "0"
        return formatted.replace(".", ",")
    except (ValueError, TypeError):
        return str(value)


def format_measure_filter(value: Any) -> str:
    try:
        return f"{float(value):.3f}".rstrip("0").rstrip(".").replace(".", ",")
    except (ValueError, TypeError):
        return str(value)


def create_app(db_path: str = "data/koc.db", media_dir: str = "data/media", serve_spa: bool = False) -> FastAPI:
    app = FastAPI(title="KOC Discovery Web", docs_url=None, redoc_url=None)
    app.state.db_path = db_path
    app.state.media_dir = Path(media_dir).resolve()
    app.state.web_dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    app.state.serve_spa = serve_spa
    app.include_router(api_router)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["format_vnd"] = format_vnd_filter
    templates.env.filters["format_number"] = format_number_filter
    templates.env.filters["format_percent"] = format_percent_filter
    templates.env.filters["format_score"] = format_score_filter
    templates.env.filters["format_decimal"] = format_decimal_filter
    templates.env.filters["format_usd"] = format_usd_filter
    templates.env.filters["format_measure"] = format_measure_filter

    def _get_conn():
        return db.connect(app.state.db_path)

    # 1. Run List / Home View
    @app.get("/", response_class=HTMLResponse)
    def view_runs_list(request: Request):
        index_file = app.state.web_dist / "index.html"
        if app.state.serve_spa and index_file.is_file():
            return FileResponse(index_file)
        conn = _get_conn()
        try:
            runs = adapter.list_all_runs(conn)
            latest_run_id = runs[0]["run_id"] if runs else None
            return templates.TemplateResponse(
                request=request,
                name="runs_list.html",
                context={
                    "runs": runs,
                    "run_options": runs,
                    "active_nav": "runs",
                    "current_run_id": latest_run_id,
                    "is_mock": any(run["is_mock"] for run in runs),
                },
            )
        finally:
            conn.close()

    # 2. Top 5 KOC Recommendations View
    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def view_run_top5(request: Request, run_id: str):
        conn = _get_conn()
        try:
            run_meta = adapter.get_run_metadata(conn, run_id)
            if not run_meta:
                raise HTTPException(status_code=404, detail="Không tìm thấy đợt chạy (Run ID không tồn tại)")

            top5_data = adapter.get_top5_with_details(conn, run_id)
            finalists = adapter.get_finalists(conn, run_id, {card["creator_id"] for card in top5_data["cards"]})
            return templates.TemplateResponse(
                request=request,
                name="top5.html",
                context={
                    "run": run_meta,
                    "top5_data": top5_data,
                    "run_options": adapter.list_all_runs(conn),
                    "active_nav": "top5",
                    "current_run_id": run_id,
                    "is_mock": run_meta["is_mock"],
                    "score_chart": score_chart(top5_data["cards"]),
                    "finalists": finalists,
                    "scatter_chart": scatter_chart(finalists, top5_data["budget_cap_vnd"]),
                },
            )
        finally:
            conn.close()

    # 3. Creator Detail View
    @app.get("/runs/{run_id}/creators/{creator_id}", response_class=HTMLResponse)
    def view_creator_detail(request: Request, run_id: str, creator_id: str):
        conn = _get_conn()
        try:
            run_meta = adapter.get_run_metadata(conn, run_id)
            if not run_meta:
                raise HTTPException(status_code=404, detail="Không tìm thấy đợt chạy (Run ID không tồn tại)")

            creator_detail = adapter.get_creator_full_detail(conn, run_id, creator_id)
            if not creator_detail:
                raise HTTPException(status_code=404, detail="Không tìm thấy KOC trong đợt chạy này")

            return templates.TemplateResponse(
                request=request,
                name="creator.html",
                context={
                    "run": run_meta,
                    "creator": creator_detail,
                    "run_options": adapter.list_all_runs(conn),
                    "active_nav": "top5",
                    "current_run_id": run_id,
                    "is_mock": run_meta["is_mock"],
                    "audience_chart": None if creator_detail["audience"]["placeholder"] else bar_chart("Tỷ lệ giới tính và độ tuổi", [
                        ("Nữ", creator_detail["audience"]["female_pct"]),
                        ("Nam", creator_detail["audience"]["male_pct"]),
                        *((age.replace("-", " đến ") + " tuổi", share) for age, share in creator_detail["audience"]["age_distribution"].items()),
                    ]),
                    "rubric_charts": [bar_chart("Điểm rubric video " + str(index + 1), [(item["label_vi"], item["score"]) for item in video["rubric"]], 5) for index, video in enumerate(creator_detail["videos"])],
                },
            )
        finally:
            conn.close()

    # 4. Performance & Operations Dashboard
    @app.get("/runs/{run_id}/dashboard", response_class=HTMLResponse)
    def view_run_dashboard(request: Request, run_id: str):
        conn = _get_conn()
        try:
            run_meta = adapter.get_run_metadata(conn, run_id)
            if not run_meta:
                raise HTTPException(status_code=404, detail="Không tìm thấy đợt chạy (Run ID không tồn tại)")

            dashboard_data = adapter.get_dashboard_data(conn, run_id)
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context={
                    "run": run_meta,
                    "dashboard": dashboard_data,
                    "run_options": adapter.list_all_runs(conn),
                    "active_nav": "dashboard",
                    "current_run_id": run_id,
                    "is_mock": run_meta["is_mock"],
                    "funnel_chart": funnel_chart(dashboard_data["funnel"]),
                    "bullet_chart": bullet_chart(dashboard_data["credits"]["used"], dashboard_data["credits"]["cap"], dashboard_data["llm"]["cost_usd"], dashboard_data["llm"]["cap_usd"]),
                },
            )
        finally:
            conn.close()

    # 5. Secure Media Frames Static Route (Strict Path Traversal Protection)
    @app.get("/media/{filepath:path}")
    def serve_media_frame(filepath: str):
        # Strict validation against directory traversal
        parts = Path(filepath).parts
        if ".." in parts or any(p.startswith("/") or p.startswith("\\") for p in parts):
            raise HTTPException(status_code=403, detail="Bị từ chối: Phát hiện đường dẫn không an toàn (Path Traversal)")

        base_dir = app.state.media_dir
        target_file = (base_dir / filepath).resolve()

        try:
            target_file.relative_to(base_dir)
        except ValueError:
            raise HTTPException(status_code=403, detail="Bị từ chối: Đường dẫn nằm ngoài thư mục media cho phép")

        if not target_file.is_file():
            raise HTTPException(status_code=404, detail="Tệp khung hình không tồn tại")

        return FileResponse(target_file)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if not app.state.serve_spa:
            raise HTTPException(status_code=404, detail="Không tìm thấy trang.")
        target = (app.state.web_dist / full_path).resolve()
        try:
            target.relative_to(app.state.web_dist.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Không tìm thấy trang.")
        if target.is_file():
            return FileResponse(target)
        index_file = app.state.web_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Không tìm thấy trang.")

    return app
