import asyncio
import time
from collections import deque

from fastapi import WebSocket

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

# ── Browser client channel (/ws/client) ───────────────────────────────────────
browser_clients: set[WebSocket] = set()


def is_esp32_connected() -> bool:
    if esp32_websocket is not None:
        return True
    if frame_times:
        return (time.monotonic() - frame_times[-1]) < 5.0
    return False


def health_snapshot() -> dict:
    fps = 0.0
    if len(frame_times) >= 2:
        elapsed = frame_times[-1] - frame_times[0]
        if elapsed > 0:
            fps = (len(frame_times) - 1) / elapsed
    connected = is_esp32_connected()
    mode = "websocket" if esp32_websocket is not None else ("push" if connected else "none")
    return {"fps": round(fps, 1), "esp32_connected": connected, "mode": mode}
