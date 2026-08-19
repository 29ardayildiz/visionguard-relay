import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import hub, state
from ..core.limiter import limiter
from ..core.security import get_current_user

router = APIRouter(prefix="/api/camera")


@router.get("/settings")
async def get_camera_settings(_: str = Depends(get_current_user)):
    return {**state.camera_settings, "esp32_connected": state.is_esp32_connected()}


@router.post("/set")
@limiter.limit("120/minute")
async def set_camera_setting(request: Request, _: str = Depends(get_current_user)):
    body = await request.json()
    key = body.get("key")
    value = body.get("value")

    if key not in state.camera_settings:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

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
