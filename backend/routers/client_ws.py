# Tarayıcı için kalıcı push kanalı — ESP32'nin bağlandığı /ws (routers/stream.py)
# ile karıştırılmamalı, o kanal dokunulmazdır. Bu endpoint tamamen ayrı ve yeni.

import json
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import state
from ..core.security import verify_token

router = APIRouter()


def _origin_allowed(websocket: WebSocket) -> bool:
    """SameSite=Strict cookie zaten cross-site bağlantılarda cookie'yi
    taşımıyor, ama bu tek katman — derinlemesine savunma için Origin
    header'ı da kendi host'umuzla karşılaştırılıyor. Tarayıcılar WS
    handshake'inde Origin'i HER ZAMAN gönderir; göndermeyen istemciler
    (wscat gibi, ?token= fallback'ini kullanan) tarayıcı olmadığı için
    reddedilmiyor — zaten token zorunluluğu onlar için birincil koruma.
    NOT: Bu kontrol yalnızca `/ws/client`'a uygulanıyor — ESP32'nin
    bağlandığı `/ws` (stream.py) bir tarayıcı olmadığı için Origin
    göndermeyebilir/farklı davranabilir, o kanala dokunulmuyor."""
    origin = websocket.headers.get("origin")
    if origin is None:
        return True
    origin_host = urlsplit(origin).netloc
    request_host = websocket.headers.get("host", "")
    return origin_host == request_host


@router.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    if not _origin_allowed(websocket):
        await websocket.close(code=1008)
        return

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
