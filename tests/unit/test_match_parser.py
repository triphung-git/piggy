"""
tests/unit/test_match_parser.py
-------------------------------
Characterization tests cho DataParser va parse_tft_match.
"""

import json
from pathlib import Path

from backend.data_parser import DDragonLoader, parse_tft_match

FIXTURES_DIR = Path("tests/fixtures")


def test_ddragon_loader_loads_successfully():
    """Kiem tra DDragonLoader nap thanh cong tu dien game."""
    loader = DDragonLoader(language="vi_VN")
    assert len(loader.champions) > 0
    assert len(loader.items) > 0
    assert len(loader.augments) > 0
    assert len(loader.traits) > 0


def test_parse_tft_match_fixture_1():
    """Kiem tra parse_tft_match voi fixture 1 da an danh."""
    raw_path = FIXTURES_DIR / "match_1_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_match = json.load(f)

    clean = parse_tft_match(raw_match, target_puuid="fake-puuid-001", language="vi_VN")

    assert clean["match_id"] == "VN2_FAKE_MATCH_001"
    assert clean["set_number"] == 16
    assert len(clean["lobby"]) == 8

    # Nguoi choi muc tieu phai la Top 1
    target = clean["target_player"]
    assert target is not None
    assert target["placement"] == 1
    assert target["player_name"] == "EsportsPlayer_1#VN1"
    assert target["level"] == 9
    assert len(target["units"]) == 8

    # Kiem tra lobby standings co du thu tu 1 den 8
    placements = [p["placement"] for p in clean["lobby"]]
    assert sorted(placements) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_parse_tft_match_fixture_2():
    """Kiem tra parse_tft_match voi fixture 2."""
    raw_path = FIXTURES_DIR / "match_2_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_match = json.load(f)

    clean = parse_tft_match(raw_match, target_puuid="fake-puuid-003", language="vi_VN")

    assert clean["match_id"] == "VN2_FAKE_MATCH_002"
    target = clean["target_player"]
    assert target is not None
    assert target["placement"] == 3
    assert target["player_name"] == "EsportsPlayer_3#VN2"


def test_parse_tft_match_without_target_puuid():
    """Kiem tra fallback khi khong truyen target_puuid (chon nguoi dau tien)."""
    raw_path = FIXTURES_DIR / "match_1_raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_match = json.load(f)

    clean = parse_tft_match(raw_match, target_puuid=None, language="vi_VN")
    assert clean["match_id"] == "VN2_FAKE_MATCH_001"
    target = clean["target_player"]
    assert target is not None
    assert target["placement"] == 1


def test_export_summary_to_csv(tmp_path):
    """Kiem tra export_summary_to_csv xuat file CSV hop le."""
    from backend.data_parser import export_summary_to_csv

    clean_path = FIXTURES_DIR / "match_1_clean.json"
    with open(clean_path, "r", encoding="utf-8") as f:
        match_data = json.load(f)

    out_csv = tmp_path / "summary.csv"
    export_summary_to_csv([match_data], out_csv)

    assert out_csv.exists()
    content = out_csv.read_text(encoding="utf-8-sig")
    assert "Match ID" in content
    assert "VN2_FAKE_MATCH_001" in content
    assert "Thứ Hạng (Top)" in content
