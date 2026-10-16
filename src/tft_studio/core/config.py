"""
src/tft_studio/core/config.py
-----------------------------
Quản lý cấu hình tập trung cho ứng dụng Post-match TFT.
Hỗ trợ nạp và lưu động từ file .env và overlay_config.json.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any

from tft_studio.core.paths import get_appdata_dir, get_resource_dir

try:
    from dotenv import load_dotenv

    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

logger = logging.getLogger("config")

BASE_DIR = get_appdata_dir()
BUNDLE_DIR = get_resource_dir()
ENV_PATH = BASE_DIR / ".env"
OVERLAY_CONFIG_PATH = BASE_DIR / "overlay_config.json"



def reload_env() -> None:
    """Tải lại biến môi trường từ file .env."""
    if _HAS_DOTENV:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    else:
        if ENV_PATH.exists():
            with open(ENV_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        os.environ[k] = v


# Nạp lần đầu
reload_env()

# Bảng ánh xạ Server/Region sang Continental & Platform routing của Riot API
REGION_MAPPING: dict[str, dict[str, str]] = {
    # Đông Nam Á (SEA)
    "VN": {"account": "asia", "match": "sea", "platform": "VN2"},
    "VN2": {"account": "asia", "match": "sea", "platform": "VN2"},
    "SG": {"account": "asia", "match": "sea", "platform": "SG2"},
    "SG2": {"account": "asia", "match": "sea", "platform": "SG2"},
    "TW": {"account": "asia", "match": "sea", "platform": "TW2"},
    "TW2": {"account": "asia", "match": "sea", "platform": "TW2"},
    "TH": {"account": "asia", "match": "sea", "platform": "TH2"},
    "TH2": {"account": "asia", "match": "sea", "platform": "TH2"},
    "PH": {"account": "asia", "match": "sea", "platform": "PH2"},
    "PH2": {"account": "asia", "match": "sea", "platform": "PH2"},
    "SEA": {"account": "asia", "match": "sea", "platform": "SG2"},
    # Châu Á (Asia)
    "KR": {"account": "asia", "match": "asia", "platform": "KR"},
    "JP": {"account": "asia", "match": "asia", "platform": "JP1"},
    "JP1": {"account": "asia", "match": "asia", "platform": "JP1"},
    # Châu Mỹ & Châu Đại Dương (Americas)
    "NA": {"account": "americas", "match": "americas", "platform": "NA1"},
    "NA1": {"account": "americas", "match": "americas", "platform": "NA1"},
    "BR": {"account": "americas", "match": "americas", "platform": "BR1"},
    "BR1": {"account": "americas", "match": "americas", "platform": "BR1"},
    "LAN": {"account": "americas", "match": "americas", "platform": "LA1"},
    "LA1": {"account": "americas", "match": "americas", "platform": "LA1"},
    "LAS": {"account": "americas", "match": "americas", "platform": "LA2"},
    "LA2": {"account": "americas", "match": "americas", "platform": "LA2"},
    "OCE": {"account": "americas", "match": "americas", "platform": "OC1"},
    "OC1": {"account": "americas", "match": "americas", "platform": "OC1"},
    # Châu Âu (Europe)
    "EUW": {"account": "europe", "match": "europe", "platform": "EUW1"},
    "EUW1": {"account": "europe", "match": "europe", "platform": "EUW1"},
    "EUNE": {"account": "europe", "match": "europe", "platform": "EUN1"},
    "EUN1": {"account": "europe", "match": "europe", "platform": "EUN1"},
    "TR": {"account": "europe", "match": "europe", "platform": "TR1"},
    "TR1": {"account": "europe", "match": "europe", "platform": "TR1"},
    "RU": {"account": "europe", "match": "europe", "platform": "RU"},
}


class ConfigError(ValueError):
    """Lỗi cấu hình không hợp lệ."""


@dataclass
class AppConfig:
    api_key: str
    riot_id: str
    game_name: str
    tag_line: str
    region: str
    platform: str
    account_routing: str
    match_routing: str
    match_count: int = 5
    language: str = "vi_VN"
    output_dir: str = "output"

    def to_dict(self) -> dict[str, Any]:
        """Trả về dict an toàn cho frontend — KHÔNG bao giờ expose api_key."""
        d = asdict(self)
        if d.get("api_key"):
            d["api_key"] = "RGAPI-****"
        return d

    def to_dict_internal(self) -> dict[str, Any]:
        """Chỉ dùng nội bộ backend — có api_key đầy đủ."""
        return asdict(self)

    @classmethod
    def load(cls) -> AppConfig:
        """Đọc và kiểm tra tính hợp lệ của toàn bộ cấu hình từ .env."""
        reload_env()
        api_key = os.environ.get("RIOT_API_KEY", "").strip()

        raw_riot_id = os.environ.get("RIOT_ID", "").strip()
        parts = raw_riot_id.split("#", 1) if "#" in raw_riot_id else [raw_riot_id, ""]
        game_name = parts[0].strip()
        tag_line = parts[1].strip() if len(parts) > 1 else ""

        raw_region = os.environ.get("REGION", "VN").strip().upper()
        mapping = REGION_MAPPING.get(raw_region, REGION_MAPPING["VN"])

        try:
            match_count = int(os.environ.get("MATCH_COUNT", "5"))
            if match_count <= 0 or match_count > 100:
                match_count = 5
        except ValueError:
            match_count = 5

        language = os.environ.get("LANGUAGE", "vi_VN").strip() or "vi_VN"
        output_dir = os.environ.get("OUTPUT_DIR", "output").strip() or "output"

        return cls(
            api_key=api_key,
            riot_id=raw_riot_id,
            game_name=game_name,
            tag_line=tag_line,
            region=raw_region,
            platform=mapping["platform"],
            account_routing=mapping["account"],
            match_routing=mapping["match"],
            match_count=match_count,
            language=language,
            output_dir=output_dir,
        )

    @staticmethod
    def save_env_values(values: dict[str, Any]) -> None:
        """Lưu các giá trị cập nhật vào file .env."""
        current_lines: list[str] = []
        if ENV_PATH.exists():
            with open(ENV_PATH, encoding="utf-8") as f:
                current_lines = f.readlines()

        key_map = {
            "api_key": "RIOT_API_KEY",
            "riot_id": "RIOT_ID",
            "region": "REGION",
            "match_count": "MATCH_COUNT",
            "language": "LANGUAGE",
            "output_dir": "OUTPUT_DIR",
        }

        updated_keys = set()
        new_lines: list[str] = []

        for line in current_lines:
            stripped = line.strip()
            matched = False
            for v_key, env_var in key_map.items():
                if v_key in values and stripped.startswith(f"{env_var}="):
                    val = str(values[v_key])
                    new_lines.append(f"{env_var}={val}\n")
                    updated_keys.add(v_key)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)

        # Thêm các key chưa tồn tại trong file
        for v_key, env_var in key_map.items():
            if v_key in values and v_key not in updated_keys:
                new_lines.append(f"{env_var}={values[v_key]}\n")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        reload_env()


def load_overlay_config() -> dict[str, Any]:
    """Nạp file overlay_config.json với giá trị mặc định trung lập."""
    default_config: dict[str, Any] = {
        "tournament_title": "YOUR TOURNAMENT NAME",
        "stage_title": "STAGE / QUALIFIER",
        "game_title": "TEAMFIGHT TACTICS",
        "server_port": 8080,
        "background_image": "assets/background.png",
        "font_family": "League Spartan",
        "player_avatars": {},
        "custom_augments": [],
    }

    if OVERLAY_CONFIG_PATH.exists():
        try:
            with open(OVERLAY_CONFIG_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
                default_config.update(loaded)
        except Exception as exc:
            logger.warning("Không thể đọc overlay_config.json: %s", exc)

    return default_config


def save_overlay_config(data: dict[str, Any]) -> dict[str, Any]:
    """Lưu cập nhật vào file overlay_config.json."""
    current = load_overlay_config()
    current.update(data)
    with open(OVERLAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


def is_configured() -> bool:
    """Kiểm tra nhanh xem người dùng đã cấu hình Riot API key chưa."""
    reload_env()
    api_key = os.environ.get("RIOT_API_KEY", "").strip()
    riot_id = os.environ.get("RIOT_ID", "").strip()
    return bool(
        api_key
        and api_key.startswith("RGAPI-")
        and len(api_key) > 20
        and "#" in riot_id
    )
