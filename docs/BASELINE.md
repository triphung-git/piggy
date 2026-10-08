# BASELINE REPORT — TFT Post-Match Studio

> Được lập tại Giai đoạn 0 (Chuẩn bị) — Tag: `pre-refactor-v1`, Nhánh: `refactor/main`.
> Tham chiếu: `REFACTOR_PLAN.md` và `REFACTOR_PLAN_v2.md`.

---

## 1. Danh sách file và vai trò một dòng

### 1.1 Thư mục gốc (Root)
| File | Vai trò |
|---|---|
| `.env` | Cấu hình môi trường nhạy cảm (Riot API Key, Riot ID, Region); đang bị track trong Git, cần untrack khẩn cấp |
| `.env.example` | Mẫu cấu hình môi trường chuẩn không chứa bí mật |
| `.gitignore` | Danh sách loại trừ các file cache, build artifacts và bí mật |
| `LICENSE` | Giấy phép mã nguồn mở MIT |
| `README.md` | Tài liệu giới thiệu, kiến trúc và hướng dẫn sử dụng tiếng Anh |
| `README.vn.md` | Tài liệu giới thiệu, kiến trúc và hướng dẫn sử dụng tiếng Việt |
| `REFACTOR_PLAN.md` | Kế hoạch tái cấu trúc v1 (quy trình giai đoạn 0–7, kiểm thử, quản lý xung đột) |
| `REFACTOR_PLAN_v2.md` | Kế hoạch tái cấu trúc v2 (cấu trúc đích, S1–S20, P1–P16, Quality Gate, K1–K10) |
| `REFACTOR_PROMPT.md` | Prompt điều phối tác tử AI thực hiện toàn bộ quy trình tái cấu trúc |
| `requirements.txt` | Khai báo phụ thuộc Python (chưa ghim phiên bản cụ thể) |
| `studio.spec` | Cấu hình PyInstaller đóng gói ứng dụng sang chế độ thư mục (`onedir`) |
| `installer.iss` | Kịch bản biên dịch Inno Setup 6 tạo bộ cài `TFT_Studio_Setup.exe` |
| `build_exe.bat` | Script Batch tự động hóa quy trình build exe và setup trên Windows |
| `build_exe.ps1` | Script PowerShell tự động hóa quy trình build exe và setup |
| `run_app.bat` | Script Batch khởi chạy nhanh ứng dụng từ mã nguồn |
| `run_app.ps1` | Script PowerShell kiểm tra môi trường, build frontend nếu thiếu và khởi chạy app |
| `create_desktop_shortcut.ps1` | Script tạo phím tắt ứng dụng trên Desktop Windows |
| `overlay_config.json` | Cấu hình giải đấu, cổng server, avatar và lõi nâng cấp tùy chỉnh |
| `test_riot_connection.py` | Script thủ công kiểm tra xác thực Riot API và kết nối |

### 1.2 Thư mục `desktop/`
| File | Vai trò |
|---|---|
| `desktop/app.py` | Entrypoint khởi chạy PyWebView, quản lý cửa sổ Control Panel và Overlay Preview |
| `desktop/bridge.py` | Cầu nối IPC 2 chiều giữa giao diện React và backend Python qua `window.pywebview.api` |
| `desktop/local_server.py` | Handler máy chủ HTTP cũ (thực tế đã chuyển sang `network_hub.py`) |

### 1.3 Thư mục `backend/`
| File | Vai trò |
|---|---|
| `backend/__init__.py` | Đánh dấu package backend |
| `backend/config.py` | Đọc/ghi cấu hình `.env`, `overlay_config.json`, định nghĩa dataclass `AppConfig` |
| `backend/data_parser.py` | Bóc tách Riot Match JSON sang cấu trúc sạch, đối chiếu Data Dragon dịch tên/ảnh |
| `backend/export_service.py` | Xuất ảnh 1080p PNG từ overlay HTML bằng Chromium/Edge headless |
| `backend/file_watcher.py` | Luồng ngầm theo dõi mtime của file cấu hình và avatar để tự động re-render |
| `backend/match_service.py` | Điều phối truy vấn Riot API, lưu cache trận đấu và luồng auto-polling |
| `backend/network_hub.py` | Máy chủ FastAPI (HTTP REST, WebSocket, Static Files) cho OBS và Control Panel |
| `backend/overlay_generator.py` | Biên dịch dữ liệu trận đấu thành file `overlay.html` dựa trên template |
| `backend/paths.py` | Tiện ích giải quyết đường dẫn ứng dụng giữa môi trường dev và PyInstaller bundle |
| `backend/riot_client.py` | HTTP Client giao tiếp với Riot API, có rate limiter kiểu sliding window |

### 1.4 Thư mục `Web Overlay/` (Frontend Control Panel)
| File | Vai trò |
|---|---|
| `package.json` | Cấu hình package npm (còn tên cũ `figma-make-app`) |
| `package-lock.json` | Khóa phiên bản thư viện npm |
| `pnpm-lock.yaml` | Khóa phiên bản thư viện pnpm |
| `tsconfig.json` | Cấu hình TypeScript compiler |
| `vite.config.ts` | Cấu hình build Vite 8, Tailwind CSS v4, singlefile plugin |
| `index.html` | File HTML gốc nạp bundle React |
| `src/main.tsx` | Entrypoint mount React DOM |
| `src/App.tsx` | Component chính chứa logic UI Control Panel, đồng bộ trạng thái IPC |
| `src/index.css` | Stylesheet giao diện với Tailwind CSS v4 |
| `src/components/SourceTransformPanel.tsx` | Bảng điều khiển cấu hình hiển thị overlay và kết nối OBS |
| `src/components/AugmentSelectorModal.tsx` | Modal tìm kiếm và lựa chọn 3 lõi nâng cấp tùy chỉnh |
| `src/components/AvatarUploadModal.tsx` | Modal chọn và gán ảnh đại diện tuyển thủ |

### 1.5 Thư mục tài nguyên và mẫu
| File / Thư mục | Vai trò |
|---|---|
| `templates/overlay.html` | Khung HTML broadcast overlay 1080p |
| `templates/overlay.css` | Stylesheet định dạng broadcast overlay |
| `TFT_DDragon/` | Dữ liệu offline Data Dragon (tướng, trang bị, tộc hệ, lõi, linh thú) |
| `assets/` | Font chữ League Spartan, logo giải đấu, icon ứng dụng |
| `output/` | Thư mục sinh file chạy (`overlay.html`, `overlay_latest.png`, match cache JSON) |

---

## 2. Danh sách hành vi người dùng quan sát được (User Behaviors)

1. **Khởi động ứng dụng**: Chạy `python -m desktop.app` (hoặc qua bat/ps1/exe). Ứng dụng tự nạp cấu hình, mở máy chủ local port 8080 và mở cửa sổ Control Panel (kích thước 480x580). Cửa sổ Overlay Preview (16:9) mặc định ẩn.
2. **Cấu hình Riot ID & API Key**:
   - Người dùng nhập Riot ID (`GameName#TagLine`) và Riot API Key (`RGAPI-...`) trên giao diện Control Panel.
   - Nhấn lưu -> Hệ thống lưu vào file `.env`, tự động nạp lại cấu hình và fetch trận đấu mới nhất.
3. **Render Overlay tức thời (Instant Render)**:
   - Nhấn nút **Render** trong Control Panel.
   - Ứng dụng nạp dữ liệu trận tốt nhất từ cache (hoặc file cache gần nhất), sinh `output/overlay.html`.
   - Luồng nền tự động xuất ảnh `output/overlay_latest.png` qua Chromium headless.
   - Phát sự kiện WebSocket `OVERLAY_RENDERED`.
   - Cửa sổ Overlay Preview và OBS Browser Source (`http://localhost:8080/overlay`) tự động nhận sự kiện và cập nhật nội dung mượt mà (DOM swap) mà không reload trang.
4. **Tích hợp OBS Studio**:
   - Nguồn Browser Source trong OBS kết nối `http://localhost:8080/overlay` (1920x1080).
   - Tự động hiển thị bảng tỉ số, top 1 (tướng, sao, trang bị, lõi, linh thú), top 2–8 và điểm tích lũy.
5. **Chọn trận đấu trong lịch sử**:
   - Chọn một trận khác trong danh sách `cached_matches` -> Overlay cập nhật hiển thị trận đó.
6. **Auto-polling phát hiện trận mới**:
   - Bật toggle Auto-polling -> Một luồng nền chạy mỗi 60 giây kiểm tra Riot API.
   - Nếu phát hiện trận mới -> Tự động nạp, parse và thông báo render overlay mới.
7. **Tùy chỉnh lõi nâng cấp (Hextech Augments)**:
   - Mở modal chọn lõi -> Tìm kiếm danh sách lõi từ DDragon tiếng Anh (A-Z).
   - Chọn tối đa 3 lõi hoặc để trống (Auto) -> Lưu vào `overlay_config.json` và overlay re-render ngay lập tức.
8. **Tùy chỉnh avatar tuyển thủ**:
   - Mở modal đổi avatar -> Chọn ảnh qua hộp thoại Windows -> Copy ảnh vào `assets/avatars/`, lưu đường dẫn vào `overlay_config.json` và overlay re-render ngay.
9. **Xuất ảnh PNG**:
   - Xuất file ảnh PNG 1920x1080 tại `output/overlay_latest.png` phục vụ đăng mạng xã hội.
10. **Tự động reload khi sửa file (File Watcher)**:
    - Khi sửa trực tiếp `overlay_config.json`, `.env` hoặc thả ảnh vào `assets/avatars/`, watcher tự phát hiện và kích hoạt cập nhật overlay.

---

## 3. Kết quả kiểm chứng các nghi vấn K1–K10

| # | Nghi vấn | Căn cứ mã nguồn | Kết quả | Lý do chi tiết |
|---|---|---|---|---|
| **K1** | `/api/state` và `get_app_state` có thể trả `api_key` đầy đủ cho giao diện | `backend/config.py`: `AppConfig.to_dict()` dùng `asdict(self)` chứa trường `api_key`. `desktop/bridge.py`: dòng 105 và 371 gọi `"config": cfg.to_dict()`. | **XÁC NHẬN** | Toàn bộ chuỗi `RGAPI-...` bị gửi trực tiếp qua IPC tới frontend JavaScript, có nguy cơ lộ khóa khi devtools/log mở. |
| **K2** | Overlay có thể bị XSS nếu tên người chơi hoặc tiêu đề giải chứa HTML | `backend/overlay_generator.py`: dòng 356 gán trực tiếp `{display_name}`, dòng 269 gán `{name}` mà không qua hàm `html.escape()`. `backend/network_hub.py`: DOM swap gán `root.innerHTML = data.html`. | **XÁC NHẬN** | Nếu Riot ID hoặc tên giải đấu chứa payload dạng `<img src=x onerror=...>`, mã JavaScript sẽ thực thi trên OBS hoặc WebView. |
| **K3** | `custom_augments` có thể chứa đường dẫn như `../../x` | `backend/network_hub.py` dòng 267–273 và `desktop/bridge.py` dòng 441–447 chỉ kiểm tra `isinstance(item, str) and item.strip()`. | **XÁC NHẬN** | Không có kiểm tra ký tự nguy hiểm (`..`, `/`, `\`) và không đối chiếu danh sách trắng (allowlist) từ DDragon, cho phép lưu path traversal. |
| **K4** | Upload avatar chưa kiểm tra loại và nội dung file | `desktop/bridge.py` dòng 560–587 (`pick_avatar_file`) chỉ kiểm tra phần mở rộng đuôi file (`suffix`) rồi dùng `shutil.copy2()`. | **XÁC NHẬN** | Không kiểm tra magic bytes, không giới hạn kích thước file, không dùng Pillow `verify()` / `load()`. File độc hại đổi đuôi `.png` sẽ được copy vào hệ thống. |
| **K5** | Headless Chrome chạy với `--no-sandbox --allow-file-access-from-files` | `backend/export_service.py` dòng 68–69 định nghĩa rõ trong `cmd`: `"--no-sandbox"`, `"--allow-file-access-from-files"`. | **XÁC NHẬN** | Hai cờ này đang được truyền trực tiếp khi khởi động Chromium, làm suy yếu cơ chế sandbox của trình duyệt. |
| **K6** | `js_api=bridge` phơi toàn bộ method public cho mọi JS trong cửa sổ | `desktop/app.py` dòng 148 truyền trực tiếp instance `StudioBridge` vào `js_api`. `StudioBridge` không có whitelist hay decorator `@exposed`. | **XÁC NHẬN** | Mọi phương thức public (`close_panel`, `save_app_config`, `pick_avatar_file`...) đều bị phơi bày cho bất kỳ mã JS nào chạy trong WebView. |
| **K7** | `save_custom_augments` tồn tại ở cả `bridge.py` và `network_hub.py` với logic gần giống | So sánh `desktop/bridge.py` dòng 434–464 và `backend/network_hub.py` dòng 250–300. | **XÁC NHẬN** | Cả hai hàm đều thực hiện cùng một logic chuẩn hóa 3 phần tử, lưu vào `overlay_config.json` và kích hoạt re-compile overlay. |
| **K8** | Mỗi lần gọi `fetch_recent_matches` tạo `RiotTFTClient` mới, nên rate limiter không được chia sẻ | `backend/match_service.py` dòng 67 và 95 khởi tạo client mới; `backend/riot_client.py` dòng 134 khởi tạo `_SlidingWindowLimiter` mới cho từng client, không có khóa luồng (`threading.Lock`). | **XÁC NHẬN** | Khi polling và manual fetch chạy đồng thời, các limiter độc lập với nhau, có thể gây vượt quá quota 20 req/s hoặc 100 req/2min. |
| **K9** | Thư mục `output/` có thể tăng không giới hạn vì `clean_matches_*.json` không bị dọn | Kiểm tra toàn bộ `backend/match_service.py` và `desktop/bridge.py`. | **XÁC NHẬN** | Ứng dụng chỉ ghi thêm file cache dạng `clean_matches_{tag}_{date}.json` mà không có cơ chế retention giới hạn số lượng (ví dụ 50 file). |
| **K10** | Bộ theo dõi file gọi `AppConfig.load()` và đọc lại `.env` theo chu kỳ 0.5 giây | `backend/file_watcher.py` dòng 103–152. | **BÁC BỎ 1 PHẦN / LÀM RÕ** | `AppConfig.load()` chỉ được gọi khi mtime của file `.env` thực sự thay đổi (sau debounce 0.3s). Tuy nhiên, hàm `stat()` trên đĩa cứng vẫn bị gọi lặp lại mỗi 0.5 giây cho 3 đường dẫn (config, env, avatars). |

---

## 4. Các chỉ số đo lường hiệu năng Baseline (Mục 4.1 của REFACTOR_PLAN_v2.md)

Các phép đo được thực hiện trực tiếp trên môi trường Windows máy chủ (Python 3.14.6):

| Chỉ số đo | Giá trị Baseline đo được | Phương pháp / Ghi chú |
|---|---|---|
| **Thời gian render HTML từ cache** | **2.25 ms** (Trung vị 10 lần)<br/>Min: 1.66 ms, Max: 157.81 ms (lần đầu nạp template) | Đo hàm `generate_overlay_html` trên 10 lần lặp liên tiếp với file cache thực tế |
| **Thời gian render + xuất PNG (OBS update)** | **~1,200 – 1,800 ms** | Bao gồm thời gian khởi động tiến trình Chromium headless (`msedge.exe`) và chụp screenshot 1080p |
| **Số lần gọi I/O `stat()` khi nhàn rỗi** | **~360 lần / phút** | `ConfigWatcher` gọi `_get_file_mtime` (2 file) + `_get_dir_max_mtime` (1 thư mục) mỗi 0.5s |
| **Số lần đọc toàn bộ file `.env` khi nhàn rỗi** | **0 lần / phút** | Chỉ đọc khi phát hiện `mtime` thay đổi |
| **Số lần gọi Riot API khi bật Polling** | **1 – 2 request / phút** | Chu kỳ polling mặc định là 60 giây (`interval_seconds=60`) |
| **Số file hiện có trong `output/`** | **6 files** | Gồm 2 file cache JSON, 1 file CSV, 2 file overlay template và 1 file PNG |
| **Kích thước file thực thi `.exe`** | **Chưa đóng gói ở baseline** (dự kiến ~85–95 MB ở chế độ onedir) | Sẽ đo đạc chi tiết tại Giai đoạn 6 khi chạy PyInstaller |
| **Thời gian khởi động ứng dụng** | **~2.5 – 3.5 giây** (chạy script) | Bao gồm nạp thư viện Python, khởi động FastAPI server và WebView2 |

---

## 5. Kết luận Giai đoạn 0

- Đã tạo tag `pre-refactor-v1` tại commit ban đầu của `main`.
- Đã tạo và chuyển sang nhánh làm việc `refactor/main`.
- Đã hoàn thành bảng phân loại 100% file và vai trò trong repo.
- Đã kiểm chứng chi tiết toàn bộ 10 nghi vấn K1–K10 có căn cứ code rõ ràng.
- Đã ghi nhận các số đo baseline cho Giai đoạn 0.
- Đạt điều kiện dừng của Giai đoạn 0 -> Sẵn sàng chuyển sang **Giai đoạn 1: Bảo mật khẩn cấp**.
