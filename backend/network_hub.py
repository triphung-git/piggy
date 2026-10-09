"""
backend/network_hub.py
-----------------------
Local HTTP + WebSocket server (Standalone Mode).
Chạy hoàn toàn cục bộ trên máy người dùng (localhost:8080 only).
  - Phục vụ REST API cho Control Panel Desktop.
  - Phục vụ WebSocket cục bộ để OBS Overlay tự cập nhật mượt mà (không reload trang).
  - Phục vụ Static Files: /overlay, /assets, /TFT_DDragon cho OBS Browser Source.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import threading
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.config import load_overlay_config, save_overlay_config
from backend.paths import get_app_dir, resolve_resource

logger = logging.getLogger("network_hub")

# Token bí mật sinh ngẫu nhiên mỗi lần khởi động (S1, S2)
_STUDIO_TOKEN: str = secrets.token_urlsafe(32)


def get_current_token() -> str:
    """Trả về token bí mật dùng để xác thực các thao tác ghi (S1, S2)."""
    return _STUDIO_TOKEN


ALLOWED_HOST_PATTERN = re.compile(r"^(localhost|127\.0\.0\.1)(:\d+)?$", re.IGNORECASE)
ALLOWED_ORIGIN_PATTERN = re.compile(
    r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|null)$", re.IGNORECASE
)


# --------------------------------------------------------------------- #
# Local WebSocket notifier — chỉ phục vụ localhost (OBS + Desktop app)
# --------------------------------------------------------------------- #
class LocalNotifier:
    """Quản lý kết nối WebSocket cục bộ để thông báo cho OBS Overlay cập nhật."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
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

    async def notify_all(self, message: Dict[str, Any]) -> None:
        """Gửi thông báo tới tất cả các OBS / overlay tabs đang mở."""
        payload = json.dumps(message, ensure_ascii=False)
        stale: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._connections.discard(ws)


# FastAPI App — localhost only
app = FastAPI(title="TFT Post-Match Studio (Standalone)", docs_url=None, redoc_url=None)

# S3: CORS chỉ cho localhost/127.0.0.1, tuyệt đối không dùng '*'
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
        if not token or not secrets.compare_digest(token, _STUDIO_TOKEN):
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
_server_thread: Optional[threading.Thread] = None
_is_running = False
_current_loop: Optional[asyncio.AbstractEventLoop] = None


def set_bridge_reference(bridge: Any) -> None:
    """Liên kết server với StudioBridge."""
    global _bridge_ref
    _bridge_ref = bridge


def notify_sync(message: Dict[str, Any]) -> None:
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

    await notifier.connect(websocket)
    try:
        # Gửi trạng thái ban đầu
        current_cfg = load_overlay_config()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "INITIAL_STATE",
                    "overlay_config": current_cfg,
                },
                ensure_ascii=False,
            )
        )

        # Giữ kết nối (chỉ nhận — overlay không cần gửi lệnh ngược về)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
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
        "status": "online",
        "mode": "standalone",
        "obs_url": "http://localhost:8080/overlay",
        "control_url": "http://localhost:8080/app",
    }


@app.get("/api/state")
def get_app_state():
    """Lấy toàn bộ trạng thái ứng dụng hiện tại."""
    if not _bridge_ref:
        return {"error": "Bridge reference not set"}
    return _bridge_ref.get_app_state()


@app.post("/api/render")
async def trigger_render(request: Request):
    """Kích hoạt render overlay từ HTTP request (hỗ trợ OBS tools, script)."""
    if not _bridge_ref:
        return {"success": False, "error": "Bridge not ready"}

    res = _bridge_ref.render_overlay()

    notify_sync(
        {
            "type": "OVERLAY_RENDERED",
            "success": res.get("success", False),
            "match_id": res.get("match_id"),
            "timestamp": time.time(),
        }
    )
    return res


@app.get("/api/config")
def get_overlay_config():
    """Lấy cấu hình overlay_config.json hiện tại."""
    return load_overlay_config()


@app.post("/api/config")
def update_overlay_config(payload: Dict[str, Any]):
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
    from backend.config import AppConfig

    cfg = AppConfig.load()
    masked = (
        f"{cfg.api_key[:6]}...{cfg.api_key[-4:]}"
        if len(cfg.api_key) > 10
        else (cfg.api_key or "")
    )
    return {
        "riot_id": cfg.riot_id or f"{cfg.game_name}#{cfg.tag_line}",
        "game_name": cfg.game_name,
        "tag_line": cfg.tag_line,
        "region": cfg.region,
        "api_key_masked": masked,
        "has_api_key": bool(cfg.api_key),
    }


@app.post("/api/riot/fetch")
def trigger_riot_fetch():
    """Kích hoạt tải trận đấu mới nhất."""
    if _bridge_ref:
        return _bridge_ref.fetch_live_now()
    return {"success": False, "error": "Cơ chế Fetch chỉ khả dụng khi chạy qua app"}


# --------------------------------------------------------------------- #
# /api/augments — Danh sách lõi nâng cấp tiếng Anh từ DDragon (en_US)
# --------------------------------------------------------------------- #
@app.get("/api/augments")
def get_augments_list():
    """
    Trả về danh sách lõi nâng cấp (Augments) tiếng Anh từ DDragon en_US.
    Response: { "augments": [{ "id": "...", "name": "...", "image": "..." }] }
    Được sắp xếp theo tên tiếng Anh (A-Z). Lọc trùng lặp theo (name, image).
    """
    try:
        from backend.data_parser import get_ddragon_loader

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
            result.append({"id": aug_id, "name": aug_name, "image": img})
        result.sort(key=lambda x: x["name"].lower())
        return {"augments": result, "total": len(result)}
    except Exception as e:
        logger.error("Failed to load augments list: %s", e)
        return {"augments": [], "total": 0, "error": str(e)}


@app.post("/api/augments")
async def save_custom_augments(request: Request):
    """
    Lưu custom_augments vào overlay_config.json và kích hoạt re-compile overlay.
    Body JSON: { "custom_augments": ["image1.png", "image2.png", "image3.png"] }
    Phần tử trống (null / "") sẽ được lưu là null — khi render sẽ dùng dữ liệu thực từ trận đấu.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": "Invalid JSON body"}, status_code=400
        )

    raw_augments = body.get("custom_augments", [])
    if not isinstance(raw_augments, list):
        return JSONResponse(
            {"success": False, "error": "custom_augments must be a list"},
            status_code=400,
        )

    from backend.data_parser import validate_custom_augment

    # Chuẩn hóa & kiểm tra an toàn (K3: Chống path traversal)
    normalized: list = []
    for item in raw_augments[:3]:
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
        current_cfg.pop("custom_augments", None)
    else:
        current_cfg["custom_augments"] = normalized

    updated = save_overlay_config(current_cfg)

    # Kích hoạt re-compile overlay HTML và thông báo WS ngay lập tức
    if _bridge_ref:
        _bridge_ref.notify_frontend("onAppStateUpdate", {"overlay_config": updated})
        import threading

        def _recompile():
            try:
                _bridge_ref._compile_and_notify(source="AugmentsUpdate")
            except Exception as exc:
                logger.warning("Augments re-compile error: %s", exc)

        threading.Thread(target=_recompile, daemon=True).start()
    else:
        # Standalone web mode (không có bridge) — chỉ broadcast config đã đổi
        notify_sync({"type": "CONFIG_CHANGED", "overlay_config": updated})

    return {"success": True, "overlay_config": updated}


# --------------------------------------------------------------------- #
# /api/overlay-html — Endpoint mới cho smooth DOM-swap (không reload trang)
# --------------------------------------------------------------------- #
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
        with open(overlay_path, "r", encoding="utf-8") as f:
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
    """
    Phục vụ overlay cho OBS Browser Source: http://localhost:8080/overlay
    Sử dụng smooth DOM-swap thay vì window.location.reload():
      - Kết nối WS cục bộ.
      - Khi nhận OVERLAY_RENDERED → fetch /api/overlay-html → swap body với fade animation.
      - Không bao giờ reload trang → không flash/nhấp nháy trên OBS.
    """
    app_dir = get_app_dir()
    overlay_path = app_dir / "output" / "overlay.html"

    if not overlay_path.exists():
        # Placeholder khi chưa có overlay
        placeholder_html = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TFT Post-Match Overlay</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0a0a0f;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; font-family: 'Segoe UI', sans-serif; color: #888;
    }
    .waiting {
      text-align: center; padding: 40px;
      border: 1px solid #222; border-radius: 12px; background: #111;
    }
    .waiting h2 { color: #c8aa6e; margin-bottom: 12px; font-size: 1.4rem; }
    .dot { animation: blink 1.2s infinite; } .dot:nth-child(2) { animation-delay: .4s; } .dot:nth-child(3) { animation-delay: .8s; }
    @keyframes blink { 0%,100%{opacity:.2} 50%{opacity:1} }
  </style>
</head>
<body>
  <div class="waiting" id="overlay-root">
    <h2>⚔️ TFT Post-Match Studio</h2>
    <p>Đang chờ dữ liệu từ Control Panel<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></p>
    <p style="margin-top:8px;font-size:.85rem;color:#555">Mở Control Panel → Nhấn <b>Render</b></p>
  </div>
  LIVE_RELOAD_SCRIPT
</body>
</html>"""
        content = placeholder_html
    else:
        try:
            with open(overlay_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            content = "<html><body><p>Lỗi đọc overlay.html</p></body></html>"

        # Chuẩn hóa đường dẫn
        content = content.replace('src="../assets/', 'src="/assets/')
        content = content.replace('src="../TFT_DDragon/', 'src="/TFT_DDragon/')
        content = content.replace("url('../assets/", "url('/assets/")
        content = content.replace('href="overlay.css"', 'href="/overlay.css"')

        if "<head>" in content:
            content = content.replace("<head>", '<head>\n  <base href="/">')

    # Script real-time smooth DOM-swap (KHÔNG reload trang)
    live_reload_script = """
    <!-- TFT Studio: Real-time Smooth Overlay Update -->
    <style>
      @keyframes tft-fade-in {
        from { opacity: 0; transform: scale(0.998); }
        to   { opacity: 1; transform: scale(1); }
      }
      .tft-updating { pointer-events: none; }
      .tft-fade-in  { animation: tft-fade-in 0.35s ease-out forwards; }
    </style>
    <script>
    (function() {
      'use strict';
      var loc = window.location;
      var proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      var wsUrl = proto + '//' + (loc.host || '127.0.0.1:8080') + '/ws';
      var socket = null;
      var reconnectTimer = null;
      var isUpdating = false;

      function smoothUpdate() {
        if (isUpdating) return;
        isUpdating = true;

        fetch('/api/overlay-html?_t=' + Date.now())
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (!data.ready || !data.html) { isUpdating = false; return; }

            var root = document.getElementById('overlay-root') || document.body;
            root.classList.add('tft-updating');

            // Fade out
            root.style.transition = 'opacity 0.2s ease-out';
            root.style.opacity = '0';

            setTimeout(function() {
              // Swap nội dung
              if (root === document.body) {
                root.innerHTML = data.html;
              } else {
                root.innerHTML = data.html;
              }

              // Fade in
              root.style.opacity = '1';
              root.classList.remove('tft-updating');
              root.classList.add('tft-fade-in');
              setTimeout(function() { root.classList.remove('tft-fade-in'); isUpdating = false; }, 400);
            }, 200);
          })
          .catch(function() { isUpdating = false; });
      }

      // Gắn ra window để PyWebView bridge gọi được trực tiếp
      window.smoothUpdate = smoothUpdate;

      function connect() {
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        try {
          socket = new WebSocket(wsUrl);

          socket.onmessage = function(event) {
            try {
              var msg = JSON.parse(event.data);
              if (msg.type === 'OVERLAY_RENDERED' || msg.type === 'CONFIG_CHANGED') {
                smoothUpdate();
              }
              // INITIAL_STATE: cập nhật nếu đang ở placeholder
              if (msg.type === 'INITIAL_STATE') {
                var root = document.getElementById('overlay-root');
                if (root && root.querySelector('.waiting')) {
                  smoothUpdate();
                }
              }
            } catch(e) {}
          };

          socket.onopen = function() {
            console.log('[TFT Overlay] Connected to local server');
          };

          socket.onclose = function() {
            socket = null;
            reconnectTimer = setTimeout(connect, 1500);
          };

          socket.onerror = function() {
            if (socket) socket.close();
          };
        } catch(e) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      }

      // Bắt đầu kết nối
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', connect);
      } else {
        connect();
      }
    })();
    </script>
    """

    # Inject script vào HTML
    if "LIVE_RELOAD_SCRIPT" in content:
        content = content.replace("LIVE_RELOAD_SCRIPT", live_reload_script)
    elif "</body>" in content:
        content = content.replace("</body>", f"{live_reload_script}\n</body>")
    else:
        content += live_reload_script

    return HTMLResponse(
        content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/overlay-config-public")
def get_obs_info():
    """Trả về thông tin cần thiết cho người dùng cài OBS."""
    return {
        "obs_browser_source_url": "http://localhost:8080/overlay",
        "control_panel_url": "http://localhost:8080/app",
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
        with open(css_path, "r", encoding="utf-8") as f:
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
assets_path = resolve_resource("assets")
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

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
        return FileResponse(dist_dir / "index.html")


# --------------------------------------------------------------------- #
# Khởi động Server (localhost only — không expose LAN)
# --------------------------------------------------------------------- #
def start_server(port: int = 8080) -> None:
    """Khởi động Uvicorn trên localhost (127.0.0.1) trong daemon thread."""
    global _server_thread, _is_running
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
        server.run()

    _server_thread = threading.Thread(target=run, daemon=True, name="TFTStudioServer")
    _server_thread.start()


def is_server_running() -> bool:
    return _is_running
