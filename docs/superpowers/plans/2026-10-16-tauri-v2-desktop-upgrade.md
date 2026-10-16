# Tauri v2 Desktop & Auto-Update Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `triphung-git/piggy` (TFT Post-Match Studio) from a Windows-only PyWebView wrapper into a cross-platform desktop application (Windows x64, macOS Apple Silicon/Intel, Linux x64) using Tauri v2, Python FastAPI Sidecar (`--onefile`), user-confirmed auto-updates via GitHub Releases, and GitHub Actions CI/CD.

**Architecture:** A Rust-based Tauri v2 shell orchestrates the application lifecycle and sidecar process (`tft-backend`). The backend retains its full FastAPI and WebSocket stack at `http://127.0.0.1:8080` to preserve 100% compatibility with OBS Studio Browser Source (`/overlay`, `/ws/overlay`). Read-only assets (`templates/`, `assets/`, `TFT_DDragon/`) are distributed via Tauri `bundle.resources`, while writable data (`.env`, `overlay_config.json`, `output/`, `logs/`) is strictly isolated inside the OS-standard `TFT_APPDATA_DIR`.

**Tech Stack:** Tauri v2, Rust 2021, Python 3.11+, FastAPI, Uvicorn, PyInstaller, React 19, TypeScript 5.7+, Tailwind CSS v4, Vite 8, `@tauri-apps/plugin-updater`, `@tauri-apps/plugin-process`, `@tauri-apps/plugin-opener`, `html-to-image`.

**Spec:** `AGENTS.md`, `architecture.md`, `architecture_essential.md`, `product.md`.

## Global Constraints

- **OBS Compatibility:** Do NOT replace FastAPI/Uvicorn HTTP & WebSocket (`src/tft_studio/api/hub.py`) with stdin/stdout. OBS Studio Browser Source connects to `http://127.0.0.1:8080/overlay` and `ws://127.0.0.1:8080/ws/overlay`.
- **Rust Sidecar Lifecycle:** Sidecar `tft-backend` must be spawned exactly once by the Tauri Rust process on startup and terminated cleanly on exit or prior to `update.downloadAndInstall()`.
- **Resource Bundling:** Do NOT bundle `TFT_DDragon/`, `assets/`, or `templates/` inside the PyInstaller `--onefile` binary. Declare them in `bundle.resources` in `src-tauri/tauri.conf.json`.
- **Directory Isolation:** Strict separation of `TFT_RESOURCE_DIR` (Read-Only) and `TFT_APPDATA_DIR` (Read-Write).
- **User-Confirmed Updates:** Updates must display a confirmation dialog with release notes, "Cập nhật ngay" and "Để sau" buttons. No silent background auto-restarts.
- **Cross-Platform Security:** No Windows-specific hardcoded paths (`C:\Program Files\...`, `ctypes.windll`, `os.startfile`) without OS branching.
- **No Placeholders:** All code, error handling, and test fixtures must be completely implemented.

## Review Focus

1. **Port 8080 Conflict / Orphan Sidecar:** If the app crashes or user quits, sidecar process must not linger holding port 8080.
2. **Update Executable File Lock on Windows:** Calling `update.downloadAndInstall()` while `tft-backend.exe` is running causes Windows error `Access is denied (os error 5)`. Must verify `stop_backend_sidecar` runs and finishes first.
3. **Data Loss on Update:** If user updates, their `.env` (Riot API Key) and `overlay_config.json` in `TFT_APPDATA_DIR` must not be overwritten by bundle defaults.
4. **Headless Chrome Missing on macOS/Linux:** Exporting PNG via `html-to-image` must be the primary high-fidelity path, falling back to system Chromium if needed, so the app works on systems with no Chrome installed.
5. **CORS & Token Security in Tauri Webview:** Tauri origins (`tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`, `http://localhost:5173`) and `X-Studio-Token` must be allowed and enforced on write endpoints.

---

## Phase 1: Python Backend & Sidecar Entrypoint

### Task 1.1: Standardize `src/tft_studio/core/paths.py`

**Files:**
- Modify: `src/tft_studio/core/paths.py`
- Test: `tests/unit/test_paths_and_sidecar.py`

**Interfaces:**
- Produces:
  - `get_appdata_dir() -> Path`
  - `get_resource_dir() -> Path`
  - `ensure_user_config_initialized() -> tuple[Path, Path]`
  - `get_app_dir() -> Path` (points to `get_appdata_dir()`)
  - `get_bundle_dir() -> Path` (points to `get_resource_dir()`)
  - `resolve_resource(relative_path: str | Path) -> Path`

- [ ] **Step 1: Write unit tests in `tests/unit/test_paths_and_sidecar.py` for path resolution and initialization**

```python
import os
from pathlib import Path
import pytest
from tft_studio.core.paths import (
    get_appdata_dir,
    get_resource_dir,
    ensure_user_config_initialized,
    resolve_resource,
)

def test_paths_respect_environment_variables(tmp_path, monkeypatch):
    custom_appdata = tmp_path / "appdata"
    custom_resources = tmp_path / "resources"
    custom_resources.mkdir()
    (custom_resources / "templates").mkdir()
    (custom_resources / "templates" / "overlay.html").write_text("dummy", encoding="utf-8")

    monkeypatch.setenv("TFT_APPDATA_DIR", str(custom_appdata))
    monkeypatch.setenv("TFT_RESOURCE_DIR", str(custom_resources))

    assert get_appdata_dir() == custom_appdata
    assert get_resource_dir() == custom_resources
    assert (custom_appdata / "output").exists()
    assert (custom_appdata / "logs").exists()

    resolved = resolve_resource("templates/overlay.html")
    assert resolved == custom_resources / "templates" / "overlay.html"

def test_ensure_user_config_initialized_copies_defaults_without_overwrite(tmp_path, monkeypatch):
    custom_appdata = tmp_path / "appdata"
    custom_resources = tmp_path / "resources"
    custom_resources.mkdir()
    (custom_resources / ".env.example").write_text("RIOT_API_KEY=DEFAULT_KEY\n", encoding="utf-8")
    (custom_resources / "overlay_config.json").write_text('{"tournament_title":"DEFAULT"}\n', encoding="utf-8")

    monkeypatch.setenv("TFT_APPDATA_DIR", str(custom_appdata))
    monkeypatch.setenv("TFT_RESOURCE_DIR", str(custom_resources))

    env_file, config_file = ensure_user_config_initialized()
    assert env_file.exists()
    assert config_file.exists()
    assert "DEFAULT_KEY" in env_file.read_text(encoding="utf-8")

    # Second run with modified user file must not overwrite
    env_file.write_text("RIOT_API_KEY=USER_CUSTOM_KEY\n", encoding="utf-8")
    ensure_user_config_initialized()
    assert "USER_CUSTOM_KEY" in env_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_paths_and_sidecar.py -v`
Expected: FAIL (missing `get_appdata_dir`, `get_resource_dir`, etc.)

- [ ] **Step 3: Implement `src/tft_studio/core/paths.py`**

Implement OS-specific app data paths (`sys.platform`), environment variable overrides (`TFT_APPDATA_DIR`, `TFT_RESOURCE_DIR`), `ensure_user_config_initialized()`, and backward-compatible wrappers `get_app_dir()` and `get_bundle_dir()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_paths_and_sidecar.py -v`
Expected: PASS

---

### Task 1.2: Update `src/tft_studio/core/config.py` for AppData Storage

**Files:**
- Modify: `src/tft_studio/core/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Consumes: `get_appdata_dir()` from `tft_studio.core.paths`
- Produces: `ENV_PATH`, `OVERLAY_CONFIG_PATH` pointing into `get_appdata_dir()`

- [ ] **Step 1: Check existing `tests/unit/test_config.py` and ensure compatibility**
- [ ] **Step 2: Update `src/tft_studio/core/config.py`**
  - Change `BASE_DIR = get_appdata_dir()`
  - Ensure `ENV_PATH = get_appdata_dir() / ".env"` and `OVERLAY_CONFIG_PATH = get_appdata_dir() / "overlay_config.json"`.
- [ ] **Step 3: Run config tests to verify they pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

---

### Task 1.3: Update `src/tft_studio/api/hub.py` (CORS, Token Auth, Shutdown & Base64 Export)

**Files:**
- Modify: `src/tft_studio/api/hub.py`
- Test: `tests/unit/test_paths_and_sidecar.py`

**Interfaces:**
- Consumes: `STUDIO_SESSION_TOKEN` from env or generated secret
- Produces:
  - Allowed CORS origins: `["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080", "http://127.0.0.1:8080", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]`
  - `POST /api/shutdown`: triggers graceful Uvicorn stop
  - `POST /api/export/base64`: saves decoded Base64 PNG to `get_appdata_dir() / "output" / f"overlay_{timestamp}.png"` and `overlay_latest.png`

- [ ] **Step 1: Add unit tests in `tests/unit/test_paths_and_sidecar.py` for security middleware, shutdown, and base64 export**

```python
import base64
from fastapi.testclient import TestClient
from tft_studio.api.hub import app, get_current_token

def test_hub_cors_and_token_security(monkeypatch):
    monkeypatch.setenv("STUDIO_SESSION_TOKEN", "test-secret-token")
    client = TestClient(app)

    # Valid token write
    res = client.post(
        "/api/config",
        headers={"x-studio-token": "test-secret-token", "origin": "http://tauri.localhost"},
        json={"tournament_title": "Test Title"}
    )
    assert res.status_code == 200

    # Invalid token write
    res_bad = client.post(
        "/api/config",
        headers={"x-studio-token": "wrong-token", "origin": "http://tauri.localhost"},
        json={"tournament_title": "Test Title"}
    )
    assert res_bad.status_code == 403

def test_hub_export_base64(monkeypatch, tmp_path):
    monkeypatch.setenv("TFT_APPDATA_DIR", str(tmp_path))
    monkeypatch.setenv("STUDIO_SESSION_TOKEN", "test-secret-token")
    client = TestClient(app)

    # 1x1 transparent PNG in base64
    sample_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    res = client.post(
        "/api/export/base64",
        headers={"x-studio-token": "test-secret-token"},
        json={"image_base64": f"data:image/png;base64,{sample_png}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert Path(data["file_path"]).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_paths_and_sidecar.py::test_hub_cors_and_token_security -v`
Expected: FAIL

- [ ] **Step 3: Implement updates in `src/tft_studio/api/hub.py`**
  - Update CORS middleware to accept Tauri origins.
  - Check `STUDIO_SESSION_TOKEN` environment variable in `get_current_token()`.
  - Add `POST /api/shutdown`.
  - Add `POST /api/export/base64`.
- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_paths_and_sidecar.py -v`
Expected: PASS

---

### Task 1.4: Update `src/tft_studio/render/exporter.py` for Cross-Platform Chromium

**Files:**
- Modify: `src/tft_studio/render/exporter.py`
- Test: `tests/unit/test_export_service.py`

**Interfaces:**
- Produces: `find_browser_executable() -> str | None` supporting Windows, macOS, Linux.

- [ ] **Step 1: Update `find_browser_executable()` in `src/tft_studio/render/exporter.py`**
  - Windows: `chrome.exe`, `msedge.exe`, `chromium.exe` in Program Files, Program Files (x86), LOCALAPPDATA.
  - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, `/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge`, `/Applications/Chromium.app/Contents/MacOS/Chromium`.
  - Linux: search via `shutil.which` for `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser`, `microsoft-edge`.
- [ ] **Step 2: Run export tests**

Run: `pytest tests/unit/test_export_service.py -v`
Expected: PASS

---

### Task 1.5: Implement `src/tft_studio/main_sidecar.py`

**Files:**
- Create: `src/tft_studio/main_sidecar.py`

**Interfaces:**
- Produces: Executable entrypoint that redirects logs to `sys.stderr` and `get_appdata_dir() / "logs" / "studio.log"`, ensures config initialization, starts Uvicorn, and prints `{"event": "server_ready", "port": 8080, "status": "ok"}` on `sys.stdout`.

- [ ] **Step 1: Write `src/tft_studio/main_sidecar.py`**
  - Set `sys.stdout.reconfigure(encoding="utf-8")` and `sys.stderr.reconfigure(encoding="utf-8")`.
  - Configure `logging.handlers.RotatingFileHandler` writing to `get_appdata_dir() / "logs" / "studio.log"`.
  - Initialize configs via `ensure_user_config_initialized()`.
  - Start FastAPI via `uvicorn.Server` and flush `{"event": "server_ready", "port": port, "status": "ok"}` when server is listening.
- [ ] **Step 2: Verify by dry-running `python src/tft_studio/main_sidecar.py --help` or testing process execution**

---

### Task 1.6: Implement `scripts/build_sidecar.py`

**Files:**
- Create: `scripts/build_sidecar.py`

**Interfaces:**
- Produces: `src-tauri/binaries/tft-backend-<target-triple>[.exe]` and `src-tauri/icons/`.

- [ ] **Step 1: Write `scripts/build_sidecar.py`**
  - Automatic target triple discovery via `rustc -vV` with fallback to `platform.system()` & `platform.machine()` if rustc is not in PATH.
  - Generate `.ico` and `.png` icons in `src-tauri/icons/` from `assets/Logo NEC.png` using Pillow.
  - Execute PyInstaller with `--onefile --clean`, collect hidden imports (`uvicorn`, `fastapi`, `starlette`, `websockets`, `requests`, `PIL`, `dotenv`, `tft_studio`), exclude unused packages (`webview`, `tkinter`, `numpy`, `pandas`, `matplotlib`), without bundling data files.
  - Place binary in `src-tauri/binaries/tft-backend-<target-triple>[.exe]`.
  - Set permissions (`chmod 0o755`) on Unix.
- [ ] **Step 2: Test building the sidecar binary**

Run: `python scripts/build_sidecar.py`
Expected: Successfully generates `src-tauri/binaries/tft-backend-<target-triple>.exe`

---

## Phase 2: Tauri v2 Shell & Rust Process Manager

### Task 2.1: Tauri v2 Configuration & Manifest Files

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/capabilities/default.json`
- Create: `src-tauri/build.rs`

**Interfaces:**
- Produces:
  - App ID: `com.triphung.tftstudio`
  - Binary external: `binaries/tft-backend`
  - Resources: `templates`, `assets`, `TFT_DDragon`, `overlay_config.json`, `.env.example`
  - Updater endpoints: `https://github.com/triphung-git/piggy/releases/latest/download/latest.json`
  - Minimum necessary permissions in `capabilities/default.json`.

- [ ] **Step 1: Create `src-tauri/Cargo.toml` with dependencies**
  - `tauri = { version = "2", features = [] }`
  - `tauri-plugin-shell = "2"`
  - `tauri-plugin-updater = "2"`
  - `tauri-plugin-process = "2"`
  - `tauri-plugin-opener = "2"`
  - `tauri-plugin-dialog = "2"`
  - `serde = { version = "1", features = ["derive"] }`
  - `serde_json = "1"`
  - `uuid = { version = "1", features = ["v4"] }`
- [ ] **Step 2: Create `src-tauri/tauri.conf.json` matching specification**
- [ ] **Step 3: Create `src-tauri/capabilities/default.json` configuring permissions for updater, shell sidecar, opener, and dialog**
- [ ] **Step 4: Create `src-tauri/build.rs` calling `tauri_build::build()`**

---

### Task 2.2: Implement Rust Sidecar Lifecycle & IPC in `src-tauri/src/lib.rs` & `src-tauri/src/main.rs`

**Files:**
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/main.rs`

**Interfaces:**
- Produces:
  - `BackendState` (holding Child process handle, port, session token, ready flag)
  - `#[tauri::command] get_backend_connection_info`
  - `#[tauri::command] stop_backend_sidecar`
  - `#[tauri::command] open_app_folder`
  - Application exit handler stopping sidecar child process cleanly.

- [ ] **Step 1: Implement `src-tauri/src/lib.rs`**
  - In `setup`:
    - Resolve app data directory and resource directory.
    - Generate random `STUDIO_SESSION_TOKEN`.
    - Spawn `tft-backend` sidecar passing `TFT_APPDATA_DIR`, `TFT_RESOURCE_DIR`, `STUDIO_SESSION_TOKEN`.
    - Async reader on `CommandEvent::Stdout`: detect `{"event":"server_ready","port":...}`, emit `backend-ready`.
  - Expose commands:
    - `get_backend_connection_info`: returns `{ base_url, token, ready, appdata_dir }`.
    - `stop_backend_sidecar`: sends HTTP `/api/shutdown` (with fallback to `kill()`) and resets child handle.
    - `open_app_folder`: opens `output` or `logs` folder via `tauri_plugin_opener`.
  - Register `on_window_event` / `run` exit hook to guarantee cleanup of `CommandChild`.
- [ ] **Step 2: Implement `src-tauri/src/main.rs` calling `lib::run()`**

---

## Phase 3: Frontend Control Panel Upgrades

### Task 3.1: Upgrade `Web Overlay/package.json` & `Web Overlay/vite.config.ts`

**Files:**
- Modify: `Web Overlay/package.json`
- Modify: `Web Overlay/vite.config.ts`

**Interfaces:**
- Produces:
  - Installed dependencies: `@tauri-apps/api`, `@tauri-apps/plugin-updater`, `@tauri-apps/plugin-process`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-opener`, `html-to-image`.
  - Vite config chunking for standard Tauri builds, preserving singlefile option when `process.env.SINGLE_FILE === "true"`.

- [ ] **Step 1: Add dependencies to `Web Overlay/package.json`**
- [ ] **Step 2: Install packages via npm in `Web Overlay/`**

Run: `npm --prefix "Web Overlay" install`
Expected: Dependencies installed successfully.

- [ ] **Step 3: Update `Web Overlay/vite.config.ts`**
  - Configure `viteSingleFile()` only when `SINGLE_FILE=true`.
  - Configure port 5173 and strictPort for Tauri dev server.

---

### Task 3.2: Implement API Facade `Web Overlay/src/lib/api.ts`

**Files:**
- Create: `Web Overlay/src/lib/api.ts`

**Interfaces:**
- Produces: `StudioApi` object replacing `window.pywebview.api` 1-to-1:
  - `getConfig()`
  - `saveConfig(config)`
  - `saveOverlayConfig(config)`
  - `fetchMatches(count)`
  - `fetchLiveNow()`
  - `exportOverlayImage(elementId?: string)`: renders overlay via `html-to-image` `toPng()`, sends Base64 to `/api/export/base64`, with fallback to `/api/export`.
  - `openOutputFolder()`
  - `openLogsFolder()`
  - `getAugmentsList()`
  - `saveCustomAugments(augments)`
  - `getConnectionInfo()`

- [ ] **Step 1: Write `Web Overlay/src/lib/api.ts`**
  - Check `("__TAURI_INTERNALS__" in window)` to invoke Tauri commands.
  - Automatically query backend connection info (`base_url` and `x-studio-token`).
  - Implement full 1080p client-side canvas render with `html-to-image`.
  - Implement folder opening via `invoke("open_app_folder", { folderType })`.

---

### Task 3.3: Implement Update State Machine & Modal

**Files:**
- Create: `Web Overlay/src/lib/updater.ts`
- Create: `Web Overlay/src/components/UpdateModal.tsx`

**Interfaces:**
- Produces:
  - `checkForAppUpdate() -> Promise<UpdateInfo | null>`
  - `installConfirmedUpdate(updateInfo, onProgress)`: stops backend sidecar first, runs `downloadAndInstall()`, then `relaunch()`.
  - `UpdateModal` React component showing:
    - Current vs new version
    - Release date & Release notes
    - "Cập nhật ngay" and "Để sau" buttons
    - Download/Install progress bar

- [ ] **Step 1: Write `Web Overlay/src/lib/updater.ts`**
- [ ] **Step 2: Write `Web Overlay/src/components/UpdateModal.tsx`**

---

### Task 3.4: Integrate StudioApi and UpdateModal into Frontend Components

**Files:**
- Modify: `Web Overlay/src/components/SourceTransformPanel.tsx`
- Modify: `Web Overlay/src/App.tsx`

**Interfaces:**
- Replace direct `window.pywebview.api` calls with `StudioApi`.
- Mount `UpdateModal` in `App.tsx` with automatic non-intrusive update check on app launch.

- [ ] **Step 1: Replace pywebview calls in `SourceTransformPanel.tsx` with `StudioApi`**
- [ ] **Step 2: Add `UpdateModal` and updater hook into `App.tsx`**
- [ ] **Step 3: Test frontend build**

Run: `npm --prefix "Web Overlay" run build`
Expected: Build passes with 0 errors.

---

## Phase 4: GitHub Actions CI/CD Workflows

### Task 4.1: Create `.github/workflows/ci.yml`

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Trigger: Push / Pull Request to `main`.
- Jobs:
  - Python lint (`ruff check`) & tests (`pytest`).
  - Frontend build (`npm run build`).
  - Sidecar packaging dry run (`python scripts/build_sidecar.py`).

- [ ] **Step 1: Write `.github/workflows/ci.yml`**
- [ ] **Step 2: Validate yaml syntax**

---

### Task 4.2: Create `.github/workflows/release.yml`

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Trigger: Push tags `v*.*.*` or `workflow_dispatch`.
- Platform Matrix:
  - Windows x64 (`windows-latest`, `x86_64-pc-windows-msvc`)
  - macOS arm64 (`macos-latest`, `aarch64-apple-darwin`)
  - macOS x64 (`macos-13`, `x86_64-apple-darwin`)
  - Linux x64 (`ubuntu-22.04`, `x86_64-unknown-linux-gnu`)
- Steps:
  - Setup Python 3.11, Node 22, Rust stable with targets.
  - Linux dependencies: `libwebkit2gtk-4.1-dev`, `libappindicator3-dev`, `librsvg2-dev`, `patchelf`.
  - Build sidecar binary using PyInstaller on native OS runner.
  - Execute `tauri-apps/tauri-action@v0` to build installers, updater artifacts, sign packages, and publish to GitHub Release.

- [ ] **Step 1: Write `.github/workflows/release.yml`**
- [ ] **Step 2: Validate workflow configuration**

---

## Phase 5: Automated Testing, Alignment & Documentation

### Task 5.1: Align Existing Tests & Ensure 100% Pass Rate

**Files:**
- Modify: `overlay_config.json`
- Test: `tests/unit/test_overlay_generator.py`

**Interfaces:**
- Fix golden test mismatch in `tests/unit/test_overlay_generator.py` by ensuring golden overlay matches standard config.

- [ ] **Step 1: Run pytest to diagnose golden test failure**
- [ ] **Step 2: Reconcile `overlay_config.json` custom_augments or update golden fixture**
- [ ] **Step 3: Run full pytest suite**

Run: `pytest -v`
Expected: 100% PASS (64+ tests)

---

### Task 5.2: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `README.vn.md`

**Interfaces:**
- Add desktop installation instructions for Windows (`.exe`), macOS (`.dmg`), and Linux (`.AppImage`).
- Document Tauri signing key generation (`npx tauri signer generate`), GitHub Secrets setup, and release workflow.

- [ ] **Step 1: Update `README.md`**
- [ ] **Step 2: Update `README.vn.md`**

---

## Self-Review Checklist

1. **Spec Coverage:**
   - [x] Phase 1: Python backend & sidecar standardization (`src/tft_studio/`).
   - [x] Phase 2: Tauri v2 shell & Rust process manager (`src-tauri/`).
   - [x] Phase 3: Frontend Control Panel upgrade (`Web Overlay/`).
   - [x] Phase 4: GitHub Actions CI/CD workflows (`.github/workflows/`).
   - [x] Phase 5: Automated test suite & documentation (`tests/`, `README`).
2. **Global Constraints:**
   - [x] OBS Studio Browser Source compatibility retained 100%.
   - [x] PyInstaller `--onefile` does NOT embed resources.
   - [x] Clear separation of read-only and read-write directories.
   - [x] User-confirmed updates with 9-state machine.
3. **Review Focus Items:**
   - [x] Port 8080 clean release on exit & update.
   - [x] Executable file lock prevention before updater runs.
   - [x] Data loss prevention across versions.
   - [x] Fallback for headless Chrome.
   - [x] Security token & CORS restrictions.
