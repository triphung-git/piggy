"""
Script kiểm tra kết nối Riot API, tính hợp lệ của API Key và Riot ID.
Chạy: python test_riot_connection.py
"""

import sys
from pathlib import Path

# Đảm bảo import được backend
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
src_dir = BASE_DIR / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tft_studio.core.config import AppConfig, reload_env
from tft_studio.riot.client import (
    AccountNotFoundError,
    AuthenticationError,
    RateLimitError,
    RiotAPIError,
    RiotTFTClient,
)


def test_connection():
    print("=" * 60)
    print("       KIỂM TRA KẾT NỐI RIOT API — TFT POST-MATCH STUDIO")
    print("=" * 60)

    reload_env()
    cfg = AppConfig.load()

    print("\n1. CẤU HÌNH TỪ .ENV:")
    print(f"   - Riot ID         : {cfg.game_name}#{cfg.tag_line}")
    print(f"   - Khu vực (Region): {cfg.region}")
    print(f"   - Routing Account : {cfg.account_routing}")
    print(f"   - Routing Match   : {cfg.match_routing}")

    masked_key = f"{cfg.api_key[:8]}...{cfg.api_key[-4:]}" if len(cfg.api_key) > 12 else (cfg.api_key or "(TRỐNG)")
    print(f"   - API Key         : {masked_key}")

    if not cfg.api_key:
        print("\n[THẤT BẠI] RIOT_API_KEY đang để trống trong file .env!")
        print("-> Vui lòng truy cập https://developer.riotgames.com/ để lấy key mới và dán vào file .env.")
        return False

    if not cfg.game_name or not cfg.tag_line:
        print("\n[THẤT BẠI] RIOT_ID không hợp lệ hoặc thiếu #TAG (ví dụ: TenNguoiChoi#VN2)!")
        return False

    print("\n2. ĐANG KẾT NỐI VÀ XÁC THỰC...")
    client = RiotTFTClient(
        api_key=cfg.api_key,
        account_routing=cfg.account_routing,
        match_routing=cfg.match_routing,
        timeout=8.0,
        max_retries=1,
    )

    try:
        puuid = client.get_puuid_by_riot_id(cfg.game_name, cfg.tag_line)
        print("   [OK] Xác thực tài khoản thành công!")
        print(f"   - PUUID: {puuid}")

        print("\n3. ĐANG TẢI TRẬN ĐẤU MỚI NHẤT...")
        match_ids = client.get_match_ids_by_puuid(puuid, count=1)
        if match_ids:
            print(f"   [OK] Tìm thấy trận đấu gần nhất: {match_ids[0]}")
            print("\n" + "=" * 60)
            print("   >>> KẾT QUẢ: TẤT CẢ ĐỀU SẴN SÀNG ĐỂ HOẠT ĐỘNG REAL-TIME! <<<")
            print("=" * 60)
            return True
        else:
            print("   [CẢNH BÁO] Không tìm thấy trận TFT nào gần đây cho tài khoản này.")
            return True

    except AuthenticationError as e:
        print("\n[LỖI 403/401] KHÓA RIOT_API_KEY ĐÃ HẾT HẠN HOẶC KHÔNG HỢP LỆ!")
        print(f"Chi tiết: {e}")
        print("\n-> Hướng dẫn khắc phục:")
        print("   1. Truy cập https://developer.riotgames.com/")
        print("   2. Đăng nhập tài khoản Riot Games của bạn")
        print("   3. Bấm 'REGENERATE API KEY'")
        print("   4. Copy khóa mới và dán vào dòng RIOT_API_KEY trong file .env")
        return False
    except AccountNotFoundError:
        print(f"\n[LỖI 404] KHÔNG TÌM THẤY TÀI KHOẢN: {cfg.game_name}#{cfg.tag_line}")
        print("-> Vui lòng kiểm tra lại chính xác Tên và TagLine trong game.")
        return False
    except RateLimitError as e:
        print(f"\n[LỖI 429] BỊ GIỚI HẠN TẦN SUẤT GỌI (RATE LIMIT): {e}")
        return False
    except RiotAPIError as e:
        print(f"\n[LỖI RIOT API] {e}")
        return False
    except Exception as e:
        print(f"\n[LỖI KHÔNG XÁC ĐỊNH] {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    test_connection()
