"""
desktop/bridge.py
-----------------
Cầu nối IPC 2 chiều giữa Giao diện React (Web Overlay) và Logic Python.
Cung cấp các hàm API được gọi trực tiếp từ `window.pywebview.api`.

Chế độ Standalone: Mỗi người dùng chạy app của riêng họ, không cần Host server.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

try:
    import webview
except ImportError:
    webview = None

from tft_studio.core.config import load_overlay_config, save_overlay_config
from tft_studio.core.paths import get_app_dir, resolve_resource
from tft_studio.service.controller import StudioController

logger = logging.getLogger("bridge")

BASE_DIR = get_app_dir()
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = resolve_resource("assets")
AVATARS_DIR = BASE_DIR / "assets" / "avatars"

# (Transform & Crop parameters removed)


VALID_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_AVATAR_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_avatar_file(path: Path | str) -> tuple[bool, str]:
    """Kiểm tra tính an toàn của file ảnh avatar (K4).
    Kiểm tra tồn tại, kích thước (<10MB), phần mở rộng hợp lệ, và magic bytes thực tế.
    """
    p = Path(path)
    if not p.is_file():
        return False, "File không tồn tại hoặc không phải là file thông thường"

    if p.suffix.lower() not in VALID_AVATAR_EXTENSIONS:
        return False, (
            f"Định dạng file không được hỗ trợ ({p.suffix}). "
            "Chỉ chấp nhận .png, .jpg, .jpeg, .webp"
        )

    try:
        size = p.stat().st_size
        if size == 0:
            return False, "File ảnh rỗng (0 bytes)"
        if size > MAX_AVATAR_SIZE:
            return False, f"Kích thước file vượt quá giới hạn tối đa 10MB ({size} bytes)"

        with open(p, "rb") as f:
            header = f.read(16)

        is_valid_magic = any(
            header.startswith(magic)
            for magic in (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a")
        )
        is_webp = header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"
        if not is_valid_magic and is_webp:
            is_valid_magic = True

        if not is_valid_magic:
            return False, "Nội dung file không đúng định dạng ảnh hợp lệ (magic bytes mismatch)"

        return True, ""
    except Exception as exc:
        return False, f"Lỗi khi kiểm tra file ảnh: {exc}"


class StudioBridge(StudioController):
    """pywebview adapter for the shared application controller."""

    def set_windows(
        self, dashboard: webview.Window, overlay: webview.Window | None = None
    ) -> None:
        self._dashboard_window = dashboard
        self._overlay_window = overlay


    def notify_frontend(self, func_name: str, data: Any) -> None:
        """Đẩy sự kiện từ Python → Frontend Javascript an toàn."""
        super().notify_frontend(func_name, data)
        js_data = json.dumps(data, ensure_ascii=False)
        script = f"if (window.{func_name}) {{ window.{func_name}({js_data}); }}"

        for win in (self._dashboard_window, self._overlay_window):
            if win:
                if win == self._overlay_window and not self._is_overlay_visible:
                    continue
                try:
                    win.evaluate_js(script)
                except Exception as e:
                    logger.debug("evaluate_js error on window: %s", e)


    def toggle_overlay_visibility(self, visible: bool) -> bool:
        """Bật/tắt hiển thị Cửa sổ Overlay."""
        if self._overlay_window:
            if visible:
                self._overlay_window.show()
                self._is_overlay_visible = True
            else:
                self._overlay_window.hide()
                self._is_overlay_visible = False
            return self._is_overlay_visible
        return False


    def close_panel(self) -> None:
        """Đóng ứng dụng."""
        logger.info("Closing studio")
        if self._dashboard_window:
            self._dashboard_window.destroy()


    def toggle_overlay(self) -> bool:
        """Bật/tắt ẩn hiện cửa sổ Overlay."""
        if not self._overlay_window:
            return False

        if self._is_overlay_visible:
            self._overlay_window.hide()
            self._is_overlay_visible = False
        else:
            self._overlay_window.show()
            self._is_overlay_visible = True

        self.notify_frontend(
            "onAppStateUpdate", {"is_overlay_visible": self._is_overlay_visible}
        )
        return self._is_overlay_visible


    def show_overlay(self) -> None:
        if self._overlay_window:
            self._overlay_window.show()
            self._is_overlay_visible = True
            self.notify_frontend("onAppStateUpdate", {"is_overlay_visible": True})


    def hide_overlay(self) -> None:
        if self._overlay_window:
            self._overlay_window.hide()
            self._is_overlay_visible = False
            self.notify_frontend("onAppStateUpdate", {"is_overlay_visible": False})


    def pick_avatar_file(self, player_name: str) -> dict[str, Any]:
        """Mở hộp thoại chọn ảnh avatar cho tuyển thủ."""
        if not self._dashboard_window:
            return {"success": False, "error": "Cửa sổ chưa khởi tạo"}

        file_types = ("Image Files (*.png;*.jpg;*.jpeg;*.webp)", "All files (*.*)")
        dialog_flag = getattr(webview, "OPEN_DIALOG", 10) if webview else 10
        result = self._dashboard_window.create_file_dialog(
            dialog_flag, allow_multiple=False, file_types=file_types
        )

        if result and len(result) > 0:
            chosen_path = Path(result[0])
            is_valid, err_msg = validate_avatar_file(chosen_path)
            if not is_valid:
                logger.warning("Avatar validation failed for %s: %s", chosen_path, err_msg)
                return {"success": False, "error": err_msg}

            clean_name = "".join(
                c if c.isalnum() else "_" for c in player_name
            ).lower()
            dest_file = AVATARS_DIR / f"{clean_name}{chosen_path.suffix.lower()}"
            shutil.copy2(chosen_path, dest_file)

            rel_path = f"assets/avatars/{dest_file.name}"
            cfg = load_overlay_config()
            if "player_avatars" not in cfg:
                cfg["player_avatars"] = {}
            cfg["player_avatars"][player_name] = rel_path
            save_overlay_config(cfg)

            self.notify_frontend("onAppStateUpdate", {"overlay_config": cfg})
            return {"success": True, "path": rel_path}

        return {"success": False, "canceled": True}


    def get_backend_connection_info(self) -> dict[str, Any]:
        from tft_studio.api.hub import get_runtime_port
        return {"base_url": f"http://127.0.0.1:{get_runtime_port()}", "token": self.get_studio_token(), "ready": True}

    def _refresh_preview(self, config: dict) -> None:
        if self._overlay_window and self._is_overlay_visible:
            self._overlay_window.evaluate_js("if (window.smoothUpdate) window.smoothUpdate();")
