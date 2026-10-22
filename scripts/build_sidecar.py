"""
scripts/build_sidecar.py
------------------------
Đóng gói Python FastAPI backend thành Tauri v2 Sidecar binary (--onefile)
theo đúng định dạng tên target triple của Rust / Tauri:
  src-tauri/binaries/tft-backend-<target-triple>[.exe]
"""

import os
import platform
import struct
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


def verify_binary_arch(binary_path: Path, target_triple: str) -> None:
    """Xác minh định dạng nhị phân (PE/ELF/Mach-O) và kiến trúc CPU khớp với target triple."""
    binary_path = Path(binary_path)
    if not binary_path.is_file():
        raise FileNotFoundError(f"Binary file not found: {binary_path}")
    if binary_path.stat().st_size == 0:
        raise ValueError(f"Binary file is empty: {binary_path}")

    parts = target_triple.split("-")
    expected_arch = parts[0]  # x86_64 or aarch64
    if "windows" in target_triple:
        expected_os = "windows"
    elif "linux" in target_triple:
        expected_os = "linux"
    elif "darwin" in target_triple or "apple" in target_triple:
        expected_os = "darwin"
    else:
        raise ValueError(f"Unsupported target triple: {target_triple}")

    with binary_path.open("rb") as f:
        data = f.read(512)

    if len(data) < 4:
        raise ValueError(f"Binary header too short: {binary_path}")

    # Check Windows PE
    if data[:2] == b"MZ":
        if expected_os != "windows":
            raise ValueError(f"Format mismatch: binary is Windows PE, expected {expected_os} for {target_triple}")
        if len(data) < 0x40:
            raise ValueError("Corrupt PE header: file smaller than DOS header")
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        with binary_path.open("rb") as f:
            f.seek(pe_offset)
            pe_header = f.read(24)
        if len(pe_header) < 24 or pe_header[:4] != b"PE\x00\x00":
            raise ValueError("Invalid PE header: missing PE signature")
        machine = struct.unpack_from("<H", pe_header, 4)[0]
        pe_arch_map = {
            0x8664: "x86_64",
            0xAA64: "aarch64",
            0x014C: "i386",
        }
        actual_arch = pe_arch_map.get(machine, f"unknown_0x{machine:04x}")
        if actual_arch != expected_arch:
            raise ValueError(f"Binary architecture mismatch for {target_triple}: expected {expected_arch}, found {actual_arch}")
        return

    # Check Linux ELF
    if data[:4] == b"\x7fELF":
        if expected_os != "linux":
            raise ValueError(f"Format mismatch: binary is Linux ELF, expected {expected_os} for {target_triple}")
        if len(data) < 20:
            raise ValueError("Corrupt ELF header: file smaller than 20 bytes")
        endian = "<" if data[5] == 1 else ">"
        machine = struct.unpack_from(f"{endian}H", data, 18)[0]
        elf_arch_map = {
            0x003E: "x86_64",
            0x00B7: "aarch64",
            0x0003: "i386",
        }
        actual_arch = elf_arch_map.get(machine, f"unknown_0x{machine:04x}")
        if actual_arch != expected_arch:
            raise ValueError(f"Binary architecture mismatch for {target_triple}: expected {expected_arch}, found {actual_arch}")
        return

    # Check macOS Mach-O
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic in (0xFEEDFACF, 0xFEEDFACE, 0xCFFAEDFE, 0xCEFAEDFE):
        if expected_os != "darwin":
            raise ValueError(f"Format mismatch: binary is macOS Mach-O, expected {expected_os} for {target_triple}")
        endian = "<" if magic in (0xFEEDFACF, 0xFEEDFACE) else ">"
        cputype = struct.unpack_from(f"{endian}I", data, 4)[0]
        macho_arch_map = {
            0x01000007: "x86_64",
            0x0100000C: "aarch64",
            0x00000007: "i386",
        }
        actual_arch = macho_arch_map.get(cputype, f"unknown_0x{cputype:08x}")
        if actual_arch != expected_arch:
            raise ValueError(f"Binary architecture mismatch for {target_triple}: expected {expected_arch}, found {actual_arch}")
        return

    raise ValueError(f"Format mismatch: unrecognized binary format for {binary_path.name}")



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

    verify_binary_arch(output_binary, target_triple)

    size_mb = output_binary.stat().st_size / (1024 * 1024)
    print(f"[OK] Đã tạo sidecar thành công và xác minh cấu trúc CPU: {output_binary} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build_sidecar()
