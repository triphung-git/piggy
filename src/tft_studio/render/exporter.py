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

from PIL import Image

from tft_studio.core.paths import get_appdata_dir, resolve_resource
from tft_studio.core.processes import ProcessTree
from tft_studio.core.storage import EXPORT_LOCK, RENDER_LOCK, atomic_write
from tft_studio.core.tempfiles import temporary_directory
from tft_studio.render import EXPORT_TIMEOUT

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
    try:
        with EXPORT_LOCK, temporary_directory(prefix="tft-export-", dir=output_png.parent) as folder:
            working = Path(folder)
            snapshot = working / "overlay.html"
            screenshot = working / "capture.png"
            # Freeze HTML/CSS together. Resolve each resource individually so user
            # overrides do not hide bundled fonts, stars or backgrounds.
            with RENDER_LOCK:
                content = html_file.read_text(encoding="utf-8")
                css_path = html_file.parent / "overlay.css"
                css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
            import re
            def local_url(match):
                return resolve_resource(match.group(1)).as_uri()
            content = re.sub(r"\.\./((?:assets|TFT_DDragon)/[^\"'<>]+)", local_url, content)
            css = re.sub(r"\.\./((?:assets|TFT_DDragon)/[^\"')]+)", local_url, css)
            content = content.replace('<link rel="stylesheet" href="overlay.css">', f"<style>{css}</style>")
            snapshot.write_text(content, encoding="utf-8")
            cmd = [
                browser_exe, "--headless", f"--screenshot={screenshot}",
                f"--window-size={width},{height}", "--hide-scrollbars", "--disable-gpu",
                "--allow-file-access-from-files", "--virtual-time-budget=3000",
                f"--user-data-dir={working / 'profile'}", snapshot.as_uri(),
            ]
            with ProcessTree(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as browser:
                logger.info("Export browser started: pid=%s profile=%s", browser.pid, working / "profile")
                browser.communicate(timeout=EXPORT_TIMEOUT)
            # The process tree is closed before inspecting or removing its files.
            if browser.returncode != 0 or not screenshot.exists():
                logger.error("Browser export did not produce an image")
                return False
            with Image.open(screenshot) as img:
                if img.format != "PNG" or img.size != (width, height):
                    return False
                img.verify()
            with Image.open(screenshot) as img:
                img.load()
            atomic_write(output_png, screenshot.read_bytes())
            return True
    except Exception:
        logger.exception("PNG export failed")
        return False
