"""
tests/unit/test_match_service.py
--------------------------------
Characterization tests cho MatchService:
init, set_active_match, resolve_puuid, fetch_recent_matches.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.config import AppConfig
from backend.match_service import MatchService


def _get_dummy_config():
    return AppConfig(
        api_key="RGAPI-dummy-key-12345678",
        riot_id="Faker#KR1",
        game_name="Faker",
        tag_line="KR1",
        region="KR",
        platform="KR",
        account_routing="asia",
        match_routing="asia",
        match_count=2,
        language="vi_VN",
        output_dir="output",
    )


def test_match_service_init_and_set_active_match():
    """Kiem tra khoi tao MatchService va chon tran dau hoat dong."""
    cfg = _get_dummy_config()
    service = MatchService(config=cfg)
    assert service.config == cfg
    assert service.cached_matches == []
    assert service.active_match is None

    # Gia lap tran dau trong cached_matches
    match_1 = {"match_id": "KR_001", "placement": 1}
    match_2 = {"match_id": "KR_002", "placement": 4}
    service.cached_matches = [match_1, match_2]

    selected = service.set_active_match_by_id("KR_002")
    assert selected == match_2
    assert service.active_match == match_2

    # Chon tran khong ton tai
    assert service.set_active_match_by_id("KR_NON_EXISTENT") is None


def test_match_service_resolve_puuid():
    """Kiem tra resolve_puuid goi client va luu active_puuid."""
    cfg = _get_dummy_config()
    service = MatchService(config=cfg)

    with patch("backend.match_service.RiotTFTClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.get_puuid_by_riot_id.return_value = "fake-puuid-kr"
        mock_client_cls.return_value = mock_instance

        puuid = service.resolve_puuid("Faker", "KR1", "KR")
        assert puuid == "fake-puuid-kr"
        assert service.active_puuid == "fake-puuid-kr"


def test_match_service_fetch_recent_matches(tmp_path):
    """Kiem tra fetch_recent_matches tich hop doc danh sach tran va parse."""
    cfg = _get_dummy_config()
    service = MatchService(config=cfg)

    raw_path = Path("tests/fixtures/match_1_raw.json")
    with open(raw_path, encoding="utf-8") as f:
        raw_match = json.load(f)

    with (
        patch("backend.match_service.RiotTFTClient") as mock_client_cls,
        patch("backend.match_service.OUTPUT_DIR", tmp_path),
    ):
        mock_instance = MagicMock()
        mock_instance.get_puuid_by_riot_id.return_value = "fake-puuid-001"
        mock_instance.get_match_ids_by_puuid.return_value = ["VN2_FAKE_MATCH_001"]
        mock_instance.get_match_by_id.return_value = raw_match
        mock_client_cls.return_value = mock_instance

        progress_reports = []

        def on_progress(pct, msg):
            progress_reports.append((pct, msg))

        matches = service.fetch_recent_matches(
            game_name="EsportsPlayer_1",
            tag_line="VN1",
            region="VN",
            count=1,
            progress_callback=on_progress,
        )

        assert len(matches) == 1
        assert matches[0]["match_id"] == "VN2_FAKE_MATCH_001"
        assert service.active_match == matches[0]
        assert service.last_seen_match_id == "VN2_FAKE_MATCH_001"
        assert len(progress_reports) >= 3

        # Kiem tra file cache da duoc ghi
        cache_file = tmp_path / "clean_matches_latest.json"
        assert cache_file.exists()
