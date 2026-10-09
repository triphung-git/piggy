"""
src/tft_studio/service/match_service.py
---------------------------------------
Dịch vụ điều phối lấy dữ liệu trận đấu, bóc tách và tự động hóa (Auto-Polling).
Hỗ trợ callback tiến độ và chạy đa luồng để UI không bao giờ bị đơ (freeze/not responding).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from tft_studio.core.config import REGION_MAPPING, AppConfig
from tft_studio.core.paths import get_app_dir
from tft_studio.data.parser import DDragonLoader, parse_tft_match
from tft_studio.riot.client import RiotTFTClient

logger = logging.getLogger("match_service")

BASE_DIR = get_app_dir()
OUTPUT_DIR = BASE_DIR / "output"


def cleanup_cache_files(output_dir: Path, max_files: int = 20) -> int:
    """Xóa bớt các file cache clean_matches_*.json cũ (K9), giữ lại tối đa max_files file mới nhất.
    File clean_matches_latest.json luôn được bảo toàn.
    """
    if not output_dir.exists():
        return 0

    candidates = [
        f for f in output_dir.glob("clean_matches_*.json")
        if f.name != "clean_matches_latest.json" and f.is_file()
    ]
    if len(candidates) <= max_files:
        return 0

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    to_delete = candidates[max_files:]
    deleted = 0
    for p in to_delete:
        try:
            p.unlink()
            deleted += 1
        except Exception as e:
            logger.debug("Failed to remove old cache file %s: %s", p.name, e)
    return deleted


class MatchService:
    """Quản lý dữ liệu trận đấu TFT và chế độ Auto-Polling ngầm."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.load()
        self.ddragon = DDragonLoader(language=self.config.language)
        self.cached_matches: list[dict[str, Any]] = []
        self.active_match: dict[str, Any] | None = None
        self.active_puuid: str | None = None
        self.last_seen_match_id: str | None = None

        # Tái sử dụng Client để chia sẻ Rate Limiter (K8)
        self._cached_client: RiotTFTClient | None = None
        self._cached_client_key: tuple[str, str, str] | None = None

        # Quản lý Polling Thread
        self._polling_thread: threading.Thread | None = None
        self._polling_stop_event = threading.Event()
        self._polling_interval: int = 60
        self._is_polling: bool = False
        self._on_new_match_callback: Callable[[dict[str, Any]], None] | None = None

    def get_client(
        self,
        account_routing: str | None = None,
        match_routing: str | None = None,
        timeout: float = 6.0,
        max_retries: int = 2,
    ) -> RiotTFTClient:
        """Tái sử dụng client để chia sẻ sliding window rate limiter (K8)."""
        act_routing = account_routing or self.config.account_routing
        mtc_routing = match_routing or self.config.match_routing
        key = (self.config.api_key, act_routing, mtc_routing)
        if self._cached_client is None or self._cached_client_key != key:
            self._cached_client = RiotTFTClient(
                api_key=self.config.api_key,
                account_routing=act_routing,
                match_routing=mtc_routing,
                timeout=timeout,
                max_retries=max_retries,
            )
            self._cached_client_key = key
        return self._cached_client

    def _create_client(self) -> RiotTFTClient:
        return self.get_client()

    def resolve_puuid(self, game_name: str, tag_line: str, region: str) -> str:
        """Lấy PUUID của người chơi từ Riot ID."""
        mapping = REGION_MAPPING.get(region, REGION_MAPPING.get("VN", {}))
        account_routing = mapping.get("account", "asia")
        match_routing = mapping.get("match", "sea")

        client = self.get_client(
            account_routing=account_routing,
            match_routing=match_routing,
        )
        puuid = client.get_puuid_by_riot_id(game_name, tag_line)
        self.active_puuid = puuid
        return puuid

    def fetch_recent_matches(
        self,
        game_name: str,
        tag_line: str,
        region: str,
        count: int = 5,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lấy danh sách các trận gần nhất và bóc tách thành clean data.
        Báo cáo tiến trình qua progress_callback (0..100%, status text).
        """
        if progress_callback:
            progress_callback(10, f"Đang xác thực Riot ID: {game_name}#{tag_line}...")

        mapping = REGION_MAPPING.get(region, REGION_MAPPING.get("VN", {}))
        account_routing = mapping.get("account", "asia")
        match_routing = mapping.get("match", "sea")

        client = self.get_client(
            account_routing=account_routing,
            match_routing=match_routing,
            timeout=6.0,
            max_retries=2,
        )

        puuid = client.get_puuid_by_riot_id(game_name, tag_line)
        self.active_puuid = puuid

        if progress_callback:
            progress_callback(25, "Đang tải danh sách ID trận đấu gần nhất...")

        match_ids = client.get_match_ids_by_puuid(puuid, count=count)
        if not match_ids:
            if progress_callback:
                progress_callback(100, "Không tìm thấy trận đấu TFT nào gần đây.")
            return []

        parsed_list: list[dict[str, Any]] = []
        total = len(match_ids)

        for idx, m_id in enumerate(match_ids, start=1):
            pct = 25 + int((idx / total) * 70)
            if progress_callback:
                progress_callback(pct, f"Đang tải & xử lý trận {idx}/{total} ({m_id})...")

            try:
                raw_match = client.get_match_by_id(m_id)
                logger.info("Match loaded: %s", m_id)
                parsed = parse_tft_match(
                    raw_match, target_puuid=puuid, language=self.config.language
                )
                parsed_list.append(parsed)
            except Exception as exc:
                logger.warning("Failed to parse match %s: %s", m_id, exc)

        self.cached_matches = parsed_list
        if parsed_list:
            self.active_match = parsed_list[0]
            self.last_seen_match_id = parsed_list[0]["match_id"]

            # Lưu file cache cho overlay
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            cache_file = OUTPUT_DIR / "clean_matches_latest.json"
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(parsed_list, f, ensure_ascii=False, indent=2)
                cleanup_cache_files(OUTPUT_DIR, max_files=20)
            except Exception as e:
                logger.warning("Failed to save match cache: %s", e)

        if progress_callback:
            progress_callback(100, f"Đã tải hoàn tất {len(parsed_list)} trận đấu!")

        return parsed_list

    def fetch_recent_matches_async(
        self,
        game_name: str,
        tag_line: str,
        region: str,
        count: int = 1,
        on_complete: Callable[[list[dict[str, Any]]], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> threading.Thread:
        """Chạy tải trận ngầm trong luồng riêng để không bao giờ làm đứng/khựng UI."""
        def _worker():
            try:
                res = self.fetch_recent_matches(
                    game_name=game_name,
                    tag_line=tag_line,
                    region=region,
                    count=count,
                    progress_callback=progress_callback,
                )
                if on_complete:
                    on_complete(res)
            except Exception as e:
                logger.warning("Background fetch match error: %s", e)
                if on_error:
                    on_error(e)

        th = threading.Thread(target=_worker, daemon=True, name="AsyncMatchFetcher")
        th.start()
        return th

    def set_active_match_by_id(self, match_id: str) -> dict[str, Any] | None:
        """Chọn một trận đấu cụ thể để hiển thị lên Overlay."""
        for m in self.cached_matches:
            if m.get("match_id") == match_id:
                self.active_match = m
                return m
        return None

    # ------------------------------------------------------------------ #
    # Auto-Polling Engine (Tự động phát hiện trận mới ngầm)
    # ------------------------------------------------------------------ #
    def start_auto_polling(
        self,
        interval_seconds: int = 60,
        on_new_match_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> bool:
        """Khởi động luồng Auto-polling kiểm tra trận mới."""
        if self._is_polling:
            return False

        self._polling_interval = max(20, interval_seconds)
        self._on_new_match_callback = on_new_match_callback
        self._polling_stop_event.clear()

        def _poll_worker() -> None:
            logger.info("Auto-polling started (interval: %ds)", self._polling_interval)
            while not self._polling_stop_event.is_set():
                time.sleep(self._polling_interval)
                if self._polling_stop_event.is_set():
                    break

                try:
                    if not self.config.api_key or not self.config.game_name:
                        continue

                    puuid = self.active_puuid
                    if not puuid:
                        puuid = self.resolve_puuid(
                            self.config.game_name, self.config.tag_line, self.config.region
                        )

                    client = self._create_client()
                    latest_ids = client.get_match_ids_by_puuid(puuid, count=1)
                    if latest_ids:
                        new_id = latest_ids[0]
                        if new_id != self.last_seen_match_id:
                            logger.info("New match detected: %s", new_id)
                            raw = client.get_match_by_id(new_id)
                            parsed = parse_tft_match(
                                raw, target_puuid=puuid, language=self.config.language
                            )
                            self.last_seen_match_id = new_id
                            self.active_match = parsed
                            self.cached_matches.insert(0, parsed)

                            if self._on_new_match_callback:
                                self._on_new_match_callback(parsed)
                except Exception as exc:
                    logger.debug("Auto-polling check gặp lỗi: %s", exc)

            logger.info("Auto-polling stopped")

        self._polling_thread = threading.Thread(target=_poll_worker, daemon=True)
        self._polling_thread.start()
        self._is_polling = True
        return True

    def stop_auto_polling(self) -> bool:
        """Dừng luồng Auto-polling."""
        if not self._is_polling:
            return False
        self._polling_stop_event.set()
        self._is_polling = False
        return True

    def is_polling_active(self) -> bool:
        return self._is_polling
