"""
src/tft_studio/riot/client.py
-----------------------------
Module giao tiếp với Riot API cho TFT.

Trách nhiệm:
    - Lấy PUUID từ Riot ID (Account-V1)
    - Lấy danh sách match_id theo PUUID (Match-V1)
    - Lấy chi tiết 1 match theo match_id (Match-V1)
    - Tự giới hạn tốc độ gọi API (rate limiting chủ động) để tránh dính 429
    - Xử lý 429 / 5xx với backoff khi vẫn bị chặn
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger("riot_client")


# --------------------------------------------------------------------------- #
# Exceptions riêng
# --------------------------------------------------------------------------- #
class RiotAPIError(Exception):
    """Lỗi tổng quát khi gọi Riot API."""


class AuthenticationError(RiotAPIError):
    """Lỗi xác thực (401/403): API Key không đúng hoặc đã hết hạn (24h)."""


class RateLimitError(RiotAPIError):
    """Đã retry hết số lần cho phép mà vẫn bị 429."""


class MatchNotFoundError(RiotAPIError):
    """Match ID không tồn tại (404) — không nên retry vì retry vô ích."""


class AccountNotFoundError(RiotAPIError):
    """Riot ID không tồn tại (404) — không nên retry."""


# --------------------------------------------------------------------------- #
# Rate limiter chủ động — self-throttle TRƯỚC khi gửi request
# --------------------------------------------------------------------------- #
@dataclass
class _SlidingWindowLimiter:
    limits: list[tuple[int, float]]  # [(max_calls, window_seconds), ...]
    _hits: dict[float, deque] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for _, window in self.limits:
            self._hits[window] = deque()

    def acquire(self) -> None:
        """Chặn (sleep) nếu gọi ngay bây giờ sẽ vượt quá bất kỳ giới hạn nào."""
        now = time.monotonic()
        wait_time = 0.0

        for max_calls, window in self.limits:
            dq = self._hits[window]
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= max_calls:
                wait_needed = window - (now - dq[0])
                wait_time = max(wait_time, wait_needed)

        if wait_time > 0:
            logger.debug("Rate limiter: chờ %.2fs trước khi gọi tiếp", wait_time)
            time.sleep(wait_time)
            now = time.monotonic()

        for _, window in self.limits:
            self._hits[window].append(now)


class RiotTFTClient:
    """Client gọi Riot API, chỉ phục vụ TFT (Account-V1 + TFT-Match-V1)."""

    def __init__(
        self,
        api_key: str | None = None,
        match_routing: str = "sea",
        account_routing: str = "sea",
        platform: str = "VN2",
        timeout: float = 10.0,
        max_retries: int = 5,
        rate_limits: list[tuple[int, float]] | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("RIOT_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Thiếu RIOT_API_KEY. Set biến môi trường hoặc truyền api_key= khi khởi tạo."
            )

        self.match_routing = match_routing
        self.account_routing = account_routing
        self.platform = platform
        self.timeout = timeout
        self.max_retries = max_retries

        self._session = requests.Session()
        self._session.headers.update({"X-Riot-Token": self.api_key})

        self._limiter = _SlidingWindowLimiter(
            rate_limits or [(20, 1.0), (100, 120.0)]
        )

    # ------------------------------------------------------------------ #
    # Internal request wrapper
    # ------------------------------------------------------------------ #
    def _request(self, url: str, *, not_found_exc: type[RiotAPIError] = RiotAPIError) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            self._limiter.acquire()

            start = time.monotonic()
            try:
                resp = self._session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = exc
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "Network error (lần %d/%d): %s — chờ %ds rồi thử lại",
                    attempt, self.max_retries, exc, wait,
                )
                time.sleep(wait)
                continue

            elapsed_ms = (time.monotonic() - start) * 1000
            resource = "request"
            if "/riot/account/" in url:
                resource = "account"
            elif "/tft/match/v1/matches/by-puuid/" in url:
                resource = "matches"
            elif "/tft/match/v1/matches/" in url:
                resource = "match"
            else:
                resource = url.split("?")[0].rstrip("/").split("/")[-1]

            logger.info("GET %s -> %d (%.0fms)", resource, resp.status_code, elapsed_ms)

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 404:
                raise not_found_exc(f"Không tìm thấy tài nguyên: {url}")

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(2 ** attempt, 30)
                logger.warning(
                    "429 Rate limited (lần %d/%d) — chờ %.1fs theo Retry-After",
                    attempt, self.max_retries, wait,
                )
                time.sleep(wait)
                last_error = RateLimitError(f"429 tại {url}")
                continue

            if 500 <= resp.status_code < 600:
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "%d Server error (lần %d/%d) — backoff %ds",
                    resp.status_code, attempt, self.max_retries, wait,
                )
                time.sleep(wait)
                last_error = RiotAPIError(f"{resp.status_code} tại {url}")
                continue

            if resp.status_code in (401, 403):
                raise AuthenticationError(
                    f"Lỗi xác thực Riot API ({resp.status_code}): "
                    "API Key không hợp lệ hoặc đã hết hạn!\n"
                    "Lưu ý: Riot Development API Key chỉ có hiệu lực trong vòng 24 giờ.\n"
                    "👉 Vui lòng truy cập https://developer.riotgames.com để 'Regenerate API Key' "
                    "và dán vào file .env"
                )

            # Lỗi khác (400, v.v.) — không retry
            raise RiotAPIError(f"Lỗi {resp.status_code} tại {url}: {resp.text[:200]}")

        raise RateLimitError(
            f"Hết {self.max_retries} lần retry mà vẫn lỗi tại {url}: {last_error}"
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_puuid_by_riot_id(self, game_name: str, tag_line: str) -> str:
        """Account-V1: đổi Riot ID (name#tag) sang PUUID."""
        safe_name = urllib.parse.quote(game_name.strip())
        safe_tag = urllib.parse.quote(tag_line.strip())
        url = (
            f"https://{self.account_routing}.api.riotgames.com"
            f"/riot/account/v1/accounts/by-riot-id/{safe_name}/{safe_tag}"
        )
        data = self._request(url, not_found_exc=AccountNotFoundError)
        return data["puuid"]

    def get_match_ids_by_puuid(
        self, puuid: str, count: int = 20, start: int = 0
    ) -> list[str]:
        """TFT-Match-V1: lấy danh sách match_id gần nhất của 1 PUUID."""
        url = (
            f"https://{self.match_routing}.api.riotgames.com"
            f"/tft/match/v1/matches/by-puuid/{puuid}/ids"
            f"?start={start}&count={count}"
        )
        return self._request(url)

    def get_match_by_id(self, match_id: str) -> dict:
        """TFT-Match-V1: lấy raw JSON đầy đủ của 1 match."""
        url = (
            f"https://{self.match_routing}.api.riotgames.com"
            f"/tft/match/v1/matches/{match_id}"
        )
        return self._request(url, not_found_exc=MatchNotFoundError)


# --------------------------------------------------------------------------- #
# Hàm tích hợp trọn quy trình
# --------------------------------------------------------------------------- #
def fetch_and_save_complete_data(
    client: RiotTFTClient,
    game_name: str,
    tag_line: str,
    match_count: int = 5,
    output_dir: str = "raw_matches",
) -> dict:
    """Chạy trọn luồng lấy dữ liệu và lưu ra file."""
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Bước 1/3: lấy PUUID cho Riot ID '%s#%s'", game_name, tag_line)
    puuid = client.get_puuid_by_riot_id(game_name, tag_line)
    logger.info("-> PUUID: %s", puuid)

    logger.info("Bước 2/3: lấy %d match_id gần nhất", match_count)
    match_ids = client.get_match_ids_by_puuid(puuid, count=match_count)
    logger.info("-> Tìm thấy %d match: %s", len(match_ids), match_ids)

    saved_files: list[dict] = []
    failed: list[dict] = []

    logger.info("Bước 3/3: tải chi tiết từng match và lưu ra file")
    for match_id in match_ids:
        try:
            match_data = client.get_match_by_id(match_id)
        except RiotAPIError as exc:
            logger.error("Bỏ qua match %s do lỗi: %s", match_id, exc)
            failed.append({"match_id": match_id, "error": str(exc)})
            continue

        file_path = os.path.join(output_dir, f"{match_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(match_data, f, ensure_ascii=False, indent=2)

        n_participants = len(match_data.get("info", {}).get("participants", []))
        logger.info("-> Đã lưu %s (%d participants)", file_path, n_participants)
        saved_files.append({
            "match_id": match_id,
            "file_path": file_path,
            "participants_count": n_participants,
        })

    summary = {
        "riot_id": f"{game_name}#{tag_line}",
        "puuid": puuid,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "match_count_requested": match_count,
        "matches_saved": saved_files,
        "matches_failed": failed,
    }

    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("-> Đã lưu file tổng hợp: %s", summary_path)

    return summary
