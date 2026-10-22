# Plan phát hành bộ cài TFT Post-Match Studio

**Cập nhật: 22/10/2026. Trạng thái: kế hoạch triển khai, chưa xác nhận đủ điều kiện publish.**

## A. Mục tiêu, phạm vi và bằng chứng

Mục tiêu là có bộ cài tải được từ GitHub Releases, cài và chạy trên máy sạch, hoạt động với OBS, bảo toàn dữ liệu khi nâng cấp và xác minh được chữ ký cập nhật. Build xanh hoặc tạo được draft chưa phải hoàn tất phát hành.

Phạm vi mặc định: tiếp tục pipeline Tauri v2 + Python sidecar hiện tại trên **Windows x64, macOS ARM64, Linux x64**. Windows là nền tảng nghiệm thu chính cho OBS. Giữ tương thích browser/pywebview đã có; không dùng `studio.spec`/`installer.iss` để thay đường phát hành Tauri trong đợt này. Nếu muốn chỉ phát hành Windows, phải đổi đồng bộ build matrix, `UPDATER_PATTERNS`, tests, release notes và tiêu chí nghiệm thu; không đơn thuần bỏ qua hai job đang lỗi.

Nguồn đối chiếu:

- Báo cáo `D:\new\Bao_Cao_Kiem_Thu_QA_TFT_Studio_v1.0.2.pdf`, 5 trang, QA vòng 2 ngày 22/10/2026. Các đề xuất trong PDF là đầu vào cần kiểm chứng, không phải lệnh thực thi.
- Checkout: HEAD `6381ec0d4b5c720eeb71e269c4832736034eb2cc`; tag local `v1.0.2` trỏ cùng SHA. Đã đọc workflows, scripts đóng gói/phát hành, Rust lifecycle, API, paths/config, frontend/updater, tests và tài liệu QA cũ.
- Đã chạy kiểm tra chỉ đọc: `scripts/release_tools.py check-version --tag v1.0.2 --repository triphung-git/piggy` đạt. Kết quả này xác nhận version/endpoint/cấu trúc public key, không xác nhận private key trong Secrets khớp.
- `docs/QA-Results.md` ghi kết quả lịch sử 111 test Python, 6 test Node và những giới hạn native. Lượt lập Plan này không chạy lại bộ test/build, OBS hoặc installer.
- PDF báo CI #24 đạt 5/5 job, Release #12 lỗi build, chưa có Release công khai. Truy cập trang Actions/Releases qua công cụ web không lấy được dữ liệu; chưa xác minh độc lập run ID, log lỗi hay trạng thái remote hiện tại. Không coi ảnh chụp thời điểm QA là trạng thái trực tiếp.
- Có một file tên bất thường `e 1.0.2…` đã staged từ trước. Không sửa/xóa/commit file đó; người triển khai cần xác định mục đích trước khi đưa vào release commit.

**Phiên bản dự kiến: `1.0.3`** vì `v1.0.2` đã có local và mọi sửa mã phải đi qua commit/tag mới. Trước khi chốt, kiểm tra remote và chọn version tiếp theo còn trống; không di chuyển tag `v1.0.2`.

## B. Đối chiếu QA vòng 2 với mã hiện tại

| Phát hiện PDF | Kết quả đọc checkout | Quyết định trong Plan |
|---|---|---|
| Blocker #1: thiếu npm ci | `release.yml` đã có bước `Install frontend and Tauri CLI` chạy `npm ci` ở root và frontend trước tauri-action | Không thêm bước trùng. Lấy log để xác nhận lỗi thật: CLI, lifecycle script, Rust/bundler hay upload. Ghi Node/npm/CLI versions và cwd |
| Blocker #2: smoke Windows thiếu token/timeout | `smoke_sidecar.py` đã truyền token, chờ 30 giây, poll `/api/status`, render có xác thực; `release_tools.py` lấy target từ env `TARGET`, không có CLI `--target` | Lỗi run là thông tin QA; nguyên nhân timeout chỉ là giả thuyết. Thu stderr/traceback/exit code trước khi sửa; giữ cú pháp lệnh hiện có đúng parser |
| High #3: port=0 | `main_sidecar.py` dùng CLI → `TFT_BACKEND_PORT` → config → 8080; validate 1–65535; Uvicorn bind cổng đó | Giữ cổng ổn định, test khởi động lại/cổng bận. Không áp dụng fallback ngẫu nhiên làm thay URL OBS |
| High #4: pubkey giả | Chuỗi hiện tại vượt kiểm tra giải mã/cấu trúc của `check-version` | Cần chứng minh cặp khóa khớp bằng ký/xác minh thực trên CI. Không sinh key thay thế chỉ dựa vào nhận định PDF |
| verify_binary_arch đã tồn tại | `build_sidecar.py` hiện chưa có hàm này; chỉ kiểm tra output tồn tại, kiến trúc runner được so bằng `smoke-sidecar` | Bổ sung kiểm tra header/architecture có test nếu giữ tuyên bố đó; magic bytes đơn thuần không chứng minh đúng CPU |
| Rust dùng --appdata/--resource-dir; updater downloadAndInstall | Rust hiện truyền đường dẫn bằng env; updater dùng `download()` rồi `install()` và có recovery | Nghiệm thu đúng implementation hiện tại; không thay API đang có theo đoạn mô tả không khớp |

Hai khoảng trống quan trọng ngoài bốn đề xuất PDF:

1. Smoke hiện đặt `TFT_RESOURCE_DIR` về **workspace**, nên có thể đạt dù bundle thiếu tài nguyên. Chưa chứng minh bộ cài chạy độc lập repository.
2. Job publish tự công khai ngay sau build/verify. Chưa có chặng nghiệm thu installer native trước publish; phải tạo điểm dừng kiểm soát cụ thể.

## C. Thứ tự triển khai và người phụ trách

Vai trò: DEV = người sửa code/build; QA = người nghiệm thu; RELEASE = người quản lý repository, Secrets và công bố. Một người có thể kiêm nhiệm nhưng bằng chứng phải ghi riêng từng gate.

Luồng bắt buộc: **G0 baseline/log → G1 smoke/đóng gói → G2 runtime/tài nguyên → G3 signing/updater → G4 CI/draft → G5 nghiệm thu installer → G6 publish → G7 kiểm chứng công khai**. G1–G3 có thể chuẩn bị độc lập sau G0, nhưng tất cả phải đạt trước G4. Mỗi task có output và điều kiện đạt; không đóng task bằng nhận định “đã sửa trong code”.

### G0. Khóa baseline và lấy nguyên nhân lỗi thật — DEV/RELEASE

1. Kiểm tra `git status`, diff staged/unstaged, branch, HEAD, remote URL; giữ nguyên công việc người dùng. Chuẩn bị nhánh release hardening; chỉ stage file đã review, tránh `git add -A` trong checkout đang có file bất thường.
2. Lấy trạng thái remote tags/releases và tải log đầy đủ của Release #12/CI #24. Ghi run URL/ID, attempt, SHA, runner image, step thất bại, câu lệnh và traceback đầu tiên. Đối chiếu nội dung scripts tại **đúng SHA của run**, không chỉ HEAD mới nhất.
3. Kiểm tra `v1.0.3` chưa có; ghi SHA baseline. Nếu log không truy cập được, ghi blocked phần chẩn đoán và chạy một workflow diagnostic có artifact log để lấy bằng chứng tương đương; không đoán lỗi rồi tăng timeout vô hạn.
4. Cập nhật mô tả trong `docs/GITHUB-RELEASE-GUIDE.md`: hướng dẫn cũ còn ghi checkout/version 1.0.0, trong khi manifests hiện là 1.0.2. Giữ số test cũ dưới nhãn lịch sử.

**Output:** bảng lỗi theo từng OS + run log được che bí mật + version đích. **Đạt:** biết job/lệnh/SHA thật và có cách tái hiện từng lỗi; chưa có log thì root cause vẫn “chưa xác nhận”.

### G1. Làm smoke test Windows có khả năng chẩn đoán — DEV

File chính: `scripts/smoke_sidecar.py`, `scripts/release_tools.py`, `scripts/build_sidecar.py`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`; tests tương ứng trong `tests/unit/`.

1. Giữ token/env và `/api/status` hiện có. Không thêm `/api/health` khi backend chưa có route đó. Readiness phải gồm process còn sống, HTTP thành công và ready thực; kiểm tra render, shell/CSS, background, font, ảnh fixture.
2. Cho phép timeout cấu hình có giới hạn, mặc định giữ 30 giây đến khi log chứng minh cần khác. Ghi elapsed startup/render/shutdown; phân biệt timeout, process exit, HTTP lỗi, render lỗi và cleanup lỗi. Có giới hạn tổng cho subprocess/request.
3. Tách đường log bền vững khỏi TemporaryDirectory; timeout/exception phải lưu process stdout/stderr, `logs/studio.log`, exit code và thông tin tài nguyên trước cleanup. Upload artifact bằng `if: always()` khi lỗi, có retention, loại token/key/Riot ID. Trên Windows đóng/flush handle ghi log trước thao tác gây sharing violation hoặc dọn thư mục.
4. Shutdown xác thực, đợi tiến trình và process con onefile; fallback dọn đúng cây tiến trình do test tạo, không kill theo tên chung. Bảo đảm cleanup không che traceback gốc, port được giải phóng và temp không bị lock.
5. Kiểm tra binary đúng định dạng và CPU: Windows PE machine, ELF class/machine, Mach-O CPU type; so với target. Test header sai/CPU sai/thiếu binary và timeout/early exit, không chỉ kiểm tra magic `MZ`/ELF.
6. Trên runner sạch cài root/frontend bằng lockfiles, in `node --version`, `npm --version`, `npm exec tauri -- --version` sau install; không in toàn bộ env. Chỉ sửa bước cài dependencies nếu log chứng minh bước hiện tại chưa chạy/đang lỗi.

**Output:** commit sửa theo log và artifact chẩn đoán. **Đạt:** source smoke và binary smoke đạt trên cả ba runner; Windows cold start chạy thành công ít nhất ba lần độc lập, không còn process con/port sau shutdown. Failure giả lập để lại log hữu ích và exit nonzero.

### G2. Chứng minh bundle tự chứa và vòng đời native — DEV/QA

File chính: `src-tauri/tauri.conf.json`, `src-tauri/src/lib.rs`, `src/tft_studio/core/paths.py`, `main_sidecar.py`, `scripts/smoke_sidecar.py`, API/controller, frontend connection info.

1. Thêm chế độ packaged smoke nhận resource root rõ ràng và chạy từ cwd bên ngoài repo. Trong frozen build không được âm thầm fallback workspace để che tài nguyên thiếu. Kiểm tra layout Tauri `_up_` thực tế bằng bộ cài/extracted bundle.
2. Xác nhận có `templates` gồm shell/CSS, assets/font/background, DDragon, frontend dist cho `/app/`, config mẫu và `.env.example`. Defaults phải trung tính; không đóng gói `.env`, avatar cá nhân, output/log/cache hoặc fixture tài khoản thật. Kiểm tra LICENSE/font notices và nguồn các logo/game assets cần phân phối.
3. Dữ liệu ghi vào AppData, resources chỉ đọc. Cài vào vị trí chuẩn, chạy bằng tài khoản thường, username/path tiếng Việt và khoảng trắng. Sau nâng cấp giữ config, key người dùng, avatar và output; default mới không ghi đè file hiện hữu.
4. Chốt cổng production: 8080 hoặc cổng người dùng đã lưu; khởi động lại giữ URL OBS. Khi cổng bị ứng dụng khác chiếm, báo lỗi rõ và hướng dẫn đổi cổng có lưu cấu hình; không silently bind port=0, không nhận nhầm server đang chiếm cổng là backend của mình. Test IPC/REST/WS/ảnh/Copy URL/preview cùng cổng.
5. Native lifecycle: mở/ẩn preview, Close/Reopen panel, Quit, kill/crash backend, start lại, cold start chậm và hai instance đồng thời. Dọn cả bootloader/child; khi backend chết UI không báo online. Quyết định single-instance hoặc lỗi instance thứ hai rõ ràng; không kết nối chéo token/dữ liệu.
6. Kiểm tra trình duyệt xuất PNG có thực sự sẵn trên OS đích. Nếu exporter cần Chrome/Edge ngoài WebView, phải phát hiện thiếu và hướng dẫn đúng; không coi frontend build thành công là đã có runtime xuất ảnh.

**Đạt:** bundle cài mới chạy khi repository/node_modules/Python hệ thống không sẵn; toàn bộ tài nguyên và export 1920×1080 hoạt động; AppData bảo toàn và cổng được giải phóng sau Quit.

### G3. Xác minh signing và cập nhật thật — RELEASE/DEV/QA

File chính: `src-tauri/tauri.conf.json`, `scripts/release_tools.py`, `Web Overlay/src/lib/updater.ts`, `UpdateModal.tsx`, `App.tsx`, Rust lifecycle và tests release.

1. Xác minh **sự tồn tại** của `TAURI_SIGNING_PRIVATE_KEY`/password qua cấu hình Actions, không đọc/in giá trị. Ký artifact mẫu bằng secret qua CI và verify bằng public key đang phân phối. Check-version chỉ chứng minh cấu trúc, không chứng minh quyền sở hữu khóa.
2. Giữ khóa hiện có nếu khớp. Chỉ tạo khóa mới khi xác nhận mất/sai và đã có quyết định migration; các bản cũ cần bridge release hoặc cài thủ công để đổi public key. Không tự xoay key như bước sửa mặc định trong PDF.
3. Phân biệt chữ ký updater với Authenticode/macOS signing + notarization. Xác định chính sách phân phối và thông báo thật; không quảng cáo installer đã được OS tin cậy khi chưa ký. Nếu yêu cầu macOS mở theo luồng thông thường, hoàn tất Developer ID/notarization và nghiệm thu Gatekeeper trước stable release.
4. Test native cập nhật N → N+1 qua endpoint thử nghiệm kiểm soát riêng, không trỏ bản production đang cài sang payload QA. Draft không được phục vụ công khai qua `/releases/latest/...`; staging cần phân phối đúng artifact đã ký sẽ phát hành. Đối chiếu pubkey/endpoint nhúng trong chính installer N, không suy ra từ source mới. Nếu không có bản N cũ dùng cùng khóa, tạo cặp bản thử nghiệm N/N+1 và ghi giới hạn: chưa chứng minh nâng từ bản legacy.
5. Các nhánh bắt buộc: user cancel; download/mạng lỗi; signature sai; stop thất bại; install lỗi và recovery backend; thành công/relaunch; giữ AppData. Kiểm tra hành vi Windows installer kết thúc process thực tế, không chỉ IPC mock.
6. Xem lại `checkForAppUpdate()` đang catch lỗi rồi trả null: cần phân biệt “không có update” với “không kiểm tra được” trong UI/log. Đưa vào nghiệm thu lỗi mạng/signature, tránh báo up to date giả.

**Đạt:** bundle thật và `.sig` được verifier chấp nhận, sửa một byte bị từ chối, khóa sai bị từ chối; các nhánh lỗi không làm mất backend/dữ liệu. Updater chỉ cài khi người dùng xác nhận.

### G4. Build draft với gate trước publish — DEV/RELEASE

1. Giữ preflight SemVer/version/endpoint/key, CI đúng SHA, draft marker SHA, verify chữ ký và tag không đổi. Root và frontend npm ci phải chạy trên mỗi runner; target Python/PyInstaller phải khớp kiến trúc runner.
2. Thêm `src-tauri/Cargo.lock` được theo dõi cho ứng dụng, cập nhật bằng Cargo và dùng locked resolution khi build/check phù hợp. Ghim dependency Python qua constraints/lock phù hợp ba OS, lưu toolchain thực dùng; kiểm tra fresh checkout không phụ thuộc `.venv`/cache local.
3. Tách job verify/manifest khỏi publish. Build/upload/verify tạo draft và QA artifacts trước; publish chỉ chạy sau gate nghiệm thu. Phương án đề nghị: GitHub Environment `release-production` với required reviewer ở job publish; RELEASE xác nhận G5 và đối chiếu SHA/hash trước approve. Phải cấu hình protection trong Settings, YAML đơn thuần chưa đủ. Nếu repository không hỗ trợ protection, dùng workflow finalize riêng kiểm tra tag/SHA/artifact hashes và bằng chứng QA; không để auto-publish không gate.
4. Lưu inventory assets, SHA256SUMS, SHA/tag/run URLs; verify mọi artifact dự định phân phối. Hiện verifier bắt buộc EXE, app.tar.gz, AppImage và các `.sig` khác; DMG/DEB/RPM không có `.sig` cần kiểm tra riêng về đầy đủ/hash/install nếu công bố. Giới hạn `bundle.targets` theo những định dạng thật sự nghiệm thu, điều chỉnh tests/guide nếu đổi.
5. Manifest duy nhất phải có `windows-x86_64`, `darwin-aarch64`, `linux-x86_64`, version đúng, URL percent-encoded, signature đúng binary. Không giảm yêu cầu ba platform để “làm xanh” trong phạm vi mặc định.
6. Draft QA dùng đúng binary sẽ publish. Ngăn rerun/upload thay assets sau khi QA: ghi asset IDs/hash và kiểm tra lại ngay trước publish; có thay đổi thì hủy nghiệm thu cũ. Tag guard không tự ngăn asset thay đổi.
7. Tách kênh stable/prerelease: endpoint `/releases/latest/...` dành stable; `-rc` không được làm latest. Smoke cập nhật prerelease cần endpoint riêng; test cả nhánh make_latest và version ordering.

**Đạt:** ba build và CI đúng SHA xanh; draft đủ assets, signatures/checksums/manifest; negative tests chặn tag dịch chuyển, thiếu asset, signature sai, draft khác SHA, asset đổi sau QA và release đã publish. Publish còn đang chờ G5.

### G5. Ma trận nghiệm thu bộ cài — QA

Mỗi dòng ghi OS/version, installer tên + SHA256, SHA source, expected/actual, PASS/FAIL/BLOCKED, ảnh/log và người kiểm tra. “Chưa chạy” không được ghi PASS.

| Nhóm | Ca kiểm thử | Điều kiện đạt |
|---|---|---|
| Windows | Windows 10/11 x64 trong phạm vi công bố; user thường; cài mới, nâng cấp, gỡ/cài lại | Khởi động, shortcut/version đúng; không cần Python/Node/repo; không mất dữ liệu theo chính sách |
| WebView2 | Máy có runtime; máy thiếu runtime; bootstrap offline/online theo installer config | Cài được hoặc báo yêu cầu mạng/runtime đúng; không treo màn trắng. Chốt chế độ WebView2 trước phát hành |
| macOS/Linux | macOS ARM64 và Linux x64 đúng baseline runner/runtime công bố | Cài/mở native, sidecar executable, resources và preview hoạt động; ghi Gatekeeper/quyền execute/thư viện cần thiết |
| OBS | OBS Browser Source 1920×1080; mở trước render; render đầu; reconnect; restart app | Đủ CSS/font/ảnh, tự cập nhật, không refresh thủ công; URL giữ nguyên qua restart |
| Nghiệp vụ | Fixture rồi Riot thực; Render, Save & Sync, augments/Destiny/Auto, avatar, chọn trận/polling | Hiển thị đúng trận/draft, không socket/poller trùng; ảnh PNG 1920×1080 đọc được |
| Riot lỗi | Thiếu/sai/hết hạn key, region sai, 429, mất mạng | Báo lỗi phù hợp, không lộ key, không xóa cache hợp lệ; test thật ghi rõ key riêng của người kiểm thử |
| Lifecycle | Close/Reopen, preview, Quit, crash/restart, cổng bận, mở hai instance | Trạng thái thật, phục hồi rõ ràng, không tiến trình mồ côi/ghi chéo |
| UI | 960×640, 1280×800, DPI 100/125/150%, keyboard/modal | Nút quan trọng truy cập được, không cắt nội dung thao tác |
| Security | Token thiếu/sai, Origin ngoài, traversal, config/PNG sai | Bị chặn; file hợp lệ trước đó còn nguyên; không secret trong bundle/log công khai |
| Update | N→N+1 và mọi nhánh lỗi G3 trên installer native | Xác nhận trước cài, recovery/dữ liệu đúng; signature sai không cài |

Phân cấp: P0 mất dữ liệu/lộ bí mật, P1 installer không chạy/chức năng chính hỏng/signature hoặc update phá runtime đều chặn. P2 chỉ được hoãn khi có mô tả tác động/workaround/người chấp nhận, không ảnh hưởng luồng chính. Không cho một nền tảng chưa nghiệm thu xuất hiện dưới cam kết hỗ trợ ổn định.

### G6. Chốt version, công bố và kiểm chứng — RELEASE

1. Sau sửa lỗi, đồng bộ version đích ở Tauri config, Cargo.toml/lock, pyproject, hai package.json và hai package-lock.json. Chạy check-version với tag đích; kiểm tra changelog/release notes/hướng dẫn VN/EN.
2. PR chỉ chứa file đã review; CI đạt trên commit cuối. Merge main, lấy SHA chuẩn rồi tạo annotated tag mới trên SHA đó. Không force tag. Release workflow build cùng SHA; nếu mã thay đổi sau nghiệm thu thì dùng candidate/tag mới và chạy lại gate bị ảnh hưởng.
3. Trước publish, reviewer kiểm G0–G5, asset inventory/hash, chữ ký, version, latest.json và release notes. Notes nêu đúng OS/CPU, định dạng bộ cài, cách cài/OBS/AppData, yêu cầu WebView2/Chrome nếu có, known issues, tình trạng OS signing và cách báo lỗi. Thay nội dung draft chung chung “Installers for Windows, macOS and Linux”.
4. Publish đúng draft đã nghiệm thu. Từ phiên không đăng nhập, tải installer và latest.json qua URL công khai; HTTP thành công, JSON/version/platform đúng, signature và SHA256 khớp artifact đã duyệt. Cài một lượt từ **file vừa tải công khai**; app version/overlay hoạt động.
5. Kiểm tra updater qua endpoint production sau publish từ bản N dùng endpoint/khóa thật; staging trước publish không thay thế phép kiểm tra này. Theo dõi run và báo lỗi sau phát hành. Ghi URL release, tag/SHA, workflow run, checksum và biên bản G5 vào QA Results.

**Definition of Done:** bộ cài công khai đủ nền tảng đã cam kết; tải/cài/chạy từ máy sạch đạt; OBS và update thật đạt; chữ ký/hash đúng; không blocker mở; có tài liệu và đường phục hồi. Nếu thiếu một điều kiện, giữ draft hoặc công bố phạm vi thử nghiệm rõ ràng theo quyết định release, không ghi “hoàn tất stable”.

## D. Lệnh kiểm chứng khi triển khai

Các lệnh dưới đây là runbook cho giai đoạn thực thi, chưa được chạy toàn bộ trong lượt lập Plan. Dùng thư mục QA mới, không trỏ vào AppData thật. Trước tiên tạo môi trường độc lập từ requirements/dev dependencies và npm lockfiles; cấu hình `TFT_APPDATA_DIR` cho tests. Chạy lint/test trước, rồi build nguồn, binary, cuối cùng bộ cài.

```powershell
$env:TFT_APPDATA_DIR = Join-Path $PWD 'scratch/release-qa-1.0.3'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp scratch/release-tests-1.0.3
.\.venv\Scripts\ruff.exe check src desktop tests scripts
node --test tests/release_github.test.cjs
npm ci
npm --prefix "Web Overlay" ci
npm run build
.\.venv\Scripts\python.exe scripts/release_tools.py check-version --tag v1.0.3 --repository triphung-git/piggy
.\.venv\Scripts\python.exe scripts/smoke_sidecar.py
$env:TARGET = 'x86_64-pc-windows-msvc'
.\.venv\Scripts\python.exe scripts/build_sidecar.py
.\.venv\Scripts\python.exe scripts/release_tools.py smoke-sidecar
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri -- build --target x86_64-pc-windows-msvc
git diff --check
```

Check-version `v1.0.3` chỉ đạt **sau** đồng bộ manifests. `cargo --locked` và tùy chọn smoke packaged/log/timeout chỉ thêm vào runbook sau khi G1/G2/G4 triển khai. Build release có signing cần cung cấp secrets bằng môi trường bảo vệ; không dán key vào lệnh hoặc log. Workflow YAML phải qua actionlint như CI hiện có. `cargo check` không thay cho `tauri build` và cài native.

## E. Sự cố, rollback và bằng chứng bàn giao

| Sự cố | Hành động |
|---|---|
| Build/smoke lỗi | Giữ draft; đọc artifact đúng job/attempt, sửa root cause. Rerun cùng SHA chỉ khi môi trường/secrets đổi; code đổi phải có version/tag mới |
| Private/public key không khớp | Dừng trước publish, phục hồi đúng secret hoặc lập migration; không bỏ verify |
| Một platform chưa đạt | Giữ release theo matrix hiện hành; chỉ thu hẹp hỗ trợ bằng thay đổi đồng bộ đã review |
| QA phát hiện installer lỗi | Không approve publish; giữ log/hash bản lỗi, sửa và chạy lại gate liên quan |
| Lỗi nghiêm trọng sau publish | Ngừng đưa bản lỗi làm latest theo quy trình quản trị; giữ bằng chứng, thông báo workaround. Ưu tiên hotfix version cao hơn vì updater thường không downgrade; cài thủ công bản tốt cần backup AppData và kiểm tra tương thích schema |
| Manifest/asset công khai lỗi | Kiểm soát phân phối, đối chiếu file đã duyệt và audit. Không âm thầm thay binary đã phát hành; dùng bản sửa version mới |

Checklist bàn giao cuối:

- [ ] G0: baseline/log/remote state và version đích có bằng chứng.
- [ ] G1: smoke ba OS, Windows cold start/cleanup và failure artifacts đạt.
- [ ] G2: tài nguyên native độc lập repo, cổng/OBS/lifecycle/AppData đạt.
- [ ] G3: signing pair và native update/recovery được xác minh.
- [ ] G4: CI đúng SHA, draft/hash/manifest và gate publish có hiệu lực.
- [ ] G5: ma trận installer có người nghiệm thu, không P0/P1 mở.
- [ ] G6: release notes, URL tải công khai, chữ ký/hash/cài lại từ download đạt.
- [ ] Biên bản QA Results cập nhật, known issues và kế hoạch hotfix có chủ sở hữu.

Tài liệu kỹ thuật tham khảo đã đối chiếu: [Tauri Updater](https://v2.tauri.app/plugin/updater/) và [Windows Installer/WebView2](https://v2.tauri.app/distribute/windows-installer/). Mọi thiết lập GitHub Secrets/Environment, push/tag/publish thuộc giai đoạn thực thi; lượt này hoàn thiện kế hoạch.

---

# Phụ lục lịch sử: kế hoạch khắc phục QA ngày 17/10/2026

**Phần dưới giữ lại để truy vết; trạng thái và điều kiện phát hành hiện hành nằm ở phần A–E phía trên. Câu “đã duyệt/đã triển khai” dưới đây chỉ áp dụng đợt công việc cũ.**

Ngày đánh giá: 17/10/2026. Trạng thái: **ĐÃ ĐƯỢC DUYỆT — đã triển khai bản sửa, đã kiểm thử Python/browser/sidecar; còn nghiệm thu bản cài Tauri và tích hợp thực tế**.

Kết quả sau triển khai nằm trong [docs/QA-Results.md](docs/QA-Results.md). Các mục 1–7 bên dưới giữ lại kết quả đánh giá và kế hoạch ban đầu để đối chiếu; các câu “chưa sửa/chưa kiểm thử” trong các mục đó mô tả thời điểm lập kế hoạch.

## 1. Kết luận

Ứng dụng build được và bộ test hiện có đạt, nhưng chưa đủ điều kiện phát hành: luồng Tauri sidecar thiếu dịch vụ điều phối, giao diện có vòng lặp tải dữ liệu, tài nguyên mặc định bị che khuất và một số thao tác chỉ thay đổi giao diện.

Đây là danh sách phát hiện trong phạm vi đã kiểm tra, không phải cam kết đã tìm được mọi lỗi. Phân biệt:

- **A — Đã tái hiện:** kiểm thử API trực tiếp bằng FastAPI TestClient.
- **B — Xác nhận từ mã:** có đường thực thi cụ thể gây lỗi; cần kiểm thử giao diện/bản cài để xác nhận biểu hiện cuối cùng.
- **C — Rủi ro cần tái hiện:** phụ thuộc thời điểm, môi trường hoặc tác vụ đồng thời.

Mức độ: P1 = chặn chức năng hoặc sai dữ liệu đáng kể; P2 = lỗi có phạm vi nhỏ hơn; không ghi nhận P0 đã được chứng minh.

## 2. Phạm vi và kết quả kiểm tra

Đã đọc các thành phần React, API FastAPI/WebSocket, sidecar Python, cầu nối desktop cũ, cấu hình Tauri/Rust, config/path, render/export, match service, watcher, test và CI.

| Hạng mục | Kết quả thực tế |
|---|---|
| Python unit + security | **70 passed**, 1 cảnh báo Starlette/httpx, 10,55 giây |
| Ruff: `src desktop tests scripts` | **All checks passed** |
| `npm run build` | **Đạt**: TypeScript và Vite; Vite build 10,41 giây |
| API state/render/fetch khi không có bridge | Tái hiện lỗi nghiệp vụ dù HTTP 200 |
| API ghi không có token | HTTP 403, đúng kiểm soát phía server nhưng frontend browser không cung cấp token |
| Config sai kiểu | Được lưu và trả success=true |
| Export body sai kiểu | HTTP 500 |
| PNG giả chỉ có signature | Được chấp nhận và ghi file 12 byte |
| WebSocket Origin ngoài localhost | Kết nối được, nhận INITIAL_STATE |
| Tài nguyên mặc định | `/assets/background.png` và font có trong repo trả 404 |
| Browser E2E, responsive, screenshot | **Chưa chạy được**: skill Playwright thiếu package; `npm run setup` bị npm EALLOWSCRIPTS |
| Bản cài Tauri, OBS thực, Riot API thực, cập nhật thật | **Chưa kiểm thử**; không kết luận đạt |

Lần chạy pytest/build trong sandbox bị WinError 5/spawn EPERM. Chạy lại ngoài sandbox đã đạt; các lỗi môi trường này không được tính là bug sản phẩm. Test dùng `TFT_APPDATA_DIR` riêng dưới `scratch`; probe dữ liệu sai cũng dùng thư mục riêng, không dùng cấu hình thật của người dùng.

Lệnh đối chiếu:

```powershell
$env:TFT_APPDATA_DIR = Join-Path $PWD 'scratch/qa-appdata-elevated'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp scratch/qa-test-run-elevated
.\.venv\Scripts\ruff.exe check src desktop tests scripts --output-format concise
npm run build
```

## 3. Danh sách lỗi và hướng xử lý

### QA-01 — P1/A+B: Sidecar báo online nhưng không render/fetch được

**Vị trí:** `src/tft_studio/main_sidecar.py:60`, `src/tft_studio/api/hub.py:225,233,429`.

Entrypoint chỉ khởi tạo config và Uvicorn, không tạo MatchService/StudioBridge hay gán `_bridge_ref`. Việc tạo bridge chỉ có trong desktop pywebview cũ. Probe với token hợp lệ: `/api/state` trả `Bridge reference not set`; `/api/render` trả `success:false, Bridge not ready`; `/api/riot/fetch` cũng thất bại.

**Khắc phục tối ưu:** tách controller/service dùng chung khỏi pywebview; khởi tạo trong lifespan FastAPI sau khi hoàn tất config, nối notifier và đóng watcher/polling khi shutdown. Không import nguyên cầu nối GUI vào sidecar: build sidecar đang loại `webview`.

**Nghiệm thu:** chạy đúng binary sidecar với AppData mới và fixture trận; state ready chỉ khi dịch vụ sẵn sàng, render sinh HTML và fetch gọi được service mock. Lỗi chưa sẵn sàng phải trả HTTP 503.

### QA-02 — P1/B: Vòng lặp tải augments và kết nối WebSocket

**Vị trí:** `Web Overlay/src/components/SourceTransformPanel.tsx:130–217`.

Effect phụ thuộc `augmentsList` nhưng chính nó gọi `setAugmentsList(list)` với mảng mới từ mỗi request. Mỗi lần tải thành công lại kích hoạt tải mới, nạp lại config và khởi tạo socket. Khi fetch thất bại, facade cũng trả mảng rỗng mới. Lựa chọn chưa lưu có thể bị config tải lại ghi đè.

**Khắc phục:** tách effect khởi tạo một lần, effect socket và handler đồng bộ config; dùng ref/callback phù hợp để đọc catalog mới nhất. Cleanup cần cờ disposed, hủy request và bỏ onclose trước khi đóng socket để tránh tự tạo reconnect sau unmount.

**Nghiệm thu:** sau khi ổn định chỉ có một socket, không còn GET augments/config định kỳ ngoài thiết kế; giữ nguyên lựa chọn chưa lưu; unmount không reconnect. Kiểm tra cả React StrictMode.

### QA-03 — P1/A: Thư mục assets người dùng che toàn bộ tài nguyên mặc định

**Vị trí:** `src/tft_studio/core/paths.py:get_appdata_dir/resolve_resource`, `src/tft_studio/api/hub.py:843–845`.

AppData luôn tạo `assets/avatars`; `resolve_resource('assets')` vì thế luôn chọn thư mục assets AppData, rồi server mount duy nhất thư mục này. Background/font trong resources không được phục vụ. Đã tái hiện 404 background và font trên AppData mới dù file tồn tại trong repo.

**Khắc phục:** phục vụ theo từng file: ưu tiên override hợp lệ trong AppData, fallback resources; kiểm tra containment để chặn traversal. Áp dụng cùng cơ chế tìm kiếm cho generator, không chỉ route HTTP.

**Nghiệm thu:** background, font và avatar bundle trả 200 trên cài mới; override một avatar không làm mất font/background; không đọc được file ngoài các thư mục cho phép.

### QA-04 — P1/B: Tauri dev trỏ sai cổng Vite

**Vị trí:** `src-tauri/tauri.conf.json:build.devUrl`, `Web Overlay/vite.config.ts:server.port`.

Tauri đợi `http://localhost:5173` nhưng Vite mặc định mở 8443 và `strictPort:true`. Không có biến PORT phù hợp thì `npm run tauri dev` không kết nối được frontend.

**Khắc phục:** thống nhất một cổng dev, bind loopback và đảm bảo cấu hình CORS cùng giá trị. Không dựa vào biến môi trường ngầm của máy phát triển.

**Nghiệm thu:** chạy Tauri dev từ môi trường sạch, không đặt PORT, UI mở và gọi được backend.

### QA-05 — P1/A+B: Browser và pywebview cũ không xác thực được API ghi

**Vị trí:** `Web Overlay/src/lib/api.ts:getConnectionInfo/_fetchWithToken`, `desktop/app.py`, `desktop/bridge.py:get_studio_token`.

Facade chỉ lấy token qua Tauri; ở browser/pywebview luôn dùng token rỗng. Trong khi backend bắt buộc token mọi POST. GET đọc được nhưng Render/Save & Sync bị 403. Probe POST không token tái hiện đúng 403.

**Khắc phục:** adapter theo môi trường: Tauri IPC; pywebview dùng bridge đã có; browser có cơ chế ghép cặp phiên rõ ràng. Không bỏ yêu cầu token hoặc công khai token qua endpoint GET không bảo vệ.

**Nghiệm thu:** render/save hoạt động ở các chế độ được tuyên bố hỗ trợ; thiếu/sai token và Origin ngoài vẫn bị từ chối.

### QA-06 — P1/B: Cổng backend và URL ảnh không nhất quán

**Vị trí:** `SourceTransformPanel.tsx:116,176,655`, `src/lib/api.ts:getConnectionInfo`, `src-tauri/tauri.conf.json:app.security.csp`, `hub.py:get_server_status`.

REST Tauri có thể lấy cổng qua IPC nhưng WS/Copy URL dùng 8080 cố định, CSP cũng chỉ cho backend 8080. Ảnh augment dùng `/TFT_DDragon/...` tương đối origin frontend, nên ở Vite/Tauri không trỏ tới FastAPI.

**Khắc phục:** một nguồn connection info cho REST/WS/OBS/ảnh; browser dùng URL backend được cấu hình rõ. Quyết định hỗ trợ cổng cố định hay tùy chỉnh và áp dụng nhất quán trong CSP; không mở connect-src tùy tiện.

**Nghiệm thu:** test cổng 8080 và một cổng khác nếu hỗ trợ; ảnh augment trả 200 từ backend ở Tauri dev và bản cài, Copy URL đúng server thực.

### QA-07 — P1/B: Xem/Ẩn Preview không thực hiện thao tác

**Vị trí:** `src/lib/api.ts:263`, `SourceTransformPanel.tsx:282–290,475`.

`toggleOverlayVisibility` chỉ trả lại boolean, không mở/ẩn cửa sổ. UI đổi nhãn và còn hiển thị “Overlay Hidden from Stream Output” dù không điều khiển OBS.

**Khắc phục:** tạo/quản lý cửa sổ preview bằng API Tauri hoặc adapter pywebview; chỉ cập nhật state khi thao tác thành công. Tách trạng thái preview khỏi trạng thái nguồn OBS, sửa thông báo theo đúng tác dụng.

**Nghiệm thu:** mở/ẩn được cửa sổ thực; OBS vẫn hoạt động đúng thiết kế; không báo đã ẩn stream khi chỉ ẩn preview.

### QA-08 — P1/B: Close rồi Reopen làm ứng dụng mất backend

**Vị trí:** `SourceTransformPanel.tsx:292–320`, `src/lib/api.ts:253–260`, `src-tauri/src/lib.rs:stop_backend_sidecar`.

Close dừng sidecar nhưng chỉ đổi panel thành màn hình Closed; Reopen chỉ đổi React state, không khởi động lại backend. Sau Reopen các thao tác thất bại.

**Khắc phục:** định nghĩa Close Panel là ẩn panel/cửa sổ; thao tác Quit riêng mới dừng backend và thoát app. Nếu có Stop/Start dịch vụ thì cần state machine và lệnh restart thực sự.

**Nghiệm thu:** Close/Reopen nhiều lần không làm mất chức năng; Quit giải phóng tiến trình và cổng.

### QA-09 — P1/A: Config không có schema, có thể lưu giá trị làm lần khởi động sau lỗi

**Vị trí:** `hub.py:258`, `core/config.py:save_overlay_config`, `main_sidecar.py:84`.

POST config với `server_port:'bad', custom_augments:'bad'` trả success và lưu nguyên giá trị. Khởi động sidecar sẽ gọi `int()` với port này. Endpoint config cũng là đường đi vòng validation augments chuyên biệt.

**Khắc phục:** model cấu hình dùng chung, port nguyên trong 1–65535, kiểm tra cấu trúc và nội dung augments/avatar/title, giới hạn độ dài, quy tắc unknown fields rõ ràng. Validate trước ghi và trả 422; ghi atomic với khóa chung, giữ cấu hình hợp lệ trước đó khi lỗi.

**Nghiệm thu:** config sai bị từ chối và file không đổi; cổng biên hợp lệ chạy được; config hỏng không khiến UI im lặng treo.

### QA-10 — P2/A: Export sai kiểu dữ liệu gây HTTP 500

**Vị trí:** `hub.py:361–385`.

POST `/api/export/base64` body `[]` hoặc `{"image_base64":123}` với token hợp lệ đều trả 500 do dùng `.get` và phép kiểm tra chuỗi trước validate kiểu.

**Khắc phục:** request model bắt buộc object và chuỗi ảnh, giới hạn dung lượng trước giải mã, trả lỗi 400/422 có thông điệp cụ thể.

**Nghiệm thu:** null/list/number/object sai trường, JSON lỗi, base64 lỗi không gây 500 hoặc ghi file.

### QA-11 — P1/A: Chấp nhận PNG giả và ghi đè ảnh mới nhất

**Vị trí:** `hub.py:385–415`.

Endpoint chỉ kiểm tra 8 byte signature. Payload base64 của `PNG signature + FAKE` được ghi thành file 12 byte và trả success; ảnh latest có thể bị thay bằng dữ liệu không giải mã được.

**Khắc phục:** giải mã base64 strict, kiểm tra toàn vẹn bằng Pillow và load ảnh, enforce PNG/kích thước theo hợp đồng xuất 1920×1080, giới hạn byte/pixel; xác thực hoàn tất trước ghi atomic và cập nhật latest.

**Nghiệm thu:** PNG cụt/giả, ảnh quá lớn và sai định dạng không thay latest; ảnh hợp lệ mở được và đúng kích thước. Test hiện có dùng PNG 1×1 cần điều chỉnh nếu hợp đồng yêu cầu 1080p.

### QA-12 — P2/B: Xuất hai ảnh cùng giây đè file lịch sử

**Vị trí:** `hub.py:337,403`.

Cả hai endpoint đặt tên bằng `int(time.time())`. Hai lần export trong cùng giây cùng đường dẫn; mất bản xuất trước và có thể ghi đua với nhau.

**Khắc phục:** tên duy nhất bằng UUID hoặc timestamp độ phân giải cao kèm phần ngẫu nhiên; chỉ file latest được chủ động thay thế, dưới khóa/atomic replace.

**Nghiệm thu:** nhiều yêu cầu đồng thời tạo file lịch sử riêng; latest luôn là PNG hoàn chỉnh.

### QA-13 — P2/A: WebSocket bỏ qua kiểm tra Origin/Host

**Vị trí:** `hub.py:173–209`.

Middleware `http` không áp dụng WebSocket. Probe kết nối `/ws` với Origin `https://evil.example` được accept và nhận INITIAL_STATE/config. Chưa chứng minh quyền ghi qua WS; ảnh hưởng đã xác nhận là đọc trạng thái và tạo kết nối ngoài origin dự kiến.

**Khắc phục:** kiểm tra Host/Origin trước accept, chính sách riêng cho OBS không gửi Origin và origin null; tránh gửi cấu hình riêng tư không cần thiết. Cân nhắc quota kết nối/keepalive.

**Nghiệm thu:** Origin ngoài bị chặn; OBS, panel Tauri và browser hợp lệ vẫn kết nối.

### QA-14 — P1/B: OBS mở từ trạng thái chờ không nhận stylesheet sau render đầu tiên

**Vị trí:** `hub.py:serve_overlay_html/get_overlay_inner_html/smoothUpdate`.

Trang placeholder chỉ có CSS trạng thái chờ, không có link `/overlay.css`. Sau render, smoothUpdate chỉ thay innerHTML phần body từ API, không cập nhật head. Overlay chuyển khỏi placeholder nhưng thiếu stylesheet của bố cục thật cho tới khi reload.

**Khắc phục:** overlay shell cố định luôn nạp stylesheet và có một root; render API trả fragment đúng cho root; đồng bộ CSS có version khi cần. Reconnect/INITIAL_STATE luôn đối chiếu phiên bản render. Điều kiện hiện tại `root.querySelector('.waiting')` cũng không bắt trường hợp chính root là `.waiting`.

**Nghiệm thu:** mở OBS trước khi có dữ liệu, render lần đầu ra đúng bố cục 1920×1080, không cần refresh; mất kết nối rồi nối lại nhận bản mới nhất.

### QA-15 — P1/B: Cập nhật thất bại để lại backend đã bị dừng

**Vị trí:** `Web Overlay/src/lib/updater.ts:installConfirmedUpdate`, `src-tauri/src/lib.rs`.

Updater dừng sidecar trước downloadAndInstall; nếu tải/cài thất bại, modal báo lỗi nhưng không có đường khởi động lại sidecar. Ngay cả khi dừng sidecar thất bại, code vẫn tiếp tục cài.

**Khắc phục:** tách tải và cài: tải/xác minh trong khi ứng dụng còn hoạt động; chỉ dừng ngay trước install, xác nhận tiến trình đã thoát; nếu thất bại thì restart backend và làm mới connection info. Giữ xác nhận của người dùng trước cài.

**Nghiệm thu:** mô phỏng mạng lỗi, chữ ký sai, dừng thất bại và install lỗi; app phục hồi được, cấu hình/ảnh không mất. Không cài bản cập nhật thật trong lượt QA này.

### QA-16 — P2/B: Kết nối backend bị cache trước khi sidecar sẵn sàng

**Vị trí:** `src/lib/api.ts:getConnectionInfo`, `src-tauri/src/lib.rs:backend-ready`, `main_sidecar.py:on_startup_signal`.

Facade cache cả `ready:false`/cổng mặc định, không chờ event backend-ready hay invalidate cache. Init UI có thể gọi API quá sớm; WS dùng cổng khác lại là đường riêng. Tín hiệu server_ready hiện được in trong startup hook, trước thời điểm Uvicorn hoàn tất bind socket.

**Khắc phục:** state connecting/ready/failed, chờ readiness với timeout và retry giới hạn; invalidate khi backend đổi trạng thái/cổng; chỉ báo ready sau khi endpoint health xác nhận dịch vụ và socket sẵn sàng. Hiển thị lỗi khởi động/cổng bị chiếm có hành động phục hồi.

**Nghiệm thu:** backend khởi động chậm, cổng bận, sidecar crash đều không tạo trạng thái online giả hoặc cache vĩnh viễn dữ liệu cũ.

### QA-17 — P2/B: HTTP 200 và toast thành công không phản ánh kết quả tác vụ

**Vị trí:** `hub.py:trigger_render/save_custom_augments/update_overlay_config`, `SourceTransformPanel.tsx:handleSaveAugments/onmessage`, `src/lib/api.ts`.

API render trả HTTP 200 cho bridge chưa sẵn sàng và broadcast OVERLAY_RENDERED kể cả success=false; handler WS không kiểm tra success. Save augments báo “saved & overlay re-rendered” ngay sau khi server lưu config và chạy render nền, hoặc không render khi thiếu bridge.

**Khắc phục:** response và event phân biệt saved/rendering/rendered/failed; chỉ broadcast rendered khi hoàn tất; facade xử lý `res.ok` và lỗi có cấu trúc; không báo hoàn tất chỉ vì đã xếp hàng.

**Nghiệm thu:** render fail không có success toast; lưu thành công nhưng render fail hiển thị hai kết quả đúng; retry không gây thông báo nhân đôi.

## 4. Rủi ro cần kiểm thử bổ sung, chưa coi là lỗi đã tái hiện

| ID | Mức dự kiến | Bằng chứng mã / tình huống | Hướng xử lý nếu xác nhận |
|---|---|---|---|
| R-01 | P1/C | `MatchService.stop_auto_polling` không join; start xóa cùng stop event trong khi thread cũ đang sleep | Dùng Event.wait thay sleep; join worker trước restart; test stop/start nhanh không còn hai poller |
| R-02 | P1/C | Config/cache/HTML/latest được ghi trực tiếp từ API, watcher và các thread render | Một hàng đợi render có khóa, ghi temp + atomic replace, coalesce yêu cầu; test OBS không đọc file dở |
| R-03 | P2/B | `api.ts:exportOverlayImage` fallback tới document.body khi không có overlay root | Nếu đưa export ra UI, xuất từ document overlay chuyên dụng; không chụp control panel. Hiện chưa thấy nút gọi hàm này trong UI |
| R-04 | P2/B | `MatchService.fetch_recent_matches` trả sớm khi không có ID và không xóa active/cache trước đó | Xác định chính sách cache khi đổi tài khoản; test tài khoản B không có trận không hiển thị trận A như dữ liệu B |
| R-05 | P2/C | Watcher cập nhật mtime trước khi bỏ qua thay đổi trong khoảng debounce | Test burst ghi hai lần để xem có bỏ bản cuối; dùng trailing debounce nếu xác nhận |
| R-06 | P2/B | Panel hiện chỉ có chọn augment/render/preview/close, không có thiết lập Riot ID/key/region hay chọn trận | Đối chiếu phạm vi sản phẩm; nếu hỗ trợ cài mới không chỉnh file thủ công, bổ sung onboarding/settings và trạng thái chưa cấu hình |
| R-07 | P2/C | Tauri resources không đóng gói `Web Overlay/dist` vào Python resources; frontend chỉ nằm frontendDist | Bản cài kiểm tra `/app` có được cam kết hỗ trợ không; nếu có, đóng gói riêng và test assets đường dẫn |

## 5. Phương án triển khai đề xuất

Ưu tiên sửa nguyên nhân dùng chung để tránh tạo thêm các đường chạy lệch nhau; không viết lại toàn bộ ứng dụng.

### Giai đoạn 1 — Khôi phục luồng sử dụng chính

1. Chốt các chế độ hỗ trợ: Tauri là desktop chính; ghi rõ browser và pywebview cũ có còn hỗ trợ hay không.
2. Tạo controller độc lập GUI và lifecycle backend: QA-01, QA-16.
3. Đồng nhất cấu hình cổng, connection adapter và xác thực: QA-04, QA-05, QA-06.
4. Tách effect React và quản lý socket: QA-02.
5. Sửa static fallback và shell OBS: QA-03, QA-14.
6. Hoàn thiện preview/close và phản hồi tác vụ: QA-07, QA-08, QA-17.

**Cổng nghiệm thu:** cài mới → cấu hình hoặc nạp fixture → render → OBS hiển thị đúng → sửa augment → save → OBS cập nhật; không loop request và không cần refresh thủ công.

### Giai đoạn 2 — Bảo vệ dữ liệu và phục hồi lỗi

1. Schema config/export, validate ảnh, giới hạn kích thước: QA-09, QA-10, QA-11.
2. File export duy nhất, ghi atomic và serialize render: QA-12, R-02.
3. Chặn WebSocket Origin ngoài và kiểm tra client OBS: QA-13.
4. Sửa update recovery, stop/start polling và chính sách cache tài khoản: QA-15, R-01, R-04.

**Cổng nghiệm thu:** dữ liệu sai không làm app crash/ghi đè ảnh hợp lệ; tải update lỗi vẫn tiếp tục dùng app; thay tài khoản không nhầm trận.

### Giai đoạn 3 — Kiểm thử hồi quy trên bản cài thực tế

1. Khắc phục môi trường Playwright rồi chạy E2E có mock Riot API; lưu screenshot, console/network log và kết quả từng ca.
2. Windows: Tauri dev, build release và bản cài mới; đường dẫn có dấu/khoảng trắng, tài khoản không có quyền admin, AppData có dữ liệu cũ.
3. OBS thực: mở trước/sau render, reconnect, nhiều Browser Source, đổi cổng nếu hỗ trợ, offline assets/font và live update.
4. Riot: dùng mock cho 401/403/404/429/5xx/timeout; xác minh một tài khoản thật khi có điều kiện, tránh ghi key/token vào log và báo cáo.
5. Updater: mock hoặc release thử có kiểm soát; xác minh chữ ký, lỗi tải/cài và phục hồi; kiểm tra gói Windows trước, rồi nền tảng khác nếu thuộc phạm vi phát hành.
6. Bổ sung CI smoke test khởi động sidecar và gọi render thật bằng fixture; build/lint/unit đơn lẻ hiện chưa bắt QA-01/02/03.

## 6. Ma trận kiểm thử hồi quy bắt buộc

| Nhóm | Ca kiểm thử chính | Kỳ vọng |
|---|---|---|
| Startup | AppData mới/cũ, config hỏng, cổng bận, backend chậm/crash | Ready đúng, thông báo lỗi rõ, có phục hồi |
| Cấu hình | Key thiếu/hết hạn, ID có dấu/khoảng trắng/#, region sai, port biên | Validate rõ, không mất config hợp lệ |
| Match | 0/1/nhiều trận, fixture lỗi/thiếu người chơi, đổi tài khoản khi fetch | Không hiện sai trận, lỗi có ngữ cảnh |
| Augments | Auto, ba slot, Destiny từng bậc và bonus cùng bậc, lưu/reload | Giữ đúng lựa chọn, không reset hoặc loop |
| Render | Không cache/có cache, bấm liên tiếp, watcher và API cùng chạy | Không file dở, đúng bản cuối, kết quả thật |
| OBS | Placeholder → render đầu, reconnect bỏ lỡ event, nhiều client | Đúng CSS/ảnh/font, tự đồng bộ |
| Preview/Close | Xem/ẩn, đóng/mở lại, quit | Cửa sổ thực đổi đúng; không mất backend ngoài dự kiến |
| PNG | Đúng 1920×1080, font/ảnh tải xong, base64 sai, PNG giả, burst export | File hợp lệ, unique, latest không hỏng |
| Security | Host/Origin/token sai, WS ngoài, traversal, payload lớn | Từ chối đúng; không lộ thông tin phiên |
| Update | Từ chối, download lỗi, chữ ký sai, install lỗi, thành công | Chỉ cài khi đồng ý, phục hồi dịch vụ, bảo toàn dữ liệu |
| UI | 1280×800, min 960×640, DPI 125/150%, bàn phím/dropdown/modal | Không khuất nút, focus hợp lý, thông báo đúng |

## 7. Điều kiện hoàn tất và nội dung cần duyệt

- Tất cả QA P1 được sửa và có kiểm thử tương ứng; P2 còn lại phải ghi rõ nếu hoãn.
- Test Python, Ruff, TypeScript/build đạt; thêm smoke sidecar và E2E luồng chính đạt.
- Xác minh ít nhất một bản cài Windows với OBS thực trước kết luận sẵn sàng phát hành.
- Không thay đổi file `.env`, API key hay dữ liệu cá nhân ngoài phạm vi đã được duyệt.
- Lượt hiện tại chỉ tạo báo cáo/kế hoạch và dữ liệu kiểm thử tách biệt; **chưa triển khai các phương án sửa**.

Đề nghị duyệt Giai đoạn 1 → 2 → 3 theo thứ tự trên. Điểm phạm vi cần chốt khi triển khai: giữ cả browser/pywebview hay tập trung Tauri, và có cam kết cổng tùy chỉnh/đa nền tảng hay không. Nếu chưa chỉ định, ưu tiên Tauri trên Windows, bảo toàn API và dữ liệu hiện có.
