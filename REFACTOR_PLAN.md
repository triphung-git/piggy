# Kế hoạch tái cấu trúc TFT Post-Match Studio

> Mục tiêu: tổ chức lại codebase theo lớp rõ ràng, tăng bảo mật, có kiểm thử tự động, chuẩn bị cho Docker và CI, mà không làm hỏng chức năng hiện có.

---

## 1. Nguyên tắc

1. **Không thay đổi hành vi và không sửa logic trong cùng commit di chuyển file.** Commit di chuyển (`git mv`) phải tách biệt với commit sửa code.
2. **Mỗi commit đều phải chạy được.** Test xanh, app khởi động được.
3. **Test trước, di chuyển sau.** Không đụng vào code nếu chưa có characterization test.
4. **Bảo mật được xử lý trước** vì nó không phụ thuộc cấu trúc mới.
5. **Một người sở hữu refactor.** Các thay đổi khác vào `desktop/` và `backend/` tạm dừng trong thời gian này.

---

## 2. Hiện trạng (căn cứ từ phân tích trước)

```
Teamfight-Tactics_Overlay/
├── desktop/            app.py, bridge.py, local_server.py
├── backend/            config, data_parser, export_service, file_watcher,
│                       match_service, network_hub, overlay_generator, paths, riot_client
├── Web Overlay/        React 19 + TS + Vite 8 + Tailwind v4
├── templates/          overlay.html, overlay.css
├── TFT_DDragon/        dữ liệu Data Dragon (vi_VN, en_US)
├── assets/             font, avatars, icon, nền
├── output/             cache và file sinh ra (đang bị commit — cần sửa)
├── .env, .env.example, overlay_config.json
├── studio.spec, installer.iss, build_exe.bat/.ps1, run_app.bat/.ps1
├── requirements.txt, test_riot_connection.py
└── README.md, README.vn.md, LICENSE
```

### Vấn đề cần xử lý
| Mức | Vấn đề | Vị trí |
| --- | --- | --- |
| Cao | `.env` và `output/` đã bị commit | Git index |
| Cao | CORS `*`, endpoint POST không xác thực | `network_hub.py` |
| Cao | WebSocket cổng cố định `8080` | script trong `network_hub.py` |
| Cao | `window.smoothUpdate` nằm trong IIFE nên không tồn tại | `bridge.py`, overlay script |
| Trung bình | Rate limiter tạo mới mỗi lần, không có khóa luồng | `riot_client.py`, `match_service.py` |
| Trung bình | Phát hiện lỗi xác thực bằng chuỗi `"401" in str(exc)` | `bridge.py` |
| Trung bình | Dữ liệu người dùng ghi cạnh `.exe` | `paths.py`, `installer.iss` |
| Trung bình | `_bridge_ref` toàn cục giữa `network_hub` và `bridge` | `network_hub.py` |
| Thấp | Hàm trùng lặp, hàm rỗng, thiếu import `Optional` | nhiều file |
| Thấp | `requirements.txt` không ghim phiên bản, lẫn công cụ build | `requirements.txt` |
| Thấp | `package-lock.json` bị ignore; `package.json` còn tên `figma-make-app` | `Web Overlay/` |

> **Cần đọc trước khi bắt đầu:** `data_parser.py`, `overlay_generator.py`, `config.py`, `file_watcher.py`, `installer.iss`, `build_exe.*`, `run_app.*`.

---

## 3. Cấu trúc đích

```
tft-studio/
├── src/
│   └── tft_studio/
│       ├── __init__.py
│       ├── settings.py              # đọc cấu hình, không có side effect khi import
│       ├── paths.py                 # get_app_dir / get_bundle_dir / resolve_resource
│       ├── core/
│       │   ├── models.py            # dataclass/Pydantic cho Match, Participant, Config
│       │   └── errors.py            # RiotAPIError, AuthenticationError, ...
│       ├── riot/
│       │   ├── client.py            # RiotTFTClient (chỉ HTTP)
│       │   ├── rate_limiter.py      # limiter dùng chung, có Lock
│       │   └── routing.py           # REGION_MAPPING
│       ├── parsing/
│       │   ├── ddragon.py           # DDragonLoader
│       │   └── match_parser.py      # parse_tft_match
│       ├── rendering/
│       │   ├── overlay_generator.py
│       │   └── png_exporter.py      # tách từ export_service.py
│       ├── services/
│       │   ├── studio_service.py    # điều phối: render, fetch, cấu hình (không import webview)
│       │   ├── polling.py           # auto-polling
│       │   ├── match_cache.py       # đọc/ghi clean_matches_*.json
│       │   └── config_watcher.py    # từ file_watcher.py
│       ├── api/
│       │   ├── app.py               # create_app(service) -> FastAPI
│       │   ├── routes/              # status.py, config.py, riot.py, overlay.py, augments.py
│       │   ├── ws.py                # LocalNotifier
│       │   └── security.py          # token, CORS
│       └── desktop/
│           ├── main.py              # entrypoint PyWebView
│           ├── bridge.py            # lớp mỏng: JS <-> service
│           └── windows.py           # tạo cửa sổ Control Panel và Overlay
├── web/                             # React (đổi tên từ "Web Overlay/")
│   ├── src/
│   ├── package.json
│   └── package-lock.json
├── data/
│   ├── ddragon/                     # đổi từ TFT_DDragon/
│   └── templates/                   # overlay.html, overlay.css
├── assets/                          # font, icon, nền (avatars không commit)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/                      # overlay.html chuẩn
│   └── fixtures/                    # trận mẫu đã ẩn thông tin cá nhân, phản hồi Riot giả
├── packaging/
│   ├── studio.spec
│   ├── installer.iss
│   └── scripts/                     # build_exe.ps1, ...
├── docs/
│   ├── ARCHITECTURE.md
│   └── adr/                         # 0001-..., 0002-...
├── .github/workflows/ci.yml
├── pyproject.toml                   # thay requirements.txt, ghim phiên bản
├── requirements-dev.txt
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

### Ánh xạ file cũ → mới
| Cũ | Mới |
| --- | --- |
| `backend/riot_client.py` | `riot/client.py`, `riot/rate_limiter.py`, `core/errors.py` |
| `backend/match_service.py` | `services/studio_service.py`, `services/match_cache.py`, `services/polling.py` |
| `backend/data_parser.py` | `parsing/ddragon.py`, `parsing/match_parser.py` |
| `backend/overlay_generator.py` | `rendering/overlay_generator.py` |
| `backend/export_service.py` | `rendering/png_exporter.py` |
| `backend/file_watcher.py` | `services/config_watcher.py` |
| `backend/network_hub.py` | `api/app.py`, `api/routes/*`, `api/ws.py`, `api/security.py` |
| `backend/config.py` | `settings.py` |
| `backend/paths.py` | `paths.py` |
| `desktop/app.py` | `desktop/main.py`, `desktop/windows.py` |
| `desktop/bridge.py` | `desktop/bridge.py` (mỏng) |
| `Web Overlay/` | `web/` |
| `TFT_DDragon/` | `data/ddragon/` |
| `templates/` | `data/templates/` |
| `studio.spec`, `installer.iss`, `build_exe.*` | `packaging/` |
| `output/` | không commit; tạo khi chạy trong thư mục dữ liệu người dùng |

---

## 4. Các giai đoạn

### Giai đoạn 0: Đóng băng và ghi nhận trạng thái (1 ngày)
- [ ] Tạo nhánh `refactor/baseline` từ `main`, gắn tag `pre-refactor-v1`.
- [ ] Thông báo: không merge vào `main` trong thời gian refactor.
- [ ] Đọc và ghi chú các file chưa phân tích (xem mục 2).
- [ ] Ghi baseline:
  - Thời gian render một trận (ms).
  - Kích thước `.exe` và installer (MB).
  - Ảnh chụp Control Panel và Overlay.
  - Danh sách hành vi cần giữ (checklist ở mục 6).

**Điều kiện dừng:** có tài liệu baseline và tag đã push.

### Giai đoạn 1: Bảo mật (2–3 ngày)
- [ ] Chạy `gitleaks detect --log-opts="--all"` trên toàn bộ lịch sử.
- [ ] Nếu có key thật trong lịch sử: **thu hồi key trên Riot Developer Portal ngay**, không chờ.
- [ ] `git rm --cached .env`, `git rm -r --cached output/ scratch/`.
- [ ] Nếu cần xoá khỏi lịch sử: `git filter-repo --path .env --path output/ --invert-paths`. Báo mọi người clone lại sau khi force push.
- [ ] Sửa `network_hub.py`:
  - CORS: chỉ cho `http://127.0.0.1:8080` và `http://localhost:8080`.
  - Sinh token ngẫu nhiên mỗi lần chạy, yêu cầu header `X-Studio-Token` cho các endpoint POST.
  - Control Panel nạp từ `http://127.0.0.1:8080/app`, không từ `file://`.
- [ ] Sửa cổng WebSocket: dùng `location.host` thay vì `ws://127.0.0.1:8080/ws` cố định.
- [ ] Thêm `pip-audit` và `npm audit` vào kiểm tra định kỳ.

**Điều kiện dừng:** `gitleaks` sạch; test cho token và CORS xanh; đổi `server_port` trong cấu hình vẫn cập nhật được OBS.

### Giai đoạn 2: Characterization test (3–5 ngày)
- [ ] Tạo `tests/fixtures/`: 2–3 file trận JSON đã ẩn thông tin cá nhân; phản hồi giả của Riot cho các mã 200, 401, 404, 429, 500.
- [ ] Test `parse_tft_match` với fixture; kiểm tra các trường chính.
- [ ] Test `generate_overlay_html` và so với `tests/golden/overlay.html` (bỏ qua timestamp).
- [ ] Test `RiotTFTClient` bằng `responses`: retry với 429, backoff, phân loại lỗi 401/404.
- [ ] Test `_SlidingWindowLimiter`: không vượt 20 request/giây.
- [ ] Test `load_overlay_config` và `save_overlay_config`.
- [ ] Đặt `pytest` với coverage tối thiểu 60% cho `backend/`.

**Điều kiện dừng:** toàn bộ test xanh trên code hiện tại.

### Giai đoạn 3: Tạo khung và di chuyển thuần (2–3 ngày)
- [ ] Tạo `pyproject.toml`, `src/tft_studio/`, `tests/`, `packaging/`.
- [ ] Di chuyển theo thứ tự, mỗi module một commit `git mv`:
  1. `paths.py`, `settings.py`
  2. `riot/` (client, rate_limiter, routing)
  3. `parsing/`
  4. `rendering/`
  5. `services/`
  6. `api/`
  7. `desktop/`
- [ ] Trong thời gian chuyển tiếp, giữ `backend/` làm shim import từ đường dẫn mới.
- [ ] Chạy test sau mỗi commit.

**Điều kiện dừng:** test xanh; app khởi động được bằng entrypoint mới.

### Giai đoạn 4: Tách logic khỏi PyWebView (3–4 ngày)
- [ ] Tạo `StudioService` với các phương thức: `render`, `fetch_latest`, `set_active_match`, `get_state`, `update_config`, `update_riot_id`, `update_api_key`, `save_custom_augments`.
- [ ] `StudioService` không import `webview`. Nhận callback `notify` qua constructor để đẩy sự kiện.
- [ ] `bridge.py` chỉ còn: nhận lệnh từ `window.pywebview.api`, gọi service, chuyển kết quả.
- [ ] Bỏ `_bridge_ref`; API FastAPI nhận service qua `create_app(service)`.
- [ ] Sửa `window.smoothUpdate`: gắn `window.smoothUpdate = smoothUpdate` trong script overlay.
- [ ] Thay so sánh chuỗi lỗi bằng `isinstance(exc, AuthenticationError)`.
- [ ] Gom rate limiter thành một instance dùng chung, có `threading.Lock`.
- [ ] Thêm test cho `StudioService` bằng pytest, không cần cửa sổ.

**Điều kiện dừng:** test `StudioService` xanh; không còn `import webview` ngoài `desktop/`.

### Giai đoạn 5: Giao diện và đóng gói (3–4 ngày)
- [ ] Đổi `Web Overlay/` thành `web/`; sửa `packaging/` và `paths.py` tương ứng.
- [ ] Đưa `package-lock.json` vào repo; đổi tên package khỏi `figma-make-app`.
- [ ] Cập nhật `studio.spec`:
  - `datas`: `web/dist`, `data/ddragon`, `data/templates`, `assets`.
  - `hiddenimports`: giữ danh sách hiện tại, kiểm tra lại sau khi đổi package.
  - Tắt UPX hoặc ký số file exe để giảm cảnh báo của phần mềm diệt virus.
- [ ] Cập nhật `installer.iss`: ghi dữ liệu người dùng vào `%APPDATA%\TFT_PostMatch_Studio\`.
- [ ] Cập nhật `build_exe.*` và `run_app.*`.
- [ ] Đưa `requirements.txt` về runtime; công cụ build vào `requirements-dev.txt`; ghim phiên bản.

**Điều kiện dừng:** build `.exe` và installer thành công; cài trên VM Windows sạch và chạy được luồng đầy đủ.

### Giai đoạn 6: Kiểm thử tích hợp và thủ công (3–5 ngày)
Xem mục 6.

### Giai đoạn 7: Hoàn tất (2 ngày)
- [ ] Viết `docs/ARCHITECTURE.md` và ít nhất 3 ADR: tách service khỏi UI; chọn FastAPI + WebSocket; cấu trúc dữ liệu người dùng.
- [ ] Cập nhật `README.md` và `README.vn.md`: sơ đồ mới, cách chạy, cách build.
- [ ] Thêm `.github/workflows/ci.yml` (xem mục 7).
- [ ] Xoá shim `backend/`, code chết (`get_transform`, `update_overlay_transform`, hàm trùng lặp).
- [ ] Merge `refactor/main` vào `main`; tag `v2.0.0`.

---

## 5. Quản lý conflict

- **Nhánh:** `refactor/main` là nhánh tích hợp; mỗi giai đoạn là một nhánh con ngắn hạn (`refactor/s1-security`, `refactor/s3-move-riot`...).
- **Tần suất:** merge từ `refactor/main` về nhánh con ít nhất mỗi ngày; rebase thay vì merge để lịch sử gọn.
- **Review:** mọi PR trong refactor phải có một người review; PR chỉ di chuyển file phải ghi rõ "không đổi logic".
- **Khoá vùng:** trong giai đoạn 3–4, không ai sửa `desktop/`, `backend/`, `network_hub.py` ngoài nhánh refactor.
- **Cập nhật các nhánh đang mở:** trước khi bắt đầu, liệt kê các nhánh đang mở và yêu cầu rebase hoặc đóng lại.

---

## 6. Kiểm thử

### 6.1 Tự động (chạy trong CI và trên máy)
| Kiểm tra | Công cụ | Điều kiện |
| --- | --- | --- |
| Lint | `ruff check` | 0 lỗi |
| Format | `ruff format --check` | không đổi |
| Kiểu dữ liệu | `mypy src/` | 0 lỗi ở `core/` và `services/` |
| Unit | `pytest tests/unit` | 100% xanh |
| Integration | `pytest tests/integration` | 100% xanh |
| Golden | so sánh `overlay.html` | khớp ngoài timestamp |
| Coverage | `pytest --cov` | ≥ 70% `src/tft_studio/` |
| Bảo mật Python | `pip-audit` | không có lỗ hổng mức cao |
| Bảo mật frontend | `npm audit --omit=dev` | không có lỗ hổng mức cao |
| Bí mật | `gitleaks` | 0 phát hiện |
| Build | `pyinstaller packaging/studio.spec` | thành công |
| Frontend | `npm run build` trong `web/` | thành công |

### 6.2 Thủ công (trên Windows)
Checklist hành vi cần giữ:
- [ ] Khởi động từ mã nguồn và từ `.exe`.
- [ ] Nhập Riot ID và API key; lưu vào `.env` (hoặc nơi mới).
- [ ] Render: overlay hiện trong Control Panel và cửa sổ Overlay.
- [ ] OBS Browser Source `http://localhost:8080/overlay` cập nhật khi render, không nhấp nháy.
- [ ] Đổi `server_port` trong `overlay_config.json` rồi kiểm tra OBS vẫn cập nhật.
- [ ] Chọn trận khác trong danh sách; overlay đổi theo.
- [ ] Bật/tắt auto-polling; trận mới được phát hiện.
- [ ] Đổi avatar qua hộp thoại; avatar hiện trên overlay.
- [ ] Chọn lõi nâng cấp tuỳ chỉnh; overlay cập nhật.
- [ ] Xuất PNG 1920x1080; file đúng kích thước.
- [ ] Đóng và mở app nhiều lần; không có tiến trình treo (kiểm tra Task Manager).

Kiểm tra lỗi:
- [ ] API key sai hoặc hết hạn: thông báo rõ ràng, không crash.
- [ ] Không có mạng: app vẫn hiện cache.
- [ ] `.env` thiếu trường: thông báo rõ ràng.
- [ ] Không cài Chrome/Edge: PNG báo lỗi, phần còn lại vẫn chạy.
- [ ] Gửi POST không có token: trả về 401/403.
- [ ] Gọi API từ origin khác: bị chặn.

Kiểm tra cài đặt:
- [ ] Cài installer trên VM sạch; không cần quyền admin để chạy.
- [ ] Gỡ cài đặt; dữ liệu trong `%APPDATA%` được giữ hoặc xoá theo lựa chọn.
- [ ] Cài lại từ phiên bản cũ; cấu hình cũ được giữ.

### 6.3 Hiệu năng
| Chỉ số | Baseline | Ngưỡng chấp nhận |
| --- | --- | --- |
| Render từ cache | ghi ở giai đoạn 0 | không tệ hơn 10% |
| Kích thước `.exe` | ghi ở giai đoạn 0 | không lớn hơn 10% |
| Thời gian khởi động | ghi ở giai đoạn 0 | không chậm hơn 2 giây |

---

## 7. CI/CD (GitHub Actions)

```yaml
# .github/workflows/ci.yml (phác thảo)
name: ci
on: [push, pull_request]
jobs:
  python:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: ruff check . && ruff format --check .
      - run: mypy src/
      - run: pytest --cov=src/tft_studio --cov-fail-under=70
      - run: pip-audit
  web:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: npm, cache-dependency-path: web/package-lock.json }
      - run: npm ci && npm run build && npm audit --omit=dev
  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
  build:
    needs: [python, web]
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-dev.txt
      - run: pyinstaller packaging/studio.spec --clean -y
```

---

## 8. Kế hoạch quay lui

- Mỗi giai đoạn là một nhánh; nếu lỗi nghiêm trọng, quay về tag `pre-refactor-v1` và giữ nhánh lỗi để điều tra.
- Không xoá `backend/` cho đến khi toàn bộ checklist mục 6.2 đạt.
- Giữ bản `.exe` phát hành cuối cùng (v1) để người dùng có thể quay lại.
- Nếu giai đoạn 4 gây hồi quy khó xử lý, có thể giữ `bridge.py` cũ và chỉ ra mắt phần tách service ở bản sau.

---

## 9. Tiêu chí hoàn thành

- [ ] Không có bí mật trong lịch sử Git; key cũ đã thu hồi.
- [ ] Mọi endpoint ghi yêu cầu token; CORS giới hạn localhost.
- [ ] Logic điều phối không phụ thuộc `webview`; có test pytest.
- [ ] Rate limiter dùng chung, thread-safe, có test.
- [ ] `ruff`, `mypy`, `pytest`, `gitleaks`, `pip-audit`, `npm audit` đều xanh trong CI.
- [ ] Build `.exe` và installer thành công; checklist 6.2 đạt.
- [ ] Dữ liệu người dùng nằm ngoài thư mục cài đặt.
- [ ] `ARCHITECTURE.md` và ADR đã viết; README cập nhật.

---

## 10. Ước lượng

| Giai đoạn | Ngày làm việc |
| --- | --- |
| 0. Đóng băng và baseline | 1 |
| 1. Bảo mật | 2–3 |
| 2. Characterization test | 3–5 |
| 3. Khung và di chuyển | 2–3 |
| 4. Tách service | 3–4 |
| 5. Giao diện và đóng gói | 3–4 |
| 6. Kiểm thử tích hợp | 3–5 |
| 7. Hoàn tất | 2 |
| **Tổng** | **~20–27 ngày** (một người, làm bán thời gian thì nhân khoảng 2) |

Ước lượng này giả định bạn đã đọc các file còn lại ở mục 2. Nếu phát hiện ràng buộc mới, cần cập nhật lại.
