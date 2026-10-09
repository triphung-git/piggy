"""
tests/unit/test_config.py
-------------------------
Characterization tests cho load_overlay_config, save_overlay_config va AppConfig.
"""

from unittest.mock import patch

from tft_studio.core.config import (
    AppConfig,
    load_overlay_config,
    save_overlay_config,
)


def test_load_overlay_config_returns_defaults():
    """Kiem tra load_overlay_config tra ve cac gia tri mac dinh hop le."""
    cfg = load_overlay_config()
    assert isinstance(cfg, dict)
    assert "tournament_title" in cfg
    assert "stage_title" in cfg
    assert "server_port" in cfg
    assert cfg["server_port"] == 8080 or isinstance(cfg["server_port"], int)


def test_save_and_load_overlay_config(tmp_path):
    """Kiem tra save_overlay_config luu va cap nhat dung file."""
    fake_config_file = tmp_path / "overlay_config.json"
    initial_data = {"tournament_title": "TEST TOURNAMENT", "stage_title": "FINALS"}

    with patch("tft_studio.core.config.OVERLAY_CONFIG_PATH", fake_config_file):
        save_overlay_config(initial_data)
        assert fake_config_file.exists()

        loaded = load_overlay_config()
        assert loaded["tournament_title"] == "TEST TOURNAMENT"
        assert loaded["stage_title"] == "FINALS"

        # Cap nhat bo sung
        updated = save_overlay_config({"stage_title": "GRAND FINALS"})
        assert updated["stage_title"] == "GRAND FINALS"
        assert updated["tournament_title"] == "TEST TOURNAMENT"


def test_app_config_load_from_env(monkeypatch, tmp_path):
    """Kiem tra AppConfig.load doc dung bien moi truong."""
    fake_env = tmp_path / ".env.empty"
    with patch("tft_studio.core.config.ENV_PATH", fake_env):
        monkeypatch.setenv("RIOT_API_KEY", "RGAPI-test-api-key-12345678")
        monkeypatch.setenv("RIOT_ID", "TestUser#VN1")
        monkeypatch.setenv("REGION", "VN")
        monkeypatch.setenv("MATCH_COUNT", "7")
        monkeypatch.setenv("LANGUAGE", "en_US")

        cfg = AppConfig.load()
        assert cfg.api_key == "RGAPI-test-api-key-12345678"
        assert cfg.riot_id == "TestUser#VN1"
        assert cfg.game_name == "TestUser"
        assert cfg.tag_line == "VN1"
        assert cfg.region == "VN"
        assert cfg.account_routing == "asia"
        assert cfg.match_routing == "sea"
        assert cfg.match_count == 7
        assert cfg.language == "en_US"


def test_save_env_values(tmp_path):
    """Kiem tra save_env_values tao moi va ghi de cac gia tri .env dung cach."""
    fake_env = tmp_path / ".env.test"
    fake_env.write_text("RIOT_API_KEY=RGAPI-old-key\nREGION=VN\n", encoding="utf-8")

    with patch("tft_studio.core.config.ENV_PATH", fake_env):
        AppConfig.save_env_values(
            {"api_key": "RGAPI-new-key-123456", "riot_id": "NewPlayer#VN2"}
        )

        content = fake_env.read_text(encoding="utf-8")
        assert "RIOT_API_KEY=RGAPI-new-key-123456\n" in content
        assert "RIOT_ID=NewPlayer#VN2\n" in content
        assert "REGION=VN\n" in content


def test_is_configured(tmp_path, monkeypatch):
    """Kiem tra ham is_configured voi cac trang thai co va khong co key."""
    fake_env = tmp_path / ".env.empty"
    with patch("tft_studio.core.config.ENV_PATH", fake_env):
        from tft_studio.core.config import is_configured

        monkeypatch.setenv("RIOT_API_KEY", "")
        monkeypatch.setenv("RIOT_ID", "")
        assert is_configured() is False

        monkeypatch.setenv("RIOT_API_KEY", "RGAPI-abcdef12-3456-7890-abcd-1234567890ab")
        monkeypatch.setenv("RIOT_ID", "ProPlayer#KR1")
        assert is_configured() is True


def test_to_dict_masks_api_key():
    """K1: to_dict khong duoc de lo api_key."""
    cfg = AppConfig(
        api_key="RGAPI-secret-api-key-999",
        riot_id="Player#VN",
        game_name="Player",
        tag_line="VN",
        region="VN",
        platform="vn2",
        account_routing="asia",
        match_routing="sea",
    )
    d = cfg.to_dict()
    assert d["api_key"] == "RGAPI-****"
    assert "secret-api-key-999" not in str(d)


def test_to_dict_internal_exposes_api_key():
    """K1: to_dict_internal phuc vu backend van giu day du api_key."""
    cfg = AppConfig(
        api_key="RGAPI-secret-api-key-999",
        riot_id="Player#VN",
        game_name="Player",
        tag_line="VN",
        region="VN",
        platform="vn2",
        account_routing="asia",
        match_routing="sea",
    )
    d = cfg.to_dict_internal()
    assert d["api_key"] == "RGAPI-secret-api-key-999"
