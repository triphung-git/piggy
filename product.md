# Product Requirements — TFT Post-Match Studio (`piggy`)

> **Trạng thái:** Phiên bản chính thức đã chuẩn hóa cho dự án [triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy)  
> **Kiến trúc đích:** [Tauri v2](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fstart%2F) + Python FastAPI/WebSocket [Tauri Sidecar](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fsidecar%2F) ([PyInstaller](https://www.google.com/search?q=https%3A%2F%2Fpyinstaller.org%2Fen%2Fstable%2F)) + [Tauri Updater Plugin](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fupdater%2F) + [Tauri GitHub Actions](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdistribute%2Fpipelines%2Fgithub%2F)  
> **Ngôn ngữ tài liệu:** Tiếng Việt  
> **Tên sản phẩm:** `TFT Post-Match Studio` (Mã định danh bundle: `com.triphung.tftstudio`)

## 1. Tóm tắt sản phẩm

**TFT Post-Match Studio** ([triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy)) là ứng dụng desktop đa nền tảng cung cấp bảng điều khiển (Control Panel) và hệ thống hiển thị đồ họa hậu trận đấu chuẩn 1080p (Broadcast Overlay) theo thời gian thực cho bộ môn **Teamfight Tactics (Đấu Trường Chân Lý)** trên OBS Studio.

Ứng dụng kết hợp giao diện điều khiển **React 19 + Vite 8 + Tailwind CSS v4** (`Web Overlay/`), mẫu đồ họa broadcast (`templates/overlay.html`, `templates/overlay.css`) và lõi xử lý **Python 3.11+ FastAPI/Uvicorn** (`src/tft_studio/`). Toàn bộ hệ thống được đóng gói độc lập để streamer, caster và ban tổ chức giải đấu có thể tải bộ cài, cài đặt và sử dụng ngay trên **Windows, macOS và Linux** mà không phải tự cài đặt Python, Node.js, Rust, pip hay trình duyệt phụ trợ bên ngoài.

Khi có bản phát hành (Release) mới trên GitHub, ứng dụng tự động kiểm tra phiên bản, hiển thị ghi chú phát hành (Release Notes) và **chỉ tải/cài đặt bản cập nhật sau khi người dùng xác nhận**. Mọi cấu hình giải đấu (`overlay_config.json`), khóa kết nối Riot API (`.env`), lịch sử trận đấu (`output/`) và tài nguyên tướng/trang bị (`TFT_DDragon/`) đều được bảo toàn tuyệt đối qua các lần cập nhật.

## 2. Mục tiêu sản phẩm

1. **Cài đặt một chạm, không phụ thuộc môi trường dev:** Đóng gói toàn bộ Control Panel, máy chủ HTTP/WebSocket nội bộ và công cụ xuất ảnh 1080p thành gói cài đặt chuẩn cho Windows (`.exe`/`.msi`), macOS (`.dmg`/`.app`) và Linux (`.AppImage`/`.deb`).
2. **Bảo toàn 100% nghiệp vụ Python & OBS Live Overlay:** Tái sử dụng toàn bộ các module trong `src/tft_studio/` (`riot/client.py`, `data/parser.py`, `render/generator.py`, `api/hub.py`, `service/match_service.py`) dưới dạng [Tauri Sidecar](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fsidecar%2F), giữ nguyên kết nối HTTP (`http://127.0.0.1:8080/overlay`) và WebSocket (`ws://127.0.0.1:8080/ws/overlay`) cho OBS Studio Browser Source.
3. **Loại bỏ sự phụ thuộc vào [pywebview](https://www.google.com/search?q=https%3A%2F%2Fpywebview.flowrl.com%2F) và trình duyệt Chrome/Edge ngoài:** Thay thế `desktop/app.py` và `desktop/bridge.py` bằng nhân [Tauri v2](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fstart%2F) kết hợp lớp `Web Overlay/src/lib/api.ts`; đồng thời nâng cấp tính năng xuất ảnh PNG 1080p (`exporter.py`) sang cơ chế kết xuất trực tiếp qua WebView/DOM ([html-to-image](https://www.google.com/search?q=https%3A%2F%2Fwww.npmjs.com%2Fpackage%2Fhtml-to-image)) không cần gọi `chrome.exe` hay `msedge.exe` bên ngoài.
4. **Cập nhật tự động có xác nhận và ký số bảo mật:** Tích hợp [Tauri Updater Plugin](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fupdater%2F) kết nối trực tiếp tới GitHub Releases của repo [triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy), đảm bảo đóng tiến trình Python sidecar sạch sẽ trước khi ghi đè bản mới để không xảy ra lỗi khóa file hay xung đột cổng `8080`.
5. **Tách biệt hoàn toàn dữ liệu người dùng và tài nguyên `TFT_DDragon/` khỏi thư mục cài đặt:** Lưu trữ `.env`, `overlay_config.json`, `output/` và dữ liệu cập nhật `TFT_DDragon/` trong thư mục `AppData` chuẩn của từng hệ điều hành để tránh lỗi quyền ghi (`PermissionError`) trên macOS/Linux và giữ nguyên cấu hình khi nâng cấp.

## 3. Ngoài phạm vi của phiên bản đầu tiên (Out of Scope MVP)

- Ứng dụng di động (Android / iOS).
- Tự động cập nhật âm thầm (Silent Auto-Update) không hỏi ý kiến người dùng — đặc biệt nguy hiểm khi streamer/ban tổ chức đang phát sóng trực tiếp giải đấu trên OBS.
- Đóng gói cứng toàn bộ các mùa TFT cũ không còn sử dụng vào file thực thi `--onefile` của sidecar.
- Tự động rollback toàn bộ ứng dụng và dữ liệu trong mọi tình huống lỗi (hệ thống ưu tiên giữ tương thích ngược cho cấu hình `overlay_config.json` và `.env`).
- Phân phối qua Microsoft Store, Mac App Store, Snap Store hoặc Flathub trong bản MVP đầu tiên.

## 4. Người dùng mục tiêu và trải nghiệm mong muốn

### Người dùng cuối (Streamer, Caster, Kỹ thuật viên giải đấu TFT)

Người dùng không cần biết ứng dụng được viết bằng Python, React hay Rust. Luồng trải nghiệm chuẩn:

1. Tải đúng bộ cài đặt cho hệ điều hành từ trang GitHub Releases của [triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy).
2. Cài đặt và mở **TFT Post-Match Studio**.
3. Nhập `RIOT_API_KEY`, `RIOT_ID` (`GameName#TAG`), khu vực (`VN`, `KR`, `NA`, v.v.) và tiêu đề giải đấu ngay trên Control Panel; cấu hình được lưu bền vững tại thư mục dữ liệu người dùng của hệ điều hành.
4. Thêm Browser Source `http://localhost:8080/overlay` (kích thước `1920x1080`) vào OBS Studio hoặc nhấn nút xuất ảnh PNG 1080p trực tiếp mà không cần cài thêm công cụ phụ.
5. Khi có bản phát hành mới trên GitHub, ứng dụng hiển thị hộp thoại thông báo phiên bản mới kèm ghi chú thay đổi với hai lựa chọn **Cập nhật ngay** hoặc **Để sau** (để không làm gián đoạn buổi livestream đang diễn ra).
6. Khi chọn **Cập nhật ngay**, ứng dụng tự động ngắt tiến trình backend nội bộ, tải gói cập nhật đã xác minh chữ ký, cài đặt và khởi động lại cùng toàn bộ cấu hình giải đấu được giữ nguyên.

### Nhà phát triển / Phát hành (`triphung-git`)

Nhà phát triển duy trì mã nguồn trong một repository duy nhất ([triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy)), kiểm thử trên nhánh phát triển và phát hành bằng cách đẩy Git tag phiên bản (ví dụ `v2.5.0`). [Tauri GitHub Actions](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdistribute%2Fpipelines%2Fgithub%2F) tự động biên dịch Python sidecar theo từng kiến trúc CPU, đóng gói bộ cài Tauri, ký số artifact updater, sinh tệp `latest.json` và đăng tải lên GitHub Releases.

## 5. Phạm vi nền tảng (Platform Matrix)

| Nền tảng | Artifact ưu tiên | Tên Sidecar Target Triple | Ghi chú triển khai |
| :--- | :--- | :--- | :--- |
| **Windows x64** | Installer NSIS `.exe` (kèm gói cập nhật `.nsis.zip` + `.sig`) | `tft-backend-x86_64-pc-windows-msvc.exe` | Thay thế hoàn toàn `build_exe.ps1` và [Inno Setup](https://www.google.com/search?q=https%3A%2F%2Fjrsoftware.org%2Fisinfo.php) cũ; tự động kiểm tra/cài đặt WebView2 Runtime nếu máy Windows cũ chưa có. |
| **macOS Apple Silicon (arm64)** | `.dmg` cho cài đặt đầu tiên + `.app.tar.gz` (`.sig`) cho Updater | `tft-backend-aarch64-apple-darwin` | Không gọi `ctypes.windll` của Windows; lưu dữ liệu tại `~/Library/Application Support/com.triphung.tftstudio/`. |
| **macOS Intel (x64)** | `.dmg` + `.app.tar.gz` (`.sig`) | `tft-backend-x86_64-apple-darwin` | Sidecar Python phải được build đúng kiến trúc `x86_64` trên runner tương ứng. |
| **Linux x64** | `.AppImage` (hỗ trợ trực tiếp Tauri Updater) + `.deb` | `tft-backend-x86_64-unknown-linux-gnu` | Đảm bảo khai báo đầy đủ thư viện hệ thống `libwebkit2gtk-4.1` trong tài liệu cài đặt. |

## 6. Yêu cầu chức năng (Functional Requirements)

### FR-001 — Cài đặt độc lập & Tách tài nguyên tĩnh

Ứng dụng phải được phân phối dưới dạng bộ cài độc lập cho từng hệ điều hành. Lõi Python (`src/tft_studio/`) được biên dịch thành một file thực thi duy nhất bằng [PyInstaller](https://www.google.com/search?q=https%3A%2F%2Fpyinstaller.org%2Fen%2Fstable%2F) (`--onefile`) và nhúng làm [Tauri Sidecar](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fsidecar%2F). Các thư mục tài nguyên tĩnh lớn (`TFT_DDragon/`, `assets/`, `templates/`) phải được đóng gói dưới dạng `bundle.resources` của Tauri hoặc đồng bộ vào thư mục `AppData` thay vì nén chung vào file `--onefile` của PyInstaller (nhằm giúp thời gian khởi động ứng dụng dưới 2 giây).

**Tiêu chí nghiệm thu:** Cài và mở ứng dụng trên máy sạch (không có Python, Node.js, Rust, Chrome); ứng dụng mở giao diện Control Panel và hiển thị trang `/overlay` trong vòng dưới 3 giây.

### FR-002 — Giao tiếp Hybrid: Control Panel UI, OBS Browser Source & Python Sidecar

Giao diện React 19 trong `Web Overlay/` phải chuyển toàn bộ lệnh gọi từ `window.pywebview.api` (`desktop/bridge.py`) sang lớp `Web Overlay/src/lib/api.ts`. Sidecar Python khởi chạy máy chủ FastAPI/Uvicorn (`src/tft_studio/api/hub.py`) tại cổng nội bộ (mặc định `127.0.0.1:8080`) để phục vụ đồng thời:
1. **Control Panel UI** qua REST API (`/api/config`, `/api/match/latest`, `/api/match/history`, `/api/export`, `/api/health`) có bảo vệ bằng `X-Studio-Token` cho các thao tác ghi.
2. **OBS Studio Browser Source** qua HTTP (`GET /overlay`, `/assets/*`, `/TFT_DDragon/*`) và WebSocket (`WS /ws/overlay`) để cập nhật trực tiếp không cần tải lại trang.

**Tiêu chí nghiệm thu:** Thay đổi cấu hình hoặc kéo trận đấu mới trên Control Panel lập tức đẩy sự kiện WebSocket làm mới giao diện `http://127.0.0.1:8080/overlay` trên OBS Studio.

### FR-003 — Quản lý vòng đời Sidecar ở tầng Rust (`src-tauri`)

Lớp vỏ Rust của Tauri (`src-tauri/src/lib.rs`) chịu trách nhiệm khởi chạy tiến trình `tft-backend` duy nhất một lần khi mở ứng dụng, đọc tín hiệu `{"status":"ready","port":8080}` từ `stdout` của sidecar, giám sát trạng thái hoạt động và **bắt buộc dừng sạch tiến trình sidecar** khi người dùng đóng cửa sổ ứng dụng hoặc ngay trước khi [Tauri Updater Plugin](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fupdater%2F) tiến hành cài đặt bản mới.

**Tiêu chí nghiệm thu:** Nhấn F5/Reload trên giao diện Control Panel không sinh thêm tiến trình Python thứ hai; đóng ứng dụng hoặc thực hiện Auto-Update không để lại tiến trình `tft-backend` mồ côi giữ cổng `8080`.

### FR-004 — Xuất ảnh Overlay 1080p không phụ thuộc trình duyệt ngoài

Tính năng xuất ảnh tĩnh PNG 1080p phải hoạt động trên cả Windows, macOS và Linux mà không yêu cầu người dùng cài đặt Google Chrome hay Microsoft Edge ở đường dẫn cố định.

**Tiêu chí nghiệm thu:** Nhấn nút Export PNG tạo ra tệp ảnh `1920x1080` sắc nét lưu trong thư mục `output/` (thông qua kết xuất DOM/Canvas bằng [html-to-image](https://www.google.com/search?q=https%3A%2F%2Fwww.npmjs.com%2Fpackage%2Fhtml-to-image) hoặc WebView offscreen của Tauri, có giữ cơ chế headless browser làm phương án dự phòng tùy chọn).

### FR-005 — Kiểm tra và Xác nhận cập nhật (User-Confirmed Update)

Ứng dụng tự động kiểm tra endpoint `latest.json` trên GitHub Releases sau khi giao diện đã khởi tạo xong, đồng thời có nút **Kiểm tra cập nhật** thủ công trên Control Panel. Khi phát hiện bản mới, giao diện hiển thị phiên bản hiện tại, phiên bản mới, nội dung Release Notes và hai nút **Cập nhật ngay** / **Để sau**.

**Tiêu chí nghiệm thu:** Không bao giờ tự ý tải và khởi động lại ứng dụng khi streamer đang phát sóng; chọn **Để sau** cho phép tiếp tục sử dụng bình thường; lỗi mất mạng khi kiểm tra update không làm gián đoạn tính năng lấy dữ liệu trận đấu.

### FR-006 — Xác minh chữ ký số, Cài đặt cập nhật và Khởi động lại

Khi người dùng nhấn **Cập nhật ngay**, ứng dụng xác minh chữ ký gói cập nhật bằng `pubkey` nhúng trong `tauri.conf.json`, dừng tiến trình `tft-backend`, cài đặt bản cập nhật và tự động khởi động lại ứng dụng.

**Tiêu chí nghiệm thu:** Gói cập nhật sai chữ ký bị từ chối ngay lập tức; sau khi khởi động lại, phiên bản mới nhận diện đầy đủ cấu hình `.env` và `overlay_config.json` cũ.

### FR-007 — Bảo toàn dữ liệu người dùng và Cấu hình ngoài App Bundle

Toàn bộ dữ liệu phát sinh trong quá trình sử dụng phải được lưu tại thư mục dữ liệu chuẩn của hệ điều hành (`AppData`):
- File cấu hình `.env` (chứa `RIOT_API_KEY`, `RIOT_ID`, `REGION`) và `overlay_config.json`.
- Thư mục `output/` (chứa JSON cache trận đấu và ảnh PNG xuất ra).
- Thư mục `logs/` và dữ liệu `TFT_DDragon/` tải bổ sung.

**Tiêu chí nghiệm thu:** Khi chạy trên macOS (`/Applications`) hoặc Linux AppImage (vùng chỉ đọc), ứng dụng lưu cấu hình và xuất ảnh thành công mà không gặp lỗi `PermissionError`.

### FR-008 — Quy trình CI/CD phát hành tự động trên GitHub

Đẩy tag phiên bản theo chuẩn Semantic Versioning (ví dụ `v2.5.0`) lên [triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy) sẽ kích hoạt workflow GitHub Actions tự động chạy kiểm thử (`pytest` + `vite build`), đóng gói sidecar Python và bộ cài Tauri cho Windows/macOS/Linux, ký số và tạo GitHub Release kèm tệp `latest.json`.

**Tiêu chí nghiệm thu:** Bản Release tạo ra có đầy đủ bộ cài đặt, tệp cập nhật, chữ ký `.sig` và `latest.json` hợp lệ cho toàn bộ hệ điều hành trong ma trận hỗ trợ.

## 7. Yêu cầu phi chức năng (Non-Functional Requirements)

### NFR-001 — Hiệu năng & Mức tiêu thụ tài nguyên
- Dung lượng RAM tiêu thụ tổng cộng (Tauri WebView + Python FastAPI Sidecar) duy trì ở mức **80–130 MB**, đảm bảo máy tính của streamer chạy mượt đồng thời cả client Liên Minh Huyền Thoại/TFT và OBS Studio.
- Thời gian từ lúc nhấp đúp biểu tượng ứng dụng đến khi máy chủ port `8080` sẵn sàng dưới **2.5 giây**.

### NFR-002 — Bảo mật (Security)
- Cấu hình [Tauri Capabilities](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Flearn%2Fsecurity%2Fusing-plugin-permissions%2F) (`src-tauri/capabilities/default.json`) theo nguyên tắc quyền tối thiểu (Least Privilege): chỉ cấp quyền cho `updater`, `dialog`, `process` và mở thư mục `output`/`logs` được chỉ định.
- Không lưu `RIOT_API_KEY` hay khóa ký `TAURI_SIGNING_PRIVATE_KEY` vào mã nguồn Git hoặc in ra file log.
- Ràng buộc máy chủ FastAPI chỉ lắng nghe trên `127.0.0.1` (loopback) trừ khi người dùng chủ động bật chế độ LAN Broadcast trong cấu hình.

### NFR-003 — Khả năng quan sát & Chẩn đoán lỗi (Observability)
- Ghi log xoay vòng (Rotating File Handler) tại thư mục `logs/studio.log` bên trong `AppData`.
- Giữ nguyên nút **Mở thư mục Logs** và **Mở thư mục Output** trên giao diện Control Panel (sử dụng hàm mở thư mục đa nền tảng thay vì `os.startfile` chỉ chạy trên Windows).

## 8. Ma trận Rủi ro và Giải pháp phòng ngừa

| Rủi ro thực tế trong dự án `piggy` | Giải pháp xử lý triệt để |
| :--- | :--- |
| **Xung đột cổng `8080` hoặc tiến trình `tft-backend` bị khóa trên Windows khi chạy Auto-Update** | Quản lý tiến trình con trực tiếp trong Rust (`src-tauri/src/lib.rs`); trước khi cài đặt bản cập nhật, Rust gửi lệnh tắt và chờ tiến trình Python thoát hoàn toàn. |
| **PyInstaller `--onefile` khởi động chậm do phải giải nén hàng ngàn ảnh `TFT_DDragon/`** | Tách `TFT_DDragon/`, `assets/`, `templates/` ra khỏi file thực thi PyInstaller; khai báo làm `bundle.resources` của Tauri để truy cập trực tiếp trên ổ đĩa. |
| **Hàm `os.startfile()` và `ctypes.windll` gây crash trên macOS / Linux** | Bọc các lời gọi Windows API trong điều kiện `sys.platform == "win32"` và dùng giải pháp đa nền tảng (`subprocess.run(["open", path])` trên macOS, `xdg-open` trên Linux, hoặc plugin `opener` của Tauri). |
| **Người dùng macOS/Linux không có `chrome.exe` nên `exporter.py` báo lỗi khi xuất ảnh** | Tích hợp kết xuất DOM sang PNG 1080p ngay trên Frontend bằng [html-to-image](https://www.google.com/search?q=https%3A%2F%2Fwww.npmjs.com%2Fpackage%2Fhtml-to-image) kết hợp API lưu file, chỉ dùng trình duyệt headless hệ thống làm phương án dự phòng. |
| **Riot Games cập nhật mùa TFT mới (Set/Patch mới) làm thiếu ảnh tướng/trang bị** | Hỗ trợ đọc `TFT_DDragon/` ưu tiên từ thư mục `AppData` trước rồi mới fallback về `RESOURCE_DIR`, cho phép tải bổ sung dữ liệu bản vá mới mà không cần cài lại app. |

## 9. Tài liệu tham khảo chính thức

- [Kho mã nguồn dự án: triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy)
- [Tauri v2 — Embedding External Binaries (Sidecar)](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fsidecar%2F)
- [Tauri v2 — Embedding Additional Files (Resources)](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fresources%2F)
- [Tauri v2 — Updater Plugin](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fupdater%2F)
- [Tauri v2 — GitHub Actions Release Pipeline](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdistribute%2Fpipelines%2Fgithub%2F)
- [Tauri v2 — Security Capabilities \& Permissions](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Flearn%2Fsecurity%2Fusing-plugin-permissions%2F)
- [PyInstaller Official Documentation](https://www.google.com/search?q=https%3A%2F%2Fpyinstaller.org%2Fen%2Fstable%2F)
