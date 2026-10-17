"""Regression tests for the runtime failures found in Plan.md."""

import base64
import io
import json
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.websockets import WebSocketDisconnect

from tft_studio.api import hub
from tft_studio.core import config
from tft_studio.service import controller, match_service


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("TFT_APPDATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIOT_API_KEY", "")
    monkeypatch.setenv("RIOT_ID", "")
    monkeypatch.setenv("STUDIO_SESSION_TOKEN", "qa-session")
    (tmp_path / ".env").write_text("RIOT_API_KEY=\nRIOT_ID=\nREGION=VN\n", encoding="utf-8")
    (tmp_path / "overlay_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(config, "OVERLAY_CONFIG_PATH", tmp_path / "overlay_config.json")
    monkeypatch.setattr(controller, "BASE_DIR", tmp_path)
    monkeypatch.setattr(controller, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(controller, "AVATARS_DIR", tmp_path / "assets" / "avatars")
    monkeypatch.setattr(controller, "export_html_to_png", lambda *a, **kw: False)
    monkeypatch.setattr(match_service, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(hub, "_bridge_ref", None)
    yield tmp_path


@pytest.fixture
def client(isolated):
    with TestClient(hub.app, base_url="http://localhost", headers={"X-Studio-Token": "qa-session"}) as test_client:
        yield test_client


def test_lifespan_initializes_real_service_and_renders_fixture(client, isolated):
    assert client.get("/api/status").json()["ready"] is True
    assert "config" in client.get("/api/state").json()
    match = json.loads(Path("tests/fixtures/match_1_clean.json").read_text(encoding="utf-8"))
    hub._bridge_ref._match_service.active_match = match
    response = client.post("/api/render")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert (isolated / "output" / "overlay.html").exists()
    assert client.get("/api/overlay-html").json()["ready"] is True


def test_uninitialized_render_returns_service_unavailable(isolated):
    client = TestClient(hub.app, base_url="http://localhost", headers={"X-Studio-Token": "qa-session"})
    assert client.post("/api/render").status_code == 503


def test_failed_render_does_not_publish_success(client, monkeypatch):
    hub._bridge_ref._match_service.allow_disk_cache = False
    publish = Mock()
    monkeypatch.setattr(controller, "notify_sync", publish)
    assert client.post("/api/render").status_code == 409
    assert not any(c.args[0].get("type") == "OVERLAY_RENDERED" for c in publish.call_args_list)


def test_config_validation_preserves_last_valid_file(client, isolated):
    assert client.post("/api/config", json={"stage_title": "VALID"}).status_code == 200
    before = (isolated / "overlay_config.json").read_bytes()
    for body in ({"server_port": "bad"}, {"server_port": 0}, {"custom_augments": "bad"},
                 {"custom_augments": ["../file.png"]}, {"player_avatars": {"A": "../secret"}},
                 {"server_port": True}, {"unknown": 1}):
        assert client.post("/api/config", json=body).status_code == 422
        assert (isolated / "overlay_config.json").read_bytes() == before


def test_auto_augments_clear_existing_selection(client):
    assert client.post("/api/augments", json={"custom_augments": ["ThreeThrees_II.png"]}).status_code == 200
    response = client.post("/api/augments", json={"custom_augments": [None, None, None]})
    assert response.json()["overlay_config"]["custom_augments"] == []


def test_asset_override_keeps_bundled_assets_available(client, isolated):
    original = client.get("/assets/background.png")
    assert original.status_code == 200
    assert client.get("/assets/League_Spartan/static/LeagueSpartan-Regular.ttf").status_code == 200
    override = isolated / "assets" / "background.png"
    override.write_bytes(b"override")
    assert client.get("/assets/background.png").content == b"override"
    assert client.get("/assets/League_Spartan/static/LeagueSpartan-Regular.ttf").status_code == 200
    assert client.get("/assets/%2e%2e/.env").status_code == 404


def test_overlay_shell_has_styles_before_first_render(client):
    shell = client.get("/overlay").text
    assert 'href="/overlay.css"' in shell
    assert 'id="overlay-root"' in shell
    assert client.get("/overlay.css").status_code == 200


def png_payload():
    buffer = io.BytesIO()
    Image.new("RGBA", (1920, 1080), "blue").save(buffer, format="PNG")
    return {"image_base64": base64.b64encode(buffer.getvalue()).decode()}


@pytest.mark.parametrize("payload", [None, [], {"image_base64": 123},
    {"image_base64": "iVBORw0KGgpGQUtF"}, {"image_base64": "not-base64"}])
def test_bad_export_never_overwrites_latest(client, isolated, payload):
    latest = isolated / "output" / "overlay_latest.png"
    latest.write_bytes(b"existing")
    assert client.post("/api/export/base64", json=payload).status_code == 422
    assert latest.read_bytes() == b"existing"


def test_exports_get_distinct_names_and_valid_dimensions(client):
    first = client.post("/api/export/base64", json=png_payload()).json()
    second = client.post("/api/export/base64", json=png_payload()).json()
    assert first["file_path"] != second["file_path"]
    with Image.open(second["latest_path"]) as image:
        assert image.size == (1920, 1080)
        image.verify()


def test_websocket_checks_origin_and_allows_obs_without_origin(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("ws://localhost/ws", headers={"Origin": "https://evil.example"}):
        pass
    with client.websocket_connect("ws://localhost/ws") as socket:
        state = socket.receive_json()
        assert state["type"] == "INITIAL_STATE"
        assert "overlay_config" not in state


def test_empty_match_result_clears_previous_account_data(isolated):
    service = match_service.MatchService(config.AppConfig.load())
    service.active_match = {"match_id": "old"}
    service.cached_matches = [service.active_match]
    service._cached_client = Mock()
    service._cached_client.get_match_ids_by_puuid.return_value = []
    service.get_client = lambda **kw: service._cached_client
    assert service.fetch_recent_matches("New", "VN", "VN") == []
    assert service.active_match is None
    assert service.cached_matches == []
    assert not service.allow_disk_cache


def test_stop_start_polling_has_only_one_worker(isolated):
    service = match_service.MatchService(config.AppConfig.load())
    assert service.start_auto_polling()
    first = service._polling_thread
    assert service.stop_auto_polling()
    assert not first.is_alive()
    assert service.start_auto_polling()
    try:
        assert service._polling_thread is not first
        assert not service.start_auto_polling()
    finally:
        service.stop_auto_polling()


def test_account_switch_discards_inflight_fetch(isolated):
    service = match_service.MatchService(config.AppConfig.load())
    entered, release = threading.Event(), threading.Event()
    client = Mock()
    client.get_puuid_by_riot_id.return_value = "old-puuid"
    client.get_match_ids_by_puuid.return_value = ["old-match"]
    raw = json.loads(Path("tests/fixtures/match_1_raw.json").read_text(encoding="utf-8"))
    def slow_match(_):
        entered.set()
        release.wait(3)
        return raw
    client.get_match_by_id.side_effect = slow_match
    service.get_client = lambda **kw: client
    worker = service.fetch_recent_matches_async("Old", "VN", "VN")
    assert entered.wait(2)
    service.update_config(replace(service.config, riot_id="New#VN", game_name="New"))
    release.set()
    worker.join(3)
    assert service.active_match is None
    assert service.cached_matches == []


def test_empty_latest_cache_never_resurrects_old_matches(client, isolated):
    output = isolated / "output"
    old = json.loads(Path("tests/fixtures/match_1_clean.json").read_text(encoding="utf-8"))
    (output / "clean_matches_old.json").write_text(json.dumps([old]), encoding="utf-8")
    (output / "clean_matches_latest.json").write_text("[]", encoding="utf-8")
    assert hub._bridge_ref._get_best_match_data() is None


def test_destiny_bonus_does_not_shift_auto_main_slots(monkeypatch):
    from tft_studio.render import generator
    monkeypatch.setattr(generator, "get_image_set", lambda _: {"GoldenDestiny_II.png", "bonus.png", "second.png", "third.png"})
    monkeypatch.setattr(generator, "resolve_custom_augment", lambda value, cfg: {"name": value, "image": value})
    auto = [{"name": "first", "image": "first.png"}, {"name": "second", "image": "second.png"}, {"name": "third", "image": "third.png"}]
    rendered = generator.build_augments_html(auto, {"custom_augments": ["GoldenDestiny_II.png", "bonus.png", None, None]})
    assert 'second.png' in rendered
    assert 'third.png' in rendered
    assert rendered.index('second.png') < rendered.index('third.png')


def test_chunked_body_is_bounded_before_parsing():
    from fastapi import FastAPI

    from tft_studio.api.body_limit import BodyLimitMiddleware
    application = FastAPI()
    application.add_middleware(BodyLimitMiddleware, max_bytes=64)
    with TestClient(application) as client:
        result = client.post("/unused", content=iter([b"x" * 40, b"y" * 40]))
        assert result.status_code == 413
