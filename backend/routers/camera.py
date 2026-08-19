import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import hub, state
from ..core.limiter import limiter
from ..core.limits import read_body_limited
from ..core.security import get_current_user

router = APIRouter(prefix="/api/camera")

# Bir kamera ayarı isteğinin gerçek gövdesi (`{"key":"...","value":123}`)
# birkaç on byte'tır — 10 KB, her türlü meşru payload'ın çok üzerinde ama
# devasa bir JSON gövdesiyle bellek tüketimini engelleyecek kadar sıkı.
SET_MAX_BYTES = 10 * 1024

# ESP32-CAM (OV2640/benzeri) standart kamera API'sinin bilinen değer
# aralıkları — Espressif'in resmi CameraWebServer örneğinin ve yaygın
# esp32-cam projelerinin camera_httpd implementasyonundaki genel bilgiye
# dayanıyor (bu projenin ESP32 firmware kaynağına bakılmadan derlendi,
# CLAUDE.md Kural 1 gereği o repo hiç açılmadı). Aralığı burada net
# bilinmeyen alanlar (ör. "denoise") listede yok — onlar için yalnızca
# tip kontrolü uygulanır, üst/alt sınır dayatılmaz.
SETTING_RANGES: dict[str, tuple[int, int]] = {
    "framesize": (0, 13),
    "quality": (0, 63),
    "brightness": (-2, 2),
    "contrast": (-2, 2),
    "saturation": (-2, 2),
    "sharpness": (-2, 2),
    "special_effect": (0, 6),
    "whitebal": (0, 1),
    "awb_gain": (0, 1),
    "wb_mode": (0, 4),
    "exposure_ctrl": (0, 1),
    "aec2": (0, 1),
    "ae_level": (-2, 2),
    "aec_value": (0, 1200),
    "gain_ctrl": (0, 1),
    "agc_gain": (0, 30),
    "gainceiling": (0, 6),
    "bpc": (0, 1),
    "wpc": (0, 1),
    "raw_gma": (0, 1),
    "lenc": (0, 1),
    "hmirror": (0, 1),
    "vflip": (0, 1),
    "dcw": (0, 1),
    "colorbar": (0, 1),
}


@router.get("/settings")
async def get_camera_settings(_: str = Depends(get_current_user)):
    return {**state.camera_settings, "esp32_connected": state.is_esp32_connected()}


@router.post("/set")
@limiter.limit("120/minute")
async def set_camera_setting(request: Request, _: str = Depends(get_current_user)):
    raw_body = await read_body_limited(request, SET_MAX_BYTES)
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    key = body.get("key")
    value = body.get("value")

    if key not in state.camera_settings:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    # `bool` Python'da `int`'in alt sınıfı olduğu için `isinstance` kullanmak
    # JSON `true`/`false`'u da kabul ederdi — `type(value) is int` ile bunu
    # kasıtlı olarak dışarıda bırakıyoruz, ESP32'ye her zaman düz bir tamsayı
    # (`json.dumps`'ta `true` değil `1`/`0`) gitmesi garanti oluyor.
    if type(value) is not int:
        raise HTTPException(status_code=400, detail=f"'{key}' must be an integer")

    value_range = SETTING_RANGES.get(key)
    if value_range is not None:
        low, high = value_range
        if not (low <= value <= high):
            raise HTTPException(
                status_code=400, detail=f"'{key}' must be between {low} and {high}"
            )

    state.camera_settings[key] = value

    if state.esp32_websocket is not None:
        try:
            await state.esp32_websocket.send_text(json.dumps({"cmd": "set", "key": key, "value": value}))
        except Exception:
            pass

    await hub.broadcast_settings()
    return {"status": "ok", "key": key, "value": value}


@router.post("/apply_all")
@limiter.limit("20/minute")
async def apply_all_settings(request: Request, _: str = Depends(get_current_user)):
    if state.esp32_websocket is None:
        return {"status": "ok", "applied": 0, "note": "push_mode"}
    count = 0
    for key, value in state.camera_settings.items():
        try:
            await state.esp32_websocket.send_text(json.dumps({"cmd": "set", "key": key, "value": value}))
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            break
    await hub.broadcast_settings()
    return {"status": "ok", "applied": count}


@router.post("/get_from_esp")
@limiter.limit("20/minute")
async def get_from_esp(request: Request, _: str = Depends(get_current_user)):
    if state.esp32_websocket is None:
        raise HTTPException(status_code=503, detail="ESP32 WebSocket not connected (push-only mode)")
    state.esp32_settings_event.clear()
    try:
        await state.esp32_websocket.send_text(json.dumps({"cmd": "get_settings"}))
        await asyncio.wait_for(state.esp32_settings_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="ESP32 did not respond in time")
    return {**state.camera_settings, "esp32_connected": True}
