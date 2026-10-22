"""Unit tests for sidecar binary architecture and format verification."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from scripts.build_sidecar import verify_binary_arch


def make_pe_binary(path: Path, machine: int) -> Path:
    """Create a minimal mock Windows PE binary with specified machine type."""
    # DOS header: MZ (2 bytes) + 58 dummy bytes + e_lfanew at 0x3C (4 bytes)
    pe_offset = 0x80
    dos_header = bytearray(0x80)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, pe_offset)

    # PE signature (4 bytes) + IMAGE_FILE_HEADER (20 bytes)
    # Machine is uint16 at pe_offset + 4
    pe_sig = b"PE\x00\x00"
    file_header = bytearray(20)
    struct.pack_into("<H", file_header, 0, machine)

    path.write_bytes(dos_header + pe_sig + file_header + b"\x00" * 100)
    return path


def make_elf_binary(path: Path, machine: int, is_64bit: bool = True) -> Path:
    """Create a minimal mock Linux ELF binary with specified machine type."""
    # EI_MAG: \x7fELF (4 bytes)
    # EI_CLASS: 2 for 64-bit, 1 for 32-bit
    # EI_DATA: 1 for little-endian
    # e_machine: uint16 at offset 18
    header = bytearray(64)
    header[0:4] = b"\x7fELF"
    header[4] = 2 if is_64bit else 1
    header[5] = 1  # LSB little-endian
    header[6] = 1  # EV_CURRENT
    struct.pack_into("<H", header, 18, machine)

    path.write_bytes(header + b"\x00" * 100)
    return path


def make_macho_binary(path: Path, cputype: int) -> Path:
    """Create a minimal mock macOS 64-bit Mach-O binary with specified CPU type."""
    # magic: 0xfeedfacf (little-endian: \xcf\xfa\xed\xfe)
    # cputype: int32 at offset 4
    header = bytearray(32)
    struct.pack_into("<I", header, 0, 0xFEEDFACF)
    struct.pack_into("<I", header, 4, cputype)

    path.write_bytes(header + b"\x00" * 100)
    return path


def test_verify_binary_arch_missing_or_empty(tmp_path):
    missing = tmp_path / "nonexistent.exe"
    with pytest.raises(FileNotFoundError):
        verify_binary_arch(missing, "x86_64-pc-windows-msvc")

    empty = tmp_path / "empty.exe"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        verify_binary_arch(empty, "x86_64-pc-windows-msvc")


def test_verify_binary_arch_corrupt_header(tmp_path):
    corrupt = tmp_path / "corrupt.exe"
    corrupt.write_bytes(b"MZnot-a-real-pe-binary")
    with pytest.raises(ValueError, match="PE header"):
        verify_binary_arch(corrupt, "x86_64-pc-windows-msvc")


def test_verify_binary_arch_windows_pe_valid(tmp_path):
    win_x64 = make_pe_binary(tmp_path / "tft-backend-x86_64.exe", 0x8664)
    verify_binary_arch(win_x64, "x86_64-pc-windows-msvc")

    win_arm64 = make_pe_binary(tmp_path / "tft-backend-arm64.exe", 0xAA64)
    verify_binary_arch(win_arm64, "aarch64-pc-windows-msvc")


def test_verify_binary_arch_windows_pe_mismatch(tmp_path):
    win_arm64 = make_pe_binary(tmp_path / "tft-backend.exe", 0xAA64)
    with pytest.raises(ValueError, match="architecture mismatch"):
        verify_binary_arch(win_arm64, "x86_64-pc-windows-msvc")


def test_verify_binary_arch_linux_elf_valid(tmp_path):
    elf_x64 = make_elf_binary(tmp_path / "tft-backend-linux-x64", 0x003E)
    verify_binary_arch(elf_x64, "x86_64-unknown-linux-gnu")

    elf_arm64 = make_elf_binary(tmp_path / "tft-backend-linux-arm64", 0x00B7)
    verify_binary_arch(elf_arm64, "aarch64-unknown-linux-gnu")


def test_verify_binary_arch_linux_elf_mismatch(tmp_path):
    elf_x64 = make_elf_binary(tmp_path / "tft-backend-linux", 0x003E)
    with pytest.raises(ValueError, match="architecture mismatch"):
        verify_binary_arch(elf_x64, "aarch64-unknown-linux-gnu")


def test_verify_binary_arch_macho_valid(tmp_path):
    macho_arm64 = make_macho_binary(tmp_path / "tft-backend-macos-arm64", 0x0100000C)
    verify_binary_arch(macho_arm64, "aarch64-apple-darwin")

    macho_x64 = make_macho_binary(tmp_path / "tft-backend-macos-x64", 0x01000007)
    verify_binary_arch(macho_x64, "x86_64-apple-darwin")


def test_verify_binary_arch_macho_mismatch(tmp_path):
    macho_x64 = make_macho_binary(tmp_path / "tft-backend-macos", 0x01000007)
    with pytest.raises(ValueError, match="architecture mismatch"):
        verify_binary_arch(macho_x64, "aarch64-apple-darwin")


def test_verify_binary_arch_os_format_mismatch(tmp_path):
    # Passing an ELF binary to a Windows target
    elf = make_elf_binary(tmp_path / "test-binary", 0x003E)
    with pytest.raises(ValueError, match="Format mismatch"):
        verify_binary_arch(elf, "x86_64-pc-windows-msvc")
