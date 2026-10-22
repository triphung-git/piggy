"""
src/tft_studio/main_sidecar.py
------------------------------
Entrypoint chính cho Tauri v2 Sidecar (tft-backend).
Khởi chạy máy chủ FastAPI & WebSocket trong một tiến trình độc lập:
  - Giữ sys.stdout sạch 100% cho giao thức IPC (in tín hiệu JSON {"event":"server_ready",...}).
  - Chuyển toàn bộ logging và stderr sang tệp xoay vòng logs/studio.log và sys.stderr.
  - Tự động nạp cấu hình người dùng từ AppData.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import uvicorn

# Thiết lập UTF-8 cho luồng chuẩn
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from tft_studio.api.hub import app, set_runtime_port, set_uvicorn_server
from tft_studio.core.config import load_overlay_config
from tft_studio.core.paths import ensure_user_config_initialized, get_appdata_dir


def setup_logging() -> None:
    """Cấu hình logging ghi vào sys.stderr và file xoay vòng trong AppData/logs."""
    appdata = get_appdata_dir()
    logs_dir = appdata / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "studio.log"

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [stderr_handler, file_handler]

    # Đồng bộ uvicorn loggers sang stderr và file
    for uvi_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvi_logger = logging.getLogger(uvi_logger_name)
        uvi_logger.handlers = [stderr_handler, file_handler]
        uvi_logger.propagate = False


def main() -> None:
    setup_logging()
    logger = logging.getLogger("sidecar_entrypoint")
    logger.info("Initializing TFT Post-Match Studio Sidecar...")

    # 1. Khởi tạo cấu hình mặc định nếu người dùng chạy lần đầu
    try:
        env_path, config_path = ensure_user_config_initialized()
        logger.info("Config verified: env=%s, config=%s", env_path, config_path)
    except Exception as exc:
        logger.error("Failed to ensure user config: %s", exc)

    # 2. Xác định cổng lắng nghe (từ arguments, env, hoặc overlay_config.json)
    parser = argparse.ArgumentParser(description="TFT Post-Match Studio Sidecar")
    parser.add_argument("--port", type=int, default=None, help="Port to bind server")
    args, _ = parser.parse_known_args()

    cfg = load_overlay_config()
    port = args.port or int(os.environ.get("TFT_BACKEND_PORT") or cfg.get("server_port", 8080))
    if not 1 <= port <= 65535:
        parser.error("Port must be between 1 and 65535")
    host = "127.0.0.1"

    logger.info("Starting FastAPI Uvicorn server on %s:%d", host, port)

    set_runtime_port(port)

    # 4. Cấu hình và chạy Uvicorn Server
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_config=None,  # Đã cấu hình qua setup_logging()
        access_log=False,
    )
    server = uvicorn.Server(config)
    set_uvicorn_server(server)

    try:
        async def serve():
            task = asyncio.create_task(server.serve())
            while not server.started and not task.done():
                await asyncio.sleep(0.05)
            if server.started:
                print(json.dumps({"event": "server_ready", "port": port, "status": "ok"}), flush=True)
            await task
        asyncio.run(serve())
    except Exception as exc:
        is_port_conflict = isinstance(exc, OSError) and (
            getattr(exc, "errno", None) in (48, 98, 10048)
            or "10048" in str(exc)
            or "address already in use" in str(exc).lower()
        )
        if is_port_conflict:
            msg = (
                f"Cổng {port} đã bị chiếm dụng bởi một ứng dụng khác. "
                "Hãy đóng ứng dụng đang dùng cổng này, hoặc đổi 'server_port' trong overlay_config.json, "
                f"hoặc đặt biến môi trường TFT_BACKEND_PORT. "
                "Sidecar sẽ KHÔNG tự động bind cổng ngẫu nhiên để đảm bảo URL kết nối OBS không bị sai lệch."
            )
            logger.critical(msg)
            sys.stderr.write(f"\n[FATAL] {msg}\n")
        else:
            logger.critical("Sidecar encountered fatal error: %s", exc)
            sys.stderr.write(f"\n[FATAL] Sidecar encountered fatal error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
