# Đưa thay đổi lên GitHub và phát hành

## Trạng thái đã kiểm tra ngày 22/10/2026

- Checkout hiện tại: `main`, commit `6381ec0d4b5c720eeb71e269c4832736034eb2cc`.
- `main` local và `origin/main` trên GitHub cùng commit tại thời điểm kiểm tra.
- Remote: `https://github.com/triphung-git/piggy`.
- GitHub đã có các tag `v1.0.0`, `v1.0.1` và `v1.0.2` (trỏ commit `6381ec0`).
- Phiên bản phát hành tiếp theo: **`1.0.3`** (tag `v1.0.3`), hoàn toàn trống trên cả remote lẫn local.
- Manifests trong checkout hiện đang là `1.0.2` và sẽ được đồng bộ lên `1.0.3` theo Gate G6 sau khi hoàn tất kiểm thử và đóng gói.

Không thể đảm bảo không phát sinh conflict khi có người khác sửa cùng dòng. Quy trình dưới đây giúp phát hiện conflict trên nhánh làm việc trước khi merge vào `main`.

## 1. Tạo nhánh riêng từ checkout đang có thay đổi

Chạy trong thư mục gốc dự án bằng PowerShell:

```powershell
git status --short --branch
git switch -c codex/qa-release-hardening
git diff --check
git diff --stat
git add -A
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "fix: restore overlay runtime and harden release pipeline"
```

`git switch -c` giữ các thay đổi chưa commit hiện tại trên nhánh mới. Bước `git add -A` cũng lấy các module/test/template mới, tránh thiếu file khi GitHub checkout sạch. Trước khi commit, kiểm tra danh sách staged để chắc chắn có các file mới cần thiết và không có thông tin cá nhân. `.env`, `scratch/`, `node_modules/`, output và private key `.key` đã có quy tắc ignore; không dùng `git add -f` cho các file này.

Nếu tên nhánh đã tồn tại, chọn tên mới như `codex/qa-release-hardening-v2` rồi dùng đúng tên đó trong lệnh push/PR.

## 2. Đồng bộ `main` mới nhất vào nhánh làm việc

Sau khi đã commit và working tree sạch:

```powershell
git fetch origin
git merge origin/main
```

Nếu không có thay đổi mới trên `main`, Git báo đã cập nhật. Nếu có thay đổi mới, merge sẽ đưa chúng vào nhánh làm việc. Cách này phù hợp cả khi nhánh đã được chia sẻ, vì không viết lại các commit đã push.

Nếu có conflict:

1. Chạy `git status` để xem các file chưa giải quyết.
2. Mở từng file, chọn nội dung đúng và xóa marker `<<<<<<<`, `=======`, `>>>>>>>`. Đọc cả hai thay đổi để giữ logic cần thiết; với lockfile, giải quyết `package.json` trước rồi tạo lại lockfile bằng npm tương ứng.
3. Chạy lại các kiểm tra bên dưới.
4. Stage file đã sửa bằng `git add -A`, kiểm tra `git diff --cached --check` và `git diff --cached`, rồi `git commit` để hoàn tất merge.

Nếu muốn quay về trạng thái trước lần merge đang xung đột, dùng `git merge --abort`. Không dùng force push hoặc reset `main` để xử lý conflict.

## 3. Kiểm tra và push nhánh

```powershell
$env:TFT_APPDATA_DIR = Join-Path $PWD 'scratch/pre-push-appdata'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp scratch/pre-push-tests
.\.venv\Scripts\ruff.exe check .
node --test tests/release_github.test.cjs
npm run build
git diff --check
git status --short --branch
git push -u origin codex/qa-release-hardening
```

Nếu dùng Python đã cài trực tiếp thay vì `.venv`, thay đường dẫn executable bằng `python` và cài dependencies/dev tools phù hợp.

Mở Pull Request trên GitHub với **base = `main`**, **compare = `codex/qa-release-hardening`**. Đợi CI đạt, review diff, rồi merge bằng **Squash and merge** hoặc chính sách của repository. Nếu `main` thay đổi trong lúc PR đang chờ, lặp lại `fetch` → `merge origin/main` → test → commit nếu cần → push cùng nhánh.

Khuyến nghị bật ruleset/protection cho `main`: yêu cầu PR, status checks bắt buộc và nhánh được cập nhật trước khi merge; chặn force push. Các check của workflow CI gồm workflow validation, Python lint/tests, frontend build/release-guard tests, sidecar packaging và Windows Tauri compilation. Các thiết lập GitHub này cần được cấu hình trong repository; sửa YAML không tự bật branch protection.

## 4. Quy trình Release đã được sửa

```text
Tag hoặc workflow_dispatch(tag)
  → preflight: tag nằm trên lịch sử main, version khớp, endpoint đúng, có signing key
  → gọi CI trên chính SHA của tag
  → tạo hoặc tiếp tục draft gắn với SHA đó
  → build Windows x64 / macOS ARM64 / Linux x64, smoke sidecar trên từng runner
  → tải bundles + signatures từ draft
  → Minisign xác minh bằng pubkey cấu hình
  → một job tạo latest.json đủ ba nền tảng
  → kiểm tra tag không bị đổi và publish
```

Các lỗi đã sửa:

- Bỏ heredoc sai indentation khiến YAML không hợp lệ.
- Release chờ toàn bộ CI của đúng release commit, thay vì chỉ dựa vào việc có tag.
- Tag phải là SemVer và commit phải thuộc `origin/main`; chạy thủ công phải chọn workflow branch `main` và nhập tag đã tồn tại.
- Tauri/Cargo/Python/npm manifests và hai npm lockfile phải cùng version với tag.
- Thiếu private signing key làm workflow fail sớm, thay vì âm thầm tắt updater artifacts.
- Chỉ một job tạo `latest.json`, sau khi tất cả nền tảng build thành công; tránh nhiều job cùng ghi manifest.
- Xác minh chữ ký thực tế, phát hiện private/public key không khớp hoặc installer bị thay đổi trước khi publish.
- Không ghi đè release đã publish; draft của commit khác cũng bị chặn. Tag bị di chuyển sau validation sẽ không được publish.
- Quyền mặc định chỉ đọc; các job tạo/upload/publish release mới có `contents: write`.
- Cố định runner macOS 15 và Python ARM64, kiểm tra kiến trúc sidecar khớp runner.
- CI có `actionlint` để chặn lỗi workflow tương tự trong các PR sau.

## 5. Cấu hình secrets trước lần Release đầu tiên

Vào GitHub repository → **Settings → Secrets and variables → Actions**:

- `TAURI_SIGNING_PRIVATE_KEY`: nội dung private key tương ứng với `plugins.updater.pubkey` hiện có trong `src-tauri/tauri.conf.json`.
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`: mật khẩu nếu private key được mã hóa; key không có mật khẩu có thể để trống.

`GITHUB_TOKEN` do GitHub cấp tự động; workflow yêu cầu `contents: write` ở các job xuất bản. Repository/organization vẫn phải cho phép quyền và actions mà workflow sử dụng.

Giữ private key hiện có để các bản ứng dụng đã cài tiếp tục xác minh được bản cập nhật. Việc đổi key cần kế hoạch migration riêng. Updater signature khác với Windows Authenticode hoặc Apple signing/notarization; workflow này không tự cấu hình certificate của hai hệ điều hành đó.

## 6. Tạo phiên bản mới bằng PR trước khi tạo tag

Sau khi PR sửa lỗi đã merge:

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/release-1.0.2
npm version 1.0.2 --no-git-tag-version
Push-Location 'Web Overlay'
npm version 1.0.2 --no-git-tag-version
Pop-Location
```

Sửa thêm `version` thành `1.0.2` tại:

- `src-tauri/tauri.conf.json`
- `[package].version` trong `src-tauri/Cargo.toml`
- `[project].version` trong `pyproject.toml`

Hai lệnh npm cập nhật `package.json` và `package-lock.json` ở root/frontend. Nếu đã có `src-tauri/Cargo.lock` được theo dõi trong tương lai, cập nhật lockfile bằng Cargo khi đổi version.

Kiểm tra rồi commit/push nhánh version:

```powershell
.\.venv\Scripts\python.exe scripts/release_tools.py check-version --tag v1.0.2 --repository triphung-git/piggy
git add -A
git diff --cached
git commit -m "chore: prepare release 1.0.2"
git fetch origin
git merge origin/main
git push -u origin codex/release-1.0.2
```

Mở PR thứ hai vào `main`, đợi CI đạt và merge. Sau đó tạo tag từ `main` đã cập nhật:

```powershell
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe scripts/release_tools.py check-version --tag v1.0.2 --repository triphung-git/piggy
git tag -a v1.0.2 -m "TFT Post-Match Studio 1.0.2"
git push origin v1.0.2
```

Chỉ push đúng tag cần phát hành. Tag `v1.0.0` và `v1.0.1` đã tồn tại; không xóa/di chuyển chúng để tái sử dụng version. Nếu chọn version mới hơn `1.0.2`, thay đồng nhất version/tag/tên nhánh trong các bước trên.

## 7. Khi Release thất bại

- Lỗi preflight: đọc tên manifest, tag hoặc secret được báo; sửa qua PR và dùng tag/version mới nếu code thay đổi.
- Build một nền tảng lỗi: release giữ draft, không có bước publish. Có thể rerun failed jobs sau khi sửa môi trường/secrets nếu SHA không đổi.
- Chữ ký không khớp: đối chiếu private key/password với public key đang phân phối; không bỏ bước verify để phát hành.
- Nếu cần chạy thủ công: Actions → Release → Run workflow → chọn **main**, nhập tag đã tồn tại. Chỉ draft có marker SHA đúng mới được tiếp tục; release đã publish bị chặn.
- Nếu đổi mã sau lần thất bại, dùng PR và version/tag mới. Tag cũ không được force-push.

## Kết quả kiểm tra và giới hạn

Đã kiểm tra YAML và actionlint: đạt. Bộ test Python: **111 passed**, 1 cảnh báo deprecation Starlette/httpx. Bộ test Node bảo vệ xuất bản release: **6 passed**. Đã ký file mẫu bằng Tauri CLI rồi xác minh bằng Minisign thực: trường hợp hợp lệ tạo manifest đủ ba nền tảng; file bị sửa hoặc public key khác đều bị từ chối. Khóa dùng cho kiểm tra là khóa QA tạm trong `scratch`, không phải secret repository.

Build/installers của ba runner GitHub và secrets thật chưa được chạy/xác minh từ máy local; lượt chạy GitHub sau PR/tag mới là bằng chứng cho các phần đó. Máy local hiện thiếu Cargo nên chưa nghiệm thu Rust/native. Native build và các guard có thể fail để chỉ rõ vấn đề còn lại; không cam kết workflow sẽ xanh trước khi thực sự chạy trên GitHub.

Tham chiếu: [reusable workflows của GitHub](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows), [Tauri updater và định dạng bundle/signature](https://v2.tauri.app/plugin/updater/), [Minisign verifier](https://jedisct1.github.io/minisign/), [runner labels của GitHub](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
