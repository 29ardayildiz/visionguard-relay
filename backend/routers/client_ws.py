# Tarayıcı için kalıcı push kanalı — ESP32'nin bağlandığı /ws (routers/stream.py)
# ile karıştırılmamalı, o kanal dokunulmazdır. Bu endpoint tamamen ayrı ve yeni.

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import state
from ..core.security import verify_token

router = APIRouter()


@router.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    # Aynı origin'den açılan tarayıcı WebSocket bağlantıları JWT cookie'sini
    # otomatik gönderir; wscat gibi cookie desteklemeyen istemciler için
    # ?token= query param fallback olarak da kabul edilir.
    token = websocket.cookies.get("token") or websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    state.browser_clients.add(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "health", **state.health_snapshot()}))
        await websocket.send_text(json.dumps({
            "type": "settings",
            **state.camera_settings,
            "esp32_connected": state.is_esp32_connected(),
        }))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state.browser_clients.discard(websocket)
