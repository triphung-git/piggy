"""
src/tft_studio/render/exporter.py
---------------------------------
Dịch vụ xuất ảnh Overlay chuẩn 1920x1080 bằng Headless Chromium.
Phát hiện tự động trình duyệt có sẵn trên Windows, macOS và Linux.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tft_studio.core.paths import get_appdata_dir

logger = logging.getLogger("export_service")

BASE_DIR = get_appdata_dir()
OUTPUT_DIR = BASE_DIR / "output"


def find_browser_executable() -> str | None:
    """Tìm đường dẫn trình duyệt Chromium có sẵn trên Windows, macOS hoặc Linux."""
    # 1. Tìm qua PATH hệ thống
    if sys.platform == "win32":
        candidate_names = ["chrome.exe", "msedge.exe", "chromium.exe"]
    elif sys.platform == "darwin":
        candidate_names = [
            "google-chrome",
            "chromium",
            "microsoft-edge",
        ]
    else:  # Linux
        candidate_names = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
            "microsoft-edge-stable",
        ]

    for name in candidate_names:
        found = shutil.which(name)
        if found:
            return found

    # 2. Tìm theo danh sách đường dẫn mặc định của từng hệ điều hành
    if sys.platform == "win32":
        default_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for p in default_paths:
            if os.path.isfile(p):
                return p
    elif sys.platform == "darwin":
        mac_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for p in mac_paths:
            if os.path.isfile(p):
                return p
    else:  # Linux
        linux_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            "/usr/bin/microsoft-edge",
        ]
        for p in linux_paths:
            if os.path.isfile(p):
                return p

    return None


def export_html_to_png(
    html_file: Path,
    output_png: Path,
    width: int = 1920,
    height: int = 1080,
) -> bool:
    """Sử dụng Headless Chromium kết xuất ảnh chuẩn xác."""
    browser_exe = find_browser_executable()
    if not browser_exe:
        logger.error("Không tìm thấy Chrome hoặc Edge trên hệ thống.")
        return False

    output_png.parent.mkdir(parents=True, exist_ok=True)
    html_uri = html_file.resolve().as_uri()

    cmd = [
        browser_exe,
        "--headless",
        f"--screenshot={output_png.resolve()}",
        f"--window-size={width},{height}",
        "--hide-scrollbars",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        html_uri,
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if output_png.exists() and output_png.stat().st_size > 10000:
            logger.info("PNG exported: %s (%d bytes)", output_png.name, output_png.stat().st_size)
            return True
        logger.error("Render failed: %s", res.stderr)
        return False
    except Exception as exc:
        logger.error("Render error: %s", exc)
        return False
