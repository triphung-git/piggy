# Architecture Essential — TFT Post-Match Studio (`piggy`)

> **Dùng làm ngữ cảnh nhanh (Quick Reference Context) cho AI Coding Agent và Contributor.** Khi cần chi tiết thực thi từng file, bắt buộc đọc `AGENTS.md`, `architecture.md` và `product.md`.

## 1. Mục tiêu hệ thống

- **Tên ứng dụng:** `TFT Post-Match Studio` (`identifier`: `com.triphung.tftstudio`, repo: [triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy)).
- **Nền tảng mục tiêu:** Windows x64 (`.exe` NSIS), macOS Apple Silicon `arm64` & Intel `x64` (`.dmg` + `.app.tar.gz`), Linux x64 (`.AppImage` + `.deb`).
- **Frontend:** Giao diện React 19 + TypeScript + Tailwind CSS v4 + Vite 8 có sẵn trong `Web Overlay/` cùng mẫu broadcast 1080p trong `templates/overlay.html`.
- **Backend nghiệp vụ:** Giữ nguyên gói Python `src/tft_studio/` (FastAPI, Uvicorn, WebSocket, Riot API Client, Data Dragon Parser), đóng gói thành binary một file (`--onefile`) bằng [PyInstaller](https://www.google.com/search?q=https%3A%2F%2Fpyinstaller.org%2Fen%2Fstable%2F) và chạy dưới dạng [Tauri Sidecar](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fsidecar%2F).
- **Desktop Shell & Auto-Update:** [Tauri v2](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fstart%2F) + [Tauri Updater Plugin](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fupdater%2F) + [Tauri GitHub Actions](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdistribute%2Fpipelines%2Fgithub%2F).
- **Chính sách Update:** Bắt buộc có xác nhận của người dùng (**Cập nhật ngay / Để sau**) để không làm gián đoạn buổi livestream OBS đang diễn ra.

## 2. Mô hình thành phần (Component Model)

```text
TFT Post-Match Studio (Tauri v2 Desktop App)
  ├── Tauri Rust Core (src-tauri/src/lib.rs)
  │    ├── Khởi tạo thư mục AppData (.env, overlay_config.json, output/, logs/)
  │    ├── Quản lý vòng đời Sidecar (Spawn khi mở app, Kill sạch trước khi Update/Thoát)
  │    └── Cung cấp Tauri Commands: get_backend_connection_info, stop_backend_sidecar, open_app_folder
  ├── Frontend Control Panel (Web Overlay/ - React 19)
  │    ├── API Facade (Web Overlay/src/lib/api.ts) thay thế hoàn toàn window.pywebview.api
  │    ├── Xuất ảnh 1080p đa nền tảng (html-to-image + /api/export)
  │    └── Update State Machine & Modal (Web Overlay/src/lib/updater.ts)
  ├── Python FastAPI Sidecar (binaries/tft-backend-<target-triple>)
  │    ├── HTTP REST & Static Server tại http://127.0.0.1:8080
  │    └── WebSocket Hub tại ws://127.0.0.1:8080/ws/overlay (Phục vụ OBS Studio Browser Source)
  └── Bundled Read-Only Resources (Tauri bundle.resources)
       └── templates/, assets/, TFT_DDragon/, defaults/
```

## 3. 10 Quy tắc kiến trúc bất khả xâm phạm (Non-Negotiable Rules)

1. **KHÔNG xóa bỏ máy chủ HTTP/WebSocket (`src/tft_studio/api/hub.py`):** OBS Studio Browser Source là phần mềm bên ngoài bắt buộc phải kết nối vào `http://127.0.0.1:8080/overlay` và `ws://127.0.0.1:8080/ws/overlay`. Không chuyển sang giao thức thuần `stdin`/`stdout` làm mất kết nối OBS.
2. **KHÔNG khởi chạy Python sidecar từ mã JavaScript Frontend:** Tiến trình sidecar phải được quản lý duy nhất bởi nhân Rust (`src-tauri/src/lib.rs`) để tránh sinh tiến trình trùng lặp hoặc lỗi `Address already in use (port 8080)` khi người dùng nhấn F5 Reload giao diện.
3. **KHÔNG nhúng `TFT_DDragon/`, `assets/` và `templates/` vào trong file `--onefile` của PyInstaller:** Chỉ đóng gói mã nguồn Python vào binary sidecar; các thư mục tài nguyên phải được khai báo trong `bundle.resources` của `src-tauri/tauri.conf.json` để tránh giải nén hàng ngàn ảnh vào thư mục tạm `_MEIxxxxxx` mỗi lần bật app.
4. **KHÔNG ghi `.env`, `overlay_config.json`, `output/` hoặc `logs/` vào thư mục cài đặt ứng dụng:** Mọi thao tác ghi phải trỏ vào thư mục `TFT_APPDATA_DIR` chuẩn của hệ điều hành để không gặp lỗi `PermissionError` trên macOS/Linux và không bị mất cấu hình khi Auto-Update.
5. **KHÔNG gọi `window.pywebview.api` trực tiếp trong các component React:** Mọi giao tiếp giữa `Web Overlay/` và backend phải đi qua lớp `Web Overlay/src/lib/api.ts`.
6. **KHÔNG gọi API đặc thù của riêng Windows mà không có nhánh đa nền tảng:** Bọc `ctypes.windll` trong điều kiện `sys.platform == "win32"`, thay `os.startfile()` bằng lệnh mở thư mục đa nền tảng và không phụ thuộc cứng vào `chrome.exe`/`msedge.exe` khi xuất ảnh 1080p.
7. **KHÔNG gọi `update.downloadAndInstall()` trước khi người dùng xác nhận và trước khi dừng Sidecar:** Khi người dùng nhấn **Cập nhật ngay**, bắt buộc gọi Tauri command `stop_backend_sidecar` để giải phóng file lock `.exe` và cổng `8080` rồi mới cài đặt bản cập nhật.
8. **KHÔNG giả định cross-compile của Rust có thể tạo binary Python cho hệ điều hành khác:** Sidecar Python phải được build bằng PyInstaller trên đúng hệ điều hành và kiến trúc CPU đích trong GitHub Actions.
9. **KHÔNG lưu khóa riêng tư (`TAURI_SIGNING_PRIVATE_KEY`) hoặc `RIOT_API_KEY` thật vào Git:** Chỉ nhúng `pubkey` vào `src-tauri/tauri.conf.json` và giữ khóa ký bí mật trong GitHub Actions Secrets.
10. **KHÔNG cấp quyền `shell:allow-execute` rộng không giới hạn trong Tauri Capabilities:** Chỉ cấp quyền thực thi đúng sidecar `binaries/tft-backend` và các plugin cần thiết (`updater`, `dialog`, `process`).

## 4. Quy ước đặt tên Sidecar theo Target Triple

Với cấu hình `"externalBin": ["binaries/tft-backend"]` trong `src-tauri/tauri.conf.json`, tệp thực thi do `scripts/build_sidecar.py` tạo ra trong `src-tauri/binaries/` phải tuân thủ chính xác tên sau:

| Hệ điều hành / Kiến trúc | Tên tệp trong `src-tauri/binaries/` |
| :--- | :--- |
| Windows x64 | `tft-backend-x86_64-pc-windows-msvc.exe` |
| macOS Apple Silicon (arm64) | `tft-backend-aarch64-apple-darwin` |
| macOS Intel (x64) | `tft-backend-x86_64-apple-darwin` |
| Linux x64 GNU | `tft-backend-x86_64-unknown-linux-gnu` |

## 5. Luồng cập nhật chuẩn (Update Flow)

1. Ứng dụng mở, nhân Rust khởi chạy `tft-backend` sidecar và nhận tín hiệu `{"event":"server_ready","port":8080}`.
2. Sau khi UI sẵn sàng, `Web Overlay/src/lib/updater.ts` kiểm tra endpoint `https://github.com/triphung-git/piggy/releases/latest/download/latest.json`. Lỗi mạng khi kiểm tra không được chặn ứng dụng.
3. Nếu có phiên bản mới: Hiển thị `UpdateModal` với version mới, Release Notes và hai nút **Cập nhật ngay** / **Để sau**.
4. Nếu người dùng chọn **Để sau**: Đóng hộp thoại, giữ nguyên phiên bản hiện tại để không gián đoạn livestream.
5. Nếu người dùng chọn **Cập nhật ngay**:
   - Gọi `invoke("stop_backend_sidecar")` để dừng Uvicorn và đóng tiến trình `tft-backend`.
   - Gọi `update.downloadAndInstall()` để tải gói cập nhật và xác minh chữ ký bằng `pubkey`.
   - Gọi `relaunch()` từ `@tauri-apps/plugin-process` để khởi động lại ứng dụng với toàn bộ dữ liệu trong `TFT_APPDATA_DIR` được giữ nguyên.

## 6. Danh sách nghiệm thu trước khi phát hành (Release Acceptance Checklist)

- [ ] Chạy ứng dụng thành công trên máy sạch không cài Python, Node.js, Rust hay Chrome.
- [ ] OBS Studio Browser Source truy cập `http://127.0.0.1:8080/overlay` hiển thị đúng giao diện 1080p và nhận cập nhật trực tiếp qua WebSocket `/ws/overlay`.
- [ ] Cấu hình `.env`, `overlay_config.json`, `output/` và `logs/` nằm trong thư mục `AppData` của hệ điều hành, không ghi vào thư mục cài đặt ứng dụng.
- [ ] Nhấn F5 / Reload trên cửa sổ Control Panel không làm sinh thêm tiến trình `tft-backend` thứ hai.
- [ ] Nút xuất ảnh PNG 1080p hoạt động trên cả Windows, macOS và Linux.
- [ ] Nút mở thư mục `output/` và `logs/` mở đúng trình quản lý tệp trên cả Windows (Explorer), macOS (Finder) và Linux (File Manager).
- [ ] Khi có bản cập nhật mới, hộp thoại hỏi ý kiến người dùng hiển thị đúng; chọn **Để sau** không tự động cài đặt.
- [ ] Khi chọn **Cập nhật ngay**, tiến trình `tft-backend` thoát sạch trước khi cài đặt, cập nhật thành công và bảo toàn cấu hình người dùng.

## 7. Tài liệu tham khảo chính thức

- [Kho mã nguồn: triphung-git/piggy](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Ftriphung-git%2Fpiggy)
- [Tauri Sidecar](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fsidecar%2F)
- [Tauri Resources](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdevelop%2Fresources%2F)
- [Tauri Updater](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fupdater%2F)
- [Tauri GitHub Actions](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fdistribute%2Fpipelines%2Fgithub%2F)
- [Tauri Process Plugin](https://www.google.com/search?q=https%3A%2F%2Fv2.tauri.app%2Fplugin%2Fprocess%2F)
- [PyInstaller](https://www.google.com/search?q=https%3A%2F%2Fpyinstaller.org%2Fen%2Fstable%2F)
