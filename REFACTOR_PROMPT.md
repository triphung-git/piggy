# PROMPT: Tái cấu trúc TFT Post-Match Studio

> Dùng file này làm prompt đầy đủ cho một AI agent lập trình (Claude Code, Codex, Cursor agent hoặc tương đương).
> Đặt file này cùng với `REFACTOR_PLAN.md` và `REFACTOR_PLAN_v2.md` ở thư mục gốc repo trước khi chạy.

---

## 1. Vai trò và mục tiêu

Bạn là kỹ sư phần mềm cấp senior, phụ trách tái cấu trúc repo **TFT Post-Match Studio** (Python + FastAPI + PyWebView + React/TypeScript, đóng gói bằng PyInstaller và Inno Setup, chạy trên Windows).

Mục tiêu:
1. Tổ chức lại cấu trúc thư mục theo mục 2 của `REFACTOR_PLAN_v2.md`.
2. Sửa các vấn đề bảo mật theo mục 3 của `REFACTOR_PLAN_v2.md`.
3. Tối ưu hiệu năng theo mục 4 của `REFACTOR_PLAN_v2.md`, chỉ khi có số đo baseline chứng minh vấn đề.
4. Giữ nguyên toàn bộ hành vi người dùng đã có (checklist mục 6.2 của `REFACTOR_PLAN.md`).

Không có mục tiêu nào được đánh đổi hành vi hiện có để lấy cấu trúc đẹp hơn.

---

## 2. Nguyên tắc bất biến (không được vi phạm)

1. **Không đoán.** Trước khi sửa bất kỳ lỗi nào, phải tái hiện được lỗi bằng test hoặc đoạn code cụ thể. Nếu không tái hiện được, ghi vào `docs/OPEN_QUESTIONS.md` và không sửa.
2. **Mỗi commit phải chạy được.** Trước mỗi commit: `ruff check`, `ruff format --check`, `pytest` đều xanh; app khởi động được.
3. **Tách commit di chuyển khỏi commit sửa logic.** Commit di chuyển file chỉ dùng `git mv` và sửa import; không đổi logic trong cùng commit.
4. **Không xoá code cũ cho đến khi code mới đã được test.** Trong giai đoạn chuyển tiếp, giữ `backend/` làm shim.
5. **Không commit bí mật.** Không đưa `.env`, `output/`, key, token, avatar cá nhân, hay dữ liệu trận có thông tin người chơi vào Git. Nếu phát hiện bí mật trong code hoặc lịch sử, dừng lại và báo người dùng.
6. **Không tự viết lại lịch sử Git.** Các lệnh `git filter-repo`, `git push --force`, `git rebase -i` trên nhánh chung chỉ thực hiện sau khi có xác nhận rõ ràng từ người dùng. Chuẩn bị lệnh, ghi vào báo cáo, chờ xác nhận.
7. **Không tắt kiểm tra để qua CI.** Không dùng `# noqa`, `# type: ignore`, `--cov-fail-under` thấp hơn, hay bỏ test chỉ để pass. Nếu cần ngoại lệ, ghi lý do vào `docs/adr/` và báo người dùng.
8. **Không thêm phụ thuộc mới** nếu chưa liệt kê trong báo cáo kèm lý do và giấy phép.
9. **Không dùng Docker, Electron, database, hay `--onefile`** trong đợt này (xem mục 7 của `REFACTOR_PLAN_v2.md`).
10. **Giữ ngôn ngữ người dùng.** Chuỗi hiển thị cho người dùng vẫn tiếng Việt; code và docstring viết tiếng Anh.

---

## 3. Đầu vào cần đọc trước khi làm

Đọc đầy đủ các file sau, theo thứ tự:
1. `REFACTOR_PLAN.md`: trình tự giai đoạn 0–7.
2. `REFACTOR_PLAN_v2.md`: cấu trúc đích, bảo mật, hiệu năng, quality gate.
3. `README.md`, `README.vn.md`.
4. `requirements.txt`, `studio.spec`, `installer.iss`, `build_exe.bat`, `build_exe.ps1`, `run_app.bat`, `run_app.ps1`.
5. `desktop/app.py`, `desktop/bridge.py`, `desktop/local_server.py`.
6. `backend/*.py`, toàn bộ.
7. `Web Overlay/package.json`, `Web Overlay/vite.config.ts`, `Web Overlay/src/**`.
8. `templates/overlay.html`, `templates/overlay.css`, `overlay_config.json`, `.env.example`, `.gitignore`.
9. `test_riot_connection.py`.

Sau khi đọc, tạo `docs/BASELINE.md` gồm:
- Danh sách mọi file và vai trò một dòng.
- Danh sách hành vi người dùng quan sát được (từ code và README).
- Danh sách các nghi vấn K1–K10 trong `REFACTOR_PLAN_v2.md` mục 1, kèm kết quả kiểm chứng: **xác nhận**, **bác bỏ**, hoặc **chưa rõ** và lý do.

Không bắt đầu sửa code trước khi `docs/BASELINE.md` được tạo.

---

## 4. Các giai đoạn phải làm theo thứ tự

Mỗi giai đoạn kết thúc bằng một điều kiện dừng. Không chuyển giai đoạn khi điều kiện chưa đạt.

### Giai đoạn 0: Chuẩn bị
- Tạo nhánh `refactor/main` từ `main`. Mọi công việc làm trên nhánh này.
- Gắn tag `pre-refactor-v1` tại `main` (chỉ tạo tag cục bộ; push tag khi được xác nhận).
- Đo baseline theo mục 4.1 của `REFACTOR_PLAN_v2.md`; ghi vào `docs/BASELINE.md`.
- **Dừng khi:** `docs/BASELINE.md` đầy đủ, tag tồn tại.

### Giai đoạn 1: Bảo mật khẩn cấp
- Chạy `gitleaks detect --log-opts="--all"` (cài nếu chưa có). Ghi kết quả vào `docs/SECURITY_AUDIT.md`, **không** in giá trị bí mật ra terminal hay báo cáo; chỉ ghi tên file, dòng, loại bí mật, và commit.
- Nếu phát hiện bí mật thật trong lịch sử: dừng và báo người dùng để họ thu hồi key. Không tự xoá lịch sử.
- `git rm --cached` cho `.env`, `output/`, `scratch/`, `__pycache__/`. Cập nhật `.gitignore` theo mục 2 của `REFACTOR_PLAN_v2.md`.
- Thêm `tests/security/` với các test cho S1, S3 (Host/Origin, CORS, token). Viết test trước, thấy fail, rồi sửa.
- Sửa `network_hub.py` (sẽ được chuyển sang `api/` sau): bỏ `allow_origins=["*"]`, thêm kiểm tra Host và Origin, thêm token cho method ghi.
- Sửa WebSocket dùng `location.host` thay vì cổng cố định.
- Sửa `bridge.py`: gắn `window.smoothUpdate` (K-liên quan đến overlay reload).
- **Dừng khi:** `gitleaks` không phát hiện bí mật mới trong các commit; `tests/security/` xanh; app chạy được luồng render cơ bản.

### Giai đoạn 2: Characterization test
- Tạo `tests/fixtures/`: ít nhất 2 trận JSON đã ẩn thông tin cá nhân (thay tên bằng tên giả, thay PUUID bằng chuỗi giả), và phản hồi giả cho các mã 200, 401, 404, 429, 500.
- Viết test cho:
  - `parse_tft_match` với fixture.
  - `generate_overlay_html` so với `tests/golden/overlay.html` (bỏ qua timestamp).
  - `RiotTFTClient`: retry 429, backoff, phân loại 401 và 404 (dùng `responses`).
  - `_SlidingWindowLimiter`: không vượt 20 request/giây.
  - `load_overlay_config` và `save_overlay_config`.
- Test phải xanh trên mã hiện tại trước khi di chuyển bất kỳ file nào.
- **Dừng khi:** coverage ≥ 60% cho `backend/`; toàn bộ test xanh.

### Giai đoạn 3: Khung dự án và di chuyển thuần
- Tạo `pyproject.toml` theo `REFACTOR_PLAN_v2.md` mục 2 và 5.3. Dùng `uv` nếu có, nếu không dùng `pip-tools`; tạo lock file.
- Tạo cấu trúc `src/tft_studio/`, `tests/`, `packaging/`, `tools/`, `docs/`, `.github/`.
- Cài `.pre-commit-config.yaml` theo mục 5.4.
- Di chuyển theo thứ tự, mỗi module một commit `git mv`:
  1. `paths.py`, `settings.py`
  2. `riot/` (client, limiter, routing)
  3. `data/` (ddragon, match_parser)
  4. `render/` (overlay, png)
  5. `services/`
  6. `api/`
  7. `desktop/`
- Chạy test sau mỗi commit. Nếu test fail do import, sửa import; không sửa logic.
- Giữ shim `backend/` cho đến khi giai đoạn 6 hoàn tất.
- **Dừng khi:** test xanh; `python -m tft_studio` khởi động được.

### Giai đoạn 4: Tách service khỏi PyWebView
- Tạo `services/studio.py` với `StudioService`. Không import `webview`.
- Gom các hàm trùng lặp theo mục 5.2 của `REFACTOR_PLAN_v2.md` (`get_augments_list`, `save_custom_augments`, callback lỗi, kiểm tra xác thực).
- Thay kiểm tra lỗi bằng chuỗi (`"401" in str(exc)`) bằng `isinstance(exc, AuthError)`.
- Thêm `render/queue` (P6): gộp render trong 300 ms, một worker, ghi file tạm rồi đổi tên.
- Thêm `services/cache.py` với retention 50 file (P8).
- Một `RiotClient` và một `SlidingWindowLimiter` dùng chung cho toàn process, thread-safe (P4, P5).
- Bỏ `_bridge_ref` toàn cục; truyền service vào `create_app(service, token)`.
- Chuyển `bridge.py` thành lớp mỏng với allowlist `@exposed` (S12).
- Viết test cho `StudioService` không cần cửa sổ.
- **Dừng khi:** test `StudioService` xanh; không còn `import webview` ngoài `desktop/`; tests bảo mật xanh.

### Giai đoạn 5: Bảo mật đầu vào và overlay
- Overlay: chuyển sang Jinja2 với `autoescape=True` (S4). Thêm CSP header cho `/overlay`.
- Kiểm tra augment: chỉ chấp nhận tên file không có `/`, `\`, `..` và có trong danh sách DDragon (S6).
- Avatar: kiểm tra magic bytes, giới hạn 2 MB, mở bằng Pillow `verify()` và `load()`, ghi ra tên ngẫu nhiên, chặn SVG (S7).
- Không trả API key đầy đủ qua bất kỳ endpoint nào (S8). Thêm test quét toàn bộ endpoint GET.
- Bộ lọc log che key (S10).
- Chromium: bỏ `--no-sandbox` và `--allow-file-access-from-files`; render qua `http://127.0.0.1:<port>/render/<id>`; profile tạm; timeout 25 giây (S11).
- Chuyển dữ liệu người dùng sang `%APPDATA%\TFT-PostMatch-Studio\` qua `paths.user_data_dir()` (S13).
- Keyring cho API key trên Windows (S9). Nếu chưa làm được, ghi vào `docs/OPEN_QUESTIONS.md` và giữ `.env`, không được để key trong log hay API.
- **Dừng khi:** toàn bộ `tests/security/` xanh, gồm test XSS, path traversal, upload, token, không lộ key.

### Giai đoạn 6: Giao diện, đóng gói và kiểm thử
- Đổi `Web Overlay/` thành `web/`. Đổi tên package trong `package.json`. Commit `package-lock.json`.
- Cập nhật `packaging/studio.spec`: `datas` gồm `web/dist`, `data/ddragon`, `data/templates`, `assets`.
- Cập nhật `packaging/installer.iss`: per-user, không cần admin, dữ liệu vào `%APPDATA%`.
- Thay `build_exe.*` và `run_app.*` bằng `tools/build.ps1` và `tools/run.ps1`.
- Tạo `tools/sbom.py` (CycloneDX) và sinh `SHA256SUMS` khi build.
- Chạy `npm run build`, `pyinstaller packaging/studio.spec --clean -y`, build installer.
- Đo lại các chỉ số ở `docs/BASELINE.md` và so sánh với ngưỡng mục 4.3.
- Tạo `docs/MANUAL_TEST.md` theo checklist mục 6.2 của `REFACTOR_PLAN.md`. **Không tự đánh dấu hoàn thành** các mục cần chạy trên Windows thật; để trống và báo người dùng.
- **Dừng khi:** build `.exe` và installer thành công; `docs/MANUAL_TEST.md` có đầy đủ mục.

### Giai đoạn 7: Hoàn tất
- Viết `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/CONTRIBUTING.md`, và ít nhất 3 ADR trong `docs/adr/`.
- Cập nhật `README.md` và `README.vn.md`: sơ đồ mới, cách chạy, build, cấu hình. Ghi rõ dự án không chính thức, không liên kết với Riot Games.
- Thêm `.github/workflows/ci.yml` theo mục 5.5 của `REFACTOR_PLAN_v2.md`; `.github/dependabot.yml`; `.github/CODEOWNERS`.
- Xoá shim `backend/`, `test_riot_connection.py` (đã chuyển sang `tests/manual/`), và code chết đã xác định.
- Chạy toàn bộ quality gate ở mục 5.5 của `REFACTOR_PLAN_v2.md`. Ghi kết quả vào `docs/QUALITY_REPORT.md`.
- **Không** tạo tag `v2.0.0` và **không** push, trừ khi người dùng xác nhận.

---

## 5. Xử lý khi gặp vấn đề

- **Test fail sau khi di chuyển:** kiểm tra import trước. Nếu cần sửa logic để test pass, dừng, ghi vào `docs/OPEN_QUESTIONS.md`, và báo người dùng.
- **Phát hiện hành vi chưa được mô tả trong plan:** giữ nguyên hành vi, ghi vào `docs/BASELINE.md`, không "sửa cho đúng".
- **Phụ thuộc không tương thích:** ghim phiên bản đang chạy được, ghi vào báo cáo.
- **Không chắc một thay đổi có phá vỡ người dùng không:** không làm; ghi câu hỏi vào `docs/OPEN_QUESTIONS.md`.
- **Lệnh cần quyền ghi ra ngoài repo** (cài phần mềm hệ thống, sửa `Program Files`, đổi registry): dừng và hỏi.
- **Lỗi build PyInstaller:** ghi log đầy đủ vào `docs/build-logs/`; không tắt `hiddenimports` để "qua" lỗi mà không hiểu nguyên nhân.

---

## 6. Quy tắc commit

- Định dạng: `<type>(<scope>): <mô tả ngắn>`. Type: `refactor`, `fix`, `security`, `perf`, `test`, `docs`, `build`, `chore`.
- Mỗi commit một mục đích. Commit di chuyển ghi rõ `refactor(move): ...`.
- Không commit file sinh ra (`dist/`, `build/`, `output/`, `.venv/`, `node_modules/`).
- Thông điệp commit bằng tiếng Anh, ngắn gọn.

Ví dụ:
```
refactor(move): relocate riot client to src/tft_studio/riot
security(api): require token on state-changing endpoints
fix(render): escape player names in overlay template
perf(render): coalesce consecutive render requests
test(security): add path traversal cases for augment names
```

---

## 7. Báo cáo cuối cùng

Khi kết thúc (hoặc khi dừng ở một giai đoạn), tạo `docs/REFACTOR_REPORT.md` gồm:

1. **Trạng thái từng giai đoạn:** hoàn thành, dừng, chưa bắt đầu; kèm commit hash.
2. **Thay đổi bảo mật:** danh sách S1–S20, mỗi mục ghi "đã làm", "chưa làm", hoặc "cần người dùng quyết định".
3. **Thay đổi hiệu năng:** bảng so sánh baseline và sau thay đổi cho các chỉ số mục 4.1.
4. **Kết quả quality gate:** từng dòng của mục 5.5, kèm đầu ra tóm tắt.
5. **Những việc cần người dùng làm:**
   - Thu hồi key Riot nếu phát hiện bí mật trong lịch sử.
   - Quyết định có viết lại lịch sử Git không và khi nào.
   - Chạy `docs/MANUAL_TEST.md` trên Windows thật.
   - Quyết định ký số `.exe` (cần chứng chỉ).
   - Trả lời các câu hỏi trong `docs/OPEN_QUESTIONS.md`.
6. **Rủi ro còn lại** và mức độ.
7. **Lệnh đã chuẩn bị nhưng chưa chạy** (ví dụ `git push`, `git filter-repo`) để người dùng xác nhận.

Báo cáo phải ngắn gọn, đúng sự thật. Không ghi "hoàn thành" cho mục chưa được kiểm chứng.

---

## 8. Điều kiện kết thúc

Dừng và báo cáo khi một trong các điều kiện sau xảy ra:
- Hoàn thành giai đoạn 7 và quality gate xanh.
- Gặp việc cần quyết định của người dùng (mục 2.6, 2.9, mục 5).
- Phát hiện bí mật thật trong repo.
- Bất kỳ test bảo mật nào fail và không sửa được trong phạm vi plan.

Không tự tiếp tục sang bước làm rủi ro cao khi chưa có xác nhận.

---

## 9. Ghi chú về phạm vi

- Đây là dự án cá nhân, mã nguồn mở, không chính thức, không liên kết với Riot Games.
- Dữ liệu Data Dragon và tài sản của Riot thuộc về Riot Games; kiểm tra điều khoản trước khi phát hành công khai.
- Không thu thập hay lưu dữ liệu người chơi ngoài những gì người dùng cấu hình trên máy của họ.
