"""
data_parser.py
--------------
Module bóc tách, chuẩn hóa và chuyển đổi dữ liệu Post-Match TFT.
Kết hợp kho dữ liệu Data Dragon (TFT_DDragon) để dịch các mã ID thô
(TFT16_Briar, TFT_Item_InfinityEdge...) thành tên hiển thị thân thiện (Tiếng Việt/Anh).
"""

from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("data_parser")

BASE_DIR = Path(__file__).resolve().parent.parent
DDRAGON_DATA_DIR = BASE_DIR / "TFT_DDragon" / "data"

# Tên chế độ chơi TFT phổ biến (Việt hóa)
POPULAR_QUEUES: dict[int | str, str] = {
    1090: "Đấu Thường (Normal)",
    1100: "Đấu Xếp Hạng (Ranked)",
    1110: "Hướng Dẫn (Tutorial)",
    1130: "Xúc Xắc Điên Cuồng (Hyper Roll)",
    1160: "Cặp Đôi Hoàn Hảo (Double Up)",
    1170: "Vận May Phú Quý (Fortune's Favor)",
    1210: "Kho Báu Cổ Điển Choncc",
    1220: "Thử Thách Của Tocker (PVE)",
    6100: "Đấu Trường Choncc",
    6120: "Tiệc Tùng Của Pengu",
}

# Quái thú & Thú triệu hồi đặc biệt Set 18 (sử dụng tài nguyên ảnh người dùng cung cấp)
SPECIAL_UNITS: dict[str, dict[str, Any]] = {
    "DA_Sentinel18": {
        "name": "Sentinel",
        "image": "TFT18_Sentinel_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_Brambleback18": {
        "name": "Brambleback",
        "image": "TFT18_Brambleback_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_CrimsonRaptor18": {
        "name": "Mama Beak",
        "image": "TFT18_Mama Beak_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_Krug18": {
        "name": "Krug",
        "image": "TFT18_Krug_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_Scuttlecrab18": {
        "name": "Scuttlecrab",
        "image": "TFT18_Scuttlecrab_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_Murkwolf18": {
        "name": "Murkwolf",
        "image": "TFT18_Murkwolf_splash_centered_24.TFT_Set18.png",
        "cost": 1,
    },
    "DA_Gromp18_AP": {
        "name": "Gromp",
        "image": "TFT18_Gromp_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_18_ElderDragon": {
        "name": "Elder Dragon",
        "image": "TFT18_Elder Dragon_splash_centered_24.TFT_Set18.jpg",
        "cost": 5,
    },
    "DA_Cinderling18": {
        "name": "Cinderling",
        "image": "TFT18_Cinderling_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
    "DA_18_Sentry": {
        "name": "Pebbles",
        "image": "TFT18_Pebbles_splash_centered_24.TFT_Set18.jpg",
        "cost": 1,
    },
}


class DDragonLoader:
    """Tải và lưu cache dữ liệu từ TFT_DDragon."""

    def __init__(self, language: str = "vi_VN") -> None:
        self.language = language
        self.lang_dir = DDRAGON_DATA_DIR / language
        if not self.lang_dir.exists():
            logger.warning(
                "Không tìm thấy thư mục ngôn ngữ '%s', chuyển sang 'en_US'", language
            )
            self.lang_dir = DDRAGON_DATA_DIR / "en_US"

        self.champions: dict[str, str] = {}
        self.champion_costs: dict[str, int] = {}
        self.champion_images: dict[str, str] = {}
        self.items: dict[str, str] = {}
        self.item_images: dict[str, str] = {}
        self.traits: dict[str, str] = {}
        self.trait_images: dict[str, str] = {}
        self.augments: dict[str, str] = {}
        self.augment_images: dict[str, str] = {}
        self.tacticians: dict[str, str] = {}
        self.tactician_images: dict[str, str] = {}
        self.queues: dict[str, str] = {}

        self._load_all()

    def _load_json_data(self, filename: str) -> dict:
        file_path = self.lang_dir / filename
        if not file_path.exists():
            # Thử tìm ở en_US nếu file ở vi_VN không có
            fallback_path = DDRAGON_DATA_DIR / "en_US" / filename
            if fallback_path.exists():
                file_path = fallback_path
            else:
                return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                return content.get("data", {})
        except Exception as exc:
            logger.warning("Không thể đọc file %s: %s", file_path, exc)
            return {}

    def _load_all(self) -> None:
        # 1. Tướng (Champions)
        raw_champs = self._load_json_data("champion.json")
        for key, val in raw_champs.items():
            cid = val.get("id") or key.split("/")[-1]
            cname = val.get("name") or cid
            cost = int(val.get("cost") or val.get("tier", 1))
            img = val.get("image", {}).get("full", "")
            self.champions[cid] = cname
            self.champions[key] = cname
            self.champion_costs[cid] = cost
            self.champion_costs[key] = cost
            self.champion_images[cid] = img
            self.champion_images[key] = img

        # 1b. Thêm các quân cờ quái thú Set 18 được người dùng cung cấp
        for cid, info in SPECIAL_UNITS.items():
            cname = info.get("name", cid)
            cost = int(info.get("cost", 1))
            img = info.get("image", "")
            self.champions[cid] = cname
            self.champion_costs[cid] = cost
            self.champion_images[cid] = img
            clean_k = cid.split("/")[-1]
            self.champions[clean_k] = cname
            self.champion_costs[clean_k] = cost
            self.champion_images[clean_k] = img

        # 2. Trang bị & Vật phẩm (Items)
        raw_items = self._load_json_data("item.json")
        for key, val in raw_items.items():
            iid = val.get("id") or key.split("/")[-1]
            iname = val.get("name") or iid
            img = val.get("image", {}).get("full", "")
            if iname:
                self.items[iid] = iname
                self.items[key] = iname
                self.item_images[iid] = img
                self.item_images[key] = img

        # 3. Tộc / Hệ (Traits)
        raw_traits = self._load_json_data("trait.json")
        for key, val in raw_traits.items():
            tid = val.get("id") or key
            tname = val.get("name") or tid
            img = val.get("image", {}).get("full", "")
            if tname:
                self.traits[tid] = tname
                self.traits[key] = tname
                self.trait_images[tid] = img
                self.trait_images[key] = img

        # 4. Lõi Nâng Cấp (Augments)
        raw_augments = self._load_json_data("augments.json")
        for key, val in raw_augments.items():
            aid = val.get("id") or key
            aname = val.get("name") or aid
            img = val.get("image", {}).get("full", "")
            if aname:
                self.augments[aid] = aname
                self.augments[key] = aname
                self.augment_images[aid] = img
                self.augment_images[key] = img

        # 5. Linh thú (Tacticians)
        raw_tacts = self._load_json_data("tactician.json")
        for tid, val in raw_tacts.items():
            tname = val.get("name", "")
            img = val.get("image", {}).get("full", "")
            self.tacticians[str(tid)] = tname
            self.tactician_images[str(tid)] = img

        # 6. Hàng chờ (Queues)
        raw_queues = self._load_json_data("queues.json")
        for qid, val in raw_queues.items():
            self.queues[str(qid)] = val.get("name", str(qid))

    @staticmethod
    def _clean_fallback_name(raw_id: str) -> str:
        """Tạo tên hiển thị dễ đọc nếu không tìm thấy trong DDragon."""
        parts = raw_id.split("/")[-1]
        for prefix in ("TFT_Item_", "TFT_Consumable_", "TFT18_", "TFT17_", "TFT16_", "TFT15_", "TFT14_", "TFT13_", "TFT12_", "DA_18_", "DA_"):
            if parts.startswith(prefix):
                parts = parts[len(prefix):]
                break
        return parts.replace("_", " ").title()

    def get_champion_name(self, char_id: str) -> str:
        if char_id in self.champions:
            return self.champions[char_id]
        clean_id = char_id.split("/")[-1]
        return self.champions.get(clean_id, self._clean_fallback_name(char_id))

    def get_champion_cost(self, char_id: str) -> int:
        if char_id in self.champion_costs:
            return self.champion_costs[char_id]
        clean_id = char_id.split("/")[-1]
        return self.champion_costs.get(clean_id, 1)

    def calculate_unit_value(self, char_id: str, tier: int) -> int:
        """Tính giá trị của quân cờ: Giá gốc x số bản sao (1★ = 1, 2★ = 3, 3★ = 9)."""
        cost = self.get_champion_cost(char_id)
        copies = 3 ** max(0, tier - 1)
        return cost * copies

    def get_champion_image(self, char_id: str) -> str:
        if char_id in self.champion_images:
            return self.champion_images[char_id]
        clean_id = char_id.split("/")[-1]
        return self.champion_images.get(clean_id, "")

    def get_item_name(self, item_id: str) -> str:
        if item_id in self.items:
            return self.items[item_id]
        clean_id = item_id.split("/")[-1]
        return self.items.get(clean_id, self._clean_fallback_name(item_id))

    def get_item_image(self, item_id: str) -> str:
        if item_id in self.item_images:
            return self.item_images[item_id]
        clean_id = item_id.split("/")[-1]
        return self.item_images.get(clean_id, "")

    def get_trait_name(self, trait_id: str) -> str:
        if trait_id in self.traits:
            return self.traits[trait_id]
        clean_id = trait_id.split("/")[-1]
        return self.traits.get(clean_id, self._clean_fallback_name(trait_id))

    def get_trait_image(self, trait_id: str) -> str:
        if trait_id in self.trait_images:
            return self.trait_images[trait_id]
        clean_id = trait_id.split("/")[-1]
        return self.trait_images.get(clean_id, "")

    def get_augment_name(self, augment_id: str) -> str:
        if augment_id in self.augments:
            return self.augments[augment_id]
        clean_id = augment_id.split("/")[-1]
        return self.augments.get(clean_id, self._clean_fallback_name(augment_id))

    def get_augment_image(self, augment_id: str) -> str:
        if augment_id in self.augment_images:
            return self.augment_images[augment_id]
        clean_id = augment_id.split("/")[-1]
        return self.augment_images.get(clean_id, "")

    def get_tactician_image(self, item_id: int | str) -> str:
        if not item_id:
            return ""
        return self.tactician_images.get(str(item_id), "")

    def get_queue_name(self, queue_id: int | str) -> str:
        qid_int = int(queue_id) if str(queue_id).isdigit() else 0
        if qid_int in POPULAR_QUEUES:
            return POPULAR_QUEUES[qid_int]
        return self.queues.get(str(queue_id), f"Queue {queue_id}")


# Cache bộ nạp DDragon theo ngôn ngữ
_LOADERS: dict[str, DDragonLoader] = {}


def get_ddragon_loader(language: str = "vi_VN") -> DDragonLoader:
    if language not in _LOADERS:
        _LOADERS[language] = DDragonLoader(language)
    return _LOADERS[language]


def parse_tft_match(raw_match: dict, target_puuid: Optional[str] = None, language: str = "vi_VN") -> dict:
    """
    Bóc tách 1 match JSON thô từ Riot TFT-Match-V1 thành dữ liệu cấu trúc sạch.
    Nếu target_puuid được chỉ định, sẽ ưu tiên trích xuất chi tiết người chơi đó.
    """
    loader = get_ddragon_loader(language)
    metadata = raw_match.get("metadata", {})
    info = raw_match.get("info", {})

    match_id = metadata.get("match_id", "Unknown")
    game_datetime_ms = info.get("game_datetime") or info.get("gameCreation") or 0
    played_at_str = (
        datetime.fromtimestamp(game_datetime_ms / 1000.0).strftime("%Y-%m-%d %H:%M")
        if game_datetime_ms > 0
        else "N/A"
    )

    game_length_sec = info.get("game_length", 0.0)
    minutes = int(game_length_sec // 60)
    seconds = int(game_length_sec % 60)
    duration_str = f"{minutes}m {seconds:02d}s"

    queue_id = info.get("queue_id", 0)
    queue_name = loader.get_queue_name(queue_id)
    set_number = info.get("tft_set_number", 0)

    participants_raw: list[dict] = info.get("participants", [])

    # Trích xuất dữ liệu người chơi mục tiêu
    target_player_data: Optional[dict] = None
    lobby_summary: list[dict] = []

    for p in participants_raw:
        puuid = p.get("puuid", "")
        placement = p.get("placement", 8)
        level = p.get("level", 1)
        gold_left = p.get("gold_left", 0)
        total_dmg = p.get("total_damage_to_players", 0)
        players_elim = p.get("players_eliminated", 0)
        riot_name = p.get("riotIdGameName", "")
        riot_tag = p.get("riotIdTagline", "")
        player_name = f"{riot_name}#{riot_tag}" if riot_name and riot_tag else puuid[:8]

        companion_info = p.get("companion", {})
        companion_item_id = companion_info.get("item_ID", 0)
        companion_img = loader.get_tactician_image(companion_item_id)

        # 1. Tộc/Hệ kích hoạt (chỉ lấy hệ có tier_current > 0)
        active_traits = []
        for t in p.get("traits", []):
            tier_current = t.get("tier_current", 0)
            if tier_current > 0:
                raw_name = t.get("name", "")
                name = loader.get_trait_name(raw_name)
                num_units = t.get("num_units", 0)
                style = t.get("style", 0)
                trait_img = loader.get_trait_image(raw_name)
                active_traits.append({
                    "raw_id": raw_name,
                    "name": name,
                    "num_units": num_units,
                    "tier_current": tier_current,
                    "style": style,
                    "display": f"{name} ({num_units})",
                    "image": trait_img,
                })
        # Sắp xếp hệ: ưu tiên style cao (vàng/bạc/đồng) rồi đến số lượng tướng
        active_traits.sort(key=lambda x: (x["style"], x["num_units"]), reverse=True)

        # 2. Tướng trên bàn cờ & Tính tổng giá trị bàn cờ (Board Value)
        units = []
        board_value = 0
        for u in p.get("units", []):
            char_id = u.get("character_id", "")
            char_name = loader.get_champion_name(char_id)
            tier = u.get("tier", 1)
            star_str = "★" * min(tier, 4)
            cost = loader.get_champion_cost(char_id)
            unit_val = loader.calculate_unit_value(char_id, tier)
            board_value += unit_val

            raw_items = u.get("itemNames", [])
            items_detailed = []
            item_names = []
            for item_id in raw_items:
                iname = loader.get_item_name(item_id)
                iimg = loader.get_item_image(item_id)
                items_detailed.append({"id": item_id, "name": iname, "image": iimg})
                item_names.append(iname)

            rarity = u.get("rarity", 0)
            char_img = loader.get_champion_image(char_id)

            units.append({
                "character_id": char_id,
                "name": char_name,
                "tier": tier,
                "star_str": star_str,
                "display": f"{char_name} {star_str}".strip(),
                "cost": cost,
                "unit_value": unit_val,
                "image": char_img,
                "items": item_names,
                "items_detailed": items_detailed,
                "rarity": rarity,
            })
        # Sắp xếp tướng: tướng mang nhiều trang bị trước, sau đó theo tier sao
        units.sort(key=lambda x: (len(x["items"]), x["tier"], x["rarity"]), reverse=True)

        # 3. Lõi nâng cấp (Augments)
        augments = [loader.get_augment_name(a) for a in p.get("augments", [])]
        augments_detailed = [
            {"id": a, "name": loader.get_augment_name(a), "image": loader.get_augment_image(a)}
            for a in p.get("augments", [])
        ]

        # Điểm số Esports: Top 1 = 8đ, Top 2 = 7đ, ..., Top 8 = 1đ
        esports_points = max(1, 9 - placement)

        parsed_participant = {
            "puuid": puuid,
            "player_name": player_name,
            "display_name": riot_name or player_name.split("#")[0],
            "placement": placement,
            "esports_points": esports_points,
            "level": level,
            "gold_left": gold_left,
            "board_value": board_value,
            "damage_to_players": total_dmg,
            "players_eliminated": players_elim,
            "companion_id": companion_item_id,
            "companion_image": companion_img,
            "traits": active_traits,
            "units": units,
            "augments": augments,
            "augments_detailed": augments_detailed,
            "is_target": (puuid == target_puuid),
        }

        lobby_summary.append(parsed_participant)

        if target_puuid and puuid == target_puuid:
            target_player_data = parsed_participant

    # Sắp xếp sảnh theo Top 1 -> 8
    lobby_summary.sort(key=lambda x: x["placement"])

    # Nếu không chỉ định target_puuid thì mặc định target_player_data là Top 1
    if not target_player_data and lobby_summary:
        target_player_data = lobby_summary[0]

    return {
        "match_id": match_id,
        "played_at": played_at_str,
        "duration": duration_str,
        "queue_name": queue_name,
        "set_number": set_number,
        "target_player": target_player_data,
        "lobby": lobby_summary,
    }


def export_summary_to_csv(matches: list[dict], output_file: str | Path) -> None:
    """Xuất danh sách trận đấu đã parse ra file CSV tổng hợp dễ xem bằng Excel."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "Match ID",
        "Thời Gian",
        "Chế Độ",
        "Thứ Hạng (Top)",
        "Cấp Độ",
        "Vàng Dư",
        "Sát Thương Gây Ra",
        "Lõi Nâng Cấp (Augments)",
        "Tộc/Hệ Kích Hoạt",
        "Đội Hình Tướng & Trang Bị",
    ]

    rows = []
    for m in matches:
        tp = m.get("target_player") or {}
        traits_str = ", ".join(t["display"] for t in tp.get("traits", []))
        augments_str = ", ".join(tp.get("augments", []))

        units_list = []
        for u in tp.get("units", []):
            u_text = f"{u['name']} {u['star_str']}".strip()
            if u["items"]:
                items_str = " + ".join(u["items"])
                u_text += f" [{items_str}]"
            units_list.append(u_text)
        units_str = " | ".join(units_list)

        rows.append([
            m.get("match_id", ""),
            m.get("played_at", ""),
            m.get("queue_name", ""),
            f"Top {tp.get('placement', 'N/A')}",
            tp.get("level", ""),
            tp.get("gold_left", ""),
            tp.get("damage_to_players", ""),
            augments_str,
            traits_str,
            units_str,
        ])

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    logger.info("CSV exported: %s", output_path.name)


def export_clean_matches_to_json(matches: list[dict], output_file: str | Path) -> None:
    """Xuất dữ liệu sạch đầy đủ ra file JSON phục vụ phân tích lập trình."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    logger.info("JSON exported: %s", output_path.name)


def validate_custom_augment(item: Any, allowlist: Optional[set[str]] = None) -> bool:
    """Kiểm tra tính an toàn và hợp lệ của một định danh custom augment (K3).
    Ngăn chặn tuyệt đối path traversal (.., /, \\), ký tự điều khiển, injection.
    """
    if item is None:
        return True
    if not isinstance(item, str):
        return False
    val = item.strip()
    if not val:
        return True

    # 1. Chống path traversal và ký tự điều khiển / injection nguy hiểm
    if any(p in val for p in ("..", "/", "\\", "\x00", "<", ">", '"', "'", "`", "$", "{", "}")):
        return False

    # 2. Định dạng ký tự an toàn: chỉ cho phép chữ cái, số, gạch dưới, gạch ngang, khoảng trắng, dấu chấm
    if not re.match(r"^[a-zA-Z0-9_\-. ]{1,128}$", val):
        return False

    # 3. Đối chiếu allowlist nếu được cung cấp
    if allowlist is not None and len(allowlist) > 0:
        return val.lower() in allowlist

    return True
