"""
tests/fixtures/mock_responses.py
--------------------------------
Phan hoi gia (Mock Responses) cua Riot API cho cac ma trang thai HTTP:
200, 401, 404, 429, 500.
"""

from typing import Any, Dict

# Phản hồi 200: Lấy PUUID từ Riot ID
MOCK_ACCOUNT_200: Dict[str, Any] = {
    "puuid": "fake-puuid-001",
    "gameName": "EsportsPlayer_1",
    "tagLine": "VN1",
}

# Phản hồi 200: Danh sách Match IDs
MOCK_MATCH_IDS_200: list[str] = [
    "VN2_FAKE_MATCH_001",
    "VN2_FAKE_MATCH_002",
]

# Phản hồi 401: Unauthorized / API Key hết hạn
MOCK_RESPONSE_401: Dict[str, Any] = {
    "status": {
        "message": "Unauthorized: API Key invalid or expired",
        "status_code": 401,
    }
}

# Phản hồi 403: Forbidden
MOCK_RESPONSE_403: Dict[str, Any] = {
    "status": {
        "message": "Forbidden: Access denied",
        "status_code": 403,
    }
}

# Phản hồi 404: Account not found / Match not found
MOCK_RESPONSE_404: Dict[str, Any] = {
    "status": {
        "message": "Data not found",
        "status_code": 404,
    }
}

# Phản hồi 429: Rate limit exceeded
MOCK_RESPONSE_429: Dict[str, Any] = {
    "status": {
        "message": "Rate limit exceeded",
        "status_code": 429,
    }
}

# Phản hồi 500: Internal server error
MOCK_RESPONSE_500: Dict[str, Any] = {
    "status": {
        "message": "Internal server error",
        "status_code": 500,
    }
}
