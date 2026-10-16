"""
src/tft_studio/core/paths.py
----------------------------
Thư viện giải quyết đường dẫn thống nhất cho TFT Post-Match Studio.
Hỗ trợ chuyển đổi tự động và liền mạch giữa:
  1. Môi trường phát triển mã nguồn Python thông thường.
  2. Môi trường ứng dụng đã đóng gói thành file thực thi độc lập .exe (PyInstaller).
  3. Môi trường ứng dụng Desktop đa nền tảng (Tauri v2 Sidecar).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _find_project_root() -> Path:
    """Tìm thư mục gốc dự án dựa trên sự hiện diện của pyproject.toml."""
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        if (curr / "pyproject.toml").exists() or (curr / "README.md").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parents[3]


def get_appdata_dir() -> Path:
    """
    Trả về thư mục AppData chuẩn của hệ điều hành dùng để ghi dữ liệu:
    .env, overlay_config.json, output/, logs/, avatars.
    - Ưu tiên đọc biến môi trường TFT_APPDATA_DIR (do Tauri Rust truyền vào).
    - Tự động xác định theo hệ điều hành nếu không có biến môi trường.
    """
    env_dir = os.environ.get("TFT_APPDATA_DIR")
    if env_dir:
        base_dir = Path(env_dir).resolve()
    else:
        app_id = "com.triphung.tftstudio"
        if sys.platform == "win32":
            appdata_base = os.environ.get("APPDATA")
            base_dir = (
                Path(appdata_base) / app_id
                if appdata_base
                else Path.home() / "AppData" / "Roaming" / app_id
            )
        elif sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support" / app_id
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME")
            base_dir = (
                Path(xdg_data) / app_id
                if xdg_data
                else Path.home() / ".local" / "share" / app_id
            )

    # Tự động tạo thư mục gốc và các thư mục con cần thiết
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "output").mkdir(parents=True, exist_ok=True)
    (base_dir / "logs").mkdir(parents=True, exist_ok=True)
    (base_dir / "assets" / "avatars").mkdir(parents=True, exist_ok=True)

    return base_dir


def get_resource_dir() -> Path:
    """
    Trả về thư mục tài nguyên chỉ đọc (templates, assets, TFT_DDragon).
    - Ưu tiên đọc biến môi trường TFT_RESOURCE_DIR (do Tauri Rust truyền vào).
    - Nếu chạy trong PyInstaller độc lập (sys._MEIPASS), trả về sys._MEIPASS.
    - Nếu chạy dev từ mã nguồn, trả về thư mục gốc của repo.
    """
    env_dir = os.environ.get("TFT_RESOURCE_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()

    return _find_project_root()


def ensure_user_config_initialized() -> tuple[Path, Path]:
    """
    Đảm bảo .env và overlay_config.json đã được khởi tạo trong get_appdata_dir().
    Nếu chưa tồn tại, sao chép từ get_resource_dir() mà không ghi đè file cũ.
    Trả về (env_path, config_path).
    """
    appdata = get_appdata_dir()
    resources = get_resource_dir()

    env_path = appdata / ".env"
    config_path = appdata / "overlay_config.json"

    if not env_path.exists():
        candidates = [
            resources / "defaults" / ".env",
            resources / ".env.example",
            resources / ".env",
            _find_project_root() / "defaults" / ".env",
            _find_project_root() / ".env.example",
        ]
        source_found = next((c for c in candidates if c.exists()), None)
        if source_found:
            shutil.copy2(source_found, env_path)
        else:
            env_path.write_text(
                "# TFT Post-Match Studio Config\n"
                "RIOT_API_KEY=\n"
                "RIOT_ID=\n"
                "REGION=VN\n"
                "MATCH_COUNT=5\n"
                "LANGUAGE=vi_VN\n"
                "OUTPUT_DIR=output\n",
                encoding="utf-8",
            )

    if not config_path.exists():
        candidates = [
            resources / "defaults" / "overlay_config.json",
            resources / "overlay_config.json",
            _find_project_root() / "defaults" / "overlay_config.json",
            _find_project_root() / "overlay_config.json",
        ]
        source_found = next((c for c in candidates if c.exists()), None)
        if source_found:
            shutil.copy2(source_found, config_path)
        else:
            default_json = (
                "{\n"
                '  "tournament_title": "TFT POST-MATCH STUDIO",\n'
                '  "stage_title": "LIVE",\n'
                '  "game_title": "TEAMFIGHT TACTICS",\n'
                '  "server_port": 8080,\n'
                '  "background_image": "assets/background.png",\n'
                '  "font_family": "League Spartan",\n'
                '  "player_avatars": {},\n'
                '  "custom_augments": []\n'
                "}\n"
            )
            config_path.write_text(default_json, encoding="utf-8")

    return env_path, config_path


def get_app_dir() -> Path:
    """
    Trả về thư mục ghi dữ liệu của ứng dụng (trỏ về get_appdata_dir()).
    Hàm này được giữ lại để tương thích ngược 100% với các module hiện hữu.
    """
    return get_appdata_dir()


def get_bundle_dir() -> Path:
    """
    Trả về thư mục tài nguyên đóng gói (trỏ về get_resource_dir()).
    Hàm này được giữ lại để tương thích ngược 100% với các module hiện hữu.
    """
    return get_resource_dir()


def resolve_resource(relative_path: str | Path) -> Path:
    """
    Giải quyết đường dẫn tài nguyên:
    1. Ưu tiên kiểm tra xem người dùng có file tùy chỉnh ở thư mục get_appdata_dir() không.
    2. Nếu không có, nạp file từ get_resource_dir().
    3. Thử tìm ở thư mục gốc dự án.
    """
    rel = Path(relative_path)

    # 1. Kiểm tra override trong appdata (ví dụ người dùng thêm avatar vào appdata/assets/avatars/)
    override_path = get_appdata_dir() / rel
    if override_path.exists():
        return override_path

    # 2. Kiểm tra tài nguyên chuẩn trong get_resource_dir()
    resource_path = get_resource_dir() / rel
    if resource_path.exists():
        return resource_path

    # 3. Fallback thư mục gốc dự án
    root_path = _find_project_root() / rel
    if root_path.exists():
        return root_path

    return resource_path
