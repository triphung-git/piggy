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


def test_resolve_resource_and_config_up_directory_fallback(tmp_path, monkeypatch):
    """Kiem tra fallback _up_ khi Tauri v2 dong goi tai nguyen tu thu muc cha."""
    custom_appdata = tmp_path / "appdata"
    custom_resources = tmp_path / "resources"
    custom_resources.mkdir()
    up_dir = custom_resources / "_up_"
    up_dir.mkdir()
    (up_dir / "templates").mkdir()
    (up_dir / "templates" / "overlay.html").write_text("up-template", encoding="utf-8")
    (up_dir / ".env.example").write_text("RIOT_API_KEY=UP_KEY\n", encoding="utf-8")
    (up_dir / "overlay_config.json").write_text('{"tournament_title":"UP_TITLE"}\n', encoding="utf-8")

    monkeypatch.setenv("TFT_APPDATA_DIR", str(custom_appdata))
    monkeypatch.setenv("TFT_RESOURCE_DIR", str(custom_resources))

    resolved = resolve_resource("templates/overlay.html")
    assert resolved == up_dir / "templates" / "overlay.html"

    env_file, config_file = ensure_user_config_initialized()
    assert "UP_KEY" in env_file.read_text(encoding="utf-8")
    assert "UP_TITLE" in config_file.read_text(encoding="utf-8")


def test_isolated_mode_does_not_fallback_to_project_root(tmp_path, monkeypatch):
    """Kiem tra che do dong goi (frozen / isolated) khong am tham lay tai nguyen tu repo root."""
    from tft_studio.core.paths import _find_project_root

    empty_resources = tmp_path / "isolated_res"
    empty_resources.mkdir()
    custom_appdata = tmp_path / "isolated_appdata"

    monkeypatch.setenv("TFT_APPDATA_DIR", str(custom_appdata))
    monkeypatch.setenv("TFT_RESOURCE_DIR", str(empty_resources))
    monkeypatch.setenv("TFT_ISOLATED_RESOURCES", "1")

    # In isolated mode, resolving a missing resource should NOT resolve to the project root
    resolved = resolve_resource("templates/overlay.html")
    repo_root = _find_project_root()
    assert resolved != repo_root / "templates" / "overlay.html"

    # In isolated mode, ensure_user_config_initialized should NOT copy from repo root
    env_file, config_file = ensure_user_config_initialized()
    assert env_file.exists()
    assert config_file.exists()
    # It generates standard default content instead of copying developer's local .env
    assert "RIOT_API_KEY=\n" in env_file.read_text(encoding="utf-8")



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

    import base64
    import io

    from PIL import Image
    png = io.BytesIO()
    Image.new("RGBA", (1920, 1080)).save(png, format="PNG")
    valid_png_b64 = base64.b64encode(png.getvalue()).decode()

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

