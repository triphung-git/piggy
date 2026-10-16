"""
scripts/build_sidecar.py
------------------------
Đóng gói Python FastAPI backend thành Tauri v2 Sidecar binary (--onefile)
theo đúng định dạng tên target triple của Rust / Tauri:
  src-tauri/binaries/tft-backend-<target-triple>[.exe]
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent

BINARIES_DIR = ROOT_DIR / "src-tauri" / "binaries"
ICONS_DIR = ROOT_DIR / "src-tauri" / "icons"


def get_rust_target_triple() -> str:
    """Xác định Rust target triple thông qua env, rustc, hoặc platform fallback."""
    env_target = os.environ.get("TAURI_ENV_TARGET_TRIPLE") or os.environ.get("TARGET")
    if env_target:
        return env_target.strip()

    try:
        output = subprocess.check_output(["rustc", "-vV"], text=True)
        for line in output.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        # Fallback khi rustc chưa có sẵn trong PATH hệ thống
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "windows":
            if machine in ("amd64", "x86_64"):
                return "x86_64-pc-windows-msvc"
            elif machine in ("arm64", "aarch64"):
                return "aarch64-pc-windows-msvc"
            return "i686-pc-windows-msvc"
        elif system == "darwin":
            if machine in ("arm64", "aarch64"):
                return "aarch64-apple-darwin"
            return "x86_64-apple-darwin"
        elif system == "linux":
            if machine in ("arm64", "aarch64"):
                return "aarch64-unknown-linux-gnu"
            return "x86_64-unknown-linux-gnu"

    raise RuntimeError("Không thể xác định Rust target triple. Vui lòng đặt biến môi trường TARGET.")


def ensure_icons() -> None:
    """Tạo bộ icon đa nền tảng cho Tauri từ assets/Logo NEC.png."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    logo_path = ROOT_DIR / "assets" / "Logo NEC.png"
    if not logo_path.exists():
        return

    try:
        img = Image.open(logo_path).convert("RGBA")
        img.save(
            ICONS_DIR / "icon.ico",
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        for size, name in [
            (32, "32x32.png"),
            (128, "128x128.png"),
            (256, "128x128@2x.png"),
            (512, "icon.png"),
        ]:
            img.resize((size, size), Image.Resampling.LANCZOS).save(
                ICONS_DIR / name, format="PNG"
            )
        print(f"[OK] Đã tạo các biểu tượng ứng dụng tại: {ICONS_DIR}")
    except Exception as exc:
        print(f"[WARN] Lỗi khi tạo icon: {exc}")


def build_sidecar() -> None:
    """Thực thi PyInstaller để đóng gói sidecar tft-backend."""
    target_triple = get_rust_target_triple()
    ext = ".exe" if platform.system() == "Windows" else ""
    binary_name = f"tft-backend-{target_triple}{ext}"

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    ensure_icons()

    print(f"[*] Bắt đầu đóng gói Sidecar cho target: {target_triple}...")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        f"tft-backend-{target_triple}",
        "--distpath",
        str(BINARIES_DIR),
        "--workpath",
        str(ROOT_DIR / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT_DIR / "build"),
        "--paths",
        str(ROOT_DIR / "src"),
        "--collect-all",
        "uvicorn",
        "--hidden-import",
        "fastapi",
        "--hidden-import",
        "starlette",
        "--hidden-import",
        "websockets",
        "--hidden-import",
        "requests",
        "--hidden-import",
        "dotenv",
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "tft_studio",
        "--exclude-module",
        "webview",
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "pandas",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "scipy",
        "--exclude-module",
        "torch",
        "--exclude-module",
        "PyQt5",
        "--exclude-module",
        "PyQt6",
        str(ROOT_DIR / "src" / "tft_studio" / "main_sidecar.py"),
    ]

    subprocess.run(cmd, check=True, cwd=str(ROOT_DIR))

    output_binary = BINARIES_DIR / binary_name
    if not output_binary.exists():
        raise FileNotFoundError(f"Không tìm thấy binary sidecar sau khi build: {output_binary}")

    if platform.system() != "Windows":
        output_binary.chmod(0o755)

    size_mb = output_binary.stat().st_size / (1024 * 1024)
    print(f"[OK] Đã tạo sidecar thành công: {output_binary} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build_sidecar()
