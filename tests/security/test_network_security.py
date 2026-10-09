"""
tests/security/test_network_security.py
---------------------------------------
Kiem tra bao mat mang S1, S3:
- CORS khong duoc chua wildcard (*)
- Host va Origin la phai bi chan (403)
- Cac method ghi (POST, PUT, DELETE) bat buoc co header X-Studio-Token hop le.
"""

import pytest
from fastapi.testclient import TestClient

from tft_studio.api.hub import app, get_current_token


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_does_not_allow_wildcard(client):
    """S3: CORS khong duoc chua '*'."""
    resp = client.options(
        "/api/state",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin != "*", "CORS allow_origins khong duoc la '*'"


def test_post_without_token_is_rejected(client):
    """S1: Gửi request ghi ma khong co X-Studio-Token phai bi tu choi (401 hoac 403)."""
    resp = client.post("/api/augments", json={"custom_augments": []})
    assert resp.status_code in (401, 403), (
        f"Mong doi 401/403 nhung nhan {resp.status_code}"
    )


def test_post_with_invalid_token_is_rejected(client):
    """S1: Gửi request ghi voi token sai phai bi tu choi (403)."""
    resp = client.post(
        "/api/augments",
        json={"custom_augments": []},
        headers={"X-Studio-Token": "invalid-secret-token-12345"},
    )
    assert resp.status_code in (401, 403)


def test_post_with_valid_token_is_accepted(client):
    """S1: Gửi request ghi voi token hop le duoc chap nhan (200)."""
    valid_token = get_current_token()
    resp = client.post(
        "/api/augments",
        json={"custom_augments": []},
        headers={
            "X-Studio-Token": valid_token,
            "Host": "localhost:8080",
            "Origin": "http://localhost:8080",
        },
    )
    assert resp.status_code == 200


def test_foreign_origin_is_rejected(client):
    """S1: Origin la tu ben ngoai (vi du trang web tan cong) phai bi chan (403)."""
    valid_token = get_current_token()
    resp = client.post(
        "/api/augments",
        json={"custom_augments": []},
        headers={
            "X-Studio-Token": valid_token,
            "Origin": "https://evil-attacker.com",
        },
    )
    assert resp.status_code == 403


def test_foreign_host_is_rejected(client):
    """S1: Host la (DNS rebinding / proxy) phai bi chan (403)."""
    resp = client.get(
        "/api/state",
        headers={
            "Host": "attacker-controlled-host.com",
        },
    )
    assert resp.status_code == 403
