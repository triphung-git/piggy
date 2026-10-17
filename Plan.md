# Kế hoạch khắc phục sau kiểm thử QA — TFT Post-Match Studio

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
