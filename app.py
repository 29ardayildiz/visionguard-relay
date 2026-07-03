# Required environment variables:
# SECRET_KEY          - ESP32 WebSocket/push authentication key
# JWT_SECRET          - Random 32+ char string for JWT signing
# ADMIN_USERNAME      - Login username
# ADMIN_PASSWORD_HASH - bcrypt hash of password
# Generate password hash: python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"

import asyncio
import json
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
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
    if request.url.path not in ("/login",):
        response.headers["Cache-Control"] = "no-store"
    return response


# ── Login page ────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VisionGuard — Giriş</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0a0a0a;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .card {
      background: #141414;
      border: 1px solid #2a2a2a;
      border-radius: 12px;
      padding: 2.5rem 2rem;
      width: 100%;
      max-width: 400px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }
    .logo { text-align: center; margin-bottom: 1.5rem; }
    .logo h1 { font-size: 1.8rem; color: #fff; font-weight: 700; letter-spacing: -0.5px; }
    .logo span { font-size: 2rem; }
    .subtitle { color: #888; font-size: 0.85rem; text-align: center; margin-top: 0.25rem; }
    label { display: block; color: #aaa; font-size: 0.8rem; margin-bottom: 0.4rem; margin-top: 1.2rem; text-transform: uppercase; letter-spacing: 0.5px; }
    input {
      width: 100%;
      background: #1e1e1e;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 0.75rem 1rem;
      color: #fff;
      font-size: 1rem;
      outline: none;
      transition: border-color 0.2s;
    }
    input:focus { border-color: #22c55e; }
    .btn {
      display: block;
      width: 100%;
      margin-top: 1.8rem;
      padding: 0.85rem;
      background: #22c55e;
      color: #000;
      border: none;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.2s;
    }
    .btn:hover { background: #16a34a; }
    .error {
      background: #3b0000;
      border: 1px solid #7f1d1d;
      color: #fca5a5;
      border-radius: 8px;
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
    #logout { position: fixed; top: 12px; right: 16px; color: #666; font-size: 0.8rem; text-decoration: none; }
    #logout:hover { color: #fff; }
    #admin-link { position: fixed; top: 12px; left: 16px; color: #666; font-size: 0.8rem; text-decoration: none; }
    #admin-link:hover { color: #22c55e; }
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
@app.get("/health")
async def health(_: str = Depends(get_current_user)):
    fps = 0.0
    if len(frame_times) >= 2:
        elapsed = frame_times[-1] - frame_times[0]
        if elapsed > 0:
            fps = (len(frame_times) - 1) / elapsed
    return {"status": "ok", "fps": round(fps, 1), "esp32_connected": esp32_websocket is not None}


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
                        # Settings response from ESP32
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
    return {**camera_settings, "esp32_connected": esp32_websocket is not None}


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
        raise HTTPException(status_code=503, detail="ESP32 not connected")
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
        raise HTTPException(status_code=503, detail="ESP32 not connected")
    esp32_settings_event.clear()
    try:
        await esp32_websocket.send_text(json.dumps({"cmd": "get_settings"}))
        await asyncio.wait_for(esp32_settings_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="ESP32 did not respond in time")
    return {**camera_settings, "esp32_connected": True}


# ── Admin panel ───────────────────────────────────────────────────────────────
ADMIN_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VisionGuard Admin</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0a0a0a; --card: #141414; --border: #2a2a2a;
      --text: #e5e5e5; --muted: #666; --accent: #22c55e;
      --accent-dim: #15803d; --danger: #ef4444; --warn: #f59e0b;
    }
    body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }

    /* Top bar */
    .topbar {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 1.5rem;
      background: var(--card); border-bottom: 1px solid var(--border);
      position: sticky; top: 0; z-index: 100;
    }
    .topbar-left { display: flex; align-items: center; gap: 0.75rem; }
    .topbar h1 { font-size: 1.1rem; font-weight: 700; }
    .topbar-right { display: flex; align-items: center; gap: 1rem; }
    #esp-status { font-size: 0.85rem; }
    a.btn-link { color: var(--muted); font-size: 0.85rem; text-decoration: none; }
    a.btn-link:hover { color: var(--text); }

    /* Layout */
    .layout { display: flex; gap: 0; height: calc(100vh - 49px); }
    .left-panel { width: 40%; min-width: 280px; border-right: 1px solid var(--border); display: flex; flex-direction: column; }
    .right-panel { flex: 1; overflow-y: auto; padding: 1rem; }

    /* Preview */
    .preview-wrap { flex: 1; background: #000; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .preview-wrap img { width: 100%; height: 100%; object-fit: contain; }
    .preview-info { padding: 0.75rem 1rem; background: var(--card); border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: var(--muted); }

    /* Presets */
    .presets { padding: 0.75rem 1rem; border-top: 1px solid var(--border); background: var(--card); }
    .presets h3 { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-bottom: 0.5rem; }
    .preset-btns { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .preset-btn {
      padding: 0.35rem 0.75rem; border-radius: 6px; border: 1px solid var(--border);
      background: #1e1e1e; color: var(--text); font-size: 0.8rem; cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
    }
    .preset-btn:hover { border-color: var(--accent); background: #1a2e1a; }

    /* Settings sections */
    .section { margin-bottom: 1.25rem; }
    .section-header {
      font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.5px; color: var(--muted); padding: 0.5rem 0;
      border-bottom: 1px solid var(--border); margin-bottom: 0.75rem;
    }
    .control-row {
      display: flex; align-items: center; gap: 0.75rem;
      padding: 0.4rem 0;
    }
    .control-row label { flex: 0 0 140px; font-size: 0.82rem; color: #aaa; }
    .control-row .input-wrap { flex: 1; display: flex; align-items: center; gap: 0.5rem; }
    .val-display { min-width: 32px; text-align: right; font-size: 0.8rem; color: var(--accent); font-variant-numeric: tabular-nums; }

    input[type=range] {
      flex: 1; -webkit-appearance: none; height: 4px;
      background: #333; border-radius: 2px; outline: none;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none; width: 14px; height: 14px;
      background: var(--accent); border-radius: 50%; cursor: pointer;
    }
    select, input[type=range] { cursor: pointer; }
    select {
      flex: 1; background: #1e1e1e; border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); padding: 0.35rem 0.5rem;
      font-size: 0.85rem; outline: none;
    }
    select:focus { border-color: var(--accent); }

    /* Toggle */
    .toggle { position: relative; width: 36px; height: 20px; flex-shrink: 0; }
    .toggle input { opacity: 0; width: 0; height: 0; }
    .toggle-slider {
      position: absolute; inset: 0; background: #333; border-radius: 10px;
      cursor: pointer; transition: background 0.2s;
    }
    .toggle-slider::before {
      content: ''; position: absolute; width: 14px; height: 14px;
      left: 3px; top: 3px; background: #888; border-radius: 50%;
      transition: transform 0.2s, background 0.2s;
    }
    .toggle input:checked + .toggle-slider { background: var(--accent-dim); }
    .toggle input:checked + .toggle-slider::before { transform: translateX(16px); background: var(--accent); }

    /* Action buttons */
    .action-bar { display: flex; gap: 0.5rem; flex-wrap: wrap; padding-bottom: 1rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border); }
    .btn {
      padding: 0.45rem 1rem; border-radius: 7px; font-size: 0.85rem;
      font-weight: 600; cursor: pointer; border: none; transition: opacity 0.15s;
    }
    .btn:hover { opacity: 0.85; }
    .btn-green { background: var(--accent); color: #000; }
    .btn-gray { background: #2a2a2a; color: var(--text); }
    .btn-blue { background: #2563eb; color: #fff; }

    /* Toast */
    #toast {
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      padding: 0.65rem 1.1rem; border-radius: 8px; font-size: 0.88rem;
      font-weight: 500; opacity: 0; pointer-events: none;
      transition: opacity 0.2s; z-index: 999;
    }
    #toast.show { opacity: 1; }
    #toast.ok { background: #14532d; color: #86efac; border: 1px solid #166534; }
    #toast.err { background: #450a0a; color: #fca5a5; border: 1px solid #7f1d1d; }
  </style>
</head>
<body>
<div class="topbar">
  <div class="topbar-left">
    <span>📷</span>
    <h1>VisionGuard Admin</h1>
  </div>
  <div class="topbar-right">
    <span id="esp-status">🔴 ESP32 bağlı değil</span>
    <a href="/" class="btn-link">← Görüntü</a>
    <a href="/logout" class="btn-link">Çıkış</a>
  </div>
</div>

<div class="layout">
  <!-- Left: preview -->
  <div class="left-panel">
    <div class="preview-wrap">
      <img src="/stream" alt="Live">
    </div>
    <div class="preview-info">
      <span id="fps-display">FPS: --</span>
      <span id="conn-display">--</span>
    </div>
    <div class="presets">
      <h3>Hızlı Ön Ayar</h3>
      <div class="preset-btns">
        <button class="preset-btn" onclick="applyPreset('hq')">🎯 Yüksek Kalite</button>
        <button class="preset-btn" onclick="applyPreset('hfps')">⚡ Yüksek FPS</button>
        <button class="preset-btn" onclick="applyPreset('night')">🌙 Gece Modu</button>
      </div>
    </div>
  </div>

  <!-- Right: controls -->
  <div class="right-panel">
    <div class="action-bar">
      <button class="btn btn-green" onclick="applyAll()">✅ Tümünü Uygula</button>
      <button class="btn btn-blue" onclick="getFromEsp()">🔄 ESP32'den Al</button>
      <button class="btn btn-gray" onclick="resetDefaults()">↩ Varsayılana Sıfırla</button>
    </div>

    <!-- Resolution & Quality -->
    <div class="section">
      <div class="section-header">📐 Çözünürlük & Kalite</div>
      <div class="control-row">
        <label>Çözünürlük</label>
        <div class="input-wrap">
          <select id="framesize" onchange="setSetting('framesize', +this.value)">
            <option value="0">96x96</option><option value="1">QQVGA 160x120</option>
            <option value="2">QCIF 176x144</option><option value="3">HQVGA 240x176</option>
            <option value="4">240x240</option><option value="5">QVGA 320x240</option>
            <option value="6">CIF 400x296</option><option value="7">HVGA 480x320</option>
            <option value="8">VGA 640x480</option><option value="9">SVGA 800x600</option>
            <option value="10">XGA 1024x768</option><option value="11">HD 1280x720</option>
            <option value="12">SXGA 1280x1024</option><option value="13">UXGA 1600x1200</option>
          </select>
        </div>
      </div>
      <div class="control-row">
        <label>Kalite (düşük=iyi)</label>
        <div class="input-wrap">
          <input type="range" id="quality" min="4" max="63" oninput="updateVal('quality');setSetting('quality',+this.value)">
          <span class="val-display" id="quality-val">12</span>
        </div>
      </div>
    </div>

    <!-- Color & Effects -->
    <div class="section">
      <div class="section-header">🎨 Renk & Efekt</div>
      <div class="control-row">
        <label>Parlaklık</label>
        <div class="input-wrap">
          <input type="range" id="brightness" min="-2" max="2" oninput="updateVal('brightness');setSetting('brightness',+this.value)">
          <span class="val-display" id="brightness-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>Kontrast</label>
        <div class="input-wrap">
          <input type="range" id="contrast" min="-2" max="2" oninput="updateVal('contrast');setSetting('contrast',+this.value)">
          <span class="val-display" id="contrast-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>Doygunluk</label>
        <div class="input-wrap">
          <input type="range" id="saturation" min="-2" max="2" oninput="updateVal('saturation');setSetting('saturation',+this.value)">
          <span class="val-display" id="saturation-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>Netlik</label>
        <div class="input-wrap">
          <input type="range" id="sharpness" min="-2" max="2" oninput="updateVal('sharpness');setSetting('sharpness',+this.value)">
          <span class="val-display" id="sharpness-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>Gürültü Azaltma</label>
        <div class="input-wrap">
          <input type="range" id="denoise" min="0" max="255" oninput="updateVal('denoise');setSetting('denoise',+this.value)">
          <span class="val-display" id="denoise-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>Özel Efekt</label>
        <div class="input-wrap">
          <select id="special_effect" onchange="setSetting('special_effect', +this.value)">
            <option value="0">Yok</option><option value="1">Negatif</option>
            <option value="2">Gri Ton</option><option value="3">Kırmızı Ton</option>
            <option value="4">Yeşil Ton</option><option value="5">Mavi Ton</option>
            <option value="6">Sepya</option>
          </select>
        </div>
      </div>
      <div class="control-row">
        <label>Beyaz Denge</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="whitebal" onchange="setSetting('whitebal', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>AWB Kazancı</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="awb_gain" onchange="setSetting('awb_gain', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>WB Modu</label>
        <div class="input-wrap">
          <select id="wb_mode" onchange="setSetting('wb_mode', +this.value)">
            <option value="0">Otomatik</option><option value="1">Güneşli</option>
            <option value="2">Bulutlu</option><option value="3">Ofis</option><option value="4">Ev</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Exposure & Gain -->
    <div class="section">
      <div class="section-header">💡 Pozlama & Kazanç</div>
      <div class="control-row">
        <label>Pozlama Kontrolü</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="exposure_ctrl" onchange="setSetting('exposure_ctrl', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>AEC2</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="aec2" onchange="setSetting('aec2', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>AE Seviyesi</label>
        <div class="input-wrap">
          <input type="range" id="ae_level" min="-2" max="2" oninput="updateVal('ae_level');setSetting('ae_level',+this.value)">
          <span class="val-display" id="ae_level-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>AEC Değeri</label>
        <div class="input-wrap">
          <input type="range" id="aec_value" min="0" max="1200" oninput="updateVal('aec_value');setSetting('aec_value',+this.value)">
          <span class="val-display" id="aec_value-val">300</span>
        </div>
      </div>
      <div class="control-row">
        <label>Kazanç Kontrolü</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="gain_ctrl" onchange="setSetting('gain_ctrl', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>AGC Kazancı</label>
        <div class="input-wrap">
          <input type="range" id="agc_gain" min="0" max="30" oninput="updateVal('agc_gain');setSetting('agc_gain',+this.value)">
          <span class="val-display" id="agc_gain-val">0</span>
        </div>
      </div>
      <div class="control-row">
        <label>Kazanç Tavanı</label>
        <div class="input-wrap">
          <select id="gainceiling" onchange="setSetting('gainceiling', +this.value)">
            <option value="0">2x</option><option value="1">4x</option><option value="2">8x</option>
            <option value="3">16x</option><option value="4">32x</option><option value="5">64x</option><option value="6">128x</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Advanced -->
    <div class="section">
      <div class="section-header">🔧 Gelişmiş</div>
      <div class="control-row">
        <label>BPC (Siyah Piksel)</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="bpc" onchange="setSetting('bpc', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>WPC (Beyaz Piksel)</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="wpc" onchange="setSetting('wpc', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>Raw GMA</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="raw_gma" onchange="setSetting('raw_gma', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>LENC (Lens Düzeltme)</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="lenc" onchange="setSetting('lenc', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>Yatay Ayna</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="hmirror" onchange="setSetting('hmirror', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>Dikey Çevirme</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="vflip" onchange="setSetting('vflip', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>DCW</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="dcw" onchange="setSetting('dcw', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
      <div class="control-row">
        <label>Renk Çubuğu (Test)</label>
        <div class="input-wrap">
          <label class="toggle"><input type="checkbox" id="colorbar" onchange="setSetting('colorbar', this.checked?1:0)"><span class="toggle-slider"></span></label>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
const TOGGLES = ['whitebal','awb_gain','exposure_ctrl','aec2','gain_ctrl','bpc','wpc','raw_gma','lenc','hmirror','vflip','dcw','colorbar'];

function updateVal(id) {
  const el = document.getElementById(id);
  const disp = document.getElementById(id + '-val');
  if (disp && el) disp.textContent = el.value;
}

function setControls(s) {
  for (const [k, v] of Object.entries(s)) {
    const el = document.getElementById(k);
    if (!el) continue;
    if (el.type === 'checkbox') { el.checked = !!v; }
    else { el.value = v; updateVal(k); }
  }
  const espEl = document.getElementById('esp-status');
  espEl.textContent = s.esp32_connected ? '🟢 ESP32 bağlı' : '🔴 ESP32 bağlı değil';
}

let toastTimer;
function showToast(msg, ok) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + (ok ? 'ok' : 'err');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.className = '', 2500);
}

async function setSetting(key, value) {
  try {
    const r = await fetch('/api/camera/set', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key, value})
    });
    if (r.ok) showToast(key + ' = ' + value, true);
    else showToast('Hata: ' + key, false);
  } catch(e) { showToast('Bağlantı hatası', false); }
}

async function applyAll() {
  try {
    const r = await fetch('/api/camera/apply_all', {method:'POST'});
    const d = await r.json();
    if (r.ok) showToast('✅ ' + d.applied + ' ayar uygulandı', true);
    else showToast(d.detail || 'Hata', false);
  } catch(e) { showToast('Bağlantı hatası', false); }
}

async function getFromEsp() {
  try {
    const r = await fetch('/api/camera/get_from_esp', {method:'POST'});
    const d = await r.json();
    if (r.ok) { setControls(d); showToast("✅ ESP32'den alındı", true); }
    else showToast(d.detail || 'Hata', false);
  } catch(e) { showToast('Bağlantı hatası', false); }
}

async function resetDefaults() {
  const defaults = {framesize:5,quality:12,brightness:0,contrast:0,saturation:0,sharpness:0,denoise:0,special_effect:0,whitebal:1,awb_gain:1,wb_mode:0,exposure_ctrl:1,aec2:0,ae_level:0,aec_value:300,gain_ctrl:1,agc_gain:0,gainceiling:0,bpc:0,wpc:1,raw_gma:1,lenc:1,hmirror:1,vflip:1,dcw:1,colorbar:0};
  setControls(defaults);
  for (const [k, v] of Object.entries(defaults)) await setSetting(k, v);
}

function applyPreset(name) {
  const presets = {
    hq:   {framesize:10, quality:8},
    hfps: {framesize:8, quality:20},
    night:{brightness:2, contrast:1, saturation:-1, exposure_ctrl:1, aec2:1}
  };
  const p = presets[name];
  for (const [k, v] of Object.entries(p)) {
    const el = document.getElementById(k);
    if (el) { el.type === 'checkbox' ? (el.checked = !!v) : (el.value = v); updateVal(k); }
    setSetting(k, v);
  }
}

async function pollHealth() {
  try {
    const r = await fetch('/health');
    const d = await r.json();
    document.getElementById('fps-display').textContent = 'FPS: ' + d.fps;
    document.getElementById('conn-display').textContent = d.fps > 0 ? '🟢 Canlı' : '🔴 Sinyal yok';
    document.getElementById('esp-status').textContent = d.esp32_connected ? '🟢 ESP32 bağlı' : '🔴 ESP32 bağlı değil';
  } catch(e) {}
}

// Init
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
