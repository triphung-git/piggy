# TFT Post-Match Studio: Kế hoạch tái cấu trúc v2 (tối ưu cấu trúc, bảo mật, hiệu năng)

> Tài liệu này **bổ sung và thay thế một phần** `REFACTOR_PLAN.md` (v1).
> Các giai đoạn 0–7 của v1 vẫn giữ nguyên trình tự. v2 thay đổi: cấu trúc đích (mục 3 của v1), danh sách bảo mật, quality gate, và thêm tối ưu hiệu năng.

---

## 0. Cách đọc tài liệu

- Mục 1 liệt kê những điểm **cần kiểm chứng** trước khi sửa. Mình chưa đọc đủ mã nguồn để khẳng định chúng là lỗi.
- Mục 2 là cấu trúc đích v2.
- Mục 3 là bảo mật. Mỗi mối đe doạ có biện pháp, file bị ảnh hưởng và cách kiểm thử.
- Mục 4 là hiệu năng. Mỗi thay đổi có số đo baseline và ngưỡng.
- Mục 5 là chất lượng code và quality gate.
- Mục 6 là điều chỉnh các giai đoạn của v1.
- Mục 7 là những việc **không** làm, để tránh over-engineering.
- Mục 8 là tiêu chí hoàn thành.

---

## 1. Cần kiểm chứng trước khi sửa

Các mục dưới đây được suy ra từ những file đã đọc. Mỗi mục phải có bằng chứng (đoạn code, test tái hiện) trước khi đưa vào backlog chính thức.

| # | Nghi vấn | Căn cứ | Cách kiểm chứng |
| --- | --- | --- | --- |
| K1 | `/api/state` và `get_app_state` có thể trả `api_key` đầy đủ cho giao diện | `cfg.to_dict()` được gọi trong `get_app_state`; chưa đọc `AppConfig.to_dict` | Đọc `config.py`; gọi `/api/state` và xem có chuỗi `RGAPI-` không |
| K2 | Overlay có thể bị XSS nếu tên người chơi hoặc tiêu đề giải chứa HTML | HTML được sinh bằng chuỗi; `/api/overlay-html` được gắn vào `innerHTML` | Đọc `overlay_generator.py`; test với tên chứa `<img onerror>` |
| K3 | `custom_augments` có thể chứa đường dẫn như `../../x` | Giá trị được lưu nguyên và chỉ `strip()` | Test gửi `"../x.png"` qua POST; kiểm tra có đọc file ngoài `assets/` không |
| K4 | Upload avatar chưa kiểm tra loại và nội dung file | `pick_avatar_file` chỉ `copy2` theo đuôi | Thử file không phải ảnh có đuôi `.png` |
| K5 | Headless Chrome chạy với `--no-sandbox --allow-file-access-from-files` | `export_service.py` | Xác nhận render được nếu bỏ hai cờ, hoặc chuyển sang HTTP localhost |
| K6 | `js_api=bridge` phơi toàn bộ method public cho mọi JS trong cửa sổ | `app.py`, `bridge.py` | Liệt kê method public; xác định cửa sổ nào tải nội dung ngoài |
| K7 | `save_custom_augments` tồn tại ở cả `bridge.py` và `network_hub.py` với logic gần giống | So sánh hai hàm | Diff hai hàm; test hành vi tương đương |
| K8 | Mỗi lần gọi `fetch_recent_matches` tạo `RiotTFTClient` mới, nên rate limiter không được chia sẻ | `match_service.py` | Đếm số instance limiter khi polling và render chạy đồng thời |
| K9 | Thư mục `output/` có thể tăng không giới hạn vì `clean_matches_*.json` không bị dọn | Không thấy logic xoá cũ | Chạy render nhiều lần; đếm file |
| K10 | Bộ theo dõi file gọi `AppConfig.load()` và đọc lại `.env` theo chu kỳ 0.5 giây | `file_watcher.py` (chưa đọc đủ) | Đo CPU khi app chạy nhàn rỗi |

---

## 2. Cấu trúc đích v2

Thay đổi so với v1: thêm `pyproject.toml` làm trung tâm cấu hình, thêm `tools/` cho script nội bộ, thêm `.pre-commit-config.yaml`, `.github/dependabot.yml`, thư mục `sbom/` sinh tự động, và tách `tests/manual/` cho script thủ công.

```
tft-studio/
├── pyproject.toml                  # project, deps, ruff, mypy, pytest, coverage: một nguồn duy nhất
├── uv.lock                         # khoá phiên bản Python (hash-pinned)
├── .python-version                 # 3.11
├── .pre-commit-config.yaml         # ruff, gitleaks, check-added-large-files
├── .editorconfig
├── .gitattributes                  # chuẩn hoá line ending (LF), đánh dấu binary cho font/ảnh
├── .gitignore                      # đầy đủ: .env, output/, dist/, build/, avatars/, sbom/, .venv
├── .env.example                    # chỉ có tên biến, không có giá trị thật
├── overlay_config.example.json     # mẫu; file thật do người dùng tạo
│
├── src/tft_studio/
│   ├── __init__.py                 # __version__ đọc từ metadata
│   ├── __main__.py                 # python -m tft_studio
│   ├── paths.py                    # app_dir, bundle_dir, user_data_dir (%APPDATA%), resource()
│   ├── settings.py                 # pydantic-settings; không đọc file khi import
│   ├── logging_setup.py            # cấu hình log, có bộ lọc che bí mật
│   ├── core/
│   │   ├── models.py               # Pydantic v2 hoặc dataclass(slots=True): Match, Participant, OverlayConfig
│   │   ├── errors.py               # cây lỗi: TFTError > RiotAPIError > (AuthError, RateLimitError, NotFoundError)
│   │   └── security.py             # validate tên file, che bí mật, token
│   ├── riot/
│   │   ├── client.py               # RiotClient: chỉ HTTP, dùng requests.Session chung
│   │   ├── limiter.py              # SlidingWindowLimiter, thread-safe, dùng chung toàn process
│   │   └── routing.py              # REGION_MAPPING, kiểm tra region hợp lệ
│   ├── data/
│   │   ├── ddragon.py              # DDragonCatalog: load một lần, cache theo ngôn ngữ
│   │   └── match_parser.py         # raw JSON -> Match
│   ├── render/
│   │   ├── overlay.py              # sinh HTML bằng Jinja2 với autoescape=True
│   │   ├── templates/              # *.html.j2 (đổi từ overlay.html tĩnh)
│   │   └── png.py                  # xuất PNG qua Chromium headless, có timeout và hàng đợi
│   ├── services/
│   │   ├── studio.py               # StudioService: API nghiệp vụ, không phụ thuộc webview
│   │   ├── render_queue.py         # gộp render liên tiếp (coalesce), một worker
│   │   ├── polling.py              # auto-polling, dùng threading.Event
│   │   ├── cache.py                # đọc/ghi match cache, giới hạn số file (retention)
│   │   └── config_watcher.py       # theo dõi file, debounce
│   ├── api/
│   │   ├── app.py                  # create_app(service, token) -> FastAPI
│   │   ├── deps.py                 # dependency: service, xác thực token
│   │   ├── schemas.py              # Pydantic request/response, đầu vào có ràng buộc
│   │   ├── routes/
│   │   │   ├── status.py
│   │   │   ├── config.py
│   │   │   ├── riot.py
│   │   │   ├── overlay.py
│   │   │   └── assets.py           # augments, avatars
│   │   └── ws.py                   # Broadcaster
│   └── desktop/
│       ├── main.py                 # entrypoint PyWebView
│       ├── bridge.py               # lớp mỏng, có allowlist method
│       └── windows.py
│
├── web/                            # React + TS (đổi tên từ "Web Overlay/")
│   ├── src/
│   │   ├── api/                    # client gọi API, gắn token
│   │   ├── components/
│   │   └── lib/
│   ├── package.json                # đổi tên package, không còn "figma-make-app"
│   ├── package-lock.json
│   └── vite.config.ts
│
├── data/
│   ├── ddragon/                    # dữ liệu Data Dragon (có ghi chú giấy phép)
│   └── templates/                  # overlay.css; overlay.html.j2 nằm trong src
│
├── assets/
│   ├── fonts/
│   ├── branding/                   # icon, nền mặc định
│   └── avatars/.gitkeep            # avatar người dùng không commit
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/                     # overlay HTML chuẩn
│   ├── fixtures/                   # trận đã ẩn thông tin, phản hồi Riot giả
│   ├── security/                   # test XSS, path traversal, upload, token, CORS
│   ├── manual/                     # script thủ công (từ test_riot_connection.py)
│   └── conftest.py
│
├── packaging/
│   ├── studio.spec
│   ├── installer.iss
│   └── version_info.txt            # metadata cho exe
│
├── tools/
│   ├── build.ps1                   # thay build_exe.bat và .ps1
│   ├── run.ps1                     # thay run_app.bat và .ps1
│   └── sbom.py                     # sinh SBOM CycloneDX
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md                 # mô hình đe doạ, cách báo lỗi
│   ├── CONTRIBUTING.md
│   └── adr/
│
├── .github/
│   ├── workflows/ci.yml
│   ├── workflows/release.yml
│   ├── dependabot.yml
│   └── CODEOWNERS
│
├── README.md
├── README.vn.md
└── LICENSE
```

### Quy tắc đặt tên và phụ thuộc
- Dependency một chiều: `desktop → api/services → core`. `riot`, `data`, `render` không import `services`. `core` không import gì trong dự án.
- Kiểm tra bằng `import-linter` trong CI để chặn vi phạm.
- Tên module ngắn, không lặp tiền tố (`riot/client.py` thay vì `riot/riot_client.py`).

---

## 3. Bảo mật

### 3.1 Mô hình đe doạ

Ứng dụng chạy cục bộ, nhưng vẫn có các bề mặt tấn công:
1. **Trang web bên ngoài** trong trình duyệt của người dùng gửi request đến `localhost:8080` (CSRF, DNS rebinding).
2. **Dữ liệu từ Riot** và **tên người chơi** được hiển thị trong overlay (XSS).
3. **Đầu vào người dùng**: đường dẫn augment, file avatar, API key, Riot ID.
4. **Bí mật**: API key trong `.env`, log, phản hồi API, lịch sử Git.
5. **Chuỗi cung ứng**: thư viện Python và npm, công cụ build.
6. **Quyền hệ điều hành**: ghi file cạnh `.exe` trong Program Files; cờ `--no-sandbox` của Chromium.
7. **Cầu nối JS ↔ Python**: `js_api` phơi method cho mọi JS trong cửa sổ.

### 3.2 Biện pháp

| # | Mối đe doạ | Biện pháp | File | Kiểm thử |
| --- | --- | --- | --- | --- |
| S1 | CSRF, DNS rebinding | Kiểm tra header `Host` và `Origin` chỉ cho `127.0.0.1:<port>`, `localhost:<port>`; yêu cầu header `X-Studio-Token` cho mọi method ghi | `api/security.py`, `api/deps.py` | Gửi request với Origin lạ và Host lạ, mong đợi 403 |
| S2 | Token lộ | Token sinh ngẫu nhiên (`secrets.token_urlsafe(32)`) mỗi lần khởi động; không đưa vào URL; giao diện nhận token qua `js_api` hoặc nhúng lúc build cho cửa sổ desktop | `api/security.py`, `desktop/bridge.py` | Kiểm tra token không xuất hiện trong log và trong `/api/status` |
| S3 | CORS quá rộng | Bỏ `allow_origins=["*"]`; bỏ `allow_credentials` nếu không cần | `api/app.py` | Test header `Access-Control-Allow-Origin` |
| S4 | XSS trong overlay | Dùng Jinja2 với `autoescape=True`; mọi giá trị từ Riot và config đi qua bộ lọc escape; thêm Content-Security-Policy `default-src 'self'` cho `/overlay` | `render/overlay.py`, `api/routes/overlay.py` | Test tên `<img src=x onerror=alert(1)>`; kiểm tra CSP header |
| S5 | `innerHTML` nhận HTML chưa escape | Giao diện chỉ thay DOM bằng HTML đã được server escape; ghi chú trong `SECURITY.md` | `web/src`, `/api/overlay-html` | Test end-to-end với tên chứa HTML |
| S6 | Path traversal qua `custom_augments` | Chỉ chấp nhận tên file không có `/`, `\`, `..`; đối chiếu với danh sách augment từ DDragon (allowlist) | `core/security.py`, `api/schemas.py` | Test `../x.png`, `C:\x`, `%2e%2e` |
| S7 | Upload avatar độc hại | Kiểm tra magic bytes (không chỉ đuôi); giới hạn kích thước (ví dụ 2 MB); mở bằng Pillow `verify()` và `load()`; ghi ra tên ngẫu nhiên; chặn SVG | `api/routes/assets.py`, `core/security.py` | Thử file text đổi đuôi, file 50 MB, PNG hỏng |
| S8 | API key lộ qua API | Không bao giờ trả key đầy đủ; chỉ trả dạng che (`RGAPI-abcd...wxyz`) và `has_api_key` | `services/studio.py`, `api/schemas.py` | Test toàn bộ endpoint GET, mong đợi không có chuỗi `RGAPI-` đầy đủ |
| S9 | Key trong `.env` đọc được bởi mọi tiến trình của người dùng | Trên Windows lưu key bằng `keyring` (Windows Credential Manager, mã hoá theo người dùng); `.env` chỉ giữ cấu hình không nhạy cảm | `settings.py`, `core/secrets.py` | Test lưu và đọc lại; kiểm tra `.env` không còn key sau migration |
| S10 | Key trong log | Bộ lọc log thay `RGAPI-*` bằng `RGAPI-****`; không log URL có key (key đi trong header, không trong URL) | `logging_setup.py` | Test log không có chuỗi key |
| S11 | Chromium quá quyền | Bỏ `--no-sandbox` và `--allow-file-access-from-files`; render qua `http://127.0.0.1:<port>/render/<id>` thay vì `file://`; môi trường tối thiểu (`env={}` + `PATH` cần thiết); timeout 25 giây | `render/png.py` | Test render thành công không có hai cờ trên; test timeout |
| S12 | `js_api` phơi quá nhiều | Allowlist: bridge chỉ export các method có decorator `@exposed`; cửa sổ overlay không có `js_api` | `desktop/bridge.py`, `desktop/windows.py` | Test liệt kê method được expose bằng danh sách cố định |
| S13 | Ghi file cạnh `.exe` | Dữ liệu người dùng vào `%APPDATA%\TFT-PostMatch-Studio\`; `paths.user_data_dir()` là nguồn duy nhất | `paths.py`, `installer.iss` | Cài vào Program Files, chạy không cần quyền admin |
| S14 | Lộ bí mật trong Git | `gitleaks` ở pre-commit và CI; `git filter-repo` nếu đã commit; thu hồi key | `.pre-commit-config.yaml`, CI | Commit thử có key giả; hook phải chặn |
| S15 | Phụ thuộc có lỗ hổng | `pip-audit`, `npm audit --omit=dev`, Dependabot hằng tuần; khoá phiên bản bằng `uv.lock` và `package-lock.json` | CI, `.github/dependabot.yml` | CI chặn merge nếu có lỗ hổng mức cao |
| S16 | Chuỗi cung ứng build | Sinh SBOM CycloneDX mỗi release; ghi hash của `.exe` vào `SHA256SUMS`; GitHub Actions dùng phiên bản ghim theo SHA | `tools/sbom.py`, `release.yml` | Kiểm tra SBOM có đủ thư viện; hash khớp |
| S17 | Phát hiện mẫu bất thường | Giới hạn tần suất gọi endpoint ghi (ví dụ 10 yêu cầu/giây) | `api/security.py` | Test trả 429 khi vượt ngưỡng |
| S18 | Quyền cài đặt | Installer chạy per-user, không yêu cầu admin; ký số `.exe` và installer nếu có chứng chỉ | `installer.iss`, `release.yml` | Kiểm tra chữ ký bằng `signtool verify` |
| S19 | Điều khoản Riot | Không lưu key trong repo công khai; ghi rõ "unofficial" trong README; kiểm tra điều khoản của Riot và Data Dragon trước khi đưa dữ liệu vào repo | `docs/SECURITY.md`, `README.md` | Rà soát thủ công |
| S20 | Chính sách báo lỗi | `SECURITY.md` ghi cách báo lỗi riêng tư (GitHub Security Advisory) | `docs/SECURITY.md` | Có trong repo |

### 3.3 Hardening Chromium cụ thể

Cấu hình khuyến nghị cho `render/png.py`:
```python
args = [
    exe,
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--window-size=1920,1080",
    "--disable-extensions",
    "--disable-background-networking",
    "--no-first-run",
    f"--user-data-dir={tmp_profile}",   # profile tạm, xoá sau render
    f"--screenshot={out_png}",
    f"http://127.0.0.1:{port}/render/{render_id}",
]
subprocess.run(args, env=minimal_env(), timeout=25, check=False, capture_output=True)
```

Lý do: profile tạm không để lại cookie hay cache; không cần `--no-sandbox` khi không chạy bằng quyền admin.

---

## 4. Hiệu năng

### 4.1 Baseline cần đo ở giai đoạn 0
- Thời gian render từ cache (ms), trung vị 10 lần.
- Thời gian từ bấm Render đến khi OBS cập nhật (ms).
- CPU khi nhàn rỗi (%), trung bình 5 phút.
- Số lần đọc `.env` và `overlay_config.json` trong 1 phút khi nhàn rỗi.
- Số lần gọi Riot API trong 1 phút khi polling bật.
- Kích thước `.exe` (MB), thời gian khởi động (giây).
- Số file trong `output/` sau 20 lần render.

### 4.2 Tối ưu

| # | Vấn đề (căn cứ) | Thay đổi | Số đo mong đợi |
| --- | --- | --- | --- |
| P1 | `AppConfig.load()` và `load_overlay_config()` được gọi nhiều nơi, đọc đĩa mỗi lần (K10) | `Settings` và `OverlayConfig` nạp một lần, cache trong service; chỉ nạp lại khi watcher báo thay đổi | Số lần đọc file giảm về gần 0 khi nhàn rỗi |
| P2 | Bộ theo dõi kiểm tra mỗi 0.5 giây (K10) | Dùng `watchdog` (sự kiện hệ điều hành); fallback 2 giây nếu không có | CPU nhàn rỗi giảm đáng kể |
| P3 | `get_ddragon_loader` có thể nạp lại dữ liệu nhiều lần | `DDragonCatalog` cache theo ngôn ngữ với `functools.lru_cache`; load một lần khi khởi động trong luồng nền | Lần render đầu nhanh hơn; không nạp lại |
| P4 | Mỗi lần fetch tạo `RiotTFTClient` mới, limiter không dùng chung (K8) | Một `RiotClient` và một `SlidingWindowLimiter` cho toàn process, thread-safe | Không vượt giới hạn 20/giây và 100/2 phút khi các luồng chạy đồng thời |
| P5 | Limiter giữ lock khi `sleep` (nếu viết như vậy) | Tính thời gian chờ trong lock, `sleep` ngoài lock | Các luồng không chặn nhau không cần thiết |
| P6 | Render liên tiếp tạo nhiều luồng PNG cùng lúc (`threading.Thread` mỗi lần) | `render_queue`: gộp các yêu cầu trong 300 ms; một worker xuất PNG; ghi file tạm rồi đổi tên nguyên tử | Không còn ghi đè file PNG; ít tiến trình Chromium song song |
| P7 | Overlay HTML sinh lại dù dữ liệu không đổi | Tính hash của (trận, cấu hình, phiên bản template); bỏ qua nếu hash không đổi | Render từ cache không sinh lại HTML |
| P8 | `output/clean_matches_*.json` tăng vô hạn (K9) | `cache.py` giữ tối đa 50 file, xoá file cũ nhất; file `latest` luôn giữ | Thư mục không phình ra |
| P9 | `glob` và `stat` lặp lại trong `_get_best_match_data` | Chỉ quét một lần khi khởi động; giữ chỉ mục trong bộ nhớ | Nhanh hơn khi có nhiều file cache |
| P10 | Bọc `get_augments_list` tính lại mỗi lần gọi | Cache kết quả theo ngôn ngữ (dữ liệu tĩnh) | Phản hồi `/api/augments` gần như tức thời |
| P11 | Tạo nhiều `requests.Session` | Một session chung, `HTTPAdapter` với pool; đặt `timeout` và `Retry` của urllib3 cho lỗi kết nối (không dùng retry cho 429) | Ít bắt tay TLS; xử lý lỗi nhất quán |
| P12 | `uvicorn` ghi log cấp `warning` và luồng nền | Giữ như cũ nhưng dùng `uvicorn.Config(access_log=False)` | Bớt I/O log |
| P13 | Import nặng khi khởi động (Pillow, webview, FastAPI) | `import` có điều kiện trong các hàm dùng; `__main__` chỉ import phần cần thiết | Khởi động nhanh hơn một chút |
| P14 | Kích thước `.exe` | Giữ `excludes` hiện có; kiểm tra bằng `pyinstaller --log-level` xem module nào được kéo vào; bỏ `rich` nếu chỉ dùng cho log và đã có `logging` | Giảm MB; đo sau mỗi thay đổi |
| P15 | Frontend: bundle một file (`vite-plugin-singlefile`) | Giữ; kiểm tra kích thước bundle; tách code theo route nếu bundle > 300 KB | Bundle nhỏ hơn, mở nhanh hơn |
| P16 | WebSocket gửi `PING` mỗi 30 giây khi không có sự kiện | Giữ; kiểm tra client tự kết nối lại có backoff | Ít kết nối rơi không cần thiết |

### 4.3 Ngưỡng chấp nhận
- Render từ cache: không chậm hơn baseline; mục tiêu nhanh hơn ít nhất 20% nếu P7 có hiệu quả.
- CPU nhàn rỗi: giảm ít nhất 50% so với baseline.
- `.exe`: không lớn hơn baseline; mục tiêu nhỏ hơn 10%.
- `output/`: không quá 50 file JSON sau 100 lần render.

---

## 5. Chất lượng code và quality gate

### 5.1 Quy ước
- **Ngôn ngữ**: docstring và comment trong code viết bằng tiếng Anh; chuỗi hiển thị cho người dùng để trong file `i18n/vi.json` và `i18n/en.json`. Hiện tại code trộn tiếng Việt và tiếng Anh, nên chuẩn hoá một lần.
- **Kiểu dữ liệu**: `mypy --strict` cho `core/`, `services/`, `api/`; `mypy` thường cho phần còn lại; không dùng `Any` trong `core/`.
- **Mô hình dữ liệu**: Pydantic v2 cho đầu vào API và cấu hình; `dataclass(slots=True, frozen=True)` cho mô hình nội bộ.
- **Lỗi**: một cây exception; không so chuỗi lỗi (`"401" in str(exc)`); mỗi lỗi có mã và thông báo tiếng Việt cho người dùng.
- **Hàm**: không quá 40 dòng; không quá 4 tham số, dùng dataclass khi nhiều hơn.
- **Không có side effect khi import**: không tạo thư mục, không đọc file, không khởi động luồng ở cấp module.

### 5.2 Loại bỏ trùng lặp và code chết

| Mục | Vị trí | Hành động |
| --- | --- | --- |
| `get_augments_list` / `/api/augments` | `bridge.py`, `network_hub.py` | Gom về `services/studio.py`; hai nơi gọi chung |
| `save_custom_augments` | `bridge.py`, `network_hub.py` | Gom về `services/studio.py` (K7) |
| Callback lỗi "fetch thất bại" | `bridge.py` (3 bản gần giống) | Một hàm `_report_fetch_error(exc)` |
| Kiểm tra lỗi xác thực bằng chuỗi | `bridge.py` (3 chỗ) | `isinstance(exc, AuthError)` |
| `get_transform`, `update_overlay_transform` | `bridge.py` | Xoá (đã bỏ tính năng) |
| `toggle_overlay`, `toggle_overlay_visibility`, `show_overlay`, `hide_overlay` | `bridge.py` | Giữ hai hàm `show`, `hide` và `set_overlay_visible(bool)` |
| `load_overlay_config` import hai tên khác nhau | `bridge.py`, `network_hub.py`, `app.py` | Một nguồn duy nhất trong `settings.py` |
| `resolve_puuid` và `fetch_recent_matches` đều tạo client | `match_service.py` | Dùng `RiotClient` dùng chung (P4) |
| `test_riot_connection.py` ở thư mục gốc | gốc repo | Chuyển sang `tests/manual/` |
| `scratch/__pycache__` | gốc repo | Xoá khỏi Git; thêm vào `.gitignore` |
| `from typing import Optional` thiếu | `export_service.py` | Sửa khi chuyển sang `render/png.py` (ruff sẽ báo) |
| `rich` (nếu không dùng ngoài log) | `requirements.txt` | Gỡ bỏ sau khi kiểm tra |
| `Pillow` (nếu chỉ dùng để kiểm tra avatar) | `requirements.txt` | Giữ, vì cần cho S7 |

### 5.3 Ruff: bộ luật
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "S", "C4", "PL", "RUF", "PERF", "ANN", "TID", "ARG"]
ignore = ["ANN101", "ANN102"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN", "PLR2004"]
```

Nhóm `S` (bandit) bắt được `subprocess` không an toàn, `assert` trong code thật, và các lỗi bảo mật thường gặp.

### 5.4 Pre-commit
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-added-large-files
        args: [--maxkb=1024]
      - id: check-merge-conflict
      - id: end-of-file-fixer
```

### 5.5 Quality gate (CI)

| Gate | Công cụ | Ngưỡng |
| --- | --- | --- |
| Lint | `ruff check` | 0 lỗi |
| Format | `ruff format --check` | không đổi |
| Kiểu | `mypy` | 0 lỗi; `--strict` cho `core`, `services`, `api` |
| Kiến trúc | `import-linter` | 0 vi phạm |
| Unit và integration | `pytest` | 100% xanh |
| Bảo mật (test) | `pytest tests/security` | 100% xanh |
| Coverage | `pytest --cov` | ≥ 75% `src/tft_studio`; ≥ 90% `core/security.py` |
| Bí mật | `gitleaks` | 0 phát hiện |
| SAST | CodeQL (Python, JavaScript) | Không có lỗi mức cao |
| Phụ thuộc Python | `pip-audit` | 0 lỗ hổng mức cao |
| Phụ thuộc npm | `npm audit --omit=dev` | 0 lỗ hổng mức cao |
| Golden | so sánh `overlay.html` | khớp |
| Build | PyInstaller, Vite | thành công |
| Kích thước | script kiểm tra | `.exe` không tăng quá 10% so với baseline |

---

## 6. Điều chỉnh các giai đoạn của v1

| Giai đoạn v1 | Thay đổi trong v2 |
| --- | --- |
| 0. Đóng băng và baseline | Thêm bảng baseline hiệu năng (mục 4.1); đọc `config.py`, `overlay_generator.py`, `file_watcher.py`, `installer.iss` (K1, K2, K10) |
| 1. Bảo mật | Thêm S1–S3, S8, S10, S14, S15 vào giai đoạn này vì không phụ thuộc cấu trúc mới; S9 (keyring) làm sau khi có `settings.py` |
| 2. Characterization test | Thêm `tests/security/` cho S1–S7 và S12; thêm test hiệu năng cơ bản (P4, P6, P7) |
| 3. Khung và di chuyển | Dùng cấu trúc v2 (mục 2); thêm `pyproject.toml`, `uv`, pre-commit ngay từ đầu |
| 4. Tách service | Thêm `render_queue` (P6), `cache` với retention (P8), `RiotClient` dùng chung (P4); gom trùng lặp (mục 5.2) |
| 5. Giao diện và đóng gói | Thêm S11 (Chromium), S13 (`%APPDATA%`), S16, S18; Jinja2 cho overlay (S4) |
| 6. Kiểm thử | Thêm kiểm thử XSS và path traversal trên app thật; đo lại baseline (mục 4.1) |
| 7. Hoàn tất | Thêm `SECURITY.md`, SBOM, chữ ký số, `CODEOWNERS`, Dependabot |

Thứ tự ưu tiên khi thời gian hạn chế:
1. Giai đoạn 1 (bảo mật lộ key và lỗ hổng đã biết).
2. S4, S6, S7 (XSS, path traversal, upload): dễ bị khai thác nhất qua dữ liệu đầu vào.
3. Giai đoạn 2 (test) để đảm bảo các thay đổi sau không làm hỏng.
4. P1, P4, P6, P8 (hiệu năng và ổn định nhất).
5. Phần còn lại.

---

## 7. Những việc không nên làm

- **Không chuyển sang Electron hay Tauri** ở giai đoạn này. Chi phí viết lại lớn, lợi ích không tương xứng với một ứng dụng cục bộ.
- **Không tách microservice hay dùng Docker để chạy desktop.** Docker chỉ có ý nghĩa cho phần backend không giao diện; xem `docs/` về tách backend trước.
- **Không dùng database** (SQLite, Postgres). Cache JSON đủ cho khối lượng hiện tại; chỉ cân nhắc SQLite nếu cần truy vấn lịch sử lớn.
- **Không viết lại React sang framework khác.** Giao diện đã hoạt động; chỉ cần sắp xếp lại thư mục và đảm bảo an toàn đầu vào.
- **Không tối ưu sớm.** Chỉ làm P-items khi số đo baseline cho thấy vấn đề thật.
- **Không đổi sang `--onefile`** trong PyInstaller: thời gian khởi động chậm và dễ bị antivirus chặn hơn `onedir`.
- **Không tắt xác thực để "dễ test".** Dùng fixture token trong test.

---

## 8. Tiêu chí hoàn thành v2

Bảo mật:
- [ ] `gitleaks` sạch trên toàn lịch sử; key cũ đã thu hồi.
- [ ] Mọi endpoint ghi yêu cầu token; Host và Origin được kiểm tra.
- [ ] Không endpoint nào trả API key đầy đủ.
- [ ] Overlay escape đầy đủ; CSP có trong header; test XSS đạt.
- [ ] Augment và avatar qua kiểm tra đầu vào; test path traversal và upload đạt.
- [ ] `js_api` chỉ phơi method có `@exposed`.
- [ ] Chromium không dùng `--no-sandbox`; render qua HTTP localhost.
- [ ] Dữ liệu người dùng nằm trong `%APPDATA%`; installer per-user.
- [ ] Bí mật Riot lưu bằng keyring trên Windows; `.env` không còn key.
- [ ] SBOM và `SHA256SUMS` có trong mỗi release.

Cấu trúc và code:
- [ ] Cấu trúc đúng mục 2; `import-linter` không có vi phạm.
- [ ] Không còn trùng lặp và code chết ở mục 5.2.
- [ ] `ruff`, `mypy --strict` (phần lõi), `pytest` xanh trong CI.
- [ ] Coverage ≥ 75%.
- [ ] Pre-commit chạy trên máy mọi thành viên.

Hiệu năng:
- [ ] CPU nhàn rỗi giảm ≥ 50% so với baseline.
- [ ] Không còn đọc đĩa lặp lại khi nhàn rỗi.
- [ ] Limiter dùng chung; không vượt giới hạn Riot khi polling và render chạy cùng lúc.
- [ ] `output/` không vượt 50 file JSON.
- [ ] Render liên tiếp không tạo ghi đè PNG.
- [ ] `.exe` không lớn hơn baseline.

Vận hành:
- [ ] Checklist thủ công ở v1 mục 6.2 đạt trên VM Windows sạch.
- [ ] `ARCHITECTURE.md`, `SECURITY.md`, `CONTRIBUTING.md` và ít nhất 3 ADR có trong repo.
- [ ] README (Anh và Việt) cập nhật cách chạy, build và cấu hình.

---

## 9. Phụ lục: ví dụ kiểm thử bảo mật

```python
# tests/security/test_overlay_escape.py
def test_player_name_is_escaped(tmp_path):
    match = build_match(player_name='<img src=x onerror="alert(1)">')
    html = render_overlay(match, OverlayConfig())
    assert "<img src=x" not in html
    assert "&lt;img" in html

# tests/security/test_augment_names.py
import pytest
@pytest.mark.parametrize("name", ["../x.png", "..\\x.png", "/etc/passwd", "a/b.png", "C:x.png"])
def test_augment_rejects_path(name):
    with pytest.raises(ValidationError):
        AugmentSelection(custom_augments=[name])

# tests/security/test_token.py
def test_post_without_token_is_rejected(client):
    r = client.post("/api/config", json={})
    assert r.status_code in (401, 403)

def test_foreign_origin_is_rejected(client, token):
    r = client.post("/api/config", json={}, headers={"X-Studio-Token": token, "Origin": "https://evil.example"})
    assert r.status_code == 403

# tests/security/test_no_key_leak.py
def test_state_never_contains_full_key(client, configured_key):
    body = client.get("/api/state").text
    assert configured_key not in body
    assert "RGAPI-" not in body or "..." in body
```

---

## 10. Tóm tắt thay đổi so với v1

1. Thêm mục 1: danh sách 10 nghi vấn cần kiểm chứng, tránh sửa theo phỏng đoán.
2. Cấu trúc đích v2: `pyproject.toml`, `uv`, `tools/`, `import-linter`, Jinja2 templates, `%APPDATA%`, tách `security/`.
3. Bảo mật: 20 mối đe doạ có biện pháp, file và cách kiểm thử; thêm keyring, CSP, allowlist `js_api`, hardening Chromium.
4. Hiệu năng: 16 thay đổi có số đo, gồm cache cấu hình, watchdog, render queue, limiter dùng chung, cache DDragon và giới hạn retention.
5. Quality gate: thêm `mypy --strict`, `import-linter`, CodeQL, SBOM, kiểm tra kích thước `.exe`.
6. Thứ tự ưu tiên khi thời gian hạn chế.
7. Danh sách việc không nên làm.
