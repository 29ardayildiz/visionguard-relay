# Required environment variables:
# SECRET_KEY          - ESP32 WebSocket/push authentication key
# JWT_SECRET          - Random 32+ char string for JWT signing
# ADMIN_USERNAME      - Login username
# ADMIN_PASSWORD_HASH - bcrypt hash of password
# Generate password hash: python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"

import asyncio
import io
import json
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from PIL import Image, ImageDraw
from slowapi import Limiter
from slowapi.util import get_remote_address

load_dotenv()

# ── Security configuration ────────────────────────────────────────────────────
SECRET_KEY          = os.getenv("SECRET_KEY")
JWT_SECRET          = os.getenv("JWT_SECRET")
JWT_ALGORITHM       = "HS256"
JWT_EXPIRE_HOURS    = 24
ADMIN_USERNAME      = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── App ───────────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter

# ── Stream state ──────────────────────────────────────────────────────────────
latest_frame: bytes | None = None
frame_event = asyncio.Event()
frame_times: deque[float] = deque(maxlen=30)

# ── Camera settings ───────────────────────────────────────────────────────────
camera_settings: dict = {
    "framesize": 5,
    "quality": 12,
    "brightness": 0,
    "contrast": 0,
    "saturation": 0,
    "sharpness": 0,
    "denoise": 0,
    "special_effect": 0,
    "whitebal": 1,
    "awb_gain": 1,
    "wb_mode": 0,
    "exposure_ctrl": 1,
    "aec2": 0,
    "ae_level": 0,
    "aec_value": 300,
    "gain_ctrl": 1,
    "agc_gain": 0,
    "gainceiling": 0,
    "bpc": 0,
    "wpc": 1,
    "raw_gma": 1,
    "lenc": 1,
    "hmirror": 1,
    "vflip": 1,
    "dcw": 1,
    "colorbar": 0,
}

CAMERA_DEFAULTS = dict(camera_settings)

esp32_websocket: WebSocket | None = None
esp32_settings_event = asyncio.Event()

# ── Brute-force protection ────────────────────────────────────────────────────
failed_attempts: dict[str, list[float]] = {}
BAN_WINDOW   = 15 * 60
MAX_ATTEMPTS = 5


def check_brute_force(ip: str) -> None:
    now = time.monotonic()
    attempts = [t for t in failed_attempts.get(ip, []) if now - t < BAN_WINDOW]
    failed_attempts[ip] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")


def record_failed_attempt(ip: str) -> None:
    failed_attempts.setdefault(ip, []).append(time.monotonic())


# ── JWT helpers ───────────────────────────────────────────────────────────────
def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> str:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return data["sub"]
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── Auth dependency ───────────────────────────────────────────────────────────
async def get_current_user(token: str = Cookie(default=None)) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"Location": "/login"},
        )
    return verify_token(token)


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path not in ("/login", "/manifest.json", "/icon.png"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ── Login page ────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="VisionGuard">
  <meta name="theme-color" content="#1c1c1e">
  <link rel="manifest" href="/manifest.json">
  <title>VisionGuard — Giriş</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #1c1c1e;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .card {
      background: #2c2c2e;
      border: 1px solid #3a3a3c;
      border-radius: 16px;
      padding: 2.5rem 2rem;
      width: 100%;
      max-width: 400px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }
    .logo { text-align: center; margin-bottom: 1.5rem; }
    .logo h1 { font-size: 1.8rem; color: #fff; font-weight: 700; letter-spacing: -0.5px; }
    .logo span { font-size: 2rem; }
    .subtitle { color: #8e8e93; font-size: 0.85rem; text-align: center; margin-top: 0.25rem; }
    label { display: block; color: #aeaeb2; font-size: 0.8rem; margin-bottom: 0.4rem; margin-top: 1.2rem; text-transform: uppercase; letter-spacing: 0.5px; }
    input {
      width: 100%;
      background: #1c1c1e;
      border: 1px solid #3a3a3c;
      border-radius: 10px;
      padding: 0.75rem 1rem;
      color: #fff;
      font-size: 1rem;
      outline: none;
      transition: border-color 0.2s;
    }
    input:focus { border-color: #30d158; }
    .btn {
      display: block;
      width: 100%;
      margin-top: 1.8rem;
      padding: 0.85rem;
      background: #30d158;
      color: #000;
      border: none;
      border-radius: 10px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.2s;
    }
    .btn:hover { background: #28b34a; }
    .error {
      background: #3b0000;
      border: 1px solid #7f1d1d;
      color: #fca5a5;
      border-radius: 10px;
      padding: 0.75rem 1rem;
      font-size: 0.9rem;
      margin-top: 1.2rem;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">
      <span>📷</span>
      <h1>VisionGuard</h1>
      <p class="subtitle">Güvenli Erişim</p>
    </div>
    {error_block}
    <form method="post" action="/login">
      <label for="username">Kullanıcı Adı</label>
      <input id="username" name="username" type="text" autocomplete="username" required autofocus>
      <label for="password">Şifre</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>
      <button class="btn" type="submit">Giriş Yap</button>
    </form>
  </div>
</body>
</html>"""

ERROR_BLOCK = '<div class="error">Kullanıcı adı veya şifre hatalı.</div>'


@app.get("/login", response_class=HTMLResponse)
async def login_page(error: int = 0):
    html = LOGIN_HTML.replace("{error_block}", ERROR_BLOCK if error else "")
    return HTMLResponse(content=html)


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    ip = request.client.host
    check_brute_force(ip)

    if username != ADMIN_USERNAME or not pwd_context.verify(password, ADMIN_PASSWORD_HASH):
        record_failed_attempt(ip)
        return RedirectResponse(url="/login?error=1", status_code=303)

    token = create_token(username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400,
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("token")
    return response


# ── Stream viewer ─────────────────────────────────────────────────────────────
VIEWER_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="VisionGuard">
  <meta name="theme-color" content="#000000">
  <link rel="manifest" href="/manifest.json">
  <title>VisionGuard Remote</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #000;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #fff;
    }
    img { max-width: 100%; height: auto; display: block; }
    #info { margin-top: 12px; font-size: 1rem; text-align: center; color: #ccc; }
    #logout { position: fixed; top: 16px; right: 16px; color: #636366; font-size: 0.8rem; text-decoration: none; padding: 6px 12px; background: rgba(44,44,46,0.8); border-radius: 8px; backdrop-filter: blur(10px); }
    #logout:hover { color: #fff; }
    #admin-link { position: fixed; top: 16px; left: 16px; color: #636366; font-size: 0.8rem; text-decoration: none; padding: 6px 12px; background: rgba(44,44,46,0.8); border-radius: 8px; backdrop-filter: blur(10px); }
    #admin-link:hover { color: #30d158; }
  </style>
</head>
<body>
  <img src="/stream" alt="Live feed">
  <div id="info">
    <div id="status">⏳ Bekleniyor...</div>
    <div id="fps">FPS: --</div>
  </div>
  <a href="/admin" id="admin-link">⚙️ Admin</a>
  <a href="/logout" id="logout">Çıkış</a>
  <script>
    async function update() {
      try {
        const r = await fetch('/health');
        const d = await r.json();
        document.getElementById('fps').textContent = 'FPS: ' + d.fps;
        document.getElementById('status').textContent = d.fps > 0 ? '🟢 Canlı' : '🔴 Bağlantı yok';
      } catch(e) {
        document.getElementById('status').textContent = '🔴 Bağlantı yok';
      }
    }
    setInterval(update, 2000);
    update();
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index(_: str = Depends(get_current_user)):
    return HTMLResponse(content=VIEWER_HTML)


# ── Stream endpoint ───────────────────────────────────────────────────────────
@app.get("/stream")
async def stream(_: str = Depends(get_current_user)):
    async def generate():
        while True:
            await frame_event.wait()
            frame_event.clear()
            if latest_frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" +
                       latest_frame + b"\r\n")

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Health endpoint ───────────────────────────────────────────────────────────
def is_esp32_connected() -> bool:
    if esp32_websocket is not None:
        return True
    if frame_times:
        return (time.monotonic() - frame_times[-1]) < 5.0
    return False


@app.get("/health")
async def health(_: str = Depends(get_current_user)):
    fps = 0.0
    if len(frame_times) >= 2:
        elapsed = frame_times[-1] - frame_times[0]
        if elapsed > 0:
            fps = (len(frame_times) - 1) / elapsed
    connected = is_esp32_connected()
    mode = "websocket" if esp32_websocket is not None else ("push" if connected else "none")
    return {"status": "ok", "fps": round(fps, 1), "esp32_connected": connected, "mode": mode}


# ── ESP32 push endpoint ───────────────────────────────────────────────────────
@app.post("/push")
async def push_frame(request: Request):
    global latest_frame
    key = request.headers.get("X-Secret-Key")
    if key != SECRET_KEY:
        return Response("Unauthorized", status_code=401)
    latest_frame = await request.body()
    frame_times.append(time.monotonic())
    frame_event.set()
    return {"status": "ok"}


# ── ESP32 WebSocket endpoint ──────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global latest_frame, esp32_websocket
    key = websocket.query_params.get("key")
    if key != SECRET_KEY:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    esp32_websocket = websocket
    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                latest_frame = msg["bytes"]
                frame_times.append(time.monotonic())
                frame_event.set()
            elif "text" in msg and msg["text"]:
                text = msg["text"]
                if text.startswith("{"):
                    try:
                        data = json.loads(text)
                        if "framesize" in data or "quality" in data:
                            camera_settings.update({k: v for k, v in data.items() if k in camera_settings})
                            esp32_settings_event.set()
                    except json.JSONDecodeError:
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        esp32_websocket = None


# ── Camera API ────────────────────────────────────────────────────────────────
@app.get("/api/camera/settings")
async def get_camera_settings(_: str = Depends(get_current_user)):
    return {**camera_settings, "esp32_connected": is_esp32_connected()}


@app.post("/api/camera/set")
async def set_camera_setting(request: Request, _: str = Depends(get_current_user)):
    body = await request.json()
    key = body.get("key")
    value = body.get("value")

    if key not in camera_settings:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    camera_settings[key] = value

    if esp32_websocket is not None:
        try:
            await esp32_websocket.send_text(json.dumps({"cmd": "set", "key": key, "value": value}))
        except Exception:
            pass

    return {"status": "ok", "key": key, "value": value}


@app.post("/api/camera/apply_all")
async def apply_all_settings(_: str = Depends(get_current_user)):
    if esp32_websocket is None:
        return {"status": "ok", "applied": 0, "note": "push_mode"}
    count = 0
    for key, value in camera_settings.items():
        try:
            await esp32_websocket.send_text(json.dumps({"cmd": "set", "key": key, "value": value}))
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            break
    return {"status": "ok", "applied": count}


@app.post("/api/camera/get_from_esp")
async def get_from_esp(_: str = Depends(get_current_user)):
    if esp32_websocket is None:
        raise HTTPException(status_code=503, detail="ESP32 WebSocket not connected (push-only mode)")
    esp32_settings_event.clear()
    try:
        await esp32_websocket.send_text(json.dumps({"cmd": "get_settings"}))
        await asyncio.wait_for(esp32_settings_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="ESP32 did not respond in time")
    return {**camera_settings, "esp32_connected": True}


# ── PWA endpoints ─────────────────────────────────────────────────────────────
@app.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "name": "VisionGuard",
        "short_name": "VisionGuard",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1c1c1e",
        "theme_color": "#1c1c1e",
        "icons": [
            {"src": "/icon.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon.png", "sizes": "512x512", "type": "image/png"},
        ],
    })


@app.get("/icon.png")
async def icon():
    img = Image.new("RGB", (512, 512), color="#30d158")
    draw = ImageDraw.Draw(img)
    # Camera body
    cx, cy = 256, 256
    draw.rounded_rectangle([cx-140, cy-90, cx+140, cy+100], radius=28, fill="white")
    # Lens outer
    draw.ellipse([cx-70, cy-55, cx+70, cy+65], fill="#30d158")
    # Lens inner
    draw.ellipse([cx-48, cy-33, cx+48, cy+43], fill="white")
    # Lens glass
    draw.ellipse([cx-32, cy-17, cx+32, cy+27], fill="#1c1c1e")
    # Viewfinder bump
    draw.rounded_rectangle([cx-28, cy-110, cx+28, cy-88], radius=8, fill="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


# ── Admin panel ───────────────────────────────────────────────────────────────
ADMIN_HTML = """<!DOCTYPE html>
<html class="dark" lang="en">
<head>
  <meta charset="utf-8"/>
  <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="VisionGuard">
  <meta name="theme-color" content="#1c1c1e">
  <link rel="manifest" href="/manifest.json">
  <title>VisionGuard Admin</title>
  <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
  <style>
    body { font-family: 'Inter', sans-serif; background-color: #1c1c1e; color: #e3e2e7; -webkit-font-smoothing: antialiased; }
    .mac-slider { -webkit-appearance: none; width: 100%; height: 4px; background: #3a3a3c; border-radius: 2px; outline: none; }
    .mac-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; background: #ffffff; border-radius: 50%; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.3); border: 0.5px solid rgba(0,0,0,0.1); }
    .ios-toggle { display: none; }
    .ios-toggle-label { display: block; background: #3a3a3c; border-radius: 999px; height: 28px; width: 50px; cursor: pointer; position: relative; transition: background 0.2s; flex-shrink: 0; }
    .ios-toggle-label::after { content: ''; position: absolute; top: 3px; left: 3px; background: white; border-radius: 50%; height: 22px; width: 22px; transition: transform 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }
    .ios-toggle:checked + .ios-toggle-label { background-color: #30d158; }
    .ios-toggle:checked + .ios-toggle-label::after { transform: translateX(22px); }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: #1c1c1e; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #3a3a3c; border-radius: 3px; }
    .material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
    select { -webkit-appearance: none; appearance: none; }
    #toast {
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      padding: 10px 20px; border-radius: 12px; font-size: 13px; font-weight: 500;
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      opacity: 0; pointer-events: none; transition: opacity 0.25s; z-index: 9999;
      white-space: nowrap;
    }
    #toast.show { opacity: 1; }
    #toast.ok { background: rgba(48,209,88,0.2); color: #30d158; border: 1px solid rgba(48,209,88,0.3); }
    #toast.err { background: rgba(255,69,58,0.2); color: #ff453a; border: 1px solid rgba(255,69,58,0.3); }
    @media (max-width: 768px) {
      .mobile-stack { flex-direction: column !important; }
      .stream-section { border-right: none !important; border-bottom: 1px solid #3a3a3c; max-height: 60vh; }
    }
  </style>
  <script>
    tailwind.config = {
      darkMode: "class",
      theme: {
        extend: {
          colors: {
            "primary-container": "#30d158", "outline": "#869583",
            "surface-dim": "#121317", "on-primary": "#003910",
            "surface-container": "#1e1f23", "surface": "#121317",
            "primary": "#55ee71", "on-surface": "#e3e2e7",
            "on-surface-variant": "#bccbb7", "background": "#121317",
            "surface-variant": "#343539", "outline-variant": "#3d4a3b",
          }
        }
      }
    }
  </script>
</head>
<body class="h-screen flex flex-col overflow-hidden">

<!-- Top bar -->
<header class="flex justify-between items-center w-full px-8 h-14 bg-[#1e1f23] border-b border-[#3d4a3b] z-50 flex-shrink-0">
  <div class="flex items-center gap-4">
    <span class="text-lg font-bold text-white tracking-tight">VisionGuard</span>
    <span class="text-xs text-[#636366] hidden md:block">Admin Panel</span>
  </div>
  <div class="flex items-center gap-3">
    <div id="esp-badge" class="flex items-center gap-1.5 bg-[#2c2c2e] px-3 py-1.5 rounded-full border border-[#3a3a3c] text-xs text-[#aeaeb2]">
      <span id="esp-dot" class="w-2 h-2 rounded-full bg-[#3a3a3c]"></span>
      <span id="esp-label">ESP32: --</span>
    </div>
    <a href="/" class="text-[#636366] hover:text-white text-xs px-3 py-1.5 rounded-lg hover:bg-[#2c2c2e] transition-colors">Live</a>
    <a href="/logout" class="text-[#636366] hover:text-white text-xs px-3 py-1.5 rounded-lg hover:bg-[#2c2c2e] transition-colors flex items-center gap-1">
      Logout <span class="material-symbols-outlined text-sm">logout</span>
    </a>
  </div>
</header>

<main class="flex flex-1 overflow-hidden mobile-stack">

  <!-- Left: stream + presets (40%) -->
  <section class="stream-section w-full md:w-[40%] bg-[#1c1c1e] border-r border-[#3a3a3c] flex flex-col overflow-y-auto custom-scrollbar flex-shrink-0">

    <!-- Stream -->
    <div class="p-4 space-y-3">
      <div class="flex justify-between items-center">
        <h2 class="text-sm font-semibold text-white flex items-center gap-2">
          <span id="live-dot" class="w-2 h-2 rounded-full bg-[#3a3a3c]"></span>
          Live Feed
        </h2>
        <span id="fps-badge" class="text-xs font-mono text-[#30d158] bg-[#2c2c2e] px-2 py-0.5 rounded border border-[#3a3a3c]">-- FPS</span>
      </div>
      <div class="relative bg-black rounded-xl overflow-hidden border border-[#3a3a3c] aspect-video flex items-center justify-center">
        <img src="/stream" alt="Live" class="w-full h-full object-contain absolute inset-0">
        <span class="material-symbols-outlined text-5xl text-[#3a3a3c] z-0">videocam</span>
      </div>
    </div>

    <!-- Presets -->
    <div class="px-4 pb-4 space-y-2">
      <p class="text-[10px] font-semibold text-[#636366] uppercase tracking-widest">Quick Presets</p>
      <div class="grid grid-cols-2 gap-2 p-1 bg-[#2c2c2e] rounded-xl border border-[#3a3a3c]">
        <button onclick="applyPreset('hq')" class="text-white py-2.5 rounded-lg text-xs font-semibold hover:bg-[#3a3a3c] transition-all active:scale-95">🎯 High Quality</button>
        <button onclick="applyPreset('hfps')" class="text-[#aeaeb2] py-2.5 rounded-lg text-xs font-semibold hover:bg-[#3a3a3c] transition-all active:scale-95">⚡ High FPS (~20fps)</button>
        <button onclick="applyPreset('night')" class="text-[#aeaeb2] py-2.5 rounded-lg text-xs font-semibold hover:bg-[#3a3a3c] transition-all active:scale-95">🌙 Night Mode</button>
        <button onclick="applyPreset('fixed_light')" class="text-[#aeaeb2] py-2.5 rounded-lg text-xs font-semibold hover:bg-[#3a3a3c] transition-all active:scale-95">💡 Fixed Light</button>
      </div>
    </div>
  </section>

  <!-- Right: settings (60%) -->
  <section class="flex-1 flex flex-col overflow-hidden bg-[#1c1c1e]">
    <div class="flex-1 overflow-y-auto p-4 custom-scrollbar pb-24">
      <div class="max-w-2xl mx-auto space-y-4">

        <!-- Imaging Card -->
        <div class="bg-[#2c2c2e] rounded-xl border border-[#3a3a3c] overflow-hidden">
          <div class="px-4 py-2.5 border-b border-[#3a3a3c] bg-[#343436]/30 flex items-center gap-2">
            <span class="material-symbols-outlined text-[#30d158] text-base">photo_camera</span>
            <h3 class="text-sm font-semibold text-white">Imaging Controls</h3>
          </div>
          <div class="p-4 space-y-5">

            <!-- Resolution -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Resolution</label>
              <select id="framesize" onchange="setSetting('framesize', +this.value)"
                class="flex-1 bg-[#1c1c1e] border border-[#3a3a3c] text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-[#30d158] transition-colors min-h-[44px]">
                <option value="0">96x96</option>
                <option value="1">QQVGA 160x120</option>
                <option value="2">QCIF 176x144</option>
                <option value="3">HQVGA 240x176</option>
                <option value="4">240x240</option>
                <option value="5">QVGA 320x240</option>
                <option value="6">CIF 400x296</option>
                <option value="7">HVGA 480x320</option>
                <option value="8">VGA 640x480</option>
                <option value="9">SVGA 800x600</option>
                <option value="10">XGA 1024x768</option>
                <option value="11">HD 1280x720</option>
                <option value="12">SXGA 1280x1024</option>
                <option value="13">UXGA 1600x1200</option>
              </select>
            </div>

            <!-- Quality -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-white w-28 flex-shrink-0">JPEG Quality <span class="text-[#636366]">(low=best)</span></label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="quality" class="mac-slider" min="4" max="63"
                  oninput="syncVal('quality');setSetting('quality',+this.value)">
                <span id="quality-val" class="text-xs font-mono text-[#30d158] w-8 text-right">12</span>
              </div>
            </div>

            <hr class="border-[#3a3a3c]"/>

            <!-- Brightness -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Brightness</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="brightness" class="mac-slider" min="-2" max="2"
                  oninput="syncVal('brightness');setSetting('brightness',+this.value)">
                <span id="brightness-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <!-- Contrast -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Contrast</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="contrast" class="mac-slider" min="-2" max="2"
                  oninput="syncVal('contrast');setSetting('contrast',+this.value)">
                <span id="contrast-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <!-- Saturation -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Saturation</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="saturation" class="mac-slider" min="-2" max="2"
                  oninput="syncVal('saturation');setSetting('saturation',+this.value)">
                <span id="saturation-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <!-- Sharpness -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Sharpness</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="sharpness" class="mac-slider" min="-2" max="2"
                  oninput="syncVal('sharpness');setSetting('sharpness',+this.value)">
                <span id="sharpness-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <!-- Denoise -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Denoise</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="denoise" class="mac-slider" min="0" max="255"
                  oninput="syncVal('denoise');setSetting('denoise',+this.value)">
                <span id="denoise-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <!-- Special Effect -->
            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Special Effect</label>
              <select id="special_effect" onchange="setSetting('special_effect', +this.value)"
                class="flex-1 bg-[#1c1c1e] border border-[#3a3a3c] text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-[#30d158] transition-colors min-h-[44px]">
                <option value="0">None</option>
                <option value="1">Negative</option>
                <option value="2">Grayscale</option>
                <option value="3">Red Tint</option>
                <option value="4">Green Tint</option>
                <option value="5">Blue Tint</option>
                <option value="6">Sepia</option>
              </select>
            </div>

          </div>
        </div>

        <!-- White Balance Card -->
        <div class="bg-[#2c2c2e] rounded-xl border border-[#3a3a3c] overflow-hidden">
          <div class="px-4 py-2.5 border-b border-[#3a3a3c] bg-[#343436]/30 flex items-center gap-2">
            <span class="material-symbols-outlined text-[#30d158] text-base">wb_sunny</span>
            <h3 class="text-sm font-semibold text-white">White Balance</h3>
          </div>
          <div class="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">White Balance</span>
              <div><input type="checkbox" id="whitebal" class="sr-only ios-toggle" onchange="setSetting('whitebal', this.checked?1:0)"><label for="whitebal" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">AWB Gain</span>
              <div><input type="checkbox" id="awb_gain" class="sr-only ios-toggle" onchange="setSetting('awb_gain', this.checked?1:0)"><label for="awb_gain" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center gap-4 md:col-span-2">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">WB Mode</label>
              <select id="wb_mode" onchange="setSetting('wb_mode', +this.value)"
                class="flex-1 bg-[#1c1c1e] border border-[#3a3a3c] text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-[#30d158] transition-colors min-h-[44px]">
                <option value="0">Auto</option>
                <option value="1">Sunny</option>
                <option value="2">Cloudy</option>
                <option value="3">Office</option>
                <option value="4">Home</option>
              </select>
            </div>

          </div>
        </div>

        <!-- Exposure Card -->
        <div class="bg-[#2c2c2e] rounded-xl border border-[#3a3a3c] overflow-hidden">
          <div class="px-4 py-2.5 border-b border-[#3a3a3c] bg-[#343436]/30 flex items-center gap-2">
            <span class="material-symbols-outlined text-[#30d158] text-base">shutter_speed</span>
            <h3 class="text-sm font-semibold text-white">Exposure &amp; Gain</h3>
          </div>
          <div class="p-4 space-y-5">

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="flex items-center justify-between min-h-[44px]">
                <span class="text-xs text-[#aeaeb2]">Exposure Control</span>
                <div><input type="checkbox" id="exposure_ctrl" class="sr-only ios-toggle" onchange="setSetting('exposure_ctrl', this.checked?1:0)"><label for="exposure_ctrl" class="ios-toggle-label"></label></div>
              </div>
              <div class="flex items-center justify-between min-h-[44px]">
                <span class="text-xs text-[#aeaeb2]">AEC2</span>
                <div><input type="checkbox" id="aec2" class="sr-only ios-toggle" onchange="setSetting('aec2', this.checked?1:0)"><label for="aec2" class="ios-toggle-label"></label></div>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">AE Level</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="ae_level" class="mac-slider" min="-2" max="2"
                  oninput="syncVal('ae_level');setSetting('ae_level',+this.value)">
                <span id="ae_level-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">AEC Value</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="aec_value" class="mac-slider" min="0" max="1200"
                  oninput="syncVal('aec_value');setSetting('aec_value',+this.value)">
                <span id="aec_value-val" class="text-xs font-mono text-white w-8 text-right">300</span>
              </div>
            </div>

            <hr class="border-[#3a3a3c]"/>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="flex items-center justify-between min-h-[44px]">
                <span class="text-xs text-[#aeaeb2]">Gain Control</span>
                <div><input type="checkbox" id="gain_ctrl" class="sr-only ios-toggle" onchange="setSetting('gain_ctrl', this.checked?1:0)"><label for="gain_ctrl" class="ios-toggle-label"></label></div>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">AGC Gain</label>
              <div class="flex-1 flex items-center gap-3">
                <input type="range" id="agc_gain" class="mac-slider" min="0" max="30"
                  oninput="syncVal('agc_gain');setSetting('agc_gain',+this.value)">
                <span id="agc_gain-val" class="text-xs font-mono text-white w-8 text-right">0</span>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <label class="text-xs text-[#aeaeb2] w-28 flex-shrink-0">Gain Ceiling</label>
              <select id="gainceiling" onchange="setSetting('gainceiling', +this.value)"
                class="flex-1 bg-[#1c1c1e] border border-[#3a3a3c] text-white text-xs rounded-lg px-3 py-2.5 outline-none focus:border-[#30d158] transition-colors min-h-[44px]">
                <option value="0">2x</option>
                <option value="1">4x</option>
                <option value="2">8x</option>
                <option value="3">16x</option>
                <option value="4">32x</option>
                <option value="5">64x</option>
                <option value="6">128x</option>
              </select>
            </div>

          </div>
        </div>

        <!-- Advanced Card -->
        <div class="bg-[#2c2c2e] rounded-xl border border-[#3a3a3c] overflow-hidden">
          <div class="px-4 py-2.5 border-b border-[#3a3a3c] bg-[#343436]/30 flex items-center gap-2">
            <span class="material-symbols-outlined text-[#30d158] text-base">tune</span>
            <h3 class="text-sm font-semibold text-white">Advanced</h3>
          </div>
          <div class="p-4 grid grid-cols-2 gap-4">

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">BPC</span>
              <div><input type="checkbox" id="bpc" class="sr-only ios-toggle" onchange="setSetting('bpc', this.checked?1:0)"><label for="bpc" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">WPC</span>
              <div><input type="checkbox" id="wpc" class="sr-only ios-toggle" onchange="setSetting('wpc', this.checked?1:0)"><label for="wpc" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">Raw GMA</span>
              <div><input type="checkbox" id="raw_gma" class="sr-only ios-toggle" onchange="setSetting('raw_gma', this.checked?1:0)"><label for="raw_gma" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">LENC</span>
              <div><input type="checkbox" id="lenc" class="sr-only ios-toggle" onchange="setSetting('lenc', this.checked?1:0)"><label for="lenc" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">H-Mirror</span>
              <div><input type="checkbox" id="hmirror" class="sr-only ios-toggle" onchange="setSetting('hmirror', this.checked?1:0)"><label for="hmirror" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">V-Flip</span>
              <div><input type="checkbox" id="vflip" class="sr-only ios-toggle" onchange="setSetting('vflip', this.checked?1:0)"><label for="vflip" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">DCW</span>
              <div><input type="checkbox" id="dcw" class="sr-only ios-toggle" onchange="setSetting('dcw', this.checked?1:0)"><label for="dcw" class="ios-toggle-label"></label></div>
            </div>

            <div class="flex items-center justify-between min-h-[44px]">
              <span class="text-xs text-[#aeaeb2]">Colorbar</span>
              <div><input type="checkbox" id="colorbar" class="sr-only ios-toggle" onchange="setSetting('colorbar', this.checked?1:0)"><label for="colorbar" class="ios-toggle-label"></label></div>
            </div>

          </div>
        </div>

      </div>
    </div>

    <!-- Footer actions -->
    <footer class="px-4 py-3 border-t border-[#3a3a3c] bg-[#1c1c1e] flex items-center justify-between gap-3 flex-shrink-0">
      <div class="flex gap-2">
        <button onclick="syncFromCamera()"
          class="px-4 py-2.5 rounded-lg bg-[#3a3a3c] text-white text-xs font-semibold hover:bg-[#4a4a4c] transition-colors flex items-center gap-1.5 min-h-[44px]">
          <span class="material-symbols-outlined text-base">sync</span>
          Sync from Camera
        </button>
        <button onclick="resetDefaults()"
          class="px-4 py-2.5 rounded-lg border border-[#3a3a3c] text-[#aeaeb2] text-xs font-semibold hover:bg-[#2c2c2e] transition-colors min-h-[44px]">
          Reset Defaults
        </button>
      </div>
      <button onclick="applyAll()"
        class="px-6 py-2.5 rounded-lg bg-[#30d158] text-black text-xs font-bold hover:bg-[#28b34a] transition-all active:scale-95 shadow-lg shadow-[#30d158]/10 min-h-[44px]">
        Apply All
      </button>
    </footer>
  </section>

</main>

<div id="toast"></div>

<script>
const DEFAULTS = {framesize:5,quality:12,brightness:0,contrast:0,saturation:0,sharpness:0,denoise:0,special_effect:0,whitebal:1,awb_gain:1,wb_mode:0,exposure_ctrl:1,aec2:0,ae_level:0,aec_value:300,gain_ctrl:1,agc_gain:0,gainceiling:0,bpc:0,wpc:1,raw_gma:1,lenc:1,hmirror:1,vflip:1,dcw:1,colorbar:0};

function syncVal(id) {
  const el = document.getElementById(id);
  const sp = document.getElementById(id + '-val');
  if (el && sp) sp.textContent = el.value;
}

function setControls(s) {
  for (const [k, v] of Object.entries(s)) {
    const el = document.getElementById(k);
    if (!el) continue;
    if (el.type === 'checkbox') {
      el.checked = Boolean(v);
    } else if (el.tagName === 'SELECT') {
      el.value = v.toString();
    } else {
      el.value = v;
      el.dispatchEvent(new Event('input'));
    }
  }
  const connected = s.esp32_connected;
  document.getElementById('esp-dot').className = 'w-2 h-2 rounded-full ' + (connected ? 'bg-[#30d158]' : 'bg-[#3a3a3c]');
  document.getElementById('esp-label').textContent = connected ? 'ESP32: Online' : 'ESP32: Offline';
}

let toastTimer;
function showToast(msg, ok) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + (ok ? 'ok' : 'err');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ''; }, 2500);
}

async function setSetting(key, value) {
  try {
    const r = await fetch('/api/camera/set', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key, value})
    });
    if (r.ok) showToast(key + ' = ' + value, true);
    else { const d = await r.json(); showToast(d.detail || 'Error', false); }
  } catch(e) { showToast('Connection error', false); }
}

async function applyAll() {
  try {
    const r = await fetch('/api/camera/apply_all', {method: 'POST'});
    const d = await r.json();
    if (r.ok) showToast(d.applied > 0 ? (d.applied + ' settings applied') : 'Saved (push mode)', true);
    else showToast(d.detail || 'Error', false);
  } catch(e) { showToast('Connection error', false); }
}

async function syncFromCamera() {
  try {
    const r = await fetch('/api/camera/get_from_esp', {method: 'POST'});
    const d = await r.json();
    if (r.ok) { setControls(d); showToast('Synced from ESP32', true); }
    else showToast(d.detail || 'Error', false);
  } catch(e) { showToast('Connection error', false); }
}

async function resetDefaults() {
  setControls(DEFAULTS);
  for (const [k, v] of Object.entries(DEFAULTS)) {
    await setSetting(k, v);
  }
}

async function applyPreset(name) {
  const presets = {
    hq:   {framesize:9, quality:10, brightness:0, contrast:1, saturation:1, sharpness:1, denoise:10, whitebal:1, awb_gain:1, wb_mode:0, exposure_ctrl:1, aec2:1, ae_level:0, gain_ctrl:1, agc_gain:0, gainceiling:2, bpc:1, wpc:1, raw_gma:1, lenc:1, hmirror:1, vflip:1, dcw:1},
    hfps: {framesize:5, quality:30, brightness:0, contrast:0, saturation:0, sharpness:0, denoise:0, exposure_ctrl:1, aec2:0, gain_ctrl:1, agc_gain:0, hmirror:1, vflip:1},
    night:{framesize:5, quality:20, brightness:2, contrast:1, saturation:-1, sharpness:0, denoise:128, exposure_ctrl:1, aec2:1, ae_level:2, gain_ctrl:1, agc_gain:20, gainceiling:4, hmirror:1, vflip:1},
    fixed_light:{framesize:10, quality:12, brightness:0, contrast:1, saturation:1, sharpness:1, denoise:10, whitebal:1, awb_gain:0, wb_mode:1, exposure_ctrl:0, aec2:0, ae_level:0, aec_value:300, gain_ctrl:0, agc_gain:5, gainceiling:0, bpc:1, wpc:1, raw_gma:1, lenc:1, hmirror:1, vflip:1, dcw:1, colorbar:0}
  };
  const p = presets[name];
  for (const [k, v] of Object.entries(p)) {
    const el = document.getElementById(k);
    if (el) {
      if (el.type === 'checkbox') { el.checked = Boolean(v); }
      else if (el.tagName === 'SELECT') { el.value = v.toString(); }
      else { el.value = v; el.dispatchEvent(new Event('input')); }
    }
    await setSetting(k, v);
  }
  await fetch('/api/camera/apply_all', {method: 'POST'});
  showToast('✅ Preset applied', true);
}

async function pollHealth() {
  try {
    const r = await fetch('/health');
    const d = await r.json();
    document.getElementById('fps-badge').textContent = d.fps + ' FPS';
    const live = d.fps > 0;
    document.getElementById('live-dot').className = 'w-2 h-2 rounded-full ' + (live ? 'bg-[#30d158] animate-pulse' : 'bg-[#3a3a3c]');
    document.getElementById('esp-dot').className = 'w-2 h-2 rounded-full ' + (d.esp32_connected ? 'bg-[#30d158]' : 'bg-[#3a3a3c]');
    document.getElementById('esp-label').textContent = d.esp32_connected ? 'ESP32: Online' : 'ESP32: Offline';
  } catch(e) {}
}

(async () => {
  try {
    const r = await fetch('/api/camera/settings');
    setControls(await r.json());
  } catch(e) {}
})();
setInterval(pollHealth, 3000);
pollHealth();
</script>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(_: str = Depends(get_current_user)):
    return HTMLResponse(content=ADMIN_HTML)
