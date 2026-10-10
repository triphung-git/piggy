"""
tests/unit/test_overlay_generator.py
------------------------------------
Characterization test so sanh ket qua generate_overlay_html voi golden master.
"""

import json
import re
from pathlib import Path

from tft_studio.render.generator import generate_overlay_html, load_overlay_config

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
    with open(clean_path, encoding="utf-8") as f:
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
    with open(clean_path, encoding="utf-8") as f:
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
    from tft_studio.render.generator import find_avatar_url

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


def test_xss_payload_is_escaped_in_overlay(tmp_path):
    """K2: payload doc hai trong ten nguoi choi hoac giai dau phai bi escape."""
    clean_path = FIXTURES_DIR / "match_1_clean.json"
    with open(clean_path, encoding="utf-8") as f:
        match_data = json.load(f)

    # Them payload XSS vao ten nguoi choi top 1 va nguoi choi top 2
    match_data["lobby"][0]["game_name"] = '<script>alert("top1_xss")</script>'
    match_data["lobby"][1]["game_name"] = '<img src=x onerror="alert(2)">'

    cfg = {
        "tournament_title": "<marquee>HACKED TOURNAMENT</marquee>",
        "stage_title": '"><script>alert(3)</script>',
        "server_port": 8080,
    }
    out_file = tmp_path / "xss_test_overlay.html"
    generate_overlay_html(match_data, cfg, out_file)

    content = out_file.read_text(encoding="utf-8")
    assert '<script>alert("top1_xss")</script>' not in content
    assert '<img src=x onerror=' not in content
    assert '<marquee>' not in content
    assert '&lt;script&gt;alert(' in content
    assert '&lt;img src=x onerror=' in content
    assert '&lt;marquee&gt;' in content


def test_build_augments_html_destiny_expansion():
    """Kiểm tra build_augments_html hỗ trợ 4 lõi khi người chơi chọn Destiny Augment + Bonus."""
    from tft_studio.render.generator import build_augments_html

    cfg = {
        "custom_augments": [
            "GoldenDestiny_II.png",
            "ThreeThrees_II.png",
            "AnimaCommander_II.png",
            "QuestForTheSeven_II.png",
        ]
    }
    html_out = build_augments_html([], cfg)
    assert html_out.count("augment-slot") == 4
    assert "GoldenDestiny_II.png" in html_out
    assert "ThreeThrees_II.png" in html_out


def test_build_augments_html_destiny_six_slots():
    """Kiểm tra build_augments_html hỗ trợ tối đa 6 lõi khi có nhiều lõi Destiny."""
    from tft_studio.render.generator import build_augments_html

    cfg = {
        "custom_augments": [
            "SilverDestiny_I.png",
            "ThreeThrees_II.png",
            "GoldenDestiny_II.png",
            "AnimaCommander_II.png",
            "PrismaticDestiny_III.png",
            "QuestForTheSeven_II.png",
        ]
    }
    html_out = build_augments_html([], cfg)
    assert html_out.count("augment-slot") == 6
    assert "SilverDestiny_I.png" in html_out
    assert "PrismaticDestiny_III.png" in html_out
