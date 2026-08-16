# Tarayıcı istemcilerine (/ws/client) push mesajı yayınlayan yardımcı katman.
# routers/stream.py (ESP32 frame/bağlantı olayları) ve routers/camera.py
# (ayar değişiklikleri) buradan çağırır — döngüsel import'u önlemek için
# broadcast mantığı router'ların dışında, ayrı bir modülde tutulur.

import json
import time

from . import state

_HEALTH_THROTTLE_S = 0.5
_last_health_broadcast = 0.0


async def _send_all(payload: dict) -> None:
    if not state.browser_clients:
        return
    data = json.dumps(payload)
    dead: list = []
    for ws in list(state.browser_clients):
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.browser_clients.discard(ws)


async def broadcast_health(force: bool = False) -> None:
    """ESP32 bağlantı durumu / FPS değiştiğinde tüm tarayıcı client'larına push eder.

    Her frame'de tetiklenebildiği için varsayılan olarak throttle'lanır
    (en fazla 2 mesaj/sn); bağlantı kurulma/kopma gibi anlık durum
    değişikliklerinde `force=True` ile throttle bypass edilir.
    """
    global _last_health_broadcast
    now = time.monotonic()
    if not force and (now - _last_health_broadcast) < _HEALTH_THROTTLE_S:
        return
    _last_health_broadcast = now
    await _send_all({"type": "health", **state.health_snapshot()})


async def broadcast_settings() -> None:
    await _send_all({
        "type": "settings",
        **state.camera_settings,
        "esp32_connected": state.is_esp32_connected(),
    })
