# Kết quả triển khai và kiểm thử sau Plan.md

Ngày: 17/10/2026. Phạm vi được duyệt: sửa các phát hiện trong `Plan.md`, ưu tiên Tauri/Windows, giữ browser và adapter pywebview.

Bổ sung ngày 18/10/2026: workflow Release đã được sửa và kiểm tra riêng, xem [hướng dẫn GitHub/Release](GITHUB-RELEASE-GUIDE.md). Kết quả mới gồm 111 test Python và 6 test Node đạt, YAML/actionlint đạt, kiểm thử chữ ký Tauri/Minisign thực đạt. Các giới hạn native/OBS/Riot bên dưới vẫn còn áp dụng.

## Kết quả đã xác minh

| Kiểm tra | Kết quả |
|---|---|
| Python unit/security/regression | **90 passed**, 1 cảnh báo deprecation Starlette/httpx; 11,76 giây |
| Ruff cho `src desktop tests scripts` | Đạt |
| TypeScript + Vite production build | Đạt; có cảnh báo Vite về configLoader native tương lai |
| Smoke sidecar chạy từ Python | Đạt: startup, health ready, POST render có token, HTML, shell và assets |
| PyInstaller executable `scratch/qa-dist/tft-backend-qa.exe` | Đóng gói thành công; smoke executable đạt với resources và AppData thử nghiệm riêng |
| Chrome/Playwright, luồng panel | Đạt: catalog tải ổn định, Render, Save & Sync, Close/Reopen, không có page error |
| Overlay trong Chrome | Đạt: mở trước render rồi tự cập nhật; 35 thẻ ảnh trong fixture tải được; bố cục/stylesheet được nạp |
| Kích thước cửa sổ 960×640 và 1280×800 | Không tràn ngang; nút Close vẫn truy cập được |
| Preview browser | Mở cửa sổ thật tới đúng backend `:18080/overlay`, ẩn/đóng được |
| Destiny + bonus + Auto | Chọn Gold Destiny và bonus 3 Threes, lưu đúng `[destiny, bonus, null, null]`; lựa chọn chưa lưu không bị tải lại ghi đè |
| Xuất PNG bằng Chrome thực | Có `overlay_latest.png` hợp lệ, **1920×1080** |
| Updater mô phỏng IPC | Đạt 4 nhánh bên dưới; không cài bản cập nhật thật |
| pywebview bridge xuất hiện chậm (mô phỏng browser) | Frontend chờ bridge; không gửi API trước khi sẵn sàng; POST Render dùng đúng token từ bridge |

Kiểm thử trình duyệt dùng Chrome có sẵn qua Playwright. Việc tải Chromium riêng bị ECONNRESET, nhưng không còn chặn kiểm thử vì thư viện Playwright và Chrome hiện có hoạt động.

### Updater đã kiểm tra bằng hàm triển khai thực và IPC mô phỏng

- Download thất bại: chỉ gọi download; backend vẫn ready.
- Install thất bại sau khi dừng backend: gọi start lại, lấy connection info mới và health check; backend phục hồi.
- Stop thất bại: không gọi install; kiểm tra lại trạng thái backend và báo lỗi.
- Thành công: thứ tự download → stop backend → install → relaunch.

Đây là kiểm thử logic TypeScript và thứ tự IPC. Chưa thay thế cho kiểm thử cập nhật có chữ ký bằng installer Tauri thật.

## Đối chiếu các phát hiện

| ID | Thay đổi đã triển khai | Bằng chứng/phần còn cần xác minh |
|---|---|---|
| QA-01 | Controller dùng chung độc lập webview; lifespan tạo/dọn dịch vụ; ready sau khi bind | Smoke source và executable đạt |
| QA-02 | Effect khởi tạo không phụ thuộc catalog; socket cleanup có disposed; bảo vệ draft | Chrome xác nhận một lượt catalog ổn định, không reset draft |
| QA-03 | Fallback assets theo từng file, chặn traversal/symlink ra ngoài root | Regression API và 35 ảnh overlay trong Chrome đạt |
| QA-04 | Dev Vite/Tauri cùng cổng 5173, bind loopback | Vite thực chạy tại 5173; Tauri dev cần toolchain |
| QA-05 | Tauri IPC, pywebview connection adapter có chờ bridge, browser ghép cặp bằng token fragment/session | Browser ghi API thành công; mô phỏng bridge chậm đạt; pywebview/native còn cần chạy bản GUI |
| QA-06 | REST/WS/OBS/ảnh dùng connection info; CSP cho cổng loopback tùy chỉnh | Browser thực tại cổng backend 18080 đạt; CSP native còn cần bản cài |
| QA-07 | Native có lệnh tạo/ẩn preview; browser popup thật; thông báo preview tách OBS | Browser preview đạt; cửa sổ Tauri cần chạy native |
| QA-08 | Close Panel không dừng sidecar; Reopen giữ dịch vụ | Chrome Close/Reopen và Render lại đạt |
| QA-09 | Schema cấu hình chung, strict type, port bounds, đường dẫn an toàn; atomic write và lock | Regression chứng minh payload sai bị 422 và giữ file hợp lệ |
| QA-10 | Export request model và giới hạn body trước parse, gồm chunked body | Dữ liệu sai kiểu/JSON không hợp lệ không ghi file; body quá lớn 413 |
| QA-11 | Base64 strict, Pillow verify/load, PNG 1920×1080, validate trước khi thay latest | PNG giả/cụt và input lỗi không thay ảnh latest; ảnh hợp lệ đạt |
| QA-12 | UUID cho tên ảnh lịch sử, atomic replace và export lock | Hai lần xuất tạo file riêng; latest mở được |
| QA-13 | Kiểm tra Host/Origin trước accept WS; INITIAL_STATE chỉ gửi trạng thái cần thiết | Origin ngoài bị 1008; OBS không gửi Origin kết nối được |
| QA-14 | Shell cố định luôn có CSS/root; cập nhật/reconnect fetch fragment mới; scale sau swap | Chrome mở trước render cập nhật đúng; OBS thật còn cần kiểm tra |
| QA-15 | Download trước stop, xác nhận tiến trình thoát, restart backend nếu install lỗi | Bốn nhánh IPC mô phỏng đạt; installer/chữ ký/cây tiến trình native chưa nghiệm thu |
| QA-16 | Connection có health/retry/timeout; invalidate khi socket mất; readiness sau bind | Smoke startup thực và browser kết nối cổng tùy chỉnh đạt; crash/restart native cần kiểm tra |
| QA-17 | Lỗi chưa ready trả 503, render lỗi 409, không phát success event khi fail; lưu/render có kết quả riêng | Regression negative render và browser Save & Sync đạt |

Các rủi ro bổ sung đã được xử lý trong mã: polling dùng stop event riêng và join trước restart; cache có owner theo tài khoản/khu vực và generation để bỏ kết quả cũ; renderer/export/config ghi atomic; watcher dùng trailing debounce; export không chụp DOM control panel; UI có cài đặt Riot; resources có frontend để phục vụ Browser Panel trong gói Tauri.

Đã sửa thêm lỗi lệch slot Auto sau bonus Destiny và lỗi tên file tạm vượt giới hạn đường dẫn Windows, kèm kiểm thử hồi quy.

## Giới hạn nghiệm thu còn lại

1. Máy hiện chưa có Rust/Cargo và toolchain build Windows phù hợp. Chưa biên dịch/chạy bản cài Tauri mới, nên không kết luận các lệnh preview, stop/restart process group và CSP native đã đạt thực tế. CI đã có job Windows `cargo check` cùng build frontend/sidecar để bắt lỗi biên dịch khi chạy trên môi trường đủ công cụ.
2. Chưa chạy OBS Studio thật, Riot API với tài khoản/key thật hoặc cài cập nhật có chữ ký. Kiểm tra overlay trong Chrome và mock API/IPC không thay thế các tích hợp này.
3. Chưa nghiệm thu macOS/Linux và DPI Windows 125%/150%. Ma trận kích thước browser đã chạy chỉ bao phủ hai viewport nêu trên.
4. Binary QA nằm trong `scratch/qa-dist`, dùng resources từ workspace khi smoke test; không phải installer phát hành. Bộ assets/UI trong gói Tauri vẫn cần kiểm tra trên bản cài mới.

Đã thử `npm run tauri -- build --debug --no-bundle`: dừng tại `cargo metadata ... program not found`, trước bước biên dịch native. Đây là thiếu công cụ build, chưa phải kết quả kiểm tra mã Rust.

Sidecar native dùng process group để dừng cả tiến trình con của PyInstaller, theo [API `Command::set_process_group` của Tauri Shell](https://docs.rs/tauri-plugin-shell/latest/tauri_plugin_shell/process/struct.Command.html#method.set_process_group); vì vậy dependency shell yêu cầu phiên bản 2.5 trở lên. Hành vi trên Windows vẫn nằm trong phần nghiệm thu native còn lại.

## Cách chạy lại

```powershell
$env:TFT_APPDATA_DIR = Join-Path $PWD 'scratch/qa-final-appdata'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp scratch/qa-final-tests-rerun
.\.venv\Scripts\ruff.exe check src desktop tests scripts
npm run build
.\.venv\Scripts\python.exe scripts/smoke_sidecar.py
.\.venv\Scripts\python.exe scripts/smoke_sidecar.py --binary scratch/qa-dist/tft-backend-qa.exe
```

Đối với bản cài native: cài Rust/MSVC theo môi trường build của dự án, build sidecar bằng `scripts/build_sidecar.py`, chạy `cargo check --manifest-path src-tauri/Cargo.toml`, rồi nghiệm thu Tauri/OBS/update theo ma trận trong `Plan.md`. Không công bố bản phát hành trước khi hoàn tất các bước này.

Ảnh minh họa thử nghiệm lưu tại `scratch/panel.png` và `scratch/overlay.png`; dữ liệu dùng fixture, không phải thông tin tài khoản thật.
