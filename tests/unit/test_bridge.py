"""tests/unit/test_bridge.py
Unit tests for StudioBridge IPC methods and interface contract.
"""

from unittest.mock import MagicMock, patch

import pytest

from desktop.bridge import StudioBridge


@pytest.fixture
def mock_match_service():
    svc = MagicMock()
    svc.is_polling_active.return_value = False
    svc.cached_matches = []
    svc.active_match = None
    svc.last_seen_match_id = "TEST_MATCH_01"
    return svc


def test_bridge_has_required_interface_methods(mock_match_service):
    """Ensure all required methods exist on StudioBridge to avoid AttributeError."""
    with patch("desktop.bridge.ConfigWatcher"):
        bridge = StudioBridge(match_service=mock_match_service)

    expected_methods = [
        "fetch_live_now",
        "pick_avatar_file",
        "update_riot_id",
        "update_api_key",
        "get_riot_config",
        "get_obs_info",
        "render_overlay",
        "toggle_overlay",
        "show_overlay",
        "hide_overlay",
        "export_png",
        "set_auto_polling",
        "get_app_state",
        "save_app_config",
        "save_overlay_config",
        "save_custom_augments",
        "get_augments_list",
    ]

    for method_name in expected_methods:
        assert hasattr(bridge, method_name), f"StudioBridge missing method: {method_name}"
        assert callable(getattr(bridge, method_name)), f"{method_name} is not callable"


def test_update_riot_id_validation(mock_match_service):
    """Test validation in update_riot_id."""
    with patch("desktop.bridge.ConfigWatcher"):
        bridge = StudioBridge(match_service=mock_match_service)

    # Empty string
    res = bridge.update_riot_id("")
    assert res["success"] is False
    assert "trống" in res["error"]

    # Missing tag
    res = bridge.update_riot_id("PlayerWithoutTag")
    assert res["success"] is False
    assert "#TAG" in res["error"]
