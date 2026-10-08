"""
tests/unit/test_export_service.py
---------------------------------
Characterization tests cho export_service: find_browser_executable va export_html_to_png.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.export_service import export_html_to_png, find_browser_executable


def test_find_browser_executable():
    """Kiem tra ham tim trinh duyet co tra ve chuoi hoac None hop le."""
    exe = find_browser_executable()
    if exe is not None:
        assert isinstance(exe, str)
        assert Path(exe).name.lower() in ("chrome.exe", "msedge.exe", "chromium.exe")


def test_export_html_to_png_no_browser():
    """Kiem tra tra ve False khi khong tim thay browser executable."""
    with patch("backend.export_service.find_browser_executable", return_value=None):
        ok = export_html_to_png(Path("dummy.html"), Path("dummy.png"))
        assert ok is False


def test_export_html_to_png_successful_run(tmp_path):
    """Kiem tra chay thanh cong khi subprocess tao ra file png."""
    html_file = tmp_path / "test.html"
    html_file.write_text("<h1>Test</h1>", encoding="utf-8")
    out_png = tmp_path / "out.png"

    def fake_subprocess_run(cmd, **kwargs):
        # Gia lap tao ra file anh > 10000 bytes
        out_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 12000)
        mock_res = MagicMock()
        mock_res.stderr = ""
        mock_res.returncode = 0
        return mock_res

    with (
        patch(
            "backend.export_service.find_browser_executable",
            return_value="C:\\fake\\chrome.exe",
        ),
        patch("backend.export_service.subprocess.run", side_effect=fake_subprocess_run),
    ):
        ok = export_html_to_png(html_file, out_png)
        assert ok is True
        assert out_png.exists()
