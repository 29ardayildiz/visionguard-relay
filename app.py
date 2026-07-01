# Required environment variables:
# SECRET_KEY          - ESP32 WebSocket authentication key
# JWT_SECRET          - Random 32+ char string for JWT signing
# ADMIN_USERNAME      - Login username
# ADMIN_PASSWORD_HASH - bcrypt hash of password
# Generate password hash: python3 -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('YOUR_PASSWORD'))"

import asyncio
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

# ── Brute-force protection ────────────────────────────────────────────────────
failed_attempts: dict[str, list[float]] = {}
BAN_WINDOW   = 15 * 60   # seconds
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
  </style>
</head>
<body>
  <img src="/stream" alt="Live feed">
  <div id="info">
    <div id="status">⏳ Bekleniyor...</div>
    <div id="fps">FPS: --</div>
  </div>
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
async def index(user: str = Depends(get_current_user)):
    return HTMLResponse(content=VIEWER_HTML)


# ── Stream endpoint ───────────────────────────────────────────────────────────
@app.get("/stream")
async def stream(user: str = Depends(get_current_user)):
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
async def health(user: str = Depends(get_current_user)):
    fps = 0.0
    if len(frame_times) >= 2:
        elapsed = frame_times[-1] - frame_times[0]
        if elapsed > 0:
            fps = (len(frame_times) - 1) / elapsed
    return {"status": "ok", "fps": round(fps, 1)}


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
    global latest_frame
    key = websocket.query_params.get("key")
    if key != SECRET_KEY:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            frame = await websocket.receive_bytes()
            latest_frame = frame
            frame_times.append(time.monotonic())
            frame_event.set()
    except WebSocketDisconnect:
        pass
