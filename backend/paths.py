"""
backend/paths.py
----------------
Thư viện giải quyết đường dẫn thống nhất cho TFT Post-Match Studio.
Hỗ trợ chuyển đổi tự động và liền mạch giữa:
  1. Môi trường phát triển mã nguồn Python thông thường.
  2. Môi trường ứng dụng đã đóng gói thành file thực thi độc lập .exe (PyInstaller).
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """
    Trả về thư mục gốc thực thi của ứng dụng.
    - Chế độ .exe: Thư mục chứa file TFT_PostMatch_Studio.exe.
    - Chế độ script: Thư mục gốc của dự án.
    Dùng cho các tài nguyên động người dùng có thể chỉnh sửa:
    .env, overlay_config.json, output/, avatars.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    """
    Trả về thư mục chứa tài nguyên đóng gói bên trong PyInstaller bundle (sys._MEIPASS)
    hoặc thư mục gốc dự án khi chạy dạng script.
    Dùng cho: templates/, Web Overlay/dist/, assets mặc định.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent.parent


def resolve_resource(relative_path: str | Path) -> Path:
    """
    Giải quyết đường dẫn tài nguyên:
    1. Ưu tiên kiểm tra xem người dùng có file tùy chỉnh ở thư mục ngoài app_dir không.
    2. Nếu không có, nạp file mặc định được đóng gói sẵn trong bundle_dir.
    3. Thử tìm ở thư mục cha nếu ứng dụng đang chạy bên trong thư mục dist/ hoặc thư mục cài đặt.
    """
    rel = Path(relative_path)
    external_path = get_app_dir() / rel
    if external_path.exists():
        return external_path

    bundle_path = get_bundle_dir() / rel
    if bundle_path.exists():
        return bundle_path

    parent_path = get_app_dir().parent / rel
    if parent_path.exists():
        return parent_path

    return external_path
