"""
tests/security/test_input_validation.py
---------------------------------------
Kiểm tra bảo mật đầu vào:
- K3: Chống Path Traversal & Injection trong custom augments
- K4: Xác thực Magic Bytes, dung lượng và phần mở rộng của file ảnh Avatar
"""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from desktop.bridge import validate_avatar_file
from tft_studio.api.hub import app, get_current_token
from tft_studio.data.parser import validate_custom_augment


def test_validate_custom_augment_rejects_path_traversal():
    """K3: Không cho phép đường dẫn chứa ../ hoặc \\."""
    traversal_payloads = [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "../secret.png",
        "folder/sub/aug.png",
        "C:\\test.png",
        "/root/test.png",
    ]
    for payload in traversal_payloads:
        assert validate_custom_augment(payload) is False, f"Failed for {payload}"


def test_validate_custom_augment_rejects_script_and_special_chars():
    """K3: Không cho phép ký tự độc hại <script>, null byte, quotes."""
    malicious = [
        "<script>alert(1)</script>",
        "aug.png\x00.exe",
        'aug"name',
        "aug'name",
        "`id`",
        "${PATH}",
    ]
    for payload in malicious:
        assert validate_custom_augment(payload) is False, f"Failed for {payload}"


def test_validate_custom_augment_accepts_valid_identifiers():
    """K3: Chấp nhận None, chuỗi rỗng và tên/ID/filename an toàn."""
    valid_items = [
        None,
        "",
        "   ",
        "TFT13_Augment_StarryNight.png",
        "TFT13_Augment_StarryNight",
        "Starry Night",
        "augment-tier-1.png",
        "aug_123",
    ]
    for item in valid_items:
        assert validate_custom_augment(item) is True, f"Failed for {item}"


def test_api_augments_post_rejects_path_traversal(tmp_path):
    """K3: Endpoint POST /api/augments từ chối payload traversal với status 400."""
    fake_config = tmp_path / "overlay_config.json"
    fake_config.write_text("{}", encoding="utf-8")

    client = TestClient(app)
    token = get_current_token()
    headers = {
        "X-Studio-Token": token,
        "Origin": "http://localhost:8080",
        "Host": "localhost:8080",
    }

    with patch("tft_studio.api.hub.load_overlay_config", return_value={}):
        res = client.post(
            "/api/augments",
            json={"custom_augments": ["../../malicious.png", None, None]},
            headers=headers,
        )
        assert res.status_code == 400
        assert "Invalid augment identifier" in res.json().get("error", "")


def test_validate_avatar_file_rejects_nonexistent_and_invalid_extension(tmp_path):
    """K4: Từ chối file không tồn tại hoặc đuôi file không phải ảnh."""
    missing = tmp_path / "missing.png"
    ok, err = validate_avatar_file(missing)
    assert ok is False

    bad_ext = tmp_path / "script.exe"
    bad_ext.write_bytes(b"MZ\x90\x00" + b"\x00" * 100)
    ok, err = validate_avatar_file(bad_ext)
    assert ok is False
    assert "Định dạng file không được hỗ trợ" in err


def test_validate_avatar_file_rejects_empty_and_oversized(tmp_path):
    """K4: Từ chối file rỗng hoặc vượt quá 10MB."""
    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")
    ok, err = validate_avatar_file(empty_file)
    assert ok is False
    assert "rỗng" in err

    oversized = tmp_path / "huge.png"
    # Giả lập file > 10MB bằng cách mock st_size
    oversized.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    with patch.object(Path, "stat") as mock_stat:
        mock_stat.return_value.st_size = 11 * 1024 * 1024
        ok, err = validate_avatar_file(oversized)
        assert ok is False
        assert "vượt quá giới hạn" in err


def test_validate_avatar_file_rejects_spoofed_content(tmp_path):
    """K4: File đuôi .png nhưng nội dung là script/binary độc hại sẽ bị từ chối."""
    fake_png = tmp_path / "fake.png"
    fake_png.write_text("MZ Windows Executable stub", encoding="utf-8")
    ok, err = validate_avatar_file(fake_png)
    assert ok is False
    assert "magic bytes mismatch" in err


def test_validate_avatar_file_accepts_valid_image_formats(tmp_path):
    """K4: Chấp nhận file PNG, JPEG, WEBP hợp lệ."""
    # 1. Valid PNG
    png_file = tmp_path / "valid.png"
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50)
    ok, _ = validate_avatar_file(png_file)
    assert ok is True

    # 2. Valid JPEG
    jpg_file = tmp_path / "valid.jpg"
    jpg_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50)
    ok, _ = validate_avatar_file(jpg_file)
    assert ok is True

    # 3. Valid WEBP
    webp_file = tmp_path / "valid.webp"
    webp_file.write_bytes(b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 50)
    ok, _ = validate_avatar_file(webp_file)
    assert ok is True
