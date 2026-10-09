"""
Script kiểm tra kết nối Riot API, tính hợp lệ của API Key và Riot ID.
Chạy: python tests/manual/test_riot_connection.py
"""

import sys
from pathlib import Path

# Đảm bảo import được tft_studio
BASE_DIR = Path(__file__).resolve().parent.parent.parent
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

    masked_key = (
        f"{cfg.api_key[:8]}...{cfg.api_key[-4:]}"
        if len(cfg.api_key) > 12
        else (cfg.api_key or "(TRỐNG)")
    )
    print(f"   - API Key         : {masked_key}")

    if not cfg.api_key:
        print("\n[CẢNH BÁO] Chưa cấu hình RIOT_API_KEY trong file .env!")
        print("-> Vào https://developer.riotgames.com để lấy Development API Key.")
        return False

    if not cfg.game_name or not cfg.tag_line:
        print("\n[CẢNH BÁO] Chưa cấu hình RIOT_ID trong file .env (ví dụ: TenCuaBan#VN2)!")
        return False

    print("\n2. KIỂM TRA TÀI KHOẢN (Account-V1):")
    print(f"   Đang tìm kiếm '{cfg.game_name}#{cfg.tag_line}' trên routing '{cfg.account_routing}'...")

    client = RiotTFTClient(
        api_key=cfg.api_key,
        account_routing=cfg.account_routing,
        match_routing=cfg.match_routing,
        timeout=6.0,
        max_retries=1,
    )

    try:
        puuid = client.get_puuid_by_riot_id(cfg.game_name, cfg.tag_line)
        print("   [OK] Xác thực tài khoản thành công!")
        print(f"   - PUUID: {puuid}")

        print("\n3. KIỂM TRA LỊCH SỬ ĐẤU TFT (Match-V1):")
        print(f"   Đang truy vấn trận đấu gần nhất trên routing '{cfg.match_routing}'...")
        match_ids = client.get_match_ids_by_puuid(puuid, count=1)

        if match_ids:
            print("   [OK] Lấy danh sách trận đấu thành công!")
            print(f"   - Trận gần nhất: {match_ids[0]}")
            print("\n" + "=" * 60)
            print("   KẾT QUẢ: TẤT CẢ KẾT NỐI HOẠT ĐỘNG HOÀN HẢO! SẴN SÀNG LIVE STREAM.")
            print("=" * 60)
            return True
        else:
            print("   [CHÚ Ý] Không tìm thấy trận TFT nào gần đây trên cụm server này.")
            print("   -> Bạn có thể đã chọn sai Khu Vực (Region) hoặc chưa chơi trận TFT nào gần đây.")
            return True

    except AuthenticationError:
        print("\n[LỖI 401/403] KHÓA API HẾT HẠN HOẶC KHÔNG HỢP LỆ!")
        print("-> Hướng dẫn khắc phục:")
        print("   1. Truy cập https://developer.riotgames.com")
        print("   2. Đăng nhập tài khoản Riot")
        print("   3. Nhấn 'Regenerate API Key'")
        print("   4. Copy khóa mới và dán vào dòng RIOT_API_KEY trong file .env")
        return False
    except AccountNotFoundError:
        print(f"\n[LỖI 404] KHÔNG TÌM THẤY TÀI KHOẢN: {cfg.game_name}#{cfg.tag_line}")
        print("-> Vui lòng kiểm tra lại chính xác Tên và TagLine trong game.")
        print(f"-> Kiểm tra xem tài khoản có thực sự thuộc khu vực '{cfg.region}' không.")
        return False
    except RateLimitError:
        print("\n[LỖI 429] BỊ GIỚI HẠN TỐC ĐỘ (Rate Limited) từ Riot.")
        print("-> Vui lòng chờ 1-2 phút rồi thử lại.")
        return False
    except RiotAPIError as e:
        print(f"\n[LỖI KẾT NỐI RIOT] {e}")
        return False
    except Exception as e:
        print(f"\n[LỖI HỆ THỐNG] {e}")
        return False


if __name__ == "__main__":
    test_connection()
