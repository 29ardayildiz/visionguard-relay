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
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
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

templates = Jinja2Templates(directory="templates")

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
async def get_current_user(request: Request, token: str = Cookie(default=None)) -> str:
    def _is_browser() -> bool:
        accept = request.headers.get("accept", "")
        return "text/html" in accept

    if not token:
        if _is_browser():
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        return verify_token(token)
    except HTTPException:
        if _is_browser():
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"},
            )
        raise


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


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.get("/login")
async def login_page(request: Request, error: int = 0):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


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


# ── Page routes ───────────────────────────────────────────────────────────────
@app.get("/")
async def index(request: Request, _: str = Depends(get_current_user)):
    return templates.TemplateResponse("viewer.html", {"request": request})


@app.get("/admin")
async def admin_panel(request: Request, _: str = Depends(get_current_user)):
    return templates.TemplateResponse("admin.html", {"request": request})


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
    cx, cy = 256, 256
    draw.rounded_rectangle([cx-140, cy-90, cx+140, cy+100], radius=28, fill="white")
    draw.ellipse([cx-70, cy-55, cx+70, cy+65], fill="#30d158")
    draw.ellipse([cx-48, cy-33, cx+48, cy+43], fill="white")
    draw.ellipse([cx-32, cy-17, cx+32, cy+27], fill="#1c1c1e")
    draw.rounded_rectangle([cx-28, cy-110, cx+28, cy-88], radius=8, fill="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
