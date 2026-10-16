"""
tests/unit/test_paths_and_sidecar.py
------------------------------------
Unit tests kiem tra viec phan tach TFT_APPDATA_DIR va TFT_RESOURCE_DIR,
khoi tao cau hinh lan dau, token security va shutdown / export base64 endpoints.
"""

from __future__ import annotations

from pathlib import Path

from tft_studio.core.paths import (
    ensure_user_config_initialized,
    get_appdata_dir,
    get_resource_dir,
    resolve_resource,
)


def test_paths_respect_environment_variables(tmp_path, monkeypatch):
    """Kiem tra cac ham lay duong dan ton trong bien moi truong."""
    custom_appdata = tmp_path / "appdata"
    custom_resources = tmp_path / "resources"
    custom_resources.mkdir()
    (custom_resources / "templates").mkdir()
    (custom_resources / "templates" / "overlay.html").write_text("dummy", encoding="utf-8")

    monkeypatch.setenv("TFT_APPDATA_DIR", str(custom_appdata))
    monkeypatch.setenv("TFT_RESOURCE_DIR", str(custom_resources))

    assert get_appdata_dir() == custom_appdata
    assert get_resource_dir() == custom_resources
    assert (custom_appdata / "output").exists()
    assert (custom_appdata / "logs").exists()

    resolved = resolve_resource("templates/overlay.html")
    assert resolved == custom_resources / "templates" / "overlay.html"


def test_ensure_user_config_initialized_copies_defaults_without_overwrite(tmp_path, monkeypatch):
    """Kiem tra khoi tao file cau hinh mac dinh khong ghi de du lieu cu."""
    custom_appdata = tmp_path / "appdata"
    custom_resources = tmp_path / "resources"
    custom_resources.mkdir()
    (custom_resources / ".env.example").write_text("RIOT_API_KEY=DEFAULT_KEY\n", encoding="utf-8")
    (custom_resources / "overlay_config.json").write_text('{"tournament_title":"DEFAULT"}\n', encoding="utf-8")

    monkeypatch.setenv("TFT_APPDATA_DIR", str(custom_appdata))
    monkeypatch.setenv("TFT_RESOURCE_DIR", str(custom_resources))

    env_file, config_file = ensure_user_config_initialized()
    assert env_file.exists()
    assert config_file.exists()
    assert "DEFAULT_KEY" in env_file.read_text(encoding="utf-8")
    assert "DEFAULT" in config_file.read_text(encoding="utf-8")

    # Lan thu hai voi file nguoi dung da sua khong duoc ghi de
    env_file.write_text("RIOT_API_KEY=USER_CUSTOM_KEY\n", encoding="utf-8")
    config_file.write_text('{"tournament_title":"CUSTOM_TOURNAMENT"}\n', encoding="utf-8")

    ensure_user_config_initialized()
    assert "USER_CUSTOM_KEY" in env_file.read_text(encoding="utf-8")
    assert "CUSTOM_TOURNAMENT" in config_file.read_text(encoding="utf-8")


def test_hub_cors_and_token_security(monkeypatch):
    """Kiem tra CORS tauri origin va token security qua STUDIO_SESSION_TOKEN."""
    from fastapi.testclient import TestClient

    from tft_studio.api.hub import app

    monkeypatch.setenv("STUDIO_SESSION_TOKEN", "super-secret-tauri-token")
    client = TestClient(app)

    # Thao tac ghi voi token dung va Origin tauri
    res = client.post(
        "/api/config",
        headers={
            "x-studio-token": "super-secret-tauri-token",
            "Origin": "http://tauri.localhost",
            "Host": "localhost:8080",
        },
        json={"tournament_title": "TEST TAURI"},
    )
    assert res.status_code == 200

    # Thao tac ghi voi token sai
    res_bad = client.post(
        "/api/config",
        headers={
            "x-studio-token": "wrong-token",
            "Origin": "http://tauri.localhost",
            "Host": "localhost:8080",
        },
        json={"tournament_title": "TEST TAURI"},
    )
    assert res_bad.status_code == 403


def test_hub_export_base64(monkeypatch, tmp_path):
    """Kiem tra endpoint /api/export/base64 giai ma va luu anh PNG hop le."""
    from fastapi.testclient import TestClient

    from tft_studio.api.hub import app

    monkeypatch.setenv("TFT_APPDATA_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_SESSION_TOKEN", "token-12345")
    client = TestClient(app)

    # 1x1 transparent PNG chuan Base64
    valid_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    res = client.post(
        "/api/export/base64",
        headers={
            "x-studio-token": "token-12345",
            "Origin": "http://localhost:8080",
            "Host": "localhost:8080",
        },
        json={"image_base64": f"data:image/png;base64,{valid_png_b64}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    file_path = Path(data["file_path"])
    latest_path = Path(data["latest_path"])
    assert file_path.exists()
    assert latest_path.exists()
    assert file_path.read_bytes() == latest_path.read_bytes()


def test_hub_shutdown_endpoint(monkeypatch):
    """Kiem tra endpoint /api/shutdown tra ve thanh cong voi token hop le."""
    from fastapi.testclient import TestClient

    from tft_studio.api.hub import app

    monkeypatch.setenv("STUDIO_SESSION_TOKEN", "shutdown-token")
    client = TestClient(app)

    res = client.post(
        "/api/shutdown",
        headers={
            "x-studio-token": "shutdown-token",
            "Origin": "http://localhost:8080",
            "Host": "localhost:8080",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

