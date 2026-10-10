"""
desktop/app.py
--------------
Entrypoint khởi động TFT Post-Match Studio — Standalone Edition.
Mỗi người dùng chạy app của riêng họ, không cần kết nối máy Host.

Quản lý 2 cửa sổ:
    1. Control Panel: Bảng điều khiển Transform, Render & Cấu hình.
    2. Overlay Window: Hiển thị overlay trực tiếp, kết nối với OBS.
"""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
import sys
from pathlib import Path

# UTF-8 và DPI Awareness trên Windows
if sys.platform == "win32":
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    with contextlib.suppress(Exception):
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    with contextlib.suppress(Exception):
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()

# Thêm thư mục gốc vào PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
src_dir = BASE_DIR / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import webview

from desktop.bridge import StudioBridge
from tft_studio.api.hub import start_server
from tft_studio.core.paths import get_app_dir, resolve_resource
from tft_studio.render.generator import (
    generate_overlay_html,
)
from tft_studio.render.generator import (
    load_overlay_config as load_generator_config,
)
from tft_studio.service.match_service import MatchService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("desktop_app")

BASE_DIR = get_app_dir()
OUTPUT_DIR = BASE_DIR / "output"
WEB_OVERLAY_DIST = resolve_resource("Web Overlay/dist/index.html")
SERVER_PORT = 8080


def ensure_prerequisites() -> None:
    """Đảm bảo các file HTML và dữ liệu sẵn sàng trước khi mở cửa sổ."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build UI bundle nếu chưa có (chỉ khi chạy từ mã nguồn)
    if not WEB_OVERLAY_DIST.exists() and not getattr(sys, "frozen", False):
        logger.info("Building UI bundle: Web Overlay")
        web_overlay_dir = resolve_resource("Web Overlay")
        try:
            subprocess.run(["npm.cmd", "run", "build"], cwd=web_overlay_dir, check=True)
            logger.info("UI bundle built successfully")
        except Exception as e:
            logger.error("Failed to build UI bundle: %s", e)

    # Biên dịch overlay.html từ cache mới nhất khi khởi động
    overlay_html = OUTPUT_DIR / "overlay.html"
    cache_files = sorted(
        OUTPUT_DIR.glob("clean_matches_*.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    if not cache_files:
        # Kiểm tra trong bundle
        bundled = resolve_resource("output/clean_matches_latest.json")
        if bundled.exists():
            cache_files = [bundled]

    for cand in cache_files:
        if cand.exists():
            try:
                with open(cand, encoding="utf-8") as f:
                    data = json.load(f)
                    if data:
                        cfg = load_generator_config(BASE_DIR / "overlay_config.json")
                        generate_overlay_html(data[0], cfg, overlay_html)
                        logger.info("Overlay compiled from: %s", cand.name)
                        break
            except Exception as e:
                logger.warning("Failed to compile overlay from %s: %s", cand.name, e)


def main() -> None:
    print("══════════════════════════════════════════", flush=True)
    print("   ⚔️  TFT POST-MATCH STUDIO  ⚔️", flush=True)
    print("   Standalone Edition — Open Source", flush=True)
    print("══════════════════════════════════════════", flush=True)

    ensure_prerequisites()

    # Đọc cấu hình
    cfg = load_generator_config(BASE_DIR / "overlay_config.json")
    server_port = int(cfg.get("server_port", SERVER_PORT))

    # Khởi động Local HTTP Server (127.0.0.1 only)
    start_server(port=server_port)

    print(f"[✓] Local Server:      http://127.0.0.1:{server_port}", flush=True)
    print(f"[✓] OBS Browser Source: http://localhost:{server_port}/overlay", flush=True)
    print(f"[✓] Control Panel:     http://localhost:{server_port}/app", flush=True)
    print("══════════════════════════════════════════\n", flush=True)

    # Khởi động services
    from tft_studio.core.config import AppConfig

    match_service = MatchService()
    bridge = StudioBridge(match_service=match_service)

    # Tự động tải trận mới nhất từ thông tin trong .env
    app_cfg = AppConfig.load()
    if app_cfg.api_key and app_cfg.game_name:
        logger.info(
            "Auto-fetching latest match for %s#%s from .env...",
            app_cfg.game_name,
            app_cfg.tag_line,
        )
        bridge.fetch_live_now()

    # URL cho hai cửa sổ
    overlay_url = f"http://127.0.0.1:{server_port}/overlay"

    # Control Panel: load từ file build hoặc local server
    if WEB_OVERLAY_DIST.exists():
        controller_url = WEB_OVERLAY_DIST.resolve().as_uri()
    else:
        controller_url = f"http://127.0.0.1:{server_port}/app"

    # Cửa sổ 1: Control Panel (480x580)
    controller_win = webview.create_window(
        title="TFT Post-Match Studio — Control Panel",
        url=controller_url,
        width=480,
        height=580,
        min_size=(440, 480),
        resizable=True,
        js_api=bridge,
        background_color="#09090b",
    )

    # Cửa sổ 2: Overlay Preview (16:9)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        overlay_w = max(1280, min(1920, int(screen_w * 0.85)))
        overlay_h = int(overlay_w * 9 / 16)
    except Exception:
        overlay_w, overlay_h = 1600, 900

    overlay_win = webview.create_window(
        title="TFT Post-Match Studio — Overlay Preview",
        url=overlay_url,
        width=overlay_w,
        height=overlay_h,
        resizable=True,
        hidden=True,  # Ẩn mặc định, hiện khi user nhấn Show Overlay
        background_color="#000000",
    )

    # Liên kết windows với bridge
    bridge.set_windows(dashboard=controller_win, overlay=overlay_win)

    # Dọn dẹp khi đóng app
    def on_closed():
        logger.info("Shutting down TFT Studio")
        with contextlib.suppress(Exception):
            overlay_win.destroy()

    controller_win.events.closed += on_closed

    # Khởi động PyWebView với WebView2
    try:
        webview.start(
            debug=False,
            gui="edgechromium",
            http_server=False,
        )
    except Exception as e:
        logger.warning("WebView2 not available, falling back: %s", e)
        webview.start(debug=False, http_server=False)


if __name__ == "__main__":
    main()
