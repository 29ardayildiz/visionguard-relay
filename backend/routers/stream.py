# ── ESP32 kontratı — DOKUNULMAZ ──────────────────────────────────────────────
# /ws (path + ?key= query param + JSON komut şeması) ve /push (X-Secret-Key
# header) burada tanımlıdır. CLAUDE.md §2.1: bu endpoint'lerin path'i, query
# param adı ve mesaj formatı hiçbir fazda değiştirilemez.

import json
import time

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from .. import hub, state
from ..core import config
from ..core.security import get_current_user

router = APIRouter()


# ── Stream endpoint ───────────────────────────────────────────────────────────
@router.get("/stream")
async def stream(_: str = Depends(get_current_user)):
    async def generate():
        while True:
            await state.frame_event.wait()
            state.frame_event.clear()
            if state.latest_frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" +
                       state.latest_frame + b"\r\n")

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Health endpoint ───────────────────────────────────────────────────────────
@router.get("/health")
async def health(_: str = Depends(get_current_user)):
    return {"status": "ok", **state.health_snapshot()}


# ── ESP32 push endpoint ───────────────────────────────────────────────────────
@router.post("/push")
async def push_frame(request: Request):
    key = request.headers.get("X-Secret-Key")
    if key != config.SECRET_KEY:
        return Response("Unauthorized", status_code=401)
    state.latest_frame = await request.body()
    state.frame_times.append(time.monotonic())
    state.frame_event.set()
    await hub.broadcast_health()
    return {"status": "ok"}


# ── ESP32 WebSocket endpoint ──────────────────────────────────────────────────
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    key = websocket.query_params.get("key")
    if key != config.SECRET_KEY:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    state.esp32_websocket = websocket
    await hub.broadcast_health(force=True)
    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                state.latest_frame = msg["bytes"]
                state.frame_times.append(time.monotonic())
                state.frame_event.set()
                await hub.broadcast_health()
            elif "text" in msg and msg["text"]:
                text = msg["text"]
                if text.startswith("{"):
                    try:
                        data = json.loads(text)
                        if "framesize" in data or "quality" in data:
                            state.camera_settings.update({k: v for k, v in data.items() if k in state.camera_settings})
                            state.esp32_settings_event.set()
                            await hub.broadcast_settings()
                    except json.JSONDecodeError:
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        state.esp32_websocket = None
        await hub.broadcast_health(force=True)
