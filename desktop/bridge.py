"""
desktop/bridge.py
-----------------
Cầu nối IPC 2 chiều giữa Giao diện React (Web Overlay) và Logic Python.
Cung cấp các hàm API được gọi trực tiếp từ `window.pywebview.api`.

Chế độ Standalone: Mỗi người dùng chạy app của riêng họ, không cần Host server.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Any

import webview

from tft_studio.api.hub import is_server_running, notify_sync, set_bridge_reference
from tft_studio.core.config import AppConfig, load_overlay_config, save_overlay_config
from tft_studio.core.paths import get_app_dir, resolve_resource
from tft_studio.render.exporter import export_html_to_png
from tft_studio.render.generator import (
    generate_overlay_html,
)
from tft_studio.render.generator import (
    load_overlay_config as load_generator_config,
)
from tft_studio.service.file_watcher import ConfigWatcher
from tft_studio.service.match_service import MatchService

logger = logging.getLogger("bridge")

BASE_DIR = get_app_dir()
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = resolve_resource("assets")
AVATARS_DIR = BASE_DIR / "assets" / "avatars"

# (Transform & Crop parameters removed)

VALID_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_AVATAR_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_avatar_file(path: Path | str) -> tuple[bool, str]:
    """Kiểm tra tính an toàn của file ảnh avatar (K4).
    Kiểm tra tồn tại, kích thước (<10MB), phần mở rộng hợp lệ, và magic bytes thực tế.
    """
    p = Path(path)
    if not p.is_file():
        return False, "File không tồn tại hoặc không phải là file thông thường"

    if p.suffix.lower() not in VALID_AVATAR_EXTENSIONS:
        return False, (
            f"Định dạng file không được hỗ trợ ({p.suffix}). "
            "Chỉ chấp nhận .png, .jpg, .jpeg, .webp"
        )

    try:
        size = p.stat().st_size
        if size == 0:
            return False, "File ảnh rỗng (0 bytes)"
        if size > MAX_AVATAR_SIZE:
            return False, f"Kích thước file vượt quá giới hạn tối đa 10MB ({size} bytes)"

        with open(p, "rb") as f:
            header = f.read(16)

        is_valid_magic = any(
            header.startswith(magic)
            for magic in (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a")
        )
        is_webp = header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP"
        if not is_valid_magic and is_webp:
            is_valid_magic = True

        if not is_valid_magic:
            return False, "Nội dung file không đúng định dạng ảnh hợp lệ (magic bytes mismatch)"

        return True, ""
    except Exception as exc:
        return False, f"Lỗi khi kiểm tra file ảnh: {exc}"


class StudioBridge:
    """API Object được truyền vào pywebview — Standalone Edition."""

    def __init__(self, match_service: MatchService) -> None:
        self._match_service = match_service
        self._dashboard_window: webview.Window | None = None
        self._overlay_window: webview.Window | None = None
        self._is_overlay_visible: bool = False

        # Khởi tạo thư mục avatars và output nếu chưa có
        AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Liên kết với local server
        set_bridge_reference(self)

        # Cấu hình callback Auto-polling
        self._setup_polling_callback()

        # Tự động kích hoạt Auto-polling ngầm nếu .env đã có API Key và Riot ID
        cfg = AppConfig.load()
        if cfg.api_key and cfg.game_name:
            self._match_service.start_auto_polling(
                interval_seconds=30,
                on_new_match_callback=self._on_new_match_cb,
            )
            logger.info(
                "Auto-polling automatically started (interval 30s) for %s#%s",
                cfg.game_name,
                cfg.tag_line,
            )

        # Khởi động File Watcher theo dõi config changes cục bộ
        self._setup_file_watcher()

    def set_windows(
        self, dashboard: webview.Window, overlay: webview.Window | None = None
    ) -> None:
        self._dashboard_window = dashboard
        self._overlay_window = overlay

    def _setup_polling_callback(self) -> None:
        def on_new_match(match: dict[str, Any]) -> None:
            logger.info("New match detected: %s", match.get("match_id"))
            self._compile_and_notify(source="AutoPolling")
            self.notify_frontend(
                "onAppStateUpdate",
                {
                    "active_match": match,
                    "cached_matches": self._match_service.cached_matches,
                },
            )

        self._on_new_match_cb = on_new_match

    def _setup_file_watcher(self) -> None:
        """Kích hoạt File Watcher theo dõi .env, overlay_config.json và avatars."""
        self._config_watcher = ConfigWatcher(
            config_path=BASE_DIR / "overlay_config.json",
            env_path=BASE_DIR / ".env",
            avatars_dir=AVATARS_DIR,
            poll_interval=0.5,
            debounce_seconds=0.3,
        )

        def on_cfg_changed():
            logger.info("overlay_config.json changed → Auto re-rendering")
            cfg = load_overlay_config()
            self._compile_and_notify(source="FileWatcher_Config")
            self.notify_frontend("onAppStateUpdate", {"overlay_config": cfg})

        def on_env_changed():
            logger.info(".env changed → Reloading config")
            from tft_studio.core.config import reload_env

            reload_env()
            cfg = AppConfig.load()
            self._match_service.config = cfg
            self._match_service.active_puuid = (
                None  # Reset PUUID để tra cứu theo Riot ID mới
            )
            self.notify_frontend("onAppStateUpdate", {"config": cfg.to_dict()})

            if cfg.api_key and cfg.game_name:

                def on_matches_fetched(matches):
                    if matches:
                        logger.info("Fetched %d matches after .env edit", len(matches))
                        self._compile_and_notify(source="LiveAPI_EnvUpdate")
                        self.notify_frontend(
                            "onAppStateUpdate",
                            {
                                "active_match": self._match_service.active_match,
                                "cached_matches": self._match_service.cached_matches,
                                "fetch_status": {
                                    "success": True,
                                    "message": (
                                        f"Đã nạp trận mới nhất của {cfg.game_name}#{cfg.tag_line}"
                                    ),
                                    "timestamp": time.time(),
                                },
                            },
                        )

                def on_matches_error(exc):
                    logger.warning(
                        "Failed to fetch matches for %s#%s: %s",
                        cfg.game_name,
                        cfg.tag_line,
                        exc,
                    )
                    self.notify_frontend(
                        "onAppStateUpdate",
                        {
                            "fetch_status": {
                                "success": False,
                                "error": str(exc),
                                "is_auth_error": "401" in str(exc)
                                or "403" in str(exc)
                                or "hết hạn" in str(exc),
                                "timestamp": time.time(),
                            },
                        },
                    )

                self._match_service.fetch_recent_matches_async(
                    game_name=cfg.game_name,
                    tag_line=cfg.tag_line,
                    region=cfg.region,
                    count=1,
                    on_complete=on_matches_fetched,
                    on_error=on_matches_error,
                )

        def on_avatars_changed():
            logger.info("Avatars changed → Refreshing overlay")
            self._compile_and_notify(source="FileWatcher_Avatars")

        self._config_watcher.on_config_changed = on_cfg_changed
        self._config_watcher.on_env_changed = on_env_changed
        self._config_watcher.on_avatars_changed = on_avatars_changed
        self._config_watcher.start()

    def notify_frontend(self, func_name: str, data: Any) -> None:
        """Đẩy sự kiện từ Python → Frontend Javascript an toàn."""
        js_data = json.dumps(data, ensure_ascii=False)
        script = f"if (window.{func_name}) {{ window.{func_name}({js_data}); }}"

        for win in (self._dashboard_window, self._overlay_window):
            if win:
                if win == self._overlay_window and not self._is_overlay_visible:
                    continue
                try:
                    win.evaluate_js(script)
                except Exception as e:
                    logger.debug("evaluate_js error on window: %s", e)

    # ----------------------------------------------------------------- #
    # Core: Biên dịch Overlay & Thông báo cập nhật
    # ----------------------------------------------------------------- #
    def _get_best_match_data(self) -> dict[str, Any] | None:
        """Lấy dữ liệu trận tốt nhất hiện có (memory cache → file cache)."""
        if self._match_service.active_match:
            return self._match_service.active_match

        if self._match_service.cached_matches:
            self._match_service.active_match = self._match_service.cached_matches[0]
            return self._match_service.active_match

        # Tìm file cache tự động — không hardcode tên người dùng
        candidates = [
            *OUTPUT_DIR.glob("clean_matches_*.json"),
            OUTPUT_DIR / "clean_matches_latest.json",
            resolve_resource("output/clean_matches_latest.json"),
        ]
        for cand in sorted(
            set(candidates),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        ):
            if cand.exists():
                try:
                    with open(cand, encoding="utf-8") as f:
                        cand_list = json.load(f)
                        if cand_list:
                            # Ưu tiên trận có người đứng top 1
                            match_data = next(
                                (
                                    m
                                    for m in cand_list
                                    if any(
                                        p.get("placement") == 1
                                        for p in m.get("lobby", [])
                                    )
                                ),
                                cand_list[0],
                            )
                            self._match_service.cached_matches = cand_list
                            self._match_service.active_match = match_data
                            return match_data
                except Exception as e:
                    logger.warning("Failed to read cache %s: %s", cand.name, e)
        return None

    def _compile_and_notify(self, source: str = "Local") -> dict[str, Any]:
        """
        Biên dịch overlay HTML → thông báo OBS/overlay tabs cập nhật mượt mà (không reload).
        Thay vì broadcast tới các máy khác, chỉ notify local WS để DOM-swap.
        """
        match_data = self._get_best_match_data()
        if not match_data:
            logger.error("No match data to compile overlay")
            return {
                "success": False,
                "error": "Chưa có dữ liệu trận đấu. Vui lòng fetch matches trước.",
            }

        match_id = match_data.get("match_id", "LIVE_MATCH")
        output_html = OUTPUT_DIR / "overlay.html"
        gen_cfg = load_generator_config(BASE_DIR / "overlay_config.json")

        # 1. Sinh file overlay.html
        generate_overlay_html(match_data, gen_cfg, output_html)

        # 2. Xuất PNG ngầm
        output_png = OUTPUT_DIR / "overlay_latest.png"
        threading.Thread(
            target=export_html_to_png,
            args=(output_html, output_png, 1920, 1080),
            daemon=True,
        ).start()

        # 3. Reload Overlay Window trên Desktop (nếu có)
        if self._overlay_window:
            try:
                server_port = gen_cfg.get("server_port", 8080)
                self._overlay_window.evaluate_js(
                    f"if (window.location.pathname === '/overlay') "
                    f"{{ if (window.smoothUpdate) {{ window.smoothUpdate(); }} "
                    f"  else {{ window.location.reload(); }} }}"
                    f"else {{ window.location.href = 'http://127.0.0.1:{server_port}/overlay'; }}"
                )
                self._overlay_window.show()
                self._is_overlay_visible = True
            except Exception as e:
                logger.debug("Failed to update overlay window: %s", e)
                try:
                    server_port = gen_cfg.get("server_port", 8080)
                    self._overlay_window.load_url(
                        f"http://127.0.0.1:{server_port}/overlay"
                    )
                    self._overlay_window.show()
                    self._is_overlay_visible = True
                except Exception as exc:
                    logger.debug("Could not show overlay window: %s", exc)

        # 4. Thông báo WS cục bộ → OBS Browser Source tự fetch & DOM-swap
        notify_sync(
            {
                "type": "OVERLAY_RENDERED",
                "success": True,
                "match_id": match_id,
                "source": source,
                "timestamp": time.time(),
            }
        )

        return {
            "success": True,
            "match_id": match_id,
            "mode": source,
            "png_path": str(output_png.resolve()),
        }

    def render_overlay(
        self, transform: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Xử lý nút 'Render':
        1. Render ngay từ cache cục bộ (<50ms).
        2. Chạy ngầm kiểm tra Riot Live API, nếu có trận mới → tự động cập nhật.
        """
        logger.info("Rendering overlay (standalone mode)")

        # Phase 1: Render ngay lập tức
        res = self._compile_and_notify(source="InstantRender")

        # Phase 2: Async check Riot API
        cfg = AppConfig.load()
        if cfg.api_key and cfg.api_key.strip() and cfg.game_name:

            def on_api_complete(matches):
                if matches:
                    logger.info(
                        "Riot API returned %d matches → updating overlay", len(matches)
                    )
                    self._compile_and_notify(source="RiotLiveAPI")
                    self.notify_frontend(
                        "onAppStateUpdate",
                        {
                            "active_match": self._match_service.active_match,
                            "cached_matches": self._match_service.cached_matches,
                        },
                    )

            def on_api_error(exc):
                logger.warning("Riot API check failed (using cached data): %s", exc)
                self.notify_frontend(
                    "onAppStateUpdate",
                    {
                        "fetch_status": {
                            "success": False,
                            "error": str(exc),
                            "is_auth_error": "401" in str(exc)
                            or "403" in str(exc)
                            or "hết hạn" in str(exc),
                            "timestamp": time.time(),
                        }
                    },
                )

            self._match_service.fetch_recent_matches_async(
                game_name=cfg.game_name,
                tag_line=cfg.tag_line,
                region=cfg.region,
                count=1,
                on_complete=on_api_complete,
                on_error=on_api_error,
            )

        return res

    def toggle_overlay_visibility(self, visible: bool) -> bool:
        """Bật/tắt hiển thị Cửa sổ Overlay."""
        if self._overlay_window:
            if visible:
                self._overlay_window.show()
                self._is_overlay_visible = True
            else:
                self._overlay_window.hide()
                self._is_overlay_visible = False
            return self._is_overlay_visible
        return False

    def close_panel(self) -> None:
        """Đóng ứng dụng."""
        logger.info("Closing studio")
        if self._dashboard_window:
            self._dashboard_window.destroy()

    # ----------------------------------------------------------------- #
    # API bổ trợ
    # ----------------------------------------------------------------- #
    def get_transform(self) -> dict[str, Any]:
        """Lấy cấu hình transform hiện tại (đã loại bỏ, trả về rỗng)."""
        return {}

    def get_app_state(self) -> dict[str, Any]:
        """Trả về toàn bộ trạng thái ứng dụng."""
        cfg = AppConfig.load()
        overlay_cfg = load_overlay_config()

        cached = self._match_service.cached_matches
        if not cached:
            # Tự động load từ file cache mới nhất
            cache_files = sorted(
                OUTPUT_DIR.glob("clean_matches_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if cache_files:
                try:
                    with open(cache_files[0], encoding="utf-8") as f:
                        cached = json.load(f)
                        self._match_service.cached_matches = cached
                        if cached and not self._match_service.active_match:
                            self._match_service.active_match = cached[0]
                except Exception as e:
                    logger.warning("Không thể đọc cache: %s", e)

        return {
            "config": cfg.to_dict(),
            "overlay_config": overlay_cfg,
            "cached_matches": cached,
            "active_match": self._match_service.active_match,
            "is_polling": self._match_service.is_polling_active(),
            "is_overlay_visible": self._is_overlay_visible,
            "is_configured": bool(cfg.api_key and cfg.game_name),
            "obs_url": "http://localhost:8080/overlay",
        }

    def get_studio_token(self) -> str:
        """Lấy token xác thực cục bộ (S1, S2)."""
        from tft_studio.api.hub import get_current_token

        return get_current_token()

    def is_configured(self) -> bool:
        """Kiểm tra xem người dùng đã cấu hình API key chưa."""
        cfg = AppConfig.load()
        return bool(cfg.api_key and cfg.api_key.startswith("RGAPI-") and cfg.game_name)

    def save_app_config(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """Lưu cấu hình Riot API vào file .env."""
        try:
            AppConfig.save_env_values(config_data)
            new_cfg = AppConfig.load()
            self._match_service.config = new_cfg
            return {"success": True, "config": new_cfg.to_dict()}
        except Exception as e:
            logger.error("Failed to save config: %s", e)
            return {"success": False, "error": str(e)}

    def save_overlay_config(self, overlay_data: dict[str, Any]) -> dict[str, Any]:
        """Lưu cấu hình hiển thị giải đấu."""
        try:
            updated = save_overlay_config(overlay_data)
            self.notify_frontend("onAppStateUpdate", {"overlay_config": updated})
            return {"success": True, "overlay_config": updated}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_overlay_transform(
        self, transform_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Cập nhật transform cho Overlay (đã loại bỏ)."""
        return {"success": True}

    def get_augments_list(self) -> list[dict[str, Any]]:
        """Trả về danh sách lõi nâng cấp tiếng Anh (en_US) từ DDragon, sắp xếp A-Z.
        Mỗi mục: { "id": str, "name": str, "image": str, "tier": int, "is_destiny": bool }
        """
        try:
            from tft_studio.data.parser import get_ddragon_loader

            loader = get_ddragon_loader("en_US")
            seen: set[tuple] = set()
            result = []
            for aug_id, aug_name in loader.augments.items():
                img = loader.augment_images.get(aug_id, "")
                if not aug_name or not img:
                    continue
                dedup_key = (aug_name, img)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Phân loại bậc (tier: 1, 2, 3) và nhận diện lõi Destiny
                s_img = img.lower()
                s_name = aug_name.lower()
                s_id = str(aug_id).lower()
                if any(x in s_img for x in ("_iii", "-iii", "3.png")) or s_id.endswith("3") or "prismatic" in s_name:
                    tier = 3
                elif any(x in s_img for x in ("_ii", "-ii", "2.png")) or s_id.endswith("2") or "gold" in s_name:
                    tier = 2
                elif any(x in s_img for x in ("_i", "-i", "1.png")) or s_id.endswith("1") or "silver" in s_name:
                    tier = 1
                else:
                    tier = 2

                is_destiny = "destiny" in s_name or "destiny" in s_img or "vận mệnh" in s_name

                result.append({
                    "id": aug_id,
                    "name": aug_name,
                    "image": img,
                    "tier": tier,
                    "is_destiny": is_destiny,
                })
            result.sort(key=lambda x: x["name"].lower())
            return result
        except Exception as e:
            logger.error("get_augments_list failed: %s", e)
            return []

    def save_custom_augments(self, augments: list) -> dict[str, Any]:
        """Lưu các lõi nâng cấp đã chọn (3-6 lõi) vào overlay_config.json và re-compile overlay.
        Args:
            augments: Danh sách tối đa 6 phần tử — mỗi phần tử là tên file ảnh (str)
                      hoặc None/empty để dùng Auto (lấy từ trận đấu).
        """
        try:
            from tft_studio.data.parser import validate_custom_augment

            normalized: list = []
            for item in (augments or [])[:6]:
                if item is not None and not validate_custom_augment(item):
                    return {
                        "success": False,
                        "error": f"Định danh lõi nâng cấp không hợp lệ: {item}",
                    }
                if isinstance(item, str) and item.strip():
                    normalized.append(item.strip())
                else:
                    normalized.append(None)

            current = load_overlay_config()
            if all(v is None for v in normalized):
                # Tất cả trống → xóa custom_augments để dùng Auto từ trận đấu
                current.pop("custom_augments", None)
            else:
                current["custom_augments"] = normalized

            updated = save_overlay_config(current)
            self.notify_frontend("onAppStateUpdate", {"overlay_config": updated})

            # Re-compile overlay HTML ngay lập tức
            result = self._compile_and_notify(source="AugmentsUpdate_PyWebView")
            return {"success": True, "overlay_config": updated, "compile": result}
        except Exception as e:
            logger.error("save_custom_augments failed: %s", e)
            return {"success": False, "error": str(e)}

    def fetch_matches(self, count: int = 5) -> list[dict[str, Any]]:
        """Lấy danh sách các trận gần nhất từ Riot API."""
        cfg = AppConfig.load()

        def on_progress(pct: int, status_text: str) -> None:
            self.notify_frontend(
                "onProgressUpdate", {"pct": pct, "status": status_text}
            )

        try:
            matches = self._match_service.fetch_recent_matches(
                game_name=cfg.game_name,
                tag_line=cfg.tag_line,
                region=cfg.region,
                count=count,
                progress_callback=on_progress,
            )
            self.notify_frontend(
                "onAppStateUpdate",
                {
                    "cached_matches": matches,
                    "active_match": self._match_service.active_match,
                },
            )
            return matches
        except Exception as exc:
            logger.error("Failed to fetch matches: %s", exc)
            raise exc

    def set_active_match(self, match_id: str) -> dict[str, Any] | None:
        """Chọn trận đấu muốn hiển thị trên Overlay."""
        active = self._match_service.set_active_match_by_id(match_id)
        if active:
            self.notify_frontend("onAppStateUpdate", {"active_match": active})
        return active

    def toggle_overlay(self) -> bool:
        """Bật/tắt ẩn hiện cửa sổ Overlay."""
        if not self._overlay_window:
            return False

        if self._is_overlay_visible:
            self._overlay_window.hide()
            self._is_overlay_visible = False
        else:
            self._overlay_window.show()
            self._is_overlay_visible = True

        self.notify_frontend(
            "onAppStateUpdate", {"is_overlay_visible": self._is_overlay_visible}
        )
        return self._is_overlay_visible

    def show_overlay(self) -> None:
        if self._overlay_window:
            self._overlay_window.show()
            self._is_overlay_visible = True
            self.notify_frontend("onAppStateUpdate", {"is_overlay_visible": True})

    def hide_overlay(self) -> None:
        if self._overlay_window:
            self._overlay_window.hide()
            self._is_overlay_visible = False
            self.notify_frontend("onAppStateUpdate", {"is_overlay_visible": False})

    def export_png(self) -> dict[str, Any]:
        """Xuất ảnh PNG 1920x1080."""
        output_png = OUTPUT_DIR / "overlay_latest.png"
        html_file = OUTPUT_DIR / "overlay.html"

        if not html_file.exists():
            cfg = load_generator_config(BASE_DIR / "overlay_config.json")
            m = self._match_service.active_match
            if not m and self._match_service.cached_matches:
                m = self._match_service.cached_matches[0]
            if m:
                generate_overlay_html(m, cfg, html_file)

        ok = export_html_to_png(html_file, output_png, width=1920, height=1080)
        if ok:
            return {"success": True, "path": str(output_png.resolve())}
        else:
            return {"success": False, "error": "Không thể kết xuất ảnh PNG."}

    def set_auto_polling(self, enabled: bool, interval: int = 60) -> bool:
        """Bật/Tắt luồng tự động phát hiện trận mới."""
        if enabled:
            self._match_service.start_auto_polling(
                interval_seconds=interval, on_new_match_callback=self._on_new_match_cb
            )
        else:
            self._match_service.stop_auto_polling()

        is_p = self._match_service.is_polling_active()
        self.notify_frontend("onAppStateUpdate", {"is_polling": is_p})
        return is_p

    def pick_avatar_file(self, player_name: str) -> dict[str, Any]:
        """Mở hộp thoại chọn ảnh avatar cho tuyển thủ."""
        if not self._dashboard_window:
            return {"success": False, "error": "Cửa sổ chưa khởi tạo"}

        file_types = ("Image Files (*.png;*.jpg;*.jpeg;*.webp)", "All files (*.*)")
        result = self._dashboard_window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types
        )

        if result and len(result) > 0:
            chosen_path = Path(result[0])
            is_valid, err_msg = validate_avatar_file(chosen_path)
            if not is_valid:
                logger.warning("Avatar validation failed for %s: %s", chosen_path, err_msg)
                return {"success": False, "error": err_msg}

            clean_name = "".join(
                c if c.isalnum() else "_" for c in player_name
            ).lower()
            dest_file = AVATARS_DIR / f"{clean_name}{chosen_path.suffix.lower()}"
            shutil.copy2(chosen_path, dest_file)

            rel_path = f"assets/avatars/{dest_file.name}"
            cfg = load_overlay_config()
            if "player_avatars" not in cfg:
                cfg["player_avatars"] = {}
            cfg["player_avatars"][player_name] = rel_path
            save_overlay_config(cfg)

            self.notify_frontend("onAppStateUpdate", {"overlay_config": cfg})
            return {"success": True, "path": rel_path}

        return {"success": False, "canceled": True}

    def get_obs_info(self) -> dict[str, Any]:
        """Thông tin để cài đặt OBS Browser Source."""
        cfg = load_overlay_config()
        port = cfg.get("server_port", 8080)
        return {
            "obs_url": f"http://localhost:{port}/overlay",
            "control_url": f"http://localhost:{port}/app",
            "width": 1920,
            "height": 1080,
            "is_server_running": is_server_running(),
            "instructions": [
                "Mở OBS Studio",
                "Add Source → Browser Source",
                f"URL: http://localhost:{port}/overlay",
                "Width: 1920, Height: 1080",
                "Tick 'Refresh browser when scene becomes active'",
            ],
        }

    def get_riot_config(self) -> dict[str, Any]:
        """Lấy thông tin cấu hình Riot hiện tại."""
        cfg = AppConfig.load()
        masked_key = (
            f"{cfg.api_key[:6]}...{cfg.api_key[-4:]}"
            if len(cfg.api_key) > 10
            else (cfg.api_key or "")
        )
        return {
            "riot_id": cfg.riot_id or f"{cfg.game_name}#{cfg.tag_line}",
            "game_name": cfg.game_name,
            "tag_line": cfg.tag_line,
            "region": cfg.region,
            "api_key_masked": masked_key,
            "has_api_key": bool(cfg.api_key),
            "is_polling": self._match_service.is_polling_active(),
            "active_match_id": self._match_service.last_seen_match_id,
        }

    def update_riot_id(self, riot_id_str: str) -> dict[str, Any]:
        """Cập nhật Riot ID (GameName#TagLine) và lưu vào .env."""
        riot_id_str = riot_id_str.strip()
        if not riot_id_str:
            return {"success": False, "error": "Riot ID không được để trống"}
        if "#" not in riot_id_str:
            return {
                "success": False,
                "error": "Riot ID phải kèm theo #TAG (ví dụ: TenNguoiChoi#VN2)",
            }

        AppConfig.save_env_values({"riot_id": riot_id_str})
        cfg = AppConfig.load()
        self._match_service.config = cfg
        self._match_service.active_puuid = None

        return self.fetch_live_now()

    def update_api_key(self, api_key_str: str) -> dict[str, Any]:
        """Cập nhật Riot API Key mới vào .env."""
        api_key_str = api_key_str.strip()
        if not api_key_str:
            return {"success": False, "error": "API Key không được để trống"}

        AppConfig.save_env_values({"api_key": api_key_str})
        cfg = AppConfig.load()
        self._match_service.config = cfg
        self._match_service.active_puuid = None

        return {"success": True, "message": "Đã lưu API Key mới vào .env"}

    def fetch_live_now(self) -> dict[str, Any]:
        """Kích hoạt tải trận đấu mới nhất ngay lập tức."""
        cfg = AppConfig.load()
        if not cfg.api_key:
            return {"success": False, "error": "Chưa điền RIOT_API_KEY trong file .env"}
        if not cfg.game_name:
            return {"success": False, "error": "Chưa điền RIOT_ID trong file .env"}

        def on_complete(matches):
            if matches:
                self._compile_and_notify(source="ManualLiveFetch")
                self.notify_frontend(
                    "onAppStateUpdate",
                    {
                        "active_match": self._match_service.active_match,
                        "cached_matches": self._match_service.cached_matches,
                        "fetch_status": {
                            "success": True,
                            "message": (
                                f"Đã tải thành công trận mới của {cfg.game_name}#{cfg.tag_line}"
                            ),
                            "timestamp": time.time(),
                        },
                    },
                )

        def on_error(exc):
            logger.warning("Manual live fetch error: %s", exc)
            self.notify_frontend(
                "onAppStateUpdate",
                {
                    "fetch_status": {
                        "success": False,
                        "error": str(exc),
                        "is_auth_error": "401" in str(exc)
                        or "403" in str(exc)
                        or "hết hạn" in str(exc),
                        "timestamp": time.time(),
                    }
                },
            )

        self._match_service.fetch_recent_matches_async(
            game_name=cfg.game_name,
            tag_line=cfg.tag_line,
            region=cfg.region,
            count=1,
            on_complete=on_complete,
            on_error=on_error,
        )

        return {
            "success": True,
            "message": f"Đang kết nối Riot API tải trận của {cfg.game_name}#{cfg.tag_line}...",
        }
