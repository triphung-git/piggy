"""
desktop/local_server.py
-----------------------
Máy chủ HTTP cục bộ phục vụ cả Desktop App (Dashboard + Overlay) và OBS Studio Browser Source.
Tự động ánh xạ:
    /              -> frontend/dist/index.html (Dashboard)
    /overlay       -> frontend/dist/index.html#/overlay (OBS Source)
    /assets/*      -> thư mục assets/
    /TFT_DDragon/* -> thư mục TFT_DDragon/
    /output/*      -> thư mục output/
"""

from __future__ import annotations

import http.server
import logging
import socketserver
import threading
from pathlib import Path

logger = logging.getLogger("local_server")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
FRONTEND_DEV = BASE_DIR / "frontend"


class StudioHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handler đa năng phục vụ file tĩnh và SPA routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_GET(self) -> None:
        raw_path = self.path.split("?")[0].split("#")[0].rstrip("/")

        # 1. Route cho OBS hoặc trang chủ
        if raw_path in ("", "/overlay", "/dashboard"):
            target_html = FRONTEND_DIST / "index.html"
            if not target_html.exists():
                target_html = FRONTEND_DEV / "index.html"

            if target_html.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(target_html, "rb") as f:
                    self.wfile.write(f.read())
                return

        # 2. File trong thư mục frontend/dist (JS/CSS bundles)
        if FRONTEND_DIST.exists():
            dist_candidate = FRONTEND_DIST / raw_path.lstrip("/")
            if dist_candidate.exists() and dist_candidate.is_file():
                self.path = f"/frontend/dist/{raw_path.lstrip('/')}"
                super().do_GET()
                return

        # 3. File tĩnh tài nguyên (assets, DDragon, output)
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        pass  # Tắt log console thừa


class LocalServerManager:
    """Quản lý vòng đời máy chủ HTTP."""

    def __init__(self, port: int = 8080) -> None:
        self.port = port
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None
        self._is_running = False

    def start(self, port: int | None = None) -> bool:
        if self._is_running:
            return True

        if port:
            self.port = port

        class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        try:
            self._server = ThreadedServer(("", self.port), StudioHTTPRequestHandler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self._is_running = True
            logger.info("Local HTTP server listening at http://localhost:%d/", self.port)
            return True
        except OSError as e:
            # Thử cổng kế tiếp nếu cổng 8080 bị chiếm
            if "Address already in use" in str(e) or "10048" in str(e):
                logger.warning("Port %d in use, binding to %d", self.port, self.port + 1)
                self.port += 1
                return self.start(self.port)
            logger.error("Server start failed: %s", e)
            return False

    def stop(self) -> bool:
        if not self._is_running or not self._server:
            return False
        try:
            self._server.shutdown()
            self._server.server_close()
            self._is_running = False
            return True
        except Exception as e:
            logger.error("Server stop failed: %s", e)
            return False

    def is_running(self) -> bool:
        return self._is_running
