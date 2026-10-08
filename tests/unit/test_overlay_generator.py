"""
tests/unit/test_overlay_generator.py
------------------------------------
Characterization test so sanh ket qua generate_overlay_html voi golden master.
"""

import json
import re
from pathlib import Path

from backend.overlay_generator import generate_overlay_html, load_overlay_config

FIXTURES_DIR = Path("tests/fixtures")
GOLDEN_DIR = Path("tests/golden")


def _normalize_html(text: str) -> str:
    """Chuan hoa whitespace de so sanh on dinh giua cac OS."""
    # Bo qua cac comment timestamp neu co
    text = re.sub(r"<!--\s*timestamp:.*?-->", "", text, flags=re.DOTALL)
    # Xoa khoang trang du thua o dau/cuoi moi dong
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def test_generate_overlay_html_matches_golden(tmp_path):
    """Kiem tra overlay HTML sinh ra phai khop 100% voi golden master."""
    clean_path = FIXTURES_DIR / "match_1_clean.json"
    with open(clean_path, "r", encoding="utf-8") as f:
        match_data = json.load(f)

    cfg = load_overlay_config(Path("overlay_config.json"))
    out_file = tmp_path / "test_overlay.html"

    generate_overlay_html(match_data, cfg, out_file)

    assert out_file.exists()
    generated_content = out_file.read_text(encoding="utf-8")

    golden_file = GOLDEN_DIR / "overlay.html"
    assert golden_file.exists()
    golden_content = golden_file.read_text(encoding="utf-8")

    assert _normalize_html(generated_content) == _normalize_html(golden_content)


def test_generate_overlay_html_contains_critical_sections(tmp_path):
    """Kiem tra cac thanh phan thiet yeu cua broadcast layout co day du."""
    clean_path = FIXTURES_DIR / "match_1_clean.json"
    with open(clean_path, "r", encoding="utf-8") as f:
        match_data = json.load(f)

    cfg = load_overlay_config(Path("overlay_config.json"))
    out_file = tmp_path / "test_overlay.html"

    generate_overlay_html(match_data, cfg, out_file)
    content = out_file.read_text(encoding="utf-8")

    # Kiem tra tieu de va layout
    assert "overlay-scaler" in content
    assert "top-header" in content
    assert "main-content" in content
    assert "standing-row" in content
    assert "unit-card" in content


def test_find_avatar_url_fallback():
    """Kiem tra fallback avatar khi khong co avatar tuy bien."""
    from backend.overlay_generator import find_avatar_url

    cfg = {"player_avatars": {}}
    url = find_avatar_url(
        "Player_X#VN1", "Player_X", "Tooltip_Ghosty_Spooky_Tier1.png", cfg
    )
    assert isinstance(url, str)
    assert url.startswith("../")


def test_load_overlay_config_fallback(tmp_path):
    """Kiem tra load_overlay_config khi file khong ton tai hoac bi loi."""
    non_existent = tmp_path / "missing.json"
    cfg = load_overlay_config(non_existent)
    assert "tournament_title" in cfg
    assert cfg["server_port"] == 8080
