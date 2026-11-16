"""Seed realistic mock runs for tests and development."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess

from koc import db


MEDIA_DIR = Path(__file__).parent / "media"


def _generate_frame_image(file_path: Path) -> None:
    """Generate a neutral mock-only 360x240 placeholder using magick or a minimal fallback."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cmd = [
            "magick",
            "-size", "360x240",
            "xc:#E8E6E1",
            "-fill", "#4B4944",
            "-font", "Adwaita-Sans",
            "-pointsize", "18",
            "-gravity", "center",
            "-draw", "text 0,0 'Khung hinh gia lap'",
            str(file_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Minimal valid 1x1 JPEG fallback if magick fails
        minimal_jpg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00"
            b"\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00"
            b"\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )
        file_path.write_bytes(minimal_jpg)


def seed_fixture_db(db_path: str | Path = "data/fixture.db", media_dir: Path | str = MEDIA_DIR) -> str:
    media_path = Path(media_dir)
    media_path.mkdir(parents=True, exist_ok=True)

    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    conn = db.connect(target)
    db.init_db(conn)

    # 1. RUNS
    # Run 1: Mock Run (params_json has mock: true)
    run_mock_id = "run_mock_beauty_01"
    run_mock_params = {
        "mock": True,
        "brief": {
            "product_vi": "Kem chống nắng quang phổ rộng SPF50+ PA++++",
            "audience_vi": "Nữ, 18 đến 30 tuổi, da dầu mụn",
            "budget_vnd": 30_000_000,
        },
        "limit": 50,
        "calibration": {
            "spearman_views": 0.742,
            "spearman_gpm": 0.685,
        },
    }
    conn.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
        (run_mock_id, "2026-11-15T01:00:00+07:00", "2026-11-15T01:14:22+07:00", "done", json.dumps(run_mock_params)),
    )

    # Run 2: second mock dataset
    run_second_id = "run_mock_skincare_02"
    run_second_params = {
        "mock": True,
        "brief": {
            "product_vi": "Serum phục hồi B5 & Kem chống nắng",
            "audience_vi": "Nữ, 20 đến 35 tuổi",
            "budget_vnd": 30_000_000,
        },
        "limit": 50,
        "calibration": {
            "spearman_views": 0.812,
            "spearman_gpm": 0.734,
        },
    }
    conn.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
        (run_second_id, "2026-11-15T02:00:00+07:00", "2026-11-15T02:18:10+07:00", "done", json.dumps(run_second_params)),
    )

    # 2. CREATORS DATA (Top 5 finalists + other candidates)
    creators_seed = [
        {
            "id": "c_linh_01",
            "handle": "@linh.skindaily",
            "followers": 185000,
            "nickname": "Linh Skin Daily",
            "bio": "Chăm da • Review sản phẩm chăm sóc da • Da hỗn hợp thiên dầu",
            "avatar": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/linh.jpg",
            "mcn": "DC Media",
            "video_gpm": 145000,
            "female_pct": 82.5,
            "age_18_24": 46.0,
            "age_25_34": 37.5,
            "cost": 6500000,
            "rank": 1,
            "scores": {"S1": 88.5, "S2": 92.0, "S3": 86.0, "S4": 88.3},
        },
        {
            "id": "c_chou_02",
            "handle": "@chouchou.beauty",
            "followers": 128000,
            "nickname": "Chou Chou Skincare",
            "bio": "Dược sĩ tư vấn routine chăm da mụn & chống lão hóa lành tính",
            "avatar": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/chou.jpg",
            "mcn": "Vulcan",
            "video_gpm": 128000,
            "female_pct": 85.0,
            "age_18_24": 42.0,
            "age_25_34": 43.0,
            "cost": 5500000,
            "rank": 2,
            "scores": {"S1": 85.0, "S2": 89.0, "S3": 88.0, "S4": 86.85},
        },
        {
            "id": "c_trinh_03",
            "handle": "@trinh.review",
            "followers": 245000,
            "nickname": "Trịnh Mỹ Phẩm",
            "bio": "Test kem chống nắng dưới đèn UV thật • Nói không với quảng cáo lố",
            "avatar": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/trinh.jpg",
            "mcn": "Metub",
            "video_gpm": 152000,
            "female_pct": 79.0,
            "age_18_24": 40.0,
            "age_25_34": 45.0,
            "cost": 7000000,
            "rank": 3,
            "scores": {"S1": 82.0, "S2": 85.0, "S3": 91.0, "S4": 85.75},
        },
        {
            "id": "c_mai_04",
            "handle": "@mai.dermacare",
            "followers": 92000,
            "nickname": "Bác sĩ Mai Da Liễu",
            "bio": "Bác sĩ chuyên khoa da liễu chia sẻ kiến thức bảo vệ màng da và chống nắng",
            "avatar": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/mai.jpg",
            "mcn": None,
            "video_gpm": 115000,
            "female_pct": 88.0,
            "age_18_24": 35.0,
            "age_25_34": 52.0,
            "cost": 5000000,
            "rank": 4,
            "scores": {"S1": 86.0, "S2": 84.0, "S3": 82.0, "S4": 84.2},
        },
        {
            "id": "c_an_05",
            "handle": "@an.glowskin",
            "followers": 64000,
            "nickname": "An Nghiện Chống Nắng",
            "bio": "Hành trình tìm chân ái chống nắng cho da dầu mụn học sinh sinh viên",
            "avatar": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/an.jpg",
            "mcn": None,
            "video_gpm": 98000,
            "female_pct": 86.5,
            "age_18_24": 62.0,
            "age_25_34": 26.0,
            "cost": 4500000,
            "rank": 5,
            "scores": {"S1": 81.0, "S2": 90.0, "S3": 84.0, "S4": 83.85},
        },
        # Candidate eliminated in shortlist
        {
            "id": "c_hoa_06",
            "handle": "@hoa.beautytips",
            "followers": 110000,
            "nickname": "Hoa Beauty",
            "bio": "Tips makeup & dưỡng ẩm mùa hè",
            "avatar": "https://p16-sign-va.tiktokcdn.com/tos-maliva-avt-0068/hoa.jpg",
            "mcn": "DC Media",
            "video_gpm": 72000,
            "female_pct": 74.0,
            "age_18_24": 50.0,
            "age_25_34": 30.0,
            "cost": 5000000,
            "rank": 6,
            "scores": {"S1": 71.0, "S2": 76.0, "S3": 70.0, "S4": 71.65},
        },
    ]

    for c in creators_seed:
        creator_data = {
            "creator_id": c["id"],
            "creator_handle": c["handle"],
            "creator_nickname": c["nickname"],
            "creator_followers": c["followers"],
            "bio": c["bio"],
            "avatar_thumb": c["avatar"],
            "mcn": c["mcn"],
            "video_gpm": c["video_gpm"],
            "revenue": c["video_gpm"] * 120,
            "skincare_revenue": c["video_gpm"] * 85,
            "revenue_trend": [80000, 95000, 110000, 130000, c["video_gpm"]],
            "audience_gender": {"female": c["female_pct"], "male": round(100 - c["female_pct"], 1)},
            "audience_age": {
                "18-24": c["age_18_24"],
                "25-34": c["age_25_34"],
                "35+": round(100 - c["age_18_24"] - c["age_25_34"], 1),
            },
        }
        db.upsert_creator(conn, c["id"], c["handle"], creator_data)

        # Upsert metrics with evidence_id
        db.upsert_metric(conn, c["id"], "video_gpm", c["video_gpm"], "kalodata", "last30Day")
        db.upsert_metric(conn, c["id"], "skincare_revenue_share", 0.68, "kalodata", "last30Day")
        db.upsert_metric(conn, c["id"], "engagement_per_view", 0.048, "kalodata", "last30Day")
        db.upsert_metric(conn, c["id"], "revenue_trend_slope", 0.28, "kalodata", "last30Day")
        db.upsert_metric(conn, c["id"], "female_ratio", c["female_pct"] / 100.0, "browser", "last30Day")
        db.upsert_metric(conn, c["id"], "age_18_24_share", c["age_18_24"] / 100.0, "browser", "last30Day")
        db.upsert_metric(conn, c["id"], "age_25_34_share", c["age_25_34"] / 100.0, "browser", "last30Day")

        # Upsert scores for both runs
        for run_id in [run_mock_id, run_second_id]:
            db.upsert_score(conn, run_id, c["id"], "S1", c["scores"]["S1"], {"commercial": c["scores"]["S1"]})
            db.upsert_score(conn, run_id, c["id"], "S2", c["scores"]["S2"], {"female_pct": c["female_pct"]})
            db.upsert_score(conn, run_id, c["id"], "S3", c["scores"]["S3"], {"rubric_mean": c["scores"]["S3"]})
            db.upsert_score(conn, run_id, c["id"], "S4", c["scores"]["S4"], {"final": c["scores"]["S4"]})

    # 3. TOP 5 RECOMMENDATIONS
    recommendations_data = {
        "c_linh_01": {
            "reasons": [
                "Người theo dõi là nữ chiếm 82,5%. Nhóm 18 đến 34 tuổi chiếm 83,5%, rộng hơn đối tượng 18 đến 30 của chiến dịch (metric:c_linh_01:female_ratio).",
                "Khung hình tại 15 giây là dữ liệu giả lập, chưa có ảnh video thật (v_c_linh_01_1@15.0s).",
                "Hệ số tăng trưởng doanh thu 30 ngày là 0,28. Đơn vị và độ ổn định chưa được đo (metric:c_linh_01:revenue_trend_slope).",
            ],
            "caveats": [
                "Cần nhắc KOC tránh dùng các từ khẳng định tuyệt đối về khả năng kháng nước cả ngày (v_c_linh_01_2:risk:1).",
            ],
            "evidence_ids": [
                "metric:c_linh_01:female_ratio",
                "v_c_linh_01_1@15.0s",
                "metric:c_linh_01:revenue_trend_slope",
                "v_c_linh_01_2:risk:1",
            ],
        },
        "c_chou_02": {
            "reasons": [
                "Lời thoại video nhắc đến màng lọc chống nắng (v_c_chou_02_1:transcript:1).",
                "Người theo dõi là nữ chiếm 85% (metric:c_chou_02:female_ratio).",
                "GPM video ghi nhận 128.000 ₫ trong 30 ngày (metric:c_chou_02:video_gpm).",
            ],
            "caveats": [
                "Phong cách thiên về chia sẻ khoa học nên cần bổ sung CTA kêu gọi mua sắm rõ nét hơn (v_c_chou_02_3@45.0s).",
            ],
            "evidence_ids": [
                "v_c_chou_02_1:transcript:1",
                "metric:c_chou_02:female_ratio",
                "metric:c_chou_02:video_gpm",
                "v_c_chou_02_3@45.0s",
            ],
        },
        "c_trinh_03": {
            "reasons": [
                "Khung hình tại 15 giây là dữ liệu giả lập, chưa có ảnh video thật (v_c_trinh_03_1@15.0s).",
                "Có 245.000 người theo dõi. Chưa có dữ liệu về phạm vi địa lý.",
                "Khung hình mở đầu được tạo cho bộ dữ liệu giả lập (v_c_trinh_03_2@0.5s).",
            ],
            "caveats": [
                "Phí booking ước tính 7.000.000 ₫, cao nhất trong nhóm (booking:c_trinh_03).",
            ],
            "evidence_ids": [
                "v_c_trinh_03_1@15.0s",
                "booking:c_trinh_03",
                "v_c_trinh_03_2@0.5s",
            ],
        },
        "c_mai_04": {
            "reasons": [
                "Lời thoại nhắc đến cơ chế màng lipid da (v_c_mai_04_1:transcript:1).",
                "Nhóm 25 đến 34 tuổi chiếm 52%. Dữ liệu không đo sức mua (metric:c_mai_04:age_25_34_share).",
                "Phí booking ước tính 5.000.000 ₫ (booking:c_mai_04).",
            ],
            "caveats": [
                "Video không chèn hiệu ứng âm thanh sôi động, nhịp điệu bài giảng đều đặn (v_c_mai_04_2@20.0s).",
            ],
            "evidence_ids": [
                "v_c_mai_04_1:transcript:1",
                "metric:c_mai_04:age_25_34_share",
                "booking:c_mai_04",
                "v_c_mai_04_2@20.0s",
            ],
        },
        "c_an_05": {
            "reasons": [
                "Nhóm 18 đến 24 tuổi chiếm 62% (metric:c_an_05:age_18_24_share).",
                "Khung hình tại 15 giây là dữ liệu giả lập, chưa có ảnh video thật (v_c_an_05_1@15.0s).",
                "Phí booking ước tính 4.500.000 ₫ (booking:c_an_05).",
            ],
            "caveats": [
                "Chất lượng ánh sáng phòng chưa đạt chuẩn studio, có hiện tượng đổ bóng nhẹ (v_c_an_05_3@45.0s).",
            ],
            "evidence_ids": [
                "metric:c_an_05:age_18_24_share",
                "v_c_an_05_1@15.0s",
                "booking:c_an_05",
                "v_c_an_05_3@45.0s",
            ],
        },
    }

    for run_id in [run_mock_id, run_second_id]:
        for c in creators_seed[:5]:
            rec_info = recommendations_data[c["id"]]
            rec_payload = {
                "creator_id": c["id"],
                "reasons_vi": rec_info["reasons"],
                "cited_evidence_ids": rec_info["evidence_ids"],
                "caveats_vi": rec_info["caveats"],
                "usage": {
                    "provider": "gemini",
                    "model": "gemini-3.8-flash",
                    "prompt_version": "reasons_v1",
                    "input_tokens": 1250,
                    "output_tokens": 340,
                    "latency_ms": 780,
                    "cost_usd": 0.0022,
                    "cache_hit": False,
                },
            }
            conn.execute(
                "INSERT INTO recommendations VALUES (?, ?, ?, ?, ?)",
                (run_id, c["id"], c["rank"], c["cost"], json.dumps(rec_payload, ensure_ascii=False)),
            )

    # 4. VIDEOS & ANALYSES FOR TOP 5 KOCs (3 videos each = 15 videos)
    for c in creators_seed[:5]:
        creator_id = c["id"]
        for idx in range(1, 4):
            video_id = f"v_{creator_id}_{idx}"
            v_title = f"Review kem chống nắng cho da dầu mụn, tập {idx}: Trải nghiệm thực tế 8 tiếng"
            mp4_file = f"data/raw/media/{video_id}.mp4"
            video_data = {
                "video_id": video_id,
                "creator_id": creator_id,
                "title": v_title,
                "views": 45000 * idx,
                "digg_count": 3200 * idx,
                "comment_count": 210 * idx,
                "share_count": 140 * idx,
                "revenue": 18500000 * idx,
                "duration": 58.0,
            }
            conn.execute(
                "INSERT INTO videos VALUES (?, ?, ?, ?, ?)",
                (video_id, creator_id, json.dumps(video_data), mp4_file, "2026-11-15T01:10:00+07:00"),
            )

            # Generate realistic frames in media_path
            frame_0_disk = media_path / f"{video_id}_frame_0.jpg"
            frame_1_disk = media_path / f"{video_id}_frame_1.jpg"

            _generate_frame_image(frame_0_disk)
            _generate_frame_image(frame_1_disk)

            # Evidence records
            ev_frame0 = f"{video_id}@0.5s"
            ev_frame1 = f"{video_id}@15.0s" if idx == 1 else (f"{video_id}@20.0s" if idx == 2 else f"{video_id}@45.0s")
            ev_speech = f"{video_id}:transcript:1"
            ev_risk = f"{video_id}:risk:1"

            evidence_items = [
                {
                    "evidence_id": ev_frame0,
                    "video_id": video_id,
                    "start_s": 0.5,
                    "end_s": 3.0,
                    "kind": "frame",
                    "quote_vi": "Khung hình giả lập. Chưa có ảnh video thật.",
                    "frame_path": str(frame_0_disk),
                },
                {
                    "evidence_id": ev_frame1,
                    "video_id": video_id,
                    "start_s": 15.0 if idx == 1 else (20.0 if idx == 2 else 45.0),
                    "end_s": 22.0,
                    "kind": "frame",
                    "quote_vi": "Khung hình giả lập. Chưa có ảnh video thật.",
                    "frame_path": str(frame_1_disk),
                },
                {
                    "evidence_id": ev_speech,
                    "video_id": video_id,
                    "start_s": 5.0,
                    "end_s": 12.0,
                    "kind": "speech",
                    "quote_vi": "Bảng thành phần không cồn, không hương liệu nhân tạo (theo lời thoại).",
                    "frame_path": None,
                },
                {
                    "evidence_id": ev_risk,
                    "video_id": video_id,
                    "start_s": 30.0,
                    "end_s": 34.0,
                    "kind": "speech",
                    "quote_vi": "Khẳng định có thể chống nước cả ngày dù bơi lội, cần bổ sung điều kiện thoa lại sau 2-3 giờ.",
                    "frame_path": None,
                },
            ]

            rubric_scores = [
                {
                    "criterion": "hook",
                    "score": 5,
                    "rationale_vi": "Mở đầu 3 giây đầu trực diện vào vấn đề bí da và đổ dầu của người xem.",
                    "evidence_ids": [ev_frame0],
                },
                {
                    "criterion": "product_clarity",
                    "score": 4,
                    "rationale_vi": "Hình ảnh bao bì và nhãn phụ chống nắng được quay rõ nét, ánh sáng đều.",
                    "evidence_ids": [ev_frame0],
                },
                {
                    "criterion": "demonstration",
                    "score": 5,
                    "rationale_vi": "Thao tác thoa kem chuẩn 2 đốt ngón tay, kiểm tra vệt trắng chi tiết.",
                    "evidence_ids": [ev_frame1],
                },
                {
                    "criterion": "claim_quality",
                    "score": 4,
                    "rationale_vi": "Giải thích rõ ràng màng lọc vật lý lai hóa học, dẫn nguồn kiểm định khoa học.",
                    "evidence_ids": [ev_speech],
                },
                {
                    "criterion": "cta",
                    "score": 4,
                    "rationale_vi": "Kêu gọi mua tại giỏ hàng TikTok Shop chính hãng có voucher đi kèm.",
                    "evidence_ids": [ev_frame1],
                },
                {
                    "criterion": "brand_fit",
                    "score": 5,
                    "rationale_vi": "Phong cách nói chân thật, hợp nhóm khách hàng trẻ.",
                    "evidence_ids": [ev_speech],
                },
                {
                    "criterion": "production_quality",
                    "score": 4,
                    "rationale_vi": "Âm thanh thu âm lọc ồn tốt, khung hình 1080p sắc nét, phụ đề tiếng Việt đồng bộ.",
                    "evidence_ids": [ev_frame0],
                },
            ]

            rubric_scores[0]["score"] = [4, 5, 3][idx - 1]
            rubric_scores[0]["rationale_vi"] = [
                "Video mở bằng câu hỏi về tình trạng da dầu.",
                "Video mở bằng cảnh chuẩn bị sản phẩm.",
                "Video bắt đầu bằng lời chào, chưa nêu vấn đề.",
            ][idx - 1]
            rubric_scores[2]["score"] = [5, 3, 4][idx - 1]
            rubric_scores[2]["rationale_vi"] = [
                "Có đoạn thoa kem được mô tả trong lời thoại.",
                "Lời thoại nêu sản phẩm nhưng chưa mô tả cách thoa.",
                "Lời thoại nhắc thao tác thoa lại sau khi ra ngoài.",
            ][idx - 1]

            analysis_payload = {
                "video_id": video_id,
                "transcript_vi": [
                    "Da dầu thường gặp tình trạng bóng vùng chữ T. Video giới thiệu kem chống nắng SPF50+ và mô tả cách thoa thử.",
                    "Sản phẩm có màng lọc chống nắng. Người nói nhắc kiểm tra bảng thành phần và hướng dẫn dùng lượng vừa đủ.",
                    "Sau khi ra ngoài, người nói nhắc thoa lại kem chống nắng. Video không nêu thời gian bảo vệ chính xác.",
                ][idx - 1],
                "rubric": rubric_scores,
                "risks_vi": [[
                    "Không có dữ liệu thử nghiệm độc lập cho tuyên bố kiềm dầu.",
                ], [
                    "Thời lượng sử dụng không được nêu trong lời thoại.",
                ], [
                    "Cần tránh hứa hẹn mức bảo vệ cố định nếu chưa có phép đo.",
                ]][idx - 1],
                "evidence": evidence_items,
                "usage": {
                    "provider": "gemini",
                    "model": "gemini-3.8-flash",
                    "prompt_version": "content_v1",
                    "input_tokens": 3200,
                    "output_tokens": 580,
                    "latency_ms": 1450,
                    "cost_usd": 0.0045,
                    "cache_hit": False,
                },
            }

            conn.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?)",
                (video_id, "content_v1", "gemini-3.8-flash", json.dumps(analysis_payload, ensure_ascii=False)),
            )

    # Creators outside the top 5 have no analysed videos; give them one minimal brand_fit analysis so the real gate keeps them eligible.
    from tests.analysis_seed import seed_brand_fit
    for c in creators_seed[5:]:
        seed_brand_fit(conn, c["id"])

    # 5. TASKS (Funnel & Execution status)
    for run_id in [run_mock_id, run_second_id]:
        stages_tasks = [
            ("S0", 50, 50, 0, 0),  # 50 done
            ("S1", 40, 40, 0, 0),  # 40 done
            ("S2", 15, 15, 0, 0),  # 15 done
            ("S3", 15, 15, 0, 0),  # 15 done
            ("S4", 5, 5, 0, 0),    # 5 done
        ]
        for stage, total, done, running, failed in stages_tasks:
            for idx in range(1, total + 1):
                task_id = f"{run_id}:{stage}:koc_{idx:02d}"
                status = "done" if idx <= done else ("running" if idx <= done + running else "pending")
                conn.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (task_id, run_id, stage, f"koc_{idx:02d}", status, 0, None, "2026-11-15T01:12:00+07:00"),
                )

    # 6. API CALLS & LLM CALLS
    for run_id in [run_mock_id, run_second_id]:
        # 12 Kalodata API calls, 14.5 credits, 8 cache hits
        for i in range(1, 13):
            credits_cost = 0.5 if i <= 4 else 1.25
            cache_hit = 1 if i % 2 == 0 else 0
            conn.execute(
                "INSERT INTO api_calls (run_id, endpoint, request_hash, status, credits, latency_ms, cache_hit, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "kalodata.v1/creator_rank" if i <= 3 else "kalodata.v1/creator_detail", f"req_hash_api_{run_id}_{i}", "success", credits_cost, 210, cache_hit, "2026-11-15T01:05:00+07:00"),
            )

        # 18 LLM calls (15 video analyses + 3 reasons), total $0.85, 10 cache hits
        for i in range(1, 19):
            kind = "content" if i <= 15 else "reasons"
            cache_hit = 1 if i % 2 == 0 else 0
            conn.execute(
                "INSERT INTO llm_calls (run_id, kind, request_hash, model, prompt_version, input_tokens, output_tokens, latency_ms, cost_usd, cache_hit, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, kind, f"req_hash_llm_{run_id}_{i}", "gemini-3.8-flash", "content_v1" if kind == "content" else "reasons_v1", 2850, 420, 1120, 0.0042, cache_hit, "2026-11-15T01:10:00+07:00"),
            )

    conn.commit()
    conn.close()
    return str(target)


if __name__ == "__main__":
    db_file = seed_fixture_db("data/fixture.db")
    print(f"Realistic fixture DB seeded successfully at: {db_file}")
