"""Entry point for running the KOC Discovery Web UI server.

Run via: python -m koc.web [--db PATH] [--port 8765] [--host 127.0.0.1]
"""
import argparse
import sys
import uvicorn

from koc.web.app import create_app


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def host_warning(host: str) -> str | None:
    """Vietnamese warning when the server is bound beyond loopback (the web UI has no authentication)."""
    if host in LOCAL_HOSTS:
        return None
    return (f"CẢNH BÁO BẢO MẬT: đang mở máy chủ tại {host}. Giao diện này KHÔNG có đăng nhập; "
            "bất kỳ ai trong mạng đều xem được dữ liệu KOC, ngân sách và báo cáo. "
            "Chỉ dùng 127.0.0.1 hoặc đặt sau VPN/tường lửa.")


def main():
    parser = argparse.ArgumentParser(description="KOC Discovery Web UI Server (Vietnamese)")
    parser.add_argument("--db", default="data/koc.db", help="Path to SQLite database file")
    parser.add_argument("--media-dir", default="data/media", help="Path to video frames directory")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable autoreload for development")
    args = parser.parse_args()

    warning = host_warning(args.host)
    if warning:
        print(warning, file=sys.stderr)

    app = create_app(db_path=args.db, media_dir=args.media_dir, serve_spa=True)
    print(f"Khởi động KOC Discovery Web UI tại http://{args.host}:{args.port}")
    print(f"Cơ sở dữ liệu: {args.db} • Thư mục media: {args.media_dir}")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
