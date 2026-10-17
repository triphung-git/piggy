"""
src/tft_studio/service/file_watcher.py
--------------------------------------
Bộ theo dõi thay đổi file cấu hình và tài nguyên theo thời gian thực (Real-time Config Watcher).
Tự động phát hiện khi người dùng lưu file .env, overlay_config.json hoặc thêm ảnh đại diện mới,
ngay lập tức nạp lại cấu hình và phát tín hiệu render/đồng bộ qua WebSocket cho toàn mạng.

Sử dụng os.path.getmtime tiêu chuẩn Python:
  - Không phụ thuộc thư viện C bên ngoài.
  - Hoạt động 100% tin cậy trên Windows NTFS/FAT32.
  - Tương thích hoàn hảo với PyInstaller binary (.exe).
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger("file_watcher")


class ConfigWatcher:
    """Theo dõi các file cấu hình và thư mục tài nguyên để tự động đồng bộ."""

    def __init__(
        self,
        config_path: Path,
        env_path: Path,
        avatars_dir: Path | None = None,
        poll_interval: float = 0.5,
        debounce_seconds: float = 0.3,
    ) -> None:
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)
        self.avatars_dir = Path(avatars_dir) if avatars_dir else None
        self.poll_interval = poll_interval
        self.debounce_seconds = debounce_seconds

        # Callback events
        self.on_config_changed: Callable[[], None] | None = None
        self.on_env_changed: Callable[[], None] | None = None
        self.on_avatars_changed: Callable[[], None] | None = None

        # State timestamps
        self._mtimes: dict[str, float] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Cập nhật mtime ban đầu
        self._record_initial_mtimes()

    def _get_file_mtime(self, path: Path) -> float:
        with contextlib.suppress(Exception):
            if path.exists():
                return path.stat().st_mtime
        return 0.0

    def _get_dir_max_mtime(self, dir_path: Path | None) -> float:
        if not dir_path or not dir_path.exists():
            return 0.0
        try:
            mtimes = [dir_path.stat().st_mtime]
            for p in dir_path.iterdir():
                if p.is_file():
                    mtimes.append(p.stat().st_mtime)
            return max(mtimes)
        except Exception:
            return 0.0

    def _record_initial_mtimes(self) -> None:
        self._mtimes["config"] = self._get_file_mtime(self.config_path)
        self._mtimes["env"] = self._get_file_mtime(self.env_path)
        self._mtimes["avatars"] = self._get_dir_max_mtime(self.avatars_dir)

    def start(self) -> None:
        """Bắt đầu luồng theo dõi ngầm (Daemon Thread)."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="ConfigWatcherThread"
        )
        self._thread.start()
        logger.info(
            "ConfigWatcher started (polling every %.1fs, watching: %s, %s)",
            self.poll_interval,
            self.config_path.name,
            self.env_path.name,
        )

    def stop(self) -> None:
        """Dừng luồng theo dõi."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("ConfigWatcher stopped")

    def _watch_loop(self) -> None:
        pending: dict[str, float] = {}
        while not self._stop_event.wait(self.poll_interval):
            now = time.monotonic()
            readings = {
                "config": self._get_file_mtime(self.config_path),
                "env": self._get_file_mtime(self.env_path),
                "avatars": self._get_dir_max_mtime(self.avatars_dir),
            }
            for key, mtime in readings.items():
                if mtime != self._mtimes.get(key, 0.0):
                    self._mtimes[key] = mtime
                    pending[key] = now + self.debounce_seconds
            callbacks = {"config": self.on_config_changed, "env": self.on_env_changed, "avatars": self.on_avatars_changed}
            for key in list(pending):
                if now >= pending[key]:
                    del pending[key]
                    callback = callbacks[key]
                    if callback:
                        try:
                            callback()
                        except Exception:
                            logger.exception("Config watcher callback failed: %s", key)
