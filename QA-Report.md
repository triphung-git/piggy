# QA Report — Release CI/CD đa nền tảng

Ngày đánh giá: 22/10/2026. Phạm vi: ba lỗi do người dùng cung cấp, đối chiếu mã nguồn tại workspace hiện tại và tài liệu chính thức Python/Tauri.

**Kết luận: giữ trạng thái chặn phát hành.** Có hai nhóm sự cố: Windows gặp lỗi vòng đời tiến trình/cleanup trong smoke test; macOS ARM64 và Linux x86_64 cùng gặp lỗi giải mã private key của updater. Ba job lỗi không đồng nghĩa với ba nguyên nhân độc lập.

Các mục 1–6 ghi nhận phân tích ban đầu trước khi sửa mã. Tiến độ triển khai và kết quả kiểm chứng mới được cập nhật ở mục 7. Chưa có toàn bộ log, SHA của run lỗi, quyền đọc secrets hay lần chạy lại trên GitHub Actions. Các kết luận về mã áp dụng cho checkout được kiểm tra; cần đối chiếu SHA để xác nhận với run đã thất bại. Tên job trong log khác tên hiện tại là thêm lý do phải kiểm tra SHA. Kiến trúc đúng là `x86_64`; cách ghi `x68_64` trong mô tả không phải bằng chứng lỗi target.

## 1. Phân loại sự cố

| ID | Nền tảng / bước lỗi | Nhận định | Độ chắc chắn | Ưu tiên |
| --- | --- | --- | --- | --- |
| QA-01 | Windows, smoke packaged sidecar | File profile Chromium còn bị giữ khi thư mục tạm bị xóa | Log xác nhận file bị khóa; tiến trình giữ handle chưa được xác định | P0 |
| QA-02 | macOS ARM64, ký updater | Private key không giải mã được với cấu hình đầu vào | Log xác nhận lỗi decode; chưa phân biệt key hỏng và password sai | P0 |
| QA-03 | Linux x86_64, ký updater | Cùng loại lỗi với QA-02, khả năng cao cùng cấu hình secrets | Cao về loại lỗi, chưa xác nhận secrets thực tế | P0 |
| QA-04 | Preflight và diagnostics | Kiểm tra signing quá nông; lỗi cleanup có thể mất log chẩn đoán | Xác nhận từ mã hiện tại | P1 |

## 2. QA-01 — Windows: WinError 32 khi cleanup

### Bằng chứng và chuỗi thực thi

Log chỉ rõ file `output/tft-export-…/profile/Default/Account Web Data` đang được tiến trình khác sử dụng. Đây là đường dẫn profile mà exporter truyền cho Chromium qua `--user-data-dir`, không phải file JSON dữ liệu trận đấu đang mở trong IDE.

Các điểm liên quan trong mã:

- `scripts/smoke_sidecar.py`, `run_smoke()`: tạo `TemporaryDirectory(prefix="tft-smoke-")`; gọi `/api/render`, kiểm tra HTML/assets rồi in `PASS` ngay trong khối `try`. Shutdown và xóa thư mục tạm xảy ra sau thông báo này.
- `src/tft_studio/service/controller.py`, `_compile_locked()`: render HTML kích hoạt worker xuất PNG nền; API render thành công không bảo đảm xuất PNG đã xong.
- `src/tft_studio/render/exporter.py`, `export_html_to_png()`: tạo thư mục `tft-export-*` dưới output, khởi chạy browser bằng `subprocess.run(..., timeout=30)`, dùng profile riêng và cleanup khi thoát context manager.
- `controller.py`, `close()`: worker là daemon thread và chỉ được `join(timeout=5)`. Khoảng chờ này ngắn hơn timeout browser 30 giây; hàm không xác nhận worker đã dừng.
- Smoke chờ tiến trình sidecar tối đa 10 giây; `kill_process_tree()` bỏ qua xử lý khi tiến trình cha đã thoát. Do đó không bảo đảm xử lý được browser con còn sống sau khi cha kết thúc.

**Nguyên nhân cơ chế:** cleanup gặp một file còn mở trên Windows. Python ghi nhận `TemporaryDirectory` có thể phát sinh `PermissionError` khi xóa file đang mở trên Windows. [Tài liệu Python 3.11](https://docs.python.org/3.11/library/tempfile.html).

**Giả thuyết nguyên nhân gốc có bằng chứng mạnh:** shutdown diễn ra khi PNG exporter/browser chưa kết thúc hoặc browser con chưa nhả profile. Chênh lệch timeout và thiếu quản lý đầy đủ tiến trình con tạo điều kiện xảy ra race này. Cần log PID, worker và handle để kết luận tiến trình cụ thể; không thể chỉ từ tên file khẳng định Chrome, Edge hay phần mềm quét file nào đang giữ nó.

Thông báo `PASS` chỉ chứng minh các assertion HTTP trước đó đã qua. Ngoại lệ khi thoát `TemporaryDirectory` vẫn khiến `main()` trả exit code 1; `release_tools.py` truyền lỗi subprocess lên và chặn release đúng thiết kế. Thứ tự `FAIL`/`PASS` trong log còn có thể chịu ảnh hưởng buffering giữa stderr/stdout.

### Giải pháp đề xuất

1. **Sửa ở exporter và shutdown trước:** quản lý browser bằng handle tiến trình được lưu lại; khi đóng ứng dụng, ngừng nhận export mới, hủy hoặc chờ export đang chạy trong thời hạn hữu hạn, kết thúc và chờ toàn bộ browser thuộc lần export đó. Sau đó mới xóa profile và thoát sidecar. Trên Windows cân nhắc Job Object với vòng đời được quản lý rõ ràng; trên POSIX cân nhắc process group/session riêng. Không chỉ chờ PID cha.
2. Đồng bộ timeout: cho phép browser hoàn tất trong ngân sách export, hoặc chủ động hủy nó trước thời hạn shutdown. Nếu hết thời gian chờ worker phải ghi nhận lỗi và thực hiện fallback; không tiếp tục như đã đóng sạch.
3. **Cleanup có retry giới hạn:** sau khi đã dừng tiến trình, retry riêng lỗi khóa file tạm thời, ví dụ backoff 0,1 / 0,2 / 0,4 / 0,8 / 1,6 giây. Nếu vẫn lỗi, lưu diagnostics và giữ exit code thất bại. Retry không thay thế quản lý tiến trình.
4. Chỉ in kết quả `PASS` tổng thể sau shutdown và cleanup thành công; có thể in riêng kết quả `HTTP/render checks passed` trước đó. Kiểm tra exit code sidecar sau shutdown để tránh coi crash là thành công.
5. Đặt cơ chế bắt lỗi cleanup ở ngoài context manager, hoặc cleanup tường minh trong luồng được bắt lỗi. Lưu log bền vững trước khi xóa thư mục tạm. Hiện `except` nằm bên trong context manager nên lỗi khi context manager thoát không đi qua `save_diagnostics()` đó; bước upload artifact có thể không có dữ liệu hữu ích.

Không dùng `continue-on-error`, `ignore_cleanup_errors=True` hoặc tăng startup timeout từ 45 giây như bản sửa chính. Bỏ qua cleanup sẽ che lỗi vòng đời; startup vốn đã thành công trong 1,62 giây. Không kill toàn bộ `chrome.exe`/`msedge.exe`; chỉ xử lý tiến trình do bài kiểm tra tạo ra.

## 3. QA-02 và QA-03 — macOS/Linux: updater key decode thất bại

### Nguyên nhân và giới hạn kết luận

Hai nền tảng báo cùng lỗi:

```text
failed to decode secret key:
incorrect updater private key password: failed to fill whole buffer
```

Trong `.github/workflows/release.yml`, cả ba target nhận cùng hai secrets tại bước `tauri-action`:

```yaml
TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}
```

`src-tauri/tauri.conf.json` bật `bundle.createUpdaterArtifacts: true`. Vì vậy build cần khóa ký updater hợp lệ. Đây là cơ chế ký bản cập nhật Tauri, tách biệt với chứng thư Apple/notarization hoặc Windows Authenticode. [Tài liệu updater Tauri](https://v2.tauri.app/es/plugin/updater/).

Các khả năng cần kiểm tra theo thứ tự:

| Khả năng | Cách phân biệt |
| --- | --- |
| Secret key bị thiếu byte, cắt ngắn, copy sai hoặc encode sai | So sánh với file khóa gốc trong môi trường tin cậy; thử ký một file nhỏ bằng chính khóa đó |
| Nhầm public key, chuỗi mẫu hoặc đường dẫn máy cá nhân thành private key | Kiểm tra nguồn file và loại khóa; đường dẫn local không tồn tại trên hosted runner |
| Password không khớp, bị thêm dấu nháy/khoảng trắng/newline, hoặc key có mật khẩu nhưng secret password rỗng | Thử đúng cặp key/password gốc, không tự trim hay thay đổi password |
| Secret đặt ở scope/environment khác với job build | Kiểm tra repository/organization access và environment; build hiện không gắn `release-production`, chỉ job publish gắn environment đó |

`failed to fill whole buffer` là dấu hiệu đáng kiểm tra dữ liệu khóa không đầy đủ/không đúng cấu trúc; không đủ bằng chứng để kết luận password chắc chắn sai. Public key không khớp thường được phát hiện khi verify chữ ký, không giải thích trực tiếp lỗi decode này.

`scripts/release_tools.py`, `preflight()` hiện chỉ kiểm tra private key không rỗng. Nó chưa thử giải mã, chưa kiểm tra password và chưa chứng minh private key tương ứng với public key cấu hình. Đây là lý do lỗi có thể chỉ xuất hiện sau các bước build tốn thời gian.

Windows dừng ở smoke test trước bước Tauri signing, nên chưa có bằng chứng Windows ký thành công; sau khi sửa QA-01 có thể lộ cùng lỗi secrets.

### Quy trình khắc phục

1. Người quản trị đối chiếu khóa gốc, password và scope secrets. Cập nhật secret bằng nội dung nguyên vẹn của private key do Tauri tạo, giữ đúng định dạng; không thêm lớp base64 tùy ý, dấu nháy hoặc chuỗi escape. Nếu dùng đường dẫn thì phải tạo file khóa thật trên runner và truyền đúng cơ chế hỗ trợ.
2. Với khóa không đặt password, truyền chuỗi rỗng đúng chủ đích; với khóa có password, dùng chính xác password đó. Không yêu cầu secret password bắt buộc khác rỗng cho mọi trường hợp.
3. Thử ký file nhỏ với cùng CLI được cài từ lockfile. Checkout hiện khóa `@tauri-apps/cli` ở `2.12.3` và dùng `npm ci`; không cần nâng CLI để chữa lỗi khi chưa có bằng chứng về phiên bản. Xem `npm run tauri -- signer sign --help` của phiên bản thực tế trước khi tự động hóa.
4. Verify chữ ký thử bằng `plugins.updater.pubkey` của **commit release**, dùng cách giải mã chữ ký/public key và `minisign` như `verify_signature()` hiện có. Ký thành công nhưng verify thất bại nghĩa là keypair không khớp và vẫn phải chặn release.
5. Đưa bài kiểm tra ký/verify nhỏ vào preflight trước CI/build matrix. Cấp cả hai biến secrets cho bước này, cài Node + `npm ci` và verifier cần thiết. Chỉ ghi trạng thái tổng quát; không in key/password, nội dung khóa đã giải mã hoặc đưa chúng vào artifact. Dùng biến môi trường thay vì nhúng secret vào chuỗi shell.

Lệnh tham khảo cho preflight sau khi đã nạp secrets vào môi trường và tạo file probe không nhạy cảm:

```sh
npm ci
npm run tauri -- --version
npm run tauri -- signer sign signing-probe.txt
```

Đây mới là nửa ký; phải bổ sung verify với public key cấu hình để hoàn tất gate. Tauri CLI có hỗ trợ đầu vào private key/password qua biến môi trường; cần đối chiếu help bản cài thực tế. [Tài liệu Tauri CLI](https://v2.tauri.app/reference/cli/).

Ưu tiên phục hồi keypair đang dùng. Nếu khóa mất/hỏng và buộc tạo keypair mới, phải đánh giá đường chuyển tiếp updater cho bản đã cài: client cũ đang tin public key cũ sẽ không tự tin khóa mới. Không chỉ thay pubkey rồi phát hành và coi tương thích cập nhật đã được bảo đảm.

## 4. Thiết kế CI/CD sau khắc phục

Luồng đề xuất:

```text
Validate tag/SHA/version + signing probe/verify
  → CI trên SHA release
  → draft release
  → native build + smoke + ký cho từng target
  → verify toàn bộ chữ ký + latest.json + SHA256SUMS
  → publish qua gate hiện có
```

Giữ các kiểm soát đang đúng: build native từng kiến trúc, `fail-fast: false` để thu đủ lỗi matrix, draft trước publish, verify chữ ký từng bundle và chỉ publish sau khi verify thành công. Không tắt `createUpdaterArtifacts` để biến build đỏ thành xanh.

Các cải tiến có tác dụng trực tiếp:

- Thêm packaged smoke test thực trên Windows vào CI PR; hiện sidecar dry-run chạy Linux còn Windows chủ yếu `cargo check`. Test mock hiện có không chứng minh browser trên Windows nhả file profile.
- Xuất diagnostics cho cả startup, render, shutdown và cleanup: phase, exit code, worker còn sống, browser PID/PPID, thời gian chờ và đường dẫn tương đối bị khóa. Không upload toàn bộ browser profile.
- Giữ cache dependencies hiện có; không cache private key, profile browser hoặc output test tạm. Kiểm tra signing sớm tiết kiệm nhiều thời gian hơn việc retry toàn bộ build.
- Log thời lượng từng phase riêng để phân biệt ứng dụng chậm, browser chưa dừng và filesystem chưa nhả handle.

## 5. Kế hoạch QA và tiêu chí nghiệm thu

Các ca sau là **đề xuất cần chạy**, chưa phải kết quả đã đạt:

| Ca kiểm tra | Thực hiện | Điều kiện đạt |
| --- | --- | --- |
| WIN-01 | Packaged sidecar render rồi shutdown ngay, lặp ít nhất 10 lần trên Windows runner | Mọi lần exit 0, không WinError 32, không còn browser do test tạo, thư mục tạm được xóa |
| WIN-02 | Cho export chạy chậm rồi shutdown | Worker/browser kết thúc hoặc bị hủy có kiểm soát trước cleanup; không orphan |
| WIN-03 | Giữ file profile mở trong kiểm thử có chủ đích | Retry hữu hạn, lỗi cuối được báo đúng phase và có diagnostics; không PASS tổng thể |
| WIN-04 | Browser timeout hoặc sidecar crash | Dừng cây tiến trình thuộc test, giữ nguyên nguyên nhân lỗi chính, không treo job |
| SIGN-01 | Đúng private key, đúng password và đúng public key | Probe ký/verify thành công trước matrix |
| SIGN-02 | Password sai, key bị cắt hoặc thiếu key | Preflight thất bại trước build native, không lộ secrets |
| SIGN-03 | Private key hợp lệ nhưng thuộc keypair khác | Ký được nhưng verify thất bại; chặn release |
| SIGN-04 | Key không password với biến password rỗng | Probe thành công khi keypair đúng |
| REL-01 | Build đủ Windows/macOS/Linux | Bundle và `.sig` đủ ba platform, mọi chữ ký verify được; manifest/checksum được tạo |
| REL-02 | Cố ý làm một target thất bại | Release vẫn draft, publish không chạy |
| REL-03 | Kiểm tra cập nhật từ bản đang được hỗ trợ | Client tải đúng artifact và chấp nhận chữ ký; cài/chạy bản mới thành công |

Sau sửa mã, chạy các unit test liên quan `test_smoke_sidecar.py`, `test_export_service.py`, `test_release_tools.py`, test publication guards và workflow validation. Bổ sung test cho cleanup failure, worker timeout và sai keypair; không chỉ kiểm tra mock có gọi `taskkill`. Unit test cần đi cùng packaged smoke trên runner thật.

## 6. Thứ tự xử lý và phát hành lại

| Thứ tự | Công việc | Phụ trách đề xuất | Bằng chứng hoàn tất |
| --- | --- | --- | --- |
| 1 | Xác định tag/SHA run lỗi, lưu diagnostics, đối chiếu secrets | Release maintainer | Có commit và cấu hình signing xác định |
| 2 | Sửa key/password và thêm signing probe/verify sớm | Release maintainer | SIGN-01 đến SIGN-04 đạt |
| 3 | Sửa vòng đời exporter/shutdown và cleanup diagnostics | Backend maintainer | WIN-01 đến WIN-04 đạt |
| 4 | Thêm Windows packaged smoke vào CI | CI maintainer | PR checks bắt được lỗi hồi quy |
| 5 | Chạy lại đủ matrix, verify rồi publish | Release maintainer | REL-01 đến REL-03 đạt, artifact đúng SHA |

Nếu chỉ thay secrets, có thể chạy lại run/tag cũ chưa publish sau khi xác nhận draft đúng SHA. Nếu sửa mã, cần commit mới và release tag/version mới nhất quán theo guard hiện tại; không di chuyển tag cũ để âm thầm thay nội dung. Guard kiểm tra SHA/tag và marker của draft có thể chặn việc này. Draft/assets từ lần lỗi chỉ được tái sử dụng sau khi xác nhận cùng commit; không ghép artifact từ nhiều SHA.

**Trạng thái đánh giá ban đầu: BLOCKED.** Kết quả sau triển khai được ghi bên dưới; chưa xác minh secrets sản xuất hoặc thực hiện release đa nền tảng.

## 7. Cập nhật triển khai — 22/10/2026

### Các thay đổi đã thực hiện

- Thêm `core/processes.py`: quản lý cây tiến trình bằng Windows Job Object; khởi chạy tiến trình ở trạng thái suspended, gán vào job rồi resume để browser không kịp sinh tiến trình con ngoài phạm vi quản lý. Khi đóng job, descendants vẫn bị thu hồi dù PID cha đã thoát. Trên POSIX dùng session/process group riêng. Cơ chế kill-on-close dựa trên [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
- Exporter đóng cây browser trước khi kiểm tra/xóa profile. Thêm retry hữu hạn cho lỗi quyền truy cập tạm thời; lỗi cleanup cuối vẫn được báo, không bỏ qua.
- Controller khóa đồng bộ với render khi bắt đầu đóng, chờ worker tối đa 40 giây và báo lỗi nếu worker chưa dừng. Browser có timeout 30 giây; smoke dành tối đa 50 giây cho sidecar shutdown.
- Smoke chỉ in `PASS` sau shutdown và cleanup; yêu cầu exit code shutdown bằng 0. Diagnostics được lưu trước khi xóa thư mục và ghi phase/error khi cleanup thất bại. Cơ chế quản lý cây tiến trình cũ chỉ dựa trên PID cha đã được thay thế.
- Thêm `release_tools.py signing-probe --ref <commit>`: ký file thử bằng CLI trong lockfile và verify với public key của commit release. Output signer được giữ kín khi lỗi; secrets không đi vào tham số command.
- Job `prepare` cài CLI theo lockfile của SHA release và chạy signing probe trước CI/matrix. Guard vẫn lấy từ `main`; probe đọc public key từ commit release, không giả định key trên `main` là key của tag.
- CI chạy kiểm thử ký thật với key thử dùng một lần; Windows CI chạy smoke binary đóng gói trước `cargo check`.
- README hai ngôn ngữ đã bổ sung scope secrets, cách chạy probe, quy trình draft/verify/publish và đúng danh sách ba nền tảng đang hỗ trợ.

### Kết quả kiểm chứng tại máy local

Môi trường: Windows x64, Python 3.14.6; runner CI khai báo Python 3.11. Không coi kết quả local là thay thế cho matrix hosted runners.

| Kiểm tra | Kết quả |
| --- | --- |
| `ruff check .` | PASS |
| Actionlint trên workflows | PASS |
| Toàn bộ unit/security tests, có Minisign và CLI thật trong PATH | **144 passed**, một cảnh báo deprecation có sẵn của Starlette/httpx |
| Trong đó 5 ca signing thật | PASS: password đúng, password rỗng, từ chối password sai, key bị cắt và keypair không khớp |
| Node publication guards | **7 passed** |
| Sidecar từ source, browser thật trên Windows | PASS: startup 4,56 giây; render 0,87 giây; shutdown 3,02 giây; cleanup thành công |
| Build sidecar Windows bằng `scripts/build_sidecar.py` | PASS: binary x86_64 được xác minh, dung lượng 79,54 MB |
| Smoke binary Windows mới build, lặp 10 lần với browser thật | **10/10 PASS**, exit code 0; startup 10,03–22,50 giây, shutdown 2,31–6,49 giây; không gặp WinError 32, cleanup thành công |
| Tiến trình con giữ file `Account Web Data` sau khi PID cha thoát | PASS: file bị khóa trước khi đóng job, xóa được sau khi thu hồi descendants |
| Cleanup thất bại và sidecar shutdown exit khác 0 | PASS: không in `PASS` tổng thể; cleanup có diagnostics đúng phase và lỗi |

Một lần pytest đầu bị sandbox chặn thư mục Temp; các kết quả trên là từ lần chạy lại được cấp quyền truy cập phù hợp. Không thay đổi secrets để chạy test: tất cả key dùng trong kiểm thử ký là key thử tạm thời.

Diagnostics local nằm ở `scratch/smoke-logs-local/` và `scratch/smoke-logs-packaged-1/` đến `scratch/smoke-logs-packaged-10/` (được gitignore). Bộ icon mà script build tự sinh lại đã được hoàn nguyên; binary local vẫn nằm trong `src-tauri/binaries/`, không đưa vào thay đổi mã nguồn. Chưa build bộ cài Tauri hoặc chạy runner macOS/Linux trong phiên này.

### Phần cần hoàn tất trên GitHub

1. Maintainer kiểm tra/cập nhật đúng hai repository secrets bằng keypair gốc. Hiện chưa có quyền xác minh hoặc sửa secrets sản xuất, nên chưa thể tuyên bố lỗi ký của run cũ đã hết.
2. Commit thay đổi vào nhánh phù hợp, đồng bộ version/tag mới và chạy workflow trên SHA đó.
3. Kiểm tra đủ ba hosted runners, artifacts/chữ ký/manifest và thử cập nhật từ client cũ trước khi publish qua gate hiện có.

**Trạng thái sau sửa mã: các kiểm tra local nêu trên đã đạt; release vẫn chờ xác nhận secrets và workflow đa nền tảng.**
