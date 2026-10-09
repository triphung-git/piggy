"""
tests/unit/test_riot_client.py
------------------------------
Characterization tests cho RiotTFTClient dung thu vien responses.
Kiem tra phan loai loi 401, 404, retry 429 va backoff.
"""

import pytest
import responses

from tests.fixtures.mock_responses import (
    MOCK_ACCOUNT_200,
    MOCK_MATCH_IDS_200,
    MOCK_RESPONSE_401,
    MOCK_RESPONSE_403,
    MOCK_RESPONSE_404,
    MOCK_RESPONSE_429,
    MOCK_RESPONSE_500,
)
from tft_studio.riot.client import (
    AccountNotFoundError,
    AuthenticationError,
    MatchNotFoundError,
    RateLimitError,
    RiotAPIError,
    RiotTFTClient,
)


@pytest.fixture
def client():
    # max_retries nho va timeout ngan de test chay nhanh
    return RiotTFTClient(
        api_key="RGAPI-test-dummy-key-00000000",
        account_routing="asia",
        match_routing="sea",
        timeout=2.0,
        max_retries=2,
    )


@responses.activate
def test_get_puuid_success(client):
    """Kiem tra tra ve PUUID thanh cong voi status 200."""
    url = "https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Faker/KR1"
    responses.add(responses.GET, url, json=MOCK_ACCOUNT_200, status=200)

    puuid = client.get_puuid_by_riot_id("Faker", "KR1")
    assert puuid == "fake-puuid-001"


@responses.activate
def test_get_puuid_401_raises_authentication_error(client):
    """Kiem tra ma 401 phai nem AuthenticationError."""
    url = "https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Faker/KR1"
    responses.add(responses.GET, url, json=MOCK_RESPONSE_401, status=401)

    with pytest.raises(AuthenticationError):
        client.get_puuid_by_riot_id("Faker", "KR1")


@responses.activate
def test_get_puuid_403_raises_authentication_error(client):
    """Kiem tra ma 403 phai nem AuthenticationError."""
    url = "https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Faker/KR1"
    responses.add(responses.GET, url, json=MOCK_RESPONSE_403, status=403)

    with pytest.raises(AuthenticationError):
        client.get_puuid_by_riot_id("Faker", "KR1")


@responses.activate
def test_get_puuid_404_raises_account_not_found(client):
    """Kiem tra khong tim thay account phai nem AccountNotFoundError."""
    url = (
        "https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Unknown/000"
    )
    responses.add(responses.GET, url, json=MOCK_RESPONSE_404, status=404)

    with pytest.raises(AccountNotFoundError):
        client.get_puuid_by_riot_id("Unknown", "000")


@responses.activate
def test_get_match_404_raises_match_not_found(client):
    """Kiem tra match ID khong ton tai phai nem MatchNotFoundError."""
    url = "https://sea.api.riotgames.com/tft/match/v1/matches/VN2_NON_EXISTENT"
    responses.add(responses.GET, url, json=MOCK_RESPONSE_404, status=404)

    with pytest.raises(MatchNotFoundError):
        client.get_match_by_id("VN2_NON_EXISTENT")


@responses.activate
def test_retry_on_429_eventually_succeeds(client):
    """Kiem tra retry khi gap 429 va thanh cong o lan thu 2."""
    url = "https://sea.api.riotgames.com/tft/match/v1/matches/by-puuid/fake-puuid-001/ids?start=0&count=2"
    # Lần 1: 429 với Retry-After: 0.1
    responses.add(
        responses.GET,
        url,
        json=MOCK_RESPONSE_429,
        status=429,
        headers={"Retry-After": "0"},
    )
    # Lần 2: 200 thành công
    responses.add(responses.GET, url, json=MOCK_MATCH_IDS_200, status=200)

    match_ids = client.get_match_ids_by_puuid("fake-puuid-001", count=2)
    assert match_ids == MOCK_MATCH_IDS_200
    assert len(responses.calls) == 2


@responses.activate
def test_retry_on_429_exhausted_raises_rate_limit_error(client):
    """Kiem tra khi vuot qua max_retries voi 429 phai nem RateLimitError."""
    url = "https://sea.api.riotgames.com/tft/match/v1/matches/by-puuid/fake-puuid-001/ids?start=0&count=2"
    responses.add(
        responses.GET,
        url,
        json=MOCK_RESPONSE_429,
        status=429,
        headers={"Retry-After": "0"},
    )
    responses.add(
        responses.GET,
        url,
        json=MOCK_RESPONSE_429,
        status=429,
        headers={"Retry-After": "0"},
    )

    with pytest.raises(RateLimitError):
        client.get_match_ids_by_puuid("fake-puuid-001", count=2)


@responses.activate
def test_server_error_500_raises_riot_api_error(client):
    """Kiem tra loi 500 server nem RiotAPIError."""
    url = "https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/Faker/KR1"
    responses.add(responses.GET, url, json=MOCK_RESPONSE_500, status=500)
    responses.add(responses.GET, url, json=MOCK_RESPONSE_500, status=500)

    with pytest.raises(RiotAPIError):
        client.get_puuid_by_riot_id("Faker", "KR1")
