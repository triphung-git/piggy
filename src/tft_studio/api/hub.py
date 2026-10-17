"""
src/tft_studio/api/hub.py
-------------------------
Local HTTP + WebSocket server (Standalone Mode).
Chạy hoàn toàn cục bộ trên máy người dùng (localhost:8080 only).
  - Phục vụ REST API cho Control Panel Desktop.
  - Phục vụ WebSocket cục bộ để OBS Overlay tự cập nhật mượt mà (không reload trang).
  - Phục vụ Static Files: /overlay, /assets, /TFT_DDragon cho OBS Browser Source.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import ValidationError

from tft_studio.api.body_limit import BodyLimitMiddleware
from tft_studio.core.config import AppConfig, load_overlay_config, save_overlay_config
from tft_studio.core.paths import (
    ensure_user_config_initialized,
    get_app_dir,
    get_appdata_dir,
    resolve_resource,
)
from tft_studio.core.schemas import ExportRequest, RiotSettings
from tft_studio.core.storage import EXPORT_LOCK, atomic_write
from tft_studio.data.parser import get_ddragon_loader, validate_custom_augment

logger = logging.getLogger("network_hub")

# Token bí mật sinh ngẫu nhiên mỗi lần khởi động (S1, S2) hoặc đọc từ STUDIO_SESSION_TOKEN
_STUDIO_TOKEN: str = secrets.token_urlsafe(32)


def get_current_token() -> str:
    """Trả về token bí mật dùng để xác thực các thao tác ghi (S1, S2)."""
    return os.environ.get("STUDIO_SESSION_TOKEN") or _STUDIO_TOKEN


TAURI_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

ALLOWED_HOST_PATTERN = re.compile(
    r"^(localhost|127\.0\.0\.1|tauri\.localhost)(:\d+)?$", re.IGNORECASE
)
ALLOWED_ORIGIN_PATTERN = re.compile(
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|tauri://localhost|https?://tauri\.localhost)$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------- #
# Local WebSocket notifier — chỉ phục vụ localhost (OBS + Desktop app)
# --------------------------------------------------------------------- #
class LocalNotifier:
    """Quản lý kết nối WebSocket cục bộ để thông báo cho OBS Overlay cập nhật."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.debug("Local WS client connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.debug(
            "Local WS client disconnected. Remaining: %d", len(self._connections)
        )

    async def notify_all(self, message: dict[str, Any]) -> None:
        """Gửi thông báo tới tất cả các OBS / overlay tabs đang mở."""
        payload = json.dumps(message, ensure_ascii=False)
        stale: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._connections.discard(ws)


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _current_loop, _bridge_ref
    _current_loop = asyncio.get_running_loop()
    owned = _bridge_ref is None
    if owned:
        ensure_user_config_initialized()
        from tft_studio.service.controller import StudioController
        from tft_studio.service.match_service import MatchService
        _bridge_ref = StudioController(MatchService())
    try:
        yield
    finally:
        if owned and _bridge_ref:
            await asyncio.to_thread(_bridge_ref.close)
            _bridge_ref = None
        _current_loop = None


# FastAPI App — localhost only
app = FastAPI(title="TFT Post-Match Studio (Standalone)", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)

# S3: CORS cho localhost/127.0.0.1 và các origin hợp lệ của Tauri
app.add_middleware(
    CORSMiddleware,
    allow_origins=TAURI_ORIGINS,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|tauri://localhost|https?://tauri\.localhost)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """S1: Kiểm tra Host, Origin và yêu cầu X-Studio-Token cho các thao tác ghi."""
    # 1. Kiểm tra Host
    host = request.headers.get("host", "")
    if host and not ALLOWED_HOST_PATTERN.match(host):
        logger.warning("Blocked request with forbidden host: %s", host)
        return JSONResponse({"error": "Forbidden host"}, status_code=403)

    # 2. Kiểm tra Origin
    origin = request.headers.get("origin")
    if origin and not ALLOWED_ORIGIN_PATTERN.match(origin):
        logger.warning("Blocked request with forbidden origin: %s", origin)
        return JSONResponse({"error": "Forbidden origin"}, status_code=403)

    # 3. Yêu cầu token cho các method ghi (POST, PUT, DELETE, PATCH)
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        token = request.headers.get("x-studio-token", "")
        current_token = get_current_token()
        if not token or not secrets.compare_digest(token, current_token):
            logger.warning(
                "Unauthorized write attempt on %s without valid token", request.url.path
            )
            return JSONResponse(
                {"error": "Forbidden: Invalid or missing X-Studio-Token"},
                status_code=403,
            )

    return await call_next(request)



notifier = LocalNotifier()

# Tham chiếu tới StudioBridge (được set sau khi bridge khởi tạo)
_bridge_ref: Any = None
_server_thread: threading.Thread | None = None
_is_running = False
_runtime_port = 8080
_current_loop: asyncio.AbstractEventLoop | None = None


def get_runtime_port() -> int:
    return _runtime_port


def set_runtime_port(port: int) -> None:
    global _runtime_port
    _runtime_port = port


@app.exception_handler(ValidationError)
async def config_validation_error(request: Request, exc: ValidationError):
    return JSONResponse({"success": False, "error": "Invalid configuration", "fields": [".".join(str(p) for p in e["loc"]) for e in exc.errors()]}, status_code=422)


def set_bridge_reference(bridge: Any) -> None:
    """Liên kết server với StudioBridge."""
    global _bridge_ref
    _bridge_ref = bridge


def notify_sync(message: dict[str, Any]) -> None:
    """Gửi thông báo từ luồng Python đồng bộ → tất cả overlay tabs."""
    global _current_loop
    if _current_loop and _current_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            notifier.notify_all(message),
            _current_loop,
        )


# --------------------------------------------------------------------- #
# WebSocket Endpoint — Local overlay auto-refresh
# --------------------------------------------------------------------- #
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket cục bộ dành cho OBS Browser Source và overlay tabs.
    Khi nhận OVERLAY_RENDERED, client tự fetch /api/overlay-html và swap DOM.
    """
    global _current_loop
    _current_loop = asyncio.get_running_loop()

    host = websocket.headers.get("host", "")
    origin = websocket.headers.get("origin")
    if not ALLOWED_HOST_PATTERN.fullmatch(host) or (origin and not ALLOWED_ORIGIN_PATTERN.fullmatch(origin)):
        await websocket.close(code=1008)
        return
    await notifier.connect(websocket)
    try:
        # Gửi trạng thái ban đầu
        await websocket.send_text(
            json.dumps(
                {
                    "type": "INITIAL_STATE",
                    "ready": _bridge_ref is not None,
                },
                ensure_ascii=False,
            )
        )

        # Giữ kết nối (chỉ nhận — overlay không cần gửi lệnh ngược về)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except TimeoutError:
                # Ping keepalive
                await websocket.send_text(json.dumps({"type": "PING"}))
    except WebSocketDisconnect:
        notifier.disconnect(websocket)
    except Exception as e:
        logger.debug("Local WS error: %s", e)
        notifier.disconnect(websocket)


# --------------------------------------------------------------------- #
# REST API Endpoints
# --------------------------------------------------------------------- #
@app.get("/api/status")
def get_server_status():
    """Kiểm tra trạng thái server cục bộ."""
    return {
        "status": "online" if _bridge_ref else "starting",
        "ready": _bridge_ref is not None,
        "mode": "standalone",
        "obs_url": f"http://127.0.0.1:{_runtime_port}/overlay",
        "control_url": f"http://127.0.0.1:{_runtime_port}/app/",
    }


@app.get("/api/state")
def get_app_state():
    """Lấy toàn bộ trạng thái ứng dụng hiện tại."""
    if not _bridge_ref:
        raise HTTPException(503, "Application is starting")
    return _bridge_ref.get_app_state()


@app.post("/api/render")
def trigger_render():
    if not _bridge_ref:
        raise HTTPException(503, "Application is starting")
    result = _bridge_ref.render_overlay()
    return JSONResponse(result, status_code=200 if result.get("success") else 409)


@app.get("/api/config")
def get_overlay_config():
    """Lấy cấu hình overlay_config.json hiện tại."""
    return load_overlay_config()


@app.post("/api/config")
def update_overlay_config(payload: dict[str, Any]):
    """Cập nhật overlay config và thông báo cho overlay tự refresh."""
    updated = save_overlay_config(payload)
    if _bridge_ref:
        _bridge_ref.notify_frontend("onAppStateUpdate", {"overlay_config": updated})
    notify_sync({"type": "CONFIG_CHANGED", "overlay_config": updated})
    return {"success": True, "overlay_config": updated}


@app.get("/api/riot")
def get_riot_info():
    """Lấy thông tin tài khoản Riot và trạng thái API."""
    if _bridge_ref:
        return _bridge_ref.get_riot_config()

    cfg = AppConfig.load()
    masked = (
        f"{cfg.api_key[:6]}...{cfg.api_key[-4:]}"
        if len(cfg.api_key) > 10
        else ("****" if cfg.api_key else "")
    )
    return {
        "riot_id": cfg.riot_id or f"{cfg.game_name}#{cfg.tag_line}",
        "game_name": cfg.game_name,
        "tag_line": cfg.tag_line,
        "region": cfg.region,
        "api_key_masked": masked,
        "has_api_key": bool(cfg.api_key),
    }


# --------------------------------------------------------------------- #
# Endpoints điều khiển hệ thống & xuất ảnh
# --------------------------------------------------------------------- #
_uvicorn_server: uvicorn.Server | None = None


def set_uvicorn_server(server: uvicorn.Server) -> None:
    """Gán đối tượng Uvicorn server để có thể dừng server một cách an toàn."""
    global _uvicorn_server
    _uvicorn_server = server


@app.post("/api/shutdown")
def shutdown_server():
    """
    Dừng Uvicorn server một cách an toàn khi chuẩn bị cập nhật hoặc đóng ứng dụng.
    Yêu cầu X-Studio-Token.
    """
    logger.info("Shutdown requested via /api/shutdown")

    def _do_shutdown():
        time.sleep(0.15)
        global _uvicorn_server
        if _uvicorn_server:
            _uvicorn_server.should_exit = True
        elif not os.environ.get("PYTEST_CURRENT_TEST"):
            os._exit(0)

    threading.Thread(target=_do_shutdown, daemon=True).start()
    return {"success": True, "message": "Server is shutting down"}


@app.post("/api/export")
def export_via_browser():
    """
    Kích hoạt xuất ảnh PNG 1920x1080 qua Chromium headless (fallback).
    Yêu cầu X-Studio-Token.
    """
    from tft_studio.render.exporter import export_html_to_png

    appdata_dir = get_appdata_dir()
    html_file = appdata_dir / "output" / "overlay.html"
    if not html_file.exists():
        return JSONResponse(
            {"success": False, "error": "Chưa có file overlay.html để xuất ảnh"},
            status_code=400,
        )

    timestamp = uuid.uuid4().hex
    output_png = appdata_dir / "output" / f"overlay_{timestamp}.png"
    latest_png = appdata_dir / "output" / "overlay_latest.png"

    ok = export_html_to_png(html_file, output_png, width=1920, height=1080)
    if ok:
        try:
            with EXPORT_LOCK:
                atomic_write(latest_png, output_png.read_bytes())
        except Exception as exc:
            logger.warning("Could not copy to overlay_latest.png: %s", exc)
        return {
            "success": True,
            "file_path": str(output_png.resolve()),
            "latest_path": str(latest_png.resolve()),
            "filename": output_png.name,
        }

    return JSONResponse(
        {"success": False, "error": "Không thể kết xuất ảnh PNG qua browser"},
        status_code=500,
    )


@app.post("/api/export/base64")
def export_base64_image(body: ExportRequest):
    encoded = body.image_base64
    if encoded.startswith("data:"):
        if not encoded.startswith("data:image/png;base64,"):
            raise HTTPException(422, "Expected a PNG data URL")
        encoded = encoded.split(",", 1)[1]
    try:
        data = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(data)) as img:
            if img.format != "PNG" or img.size != (1920, 1080):
                raise ValueError("Expected PNG 1920x1080")
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
    except Exception as exc:
        raise HTTPException(422, "Invalid PNG; expected a complete 1920x1080 image") from exc
    output_dir = get_appdata_dir() / "output"
    file_path = output_dir / f"overlay_{uuid.uuid4().hex}.png"
    latest_path = output_dir / "overlay_latest.png"
    with EXPORT_LOCK:
        atomic_write(file_path, data)
        atomic_write(latest_path, data)
    return {"success": True, "file_path": str(file_path), "latest_path": str(latest_path), "filename": file_path.name}


@app.post("/api/riot/settings")
def save_riot_settings(body: RiotSettings):
    if not _bridge_ref:
        raise HTTPException(503, "Application is starting")
    return _bridge_ref.save_app_config(body.model_dump(exclude_none=True))


@app.post("/api/riot/fetch")
def trigger_riot_fetch():
    if not _bridge_ref:
        raise HTTPException(503, "Application is starting")
    return _bridge_ref.fetch_live_now()


@app.get("/api/augments")
def get_augments_list():
    """
    Trả về danh sách lõi nâng cấp (Augments) tiếng Anh từ DDragon en_US.
    Response: { "augments": [{ "id": "...", "name": "...", "image": "..." }] }
    Được sắp xếp theo tên tiếng Anh (A-Z). Lọc trùng lặp theo (name, image).
    """
    try:
        loader = get_ddragon_loader("en_US")
        seen_names: set[str] = set()
        result = []
        for aug_id, aug_name in loader.augments.items():
            img = loader.augment_images.get(aug_id, "")
            if not aug_name or not img:
                continue
            # Lọc các key trùng lặp (DataDragon lưu cả id lẫn key = id)
            dedup_key = (aug_name, img)
            if dedup_key in seen_names:
                continue
            seen_names.add(dedup_key)

            # Phân loại tier & nhận diện Destiny
            s_img = img.lower()
            s_name = aug_name.lower()
            s_id = str(aug_id).lower()
            if any(x in s_img for x in ("_iii", "-iii", "3.png")) or s_id.endswith("3") or "prismatic" in s_name:
                tier = 3
            elif any(x in s_img for x in ("_ii", "-ii", "2.png")) or s_id.endswith("2") or "gold" in s_name:
                tier = 2
            elif any(x in s_img for x in ("_i", "-i", "1.png")) or s_id.endswith("1") or "silver" in s_name:
                tier = 1
            else:
                tier = 2

            is_destiny = "destiny" in s_name or "destiny" in s_img or "vận mệnh" in s_name

            result.append({
                "id": aug_id,
                "name": aug_name,
                "image": img,
                "tier": tier,
                "is_destiny": is_destiny,
            })
        result.sort(key=lambda x: x["name"].lower())
        return {"augments": result, "total": len(result)}
    except Exception as e:
        logger.error("Failed to load augments list: %s", e)
        return {"augments": [], "total": 0, "error": str(e)}


@app.post("/api/augments")
async def save_custom_augments(request: Request):
    """
    Lưu custom_augments vào overlay_config.json và kích hoạt re-compile overlay.
    Body JSON: { "custom_augments": ["image1.png", "image2.png", "image3.png", ...] }
    Hỗ trợ từ 3 đến 6 lõi (khi có lõi Destiny).
    Phần tử trống (null / "") sẽ được lưu là null — khi render sẽ dùng dữ liệu thực từ trận đấu.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": "Invalid JSON body"}, status_code=400
        )

    if not isinstance(body, dict):
        raise HTTPException(422, "Expected an object")
    raw_augments = body.get("custom_augments", [])
    if not isinstance(raw_augments, list):
        return JSONResponse(
            {"success": False, "error": "custom_augments must be a list"},
            status_code=400,
        )

    # Chuẩn hóa & kiểm tra an toàn (K3: Chống path traversal)
    normalized: list = []
    if len(raw_augments) > 6:
        raise HTTPException(422, "At most six augment entries are allowed")
    for item in raw_augments:
        if item is not None and not validate_custom_augment(item):
            return JSONResponse(
                {"success": False, "error": f"Invalid augment identifier: {item}"},
                status_code=400,
            )
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        else:
            normalized.append(None)

    # Lưu vào overlay_config.json
    current_cfg = load_overlay_config()

    # Nếu tất cả đều None → xóa custom_augments để dùng auto từ trận đấu
    if all(v is None for v in normalized):
        current_cfg["custom_augments"] = []
    else:
        current_cfg["custom_augments"] = normalized

    updated = save_overlay_config(current_cfg)
    compile_result = {"success": False, "error": "Application is starting"}
    if _bridge_ref:
        _bridge_ref.notify_frontend("onAppStateUpdate", {"overlay_config": updated})
        compile_result = await asyncio.to_thread(_bridge_ref._compile_and_notify, "AugmentsUpdate")
    return {"success": True, "overlay_config": updated, "compile": compile_result}


@app.get("/api/overlay-html")
def get_overlay_inner_html():
    """
    Trả về nội dung HTML bên trong <body> của overlay hiện tại.
    OBS / overlay tabs dùng endpoint này để swap DOM mượt mà, không reload trang.
    Response: { "html": "<div>...</div>", "timestamp": 1234567890 }
    """
    app_dir = get_app_dir()
    overlay_path = app_dir / "output" / "overlay.html"

    if not overlay_path.exists():
        return JSONResponse(
            {
                "html": "<div style='color:#fff;font-family:sans-serif;padding:40px;text-align:center'>"
                "<p>⏳ Chưa có dữ liệu overlay. Nhấn <b>Render</b> trong Control Panel để bắt đầu.</p>"
                "</div>",
                "ready": False,
                "timestamp": time.time(),
            }
        )

    try:
        with open(overlay_path, encoding="utf-8") as f:
            content = f.read()

        # Chuẩn hóa đường dẫn assets về absolute web paths
        content = content.replace('src="../assets/', 'src="/assets/')
        content = content.replace('src="../TFT_DDragon/', 'src="/TFT_DDragon/')
        content = content.replace("url('../assets/", "url('/assets/")
        content = content.replace('href="overlay.css"', 'href="/overlay.css"')

        # Trích xuất body innerHTML
        body_start = content.find("<body")
        body_end = content.rfind("</body>")
        if body_start != -1 and body_end != -1:
            # Tìm > đầu tiên sau <body để bỏ qua attributes
            tag_close = content.find(">", body_start)
            inner_html = content[tag_close + 1 : body_end].strip()
        else:
            inner_html = content  # fallback: trả về toàn bộ

        return JSONResponse(
            {
                "html": inner_html,
                "ready": True,
                "timestamp": time.time(),
            }
        )
    except Exception as e:
        logger.error("Failed to read overlay HTML: %s", e)
        return JSONResponse(
            {"html": "", "ready": False, "error": str(e)}, status_code=500
        )


# --------------------------------------------------------------------- #
# Overlay & Static Files Serving (OBS Browser Source)
# --------------------------------------------------------------------- #
@app.get("/overlay", response_class=HTMLResponse)
def serve_overlay_html():
    shell = resolve_resource("templates/overlay-shell.html").read_text(encoding="utf-8")
    return HTMLResponse(shell, headers={"Cache-Control": "no-store"})


@app.get("/api/overlay-config-public")
def get_obs_info():
    """Trả về thông tin cần thiết cho người dùng cài OBS."""
    return {
        "obs_browser_source_url": f"http://127.0.0.1:{_runtime_port}/overlay",
        "control_panel_url": f"http://127.0.0.1:{_runtime_port}/app/",
        "width": 1920,
        "height": 1080,
    }


@app.get("/overlay.css")
def serve_overlay_css():
    """Phục vụ overlay.css với đường dẫn ảnh chuẩn xác."""
    app_dir = get_app_dir()
    css_path = app_dir / "output" / "overlay.css"
    if not css_path.exists():
        css_path = resolve_resource("templates/overlay.css")
    try:
        with open(css_path, encoding="utf-8") as f:
            css_content = f.read()
        css_content = css_content.replace("url('../assets/", "url('/assets/")
    except Exception:
        css_content = ""
    return HTMLResponse(css_content, media_type="text/css")


@app.get("/overlay_latest.png")
def serve_overlay_png():
    """Phục vụ ảnh overlay PNG 1920x1080."""
    app_dir = get_app_dir()
    png_path = app_dir / "output" / "overlay_latest.png"
    if png_path.exists():
        return FileResponse(png_path, media_type="image/png")
    return JSONResponse(
        {"error": "Chưa có ảnh overlay. Nhấn Render trước."}, status_code=404
    )


# --------------------------------------------------------------------- #
# Static Files Mount
# --------------------------------------------------------------------- #
app_dir = get_app_dir()
@app.get("/assets/{relative_path:path}")
def serve_asset(relative_path: str):
    from pathlib import Path
    relative = Path(relative_path.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or ":" in relative_path:
        raise HTTPException(404)
    try:
        resolved = resolve_resource(Path("assets") / relative)
    except ValueError as exc:
        raise HTTPException(404) from exc
    if not resolved.is_file():
        raise HTTPException(404)
    return FileResponse(resolved)


ddragon_path = resolve_resource("TFT_DDragon")
if ddragon_path.exists():
    app.mount("/TFT_DDragon", StaticFiles(directory=str(ddragon_path)), name="ddragon")

output_path = app_dir / "output"
output_path.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(output_path)), name="output")

# Web Control Panel (React build)
dist_dir = resolve_resource("Web Overlay/dist")
if dist_dir.exists():
    app.mount(
        "/app", StaticFiles(directory=str(dist_dir), html=True), name="control_app"
    )

    @app.get("/")
    def index_redirect():
        return RedirectResponse("/app/")


# --------------------------------------------------------------------- #
# Khởi động Server (localhost only — không expose LAN)
# --------------------------------------------------------------------- #
def start_server(port: int = 8080) -> None:
    """Khởi động Uvicorn trên localhost (127.0.0.1) trong daemon thread."""
    global _server_thread, _is_running
    set_runtime_port(port)
    if _is_running:
        return

    _is_running = True

    def run():
        logger.info(
            "TFT Studio Server started at http://127.0.0.1:%d (localhost only)", port
        )
        logger.info("OBS Browser Source: http://localhost:%d/overlay", port)
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",  # localhost only — bảo mật, không expose LAN
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        set_uvicorn_server(server)
        try:
            server.run()
        finally:
            global _is_running
            _is_running = False

    _server_thread = threading.Thread(target=run, daemon=True, name="TFTStudioServer")
    _server_thread.start()


def is_server_running() -> bool:
    return bool(_uvicorn_server and _uvicorn_server.started)
