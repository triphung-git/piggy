"""
src/tft_studio/render/generator.py
----------------------------------
Tạo file HTML Overlay 1920x1080 từ dữ liệu Clean Match JSON của TFT.
Dựa trên phong cách thiết kế giải đấu Esports HOSC 2026.
"""

from __future__ import annotations

import contextlib
import html
import json
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from tft_studio.core.paths import get_app_dir, get_bundle_dir, resolve_resource
from tft_studio.data.parser import get_ddragon_loader

# Đảm bảo terminal Windows in UTF-8
if sys.platform == "win32":
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("overlay_generator")

BASE_DIR = get_app_dir()
BUNDLE_DIR = get_bundle_dir()
TEMPLATES_DIR = resolve_resource("templates")
ASSETS_DIR = resolve_resource("assets")
OUTPUT_DIR = BASE_DIR / "output"
DDRAGON_IMG_DIR = resolve_resource("TFT_DDragon/img")

DEFAULT_CONFIG_FILE = BASE_DIR / "overlay_config.json"
DEFAULT_TEMPLATE_FILE = resolve_resource("templates/overlay.html")
DEFAULT_CSS_FILE = resolve_resource("templates/overlay.css")


def load_overlay_config(config_path: Path) -> dict:
    """Nạp file cấu hình overlay tùy chỉnh."""
    default_config = {
        "tournament_title": "HOSC 2026",
        "stage_title": "LAST CHANCE QUALIFIER",
        "game_title": "TEAMFIGHT TACTICS",
        "server_port": 8080,
        "background_image": "../assets/background.png",
        "player_avatars": {},
    }
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = json.load(f)
                default_config.update(loaded)
        except Exception as exc:
            logger.warning("Không thể đọc file config %s: %s", config_path, exc)
    return default_config


_IMAGE_SETS: dict[str, set[str]] = {}


def get_image_set(folder_name: str) -> set[str]:
    """Cache danh sách tên ảnh để tra cứu O(1) trong RAM, tránh I/O quét đĩa."""
    if folder_name not in _IMAGE_SETS:
        folder = DDRAGON_IMG_DIR / folder_name
        if folder.exists():
            try:
                _IMAGE_SETS[folder_name] = {f.name for f in folder.iterdir() if f.is_file()}
            except Exception:
                _IMAGE_SETS[folder_name] = set()
        else:
            _IMAGE_SETS[folder_name] = set()
    return _IMAGE_SETS[folder_name]


def find_avatar_url(player_name: str, display_name: str, companion_img: str, config: dict) -> str:
    """
    Xác định URL ảnh chân dung đại diện:
    1. Tra cứu trong overlay_config.json ("player_avatars")
    2. Tra cứu trong thư mục assets/avatars/{name}.png
    3. Fallback: DDragon linh thú companion_image (tra cứu O(1) RAM)
    4. Fallback cuối: linh thú mặc định
    """
    avatars_map = config.get("player_avatars", {})

    # Kiểm tra map cấu hình
    for key in (player_name, display_name, player_name.split("#")[0]):
        if avatars_map.get(key):
            avatar_path = BASE_DIR / avatars_map[key]
            if avatar_path.exists():
                rel_clean = avatars_map[key].replace("\\", "/")
                return f"../{rel_clean}"

    # Kiểm tra thư mục assets/avatars/
    avatars_folder = ASSETS_DIR / "avatars"
    clean_name = "".join(c if c.isalnum() else "_" for c in display_name).lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = avatars_folder / f"{display_name}{ext}"
        if candidate.exists():
            return f"../assets/avatars/{candidate.name}"
        candidate_clean = avatars_folder / f"{clean_name}{ext}"
        if candidate_clean.exists():
            return f"../assets/avatars/{candidate_clean.name}"

    # Fallback: Linh thú DDragon (tra cứu O(1) trong RAM)
    tacticians_set = get_image_set("tactician")
    if companion_img and companion_img in tacticians_set:
        return f"../TFT_DDragon/img/tactician/{companion_img}"

    # Fallback nếu không có gì: Tìm một linh thú có sẵn
    default_tacticians = [
        "Tooltip_ChibiKatarina_Base_Classic_Tier1.png",
        "Tooltip_PenguFeatherknight_Base_Tier1.png",
    ]
    for def_tact in default_tacticians:
        if def_tact in tacticians_set:
            return f"../TFT_DDragon/img/tactician/{def_tact}"

    # Fallback cuối
    return "../assets/background.png"


_AUGMENT_CACHE: dict[str, dict] = {}


def resolve_custom_augment(item: Any, config: dict) -> dict:
    """Xác định tên và ảnh của lõi nâng cấp từ cấu hình (hỗ trợ file, tên Việt/Anh, mã ID, không phân biệt hoa thường/đuôi .png)."""
    if isinstance(item, dict):
        return {
            "name": item.get("name", "Augment"),
            "image": item.get("image", ""),
        }
    if isinstance(item, str):
        val = item.strip()
        if not val:
            return {"name": "Augment", "image": ""}

        cache_key = f"{val}_{config.get('language', 'vi_VN')}"
        if cache_key in _AUGMENT_CACHE:
            return _AUGMENT_CACHE[cache_key]

        aug_set = get_image_set("augment")
        aug_lower = {f.lower(): f for f in aug_set}

        # 1. Khớp trực tiếp tên file ảnh có trong thư mục (chính xác hoặc không phân biệt hoa thường)
        if val in aug_set:
            res = {"name": Path(val).stem, "image": val}
            _AUGMENT_CACHE[cache_key] = res
            return res
        if val.lower() in aug_lower:
            res = {"name": Path(val).stem, "image": aug_lower[val.lower()]}
            _AUGMENT_CACHE[cache_key] = res
            return res

        # 2. Xóa đuôi file nếu người dùng gõ nhầm đuôi .png/.jpg vào tên lõi (vd: "Cluttered Mind.png" -> "Cluttered Mind")
        query = re.sub(r'\.(png|jpg|jpeg|webp)$', '', val, flags=re.IGNORECASE).strip()
        query_norm = re.sub(r'[^a-zA-Z0-9]', '', query).lower()

        lang = config.get("language", "vi_VN")
        loaders = [get_ddragon_loader(lang)]
        if lang != "en_US":
            with contextlib.suppress(Exception):
                loaders.append(get_ddragon_loader("en_US"))

        # 3. Tìm theo ID hoặc Tên trong từ điển Data Dragon (tiếng Việt và tiếng Anh)
        for loader in loaders:
            # Khớp chính xác ID (vd: "DA_URF", "TFT7_Augment_ClutteredMind")
            for aid, img in loader.augment_images.items():
                aid_norm = re.sub(r'[^a-zA-Z0-9]', '', aid).lower()
                if query.lower() == aid.lower() or (query_norm and query_norm == aid_norm):
                    actual_img = img if img in aug_set else aug_lower.get(img.lower(), "")
                    res = {"name": loader.augments.get(aid, query), "image": actual_img}
                    _AUGMENT_CACHE[cache_key] = res
                    return res

            # Khớp chính xác Tên (vd: "Bừa Bộn", "Cluttered Mind", "U.R.F.")
            for aid, aname in loader.augments.items():
                aname_norm = re.sub(r'[^a-zA-Z0-9]', '', aname).lower()
                if query.lower() == aname.lower() or (query_norm and query_norm == aname_norm):
                    raw_img = loader.augment_images.get(aid, "")
                    actual_img = raw_img if raw_img in aug_set else aug_lower.get(raw_img.lower(), "")
                    res = {"name": aname, "image": actual_img}
                    _AUGMENT_CACHE[cache_key] = res
                    return res

            # Khớp một phần Tên
            for aid, aname in loader.augments.items():
                aname_norm = re.sub(r'[^a-zA-Z0-9]', '', aname).lower()
                if query_norm and query_norm in aname_norm:
                    raw_img = loader.augment_images.get(aid, "")
                    actual_img = raw_img if raw_img in aug_set else aug_lower.get(raw_img.lower(), "")
                    res = {"name": aname, "image": actual_img}
                    _AUGMENT_CACHE[cache_key] = res
                    return res

            # Khớp một phần ID
            for aid, img in loader.augment_images.items():
                aid_norm = re.sub(r'[^a-zA-Z0-9]', '', aid).lower()
                if query_norm and query_norm in aid_norm:
                    actual_img = img if img in aug_set else aug_lower.get(img.lower(), "")
                    res = {"name": loader.augments.get(aid, query), "image": actual_img}
                    _AUGMENT_CACHE[cache_key] = res
                    return res

        # 4. Tìm kiếm mờ theo tên file ảnh trong thư mục augment
        if query_norm:
            for f in aug_set:
                f_norm = re.sub(r'[^a-zA-Z0-9]', '', f).lower()
                if query_norm in f_norm:
                    res = {"name": query, "image": f}
                    _AUGMENT_CACHE[cache_key] = res
                    return res

        res = {"name": val, "image": ""}
        _AUGMENT_CACHE[cache_key] = res
        return res
    return {"name": "Augment", "image": ""}


def build_augments_html(augments_detailed: list[dict], config: dict | None = None) -> str:
    """Tạo HTML cho 3 lõi nâng cấp với hỗ trợ slot None (Auto từ trận đấu).

    Logic ưu tiên theo từng slot:
    - custom_augments = None/không có → dùng augments_detailed từ trận đấu cho cả 3 slot.
    - custom_augments = [item0, None, item2] → slot 1 dùng auto từ trận đấu, slot 0 & 2 dùng custom.
    - item có thể là: str (tên file ảnh / tên lõi tiếng Anh) hoặc None.
    """
    cfg = config or {}
    custom = cfg.get("custom_augments", None)
    aug_set = get_image_set("augment")

    # Chuẩn bị nguồn dữ liệu auto (từ trận đấu)
    auto_source = list(augments_detailed[:3]) if augments_detailed else []

    # Xây dựng danh sách các slot (tối thiểu 3 slot, tối đa 6 slot khi có lõi Destiny)
    items_to_render: list[dict | None] = []
    if custom and isinstance(custom, list):
        for i, item in enumerate(custom[:6]):
            if item is None or (isinstance(item, str) and not item.strip()):
                # Slot này để Auto — lấy từ trận đấu nếu có
                items_to_render.append(auto_source[i] if i < len(auto_source) else None)
            else:
                items_to_render.append(resolve_custom_augment(item, cfg))
    elif augments_detailed:
        items_to_render = auto_source
    # else: không có gì → danh sách trống

    slots = []
    for aug in items_to_render:
        if aug is None:
            slots.append('<div class="augment-slot empty-slot" title="Chưa có lõi"></div>')
            continue
        img_name = aug.get("image") or ""
        name = aug.get("name") or "Augment"
        safe_name = html.escape(str(name), quote=True)
        if img_name and img_name in aug_set:
            img_path = f"../TFT_DDragon/img/augment/{img_name}"
            slot_html = f'<div class="augment-slot" title="{safe_name}"><img src="{img_path}" alt="{safe_name}"></div>'
        else:
            # Fallback thanh lịch nếu không tìm thấy file ảnh (không bao giờ sinh thẻ img lỗi [x])
            slot_html = f'<div class="augment-slot empty-slot" title="{safe_name}"><span style="font-size:10px;text-align:center;padding:4px;color:#caa867;line-height:1.2;font-weight:700;">{safe_name}</span></div>'
        slots.append(slot_html)

    # Đảm bảo luôn có đủ 3 ô lõi
    while len(slots) < 3:
        slots.append('<div class="augment-slot empty-slot" title="Chưa có lõi"></div>')

    return "\n              ".join(slots)


def build_units_html(units: list[dict]) -> str:
    """Tạo HTML cho dải tướng trên bàn cờ của Top 1 với Image Guard."""
    champ_set = get_image_set("champion")
    item_set = get_image_set("item")
    unit_cards = []

    for u in units:
        tier = max(1, min(4, u.get("tier", 1)))
        cost = u.get("cost", 1)
        name = u.get("name", "Champion")
        safe_name = html.escape(str(name), quote=True)
        char_img = u.get("image", "")
        img_url = f"../TFT_DDragon/img/champion/{char_img}" if (char_img and char_img in champ_set) else ""

        # Sinh danh sách các ngôi sao sử dụng ảnh assets/stars.png
        stars_html = "".join(
            ['<img src="../assets/stars.png" class="star-icon" alt="★">' for _ in range(tier)]
        )

        items_html = []
        raw_items = u.get("items_detailed", [])
        for item in raw_items[:3]:
            iimg = item.get("image", "")
            iname = item.get("name", "Trang bị")
            safe_iname = html.escape(str(iname), quote=True)
            if iimg and iimg in item_set:
                items_html.append(
                    f'<div class="item-slot" title="{safe_iname}"><img src="../TFT_DDragon/img/item/{iimg}" alt="{safe_iname}"></div>'
                )
        items_row_content = "".join(items_html)

        champ_content = f'<img src="{img_url}" alt="{safe_name}">' if img_url else f'<span style="font-size:10px;color:#caa867;display:flex;align-items:center;justify-content:center;height:100%;">{html.escape(str(name)[:4])}</span>'

        card = f"""
        <div class="unit-card">
          <div class="star-rating-bar">
            {stars_html}
          </div>
          <div class="champion-frame cost-{cost}">
            {champ_content}
          </div>
          <div class="items-row">
            {items_row_content}
          </div>
        </div>
        """
        unit_cards.append(card.strip())

    return "\n        ".join(unit_cards)


def build_lobby_standings_html(lobby: list[dict]) -> str:
    """Tạo HTML cho bảng xếp hạng Top 2 -> Top 8."""
    rows = []
    rank_suffixes = {
        2: "2ND",
        3: "3RD",
        4: "4TH",
        5: "5TH",
        6: "6TH",
        7: "7TH",
        8: "8TH",
    }

    standing_players = [p for p in lobby if p.get("placement", 0) >= 2][:7]

    for p in standing_players:
        place = p.get("placement", 2)
        rank_text = rank_suffixes.get(place, f"{place}TH")
        display_name = p.get("game_name") or p.get("display_name") or p.get("player_name", "").split("#")[0]
        safe_display_name = html.escape(str(display_name))
        points = p.get("esports_points", max(1, 9 - place))

        row_html = f"""
        <div class="standing-row">
          <div class="standing-rank">{rank_text}</div>
          <div class="standing-name-box">
            <span class="standing-name">{safe_display_name}</span>
          </div>
          <div class="standing-pts">
            <span class="pts-num">{points}</span>
            <span class="pts-text">ĐIỂM</span>
          </div>
        </div>
        """
        rows.append(row_html.strip())

    return "\n        ".join(rows)


_TEMPLATE_CACHE: str = ""
_TEMPLATE_MTIME: float = 0.0


def _get_html_template() -> str:
    """Nạp template HTML với invalidation theo mtime — tự cập nhật khi file thay đổi."""
    global _TEMPLATE_CACHE, _TEMPLATE_MTIME
    try:
        current_mtime = DEFAULT_TEMPLATE_FILE.stat().st_mtime
        if not _TEMPLATE_CACHE or current_mtime != _TEMPLATE_MTIME:
            with open(DEFAULT_TEMPLATE_FILE, encoding="utf-8") as f:
                _TEMPLATE_CACHE = f.read()
            _TEMPLATE_MTIME = current_mtime
    except Exception as exc:
        logger.warning("Không thể đọc template: %s", exc)
    return _TEMPLATE_CACHE


def generate_overlay_html(
    match_data: dict,
    config: dict,
    output_html_path: Path,
) -> Path:
    """Biên dịch template HTML với dữ liệu trận đấu và ghi ra file."""
    lobby = match_data.get("lobby", [])
    if not lobby:
        raise ValueError("Dữ liệu trận đấu không có thông tin lobby!")

    # 1. Tìm người chơi đạt Top 1
    top1 = next((p for p in lobby if p.get("placement") == 1), lobby[0])

    top1_player_name = top1.get("player_name", "Unknown")
    top1_display_name = top1.get("game_name") or top1.get("display_name") or top1_player_name.split("#")[0]
    top1_board_value = top1.get("board_value", 0)
    top1_companion_img = top1.get("companion_image", "")

    # 2. Chuẩn bị các thành phần
    avatar_url = find_avatar_url(top1_player_name, top1_display_name, top1_companion_img, config)
    augments_html = build_augments_html(top1.get("augments_detailed", []), config=config)
    units_html = build_units_html(top1.get("units", []))
    standings_html = build_lobby_standings_html(lobby)

    # 3. Đọc template từ RAM cache
    html_template = _get_html_template()

    # 4. Thay thế biến
    rendered = html_template.replace("{{ GAME_TITLE }}", html.escape(str(config.get("game_title", "TEAMFIGHT TACTICS"))))
    rendered = rendered.replace("{{ TOURNAMENT_TITLE }}", html.escape(str(config.get("tournament_title", "HOSC 2026 | TEAMFIGHT TACTICS"))))
    rendered = rendered.replace("{{ STAGE_TITLE }}", html.escape(str(config.get("stage_title", "LAST CHANCE QUALIFIER"))))
    rendered = rendered.replace("{{ TOP1_NAME }}", html.escape(str(top1_display_name)))
    rendered = rendered.replace("{{ TOP1_AVATAR_URL }}", html.escape(str(avatar_url), quote=True))
    rendered = rendered.replace("{{ TOP1_BOARD_VALUE }}", html.escape(str(top1_board_value)))
    rendered = rendered.replace("{{ TOP1_AUGMENTS_HTML }}", augments_html)
    rendered = rendered.replace("{{ TOP1_UNITS_HTML }}", units_html)
    rendered = rendered.replace("{{ LOBBY_STANDINGS_HTML }}", standings_html)

    # 5. Ghi file HTML đầu ra
    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    # 6. Đồng bộ file CSS sang output/ (chỉ copy nếu chưa có hoặc file nguồn mới hơn)
    output_css_path = output_html_path.parent / "overlay.css"
    if not output_css_path.exists() or (DEFAULT_CSS_FILE.exists() and output_css_path.stat().st_mtime < DEFAULT_CSS_FILE.stat().st_mtime):
        shutil.copy(DEFAULT_CSS_FILE, output_css_path)

    logger.info("Overlay created")
    return output_html_path
