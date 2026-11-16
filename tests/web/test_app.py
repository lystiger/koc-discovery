"""Tests for KOC Discovery Web UI.

Verifies:
- All routes return 200 on fixture DB
- Vietnamese business labels are present
- Evidence anchors cited in recommendations resolve to DOM element IDs
- Mock banner is displayed for mock runs and omitted for real runs
- Path traversal attacks on media frames are strictly blocked
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from koc.web.app import create_app
from koc.web.app import format_usd_filter
from koc.web.charts import bullet_chart
from tests.web.fixtures.seed import seed_fixture_db


@pytest.fixture(scope="session")
def fixture_env(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("web_fixture")
    db_file = tmp_dir / "fixture.db"
    media_dir = tmp_dir / "media"
    seed_fixture_db(db_path=db_file, media_dir=media_dir)
    return str(db_file), str(media_dir)


@pytest.fixture
def client(fixture_env):
    db_file, media_dir = fixture_env
    app = create_app(db_path=db_file, media_dir=media_dir)
    return TestClient(app)


def render_route(fixture_env, route_path, **route_params):
    db_file, media_dir = fixture_env
    app = create_app(db_path=db_file, media_dir=media_dir)
    route = next(route for route in app.routes if getattr(route, "path", None) == route_path)
    request = Request({"type": "http", "method": "GET", "path": route_path, "headers": []})
    return route.endpoint(request, **route_params).body.decode()


def test_routes_200_on_fixture_db(client):
    # 1. Run list
    r_list = client.get("/")
    assert r_list.status_code == 200
    assert "Các đợt chạy" in r_list.text

    # 2. Top 5 recommendations
    r_top5 = client.get("/runs/run_mock_beauty_01")
    assert r_top5.status_code == 200
    assert "Đề xuất creator" in r_top5.text

    # 3. Creator detail
    r_creator = client.get("/runs/run_mock_beauty_01/creators/c_linh_01")
    assert r_creator.status_code == 200
    assert "@linh.skindaily" in r_creator.text

    # 4. Dashboard
    r_dash = client.get("/runs/run_mock_beauty_01/dashboard")
    assert r_dash.status_code == 200
    assert "Vận hành đợt chạy" in r_dash.text

    # 5. Media frame
    r_media = client.get("/media/v_c_linh_01_1_frame_0.jpg")
    assert r_media.status_code == 200
    assert r_media.headers.get("content-type", "").startswith("image/")


def test_vietnamese_labels_present(client):
    # Check top 5 view
    r_top5 = client.get("/runs/run_mock_beauty_01")
    text_top5 = r_top5.text
    assert "Phí ước tính" in text_top5
    assert "Thương mại · 45%" in text_top5
    assert "Khán giả · 20%" in text_top5
    assert "Nội dung · 35%" in text_top5
    assert "Tổng phí booking ước tính" in text_top5
    assert "30.000.000" in text_top5
    assert "người theo dõi" in text_top5
    assert "Thứ hạng và căn cứ" in text_top5

    # Check creator detail view
    r_creator = client.get("/runs/run_mock_beauty_01/creators/c_linh_01")
    text_creator = r_creator.text
    assert "Lý do chọn" in text_creator
    assert "Điểm cần kiểm tra trước khi booking" in text_creator
    assert "Chỉ số thương mại" in text_creator
    assert "Khán giả" in text_creator
    assert "Bằng chứng video" in text_creator
    assert "Mở đầu thu hút (Hook)" in text_creator
    assert "Độ rõ ràng về sản phẩm" in text_creator
    assert "Trải nghiệm" in text_creator
    assert "Tính chuẩn xác của cam kết" in text_creator
    assert "Kêu gọi hành động (CTA)" in text_creator
    assert "Độ phù hợp thương hiệu" in text_creator
    assert "Chất lượng sản xuất video" in text_creator

    # Check dashboard view
    r_dash = client.get("/runs/run_mock_beauty_01/dashboard")
    text_dash = r_dash.text
    assert "Vận hành đợt chạy" in text_dash
    assert "Ứng viên qua từng giai đoạn" in text_dash
    assert "Kalodata · hạn mức 100,0 credit" in text_dash
    assert "chi phí ước tính" in text_dash
    assert "Tokens vào / ra" in text_dash
    assert "Cache Kalodata" in text_dash
    assert "Tác vụ" in text_dash
    assert "Thời gian xử lý" in text_dash
    assert "Đối chiếu điểm nội dung" in text_dash


def test_all_fragment_links_resolve_on_target_page(client):
    """Every href fragment on the recommendation page must exist on its target page."""
    from urllib.parse import urlsplit

    creator_ids = ("c_linh_01", "c_chou_02", "c_trinh_03", "c_mai_04", "c_an_05")
    source_paths = [
        "/runs/run_mock_beauty_01",
        *(f"/runs/run_mock_beauty_01/creators/{creator_id}" for creator_id in creator_ids),
    ]
    for source_path in source_paths:
        page = client.get(source_path)
        assert page.status_code == 200
        hrefs = re.findall(r'href="([^"]*#[^"]+)"', page.text)
        assert hrefs, f"Expected fragment links on {source_path}"
        for href in hrefs:
            link = urlsplit(href)
            target_path = link.path or urlsplit(source_path).path
            target = client.get(target_path)
            assert target.status_code == 200, f"Fragment target page missing: {href}"
            defined_ids = set(re.findall(r'id="([^"]+)"', target.text))
            assert link.fragment in defined_ids, f"Missing target id for {href}"


def test_fixture_video_evidence_varies_and_stays_mock_only(fixture_env):
    from koc import db

    db_path, _ = fixture_env
    conn = db.connect(db_path)
    try:
        params = conn.execute("SELECT params_json FROM runs WHERE run_id='run_mock_beauty_01'").fetchone()
        analyses = [
            json.loads(row[0])
            for row in conn.execute(
                "SELECT a.analysis_json FROM analyses a JOIN videos v USING(video_id) "
                "WHERE v.creator_id='c_linh_01' ORDER BY v.rowid"
            )
        ]
    finally:
        conn.close()

    assert json.loads(params[0])["mock"] is True
    assert len({item["transcript_vi"] for item in analyses}) == 3
    assert len({json.dumps(item["rubric"], sort_keys=True) for item in analyses}) == 3
    assert len({json.dumps(item["risks_vi"], sort_keys=True) for item in analyses}) == 3


def test_every_fixture_run_is_marked_mock_and_shows_banner(client, fixture_env):
    from koc import db

    db_path, _ = fixture_env
    conn = db.connect(db_path)
    try:
        runs = conn.execute(
            "SELECT run_id, params_json, (SELECT creator_id FROM recommendations WHERE run_id=runs.run_id ORDER BY rank LIMIT 1) AS creator_id FROM runs"
        ).fetchall()
    finally:
        conn.close()

    assert runs
    for run in runs:
        run_id = run["run_id"]
        assert "prod" not in run_id
        assert '"mock": true' in run["params_json"].lower()
        for path in (f"/runs/{run_id}", f"/runs/{run_id}/dashboard"):
            response = client.get(path)
            assert response.status_code == 200
            assert "GIẢ LẬP" in response.text
            assert "Dữ liệu mô phỏng, chỉ dùng để kiểm thử." in response.text

        response = client.get(f"/runs/{run_id}/creators/{run['creator_id']}")
        assert "GIẢ LẬP" in response.text


def test_single_dashboard_layout_and_charts_ignore_theme_query(client):
    response = client.get("/runs/run_mock_beauty_01?theme=c")
    assert response.status_code == 200
    assert "theme=c" not in response.headers.get("set-cookie", "")
    assert 'data-theme="' not in response.text
    assert "Chọn giao diện" not in response.text
    assert "Điểm theo trọng số" in response.text
    assert "Chi phí và điểm của ứng viên" in response.text
    assert "30.000.000 ₫" in response.text
    assert response.text.count('class="chart-bars" role="img" aria-label=') >= 1
    assert 'class="scatter-chart" width="720" height="265"' in response.text
    assert "Chi phí (₫ triệu)" in response.text
    assert ">Điểm</text>" in response.text
    assert 'class="mobile-koc-cards"' in response.text
    assert ".mobile-koc-cards { display: block; }" in response.text
    assert ".score-parts strong { display: block;" in response.text

    dashboard = client.get("/runs/run_mock_beauty_01/dashboard")
    assert "Mức dùng so với hạn mức" in dashboard.text
    assert "Số ứng viên qua phễu S0 đến S4" in dashboard.text
    assert 'class="chart-bars" role="img" aria-label="Số ứng viên qua phễu S0 đến S4.' in dashboard.text
    assert '<title id="scatter-cost-score-title">' in response.text
    assert '<desc id="scatter-cost-score-desc">' in response.text
    assert 'bar-row funnel-row' in dashboard.text
    assert re.search(r'class="bar-fill" style="width:100\.0%;background:#1E40AF"', dashboard.text)
    assert re.search(r'class="bar-value">\d+</strong>', dashboard.text)


def test_creator_has_demographic_and_rubric_charts(fixture_env):
    html = render_route(
        fixture_env,
        "/runs/{run_id}/creators/{creator_id}",
        run_id="run_mock_beauty_01",
        creator_id="c_linh_01",
    )
    assert "Tỷ lệ giới tính và độ tuổi" in html
    assert "Điểm rubric video 1" in html
    assert html.count('class="chart-bars" role="img" aria-label=') >= 4
    assert re.search(r'class="bar-fill" style="width:[\d.]+%;background:#1E40AF"', html)
    assert 'class="frame-placeholder" aria-hidden="true"' in html
    assert html.count("Khung hình mô phỏng; chưa có ảnh video thật.") == 3
    assert "không nhận seeding bẩn" not in html
    assert "rất an toàn cho làn da" not in html


def test_dashboard_mobile_table_cues_and_number_format(fixture_env):
    html = render_route(fixture_env, "/runs/{run_id}/dashboard", run_id="run_mock_beauty_01")

    assert html.count("Vuốt ngang để xem đầy đủ bảng.") == 3
    assert "S0 · S0:" not in html
    assert "0,742" in html
    assert "$0,0756 / $5,00" in html


def test_finalists_heading_matches_visible_rows(fixture_env):
    html = render_route(
        fixture_env,
        "/runs/{run_id}",
        run_id="run_mock_beauty_01",
    )
    assert "↕" not in html
    assert "sortable" not in html
    heading_count = int(re.search(r'<h2>(\d+) ứng viên vào vòng cuối</h2>', html).group(1))
    chart_count = int(re.search(r'<title id="scatter-cost-score-title">Chi phí và điểm của (\d+) ứng viên vòng cuối</title>', html).group(1))
    finalists_table = re.search(r'<h2>\d+ ứng viên vào vòng cuối</h2>.*?<tbody>(.*?)</tbody>', html, re.S).group(1)
    visible_rows = len(re.findall(r'<tr><td>', finalists_table))

    assert heading_count == chart_count == visible_rows


@pytest.mark.parametrize(("value", "expected"), [(0.0756, "0,0756"), (5, "5,00")])
def test_usd_format_preserves_precision(value, expected):
    assert format_usd_filter(value) == expected
    assert f"${expected} / $5,00" in bullet_chart(0, 1, value, 5)


def test_creator_metrics_stack_with_compact_source_and_evidence(client):
    html = client.get("/runs/run_mock_beauty_01/creators/c_linh_01").text

    assert 'class="metrics-list"' in html
    assert 'class="metric-item" id="metric:c_linh_01:female_ratio"' in html
    assert "kalodata · last30Day" in html
    assert "<code class=\"evidence-id\">metric:c_linh_01:female_ratio</code>" in html


def test_inline_reason_evidence_uses_linked_numbered_markers(client):
    html = client.get("/runs/run_mock_beauty_01/creators/c_linh_01").text
    reason_list = re.search(r'<ul class="evidence-list">(.*?)</ul>', html, re.S).group(1)

    assert "(metric:c_linh_01:female_ratio)" not in reason_list
    assert re.search(r'<sup class="evidence-reference"><a href="#metric:c_linh_01:female_ratio"[^>]*>\[1\]</a></sup>', reason_list)
    assert 'id="metric:c_linh_01:female_ratio"' in html


def test_path_traversal_blocked(client):
    traversal_attacks = [
        "/media/../fixture.db",
        "/media/..%2Ffixture.db",
        "/media/%2e%2e/fixture.db",
        "/media/subdir/../../etc/passwd",
        "/media/%2e%2e%2f%2e%2e%2fetc/passwd",
    ]
    for url in traversal_attacks:
        resp = client.get(url)
        assert resp.status_code in (400, 403, 404), (
            f"Path traversal not blocked! Path {url} returned {resp.status_code}"
        )


def test_404_error_handling(client):
    assert client.get("/runs/non_existent_run").status_code == 404
    assert client.get("/runs/run_mock_beauty_01/creators/non_existent_creator").status_code == 404
    assert client.get("/media/non_existent_frame.jpg").status_code == 404
