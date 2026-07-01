import asyncio
import os
import time
from collections import deque

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse

load_dotenv()

app = FastAPI()

SECRET_KEY = os.getenv("SECRET_KEY")

latest_frame: bytes | None = None
frame_event = asyncio.Event()
frame_times: deque[float] = deque(maxlen=30)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global latest_frame
    key = websocket.query_params.get("key")
    if key != SECRET_KEY:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    print("ESP32 bağlandı")

    try:
        while True:
            frame = await websocket.receive_bytes()
            latest_frame = frame
            frame_times.append(time.monotonic())
            frame_event.set()
    except WebSocketDisconnect:
        print("ESP32 bağlantısı kesildi")


@app.get("/stream")
async def stream():
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


@app.get("/health")
async def health():
    fps = 0.0
    if len(frame_times) >= 2:
        elapsed = frame_times[-1] - frame_times[0]
        if elapsed > 0:
            fps = (len(frame_times) - 1) / elapsed
    return {"status": "ok", "fps": round(fps, 1)}


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
    <head>
        <title>VisionGuard Remote</title>
        <style>
            body {
                background: black;
                margin: 0;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                font-family: sans-serif;
                color: white;
            }
            img { max-width: 100%; height: auto; }
            #info { margin-top: 10px; font-size: 1.1em; text-align: center; }
        </style>
    </head>
    <body>
        <img src="/stream">
        <div id="info">
            <div id="status">⏳ Bekleniyor...</div>
            <div id="fps">FPS: --</div>
        </div>
        <script>
            async function update() {
                try {
                    const r = await fetch('/health');
                    const d = await r.json();
                    document.getElementById('fps').textContent = 'FPS: ' + d.fps;
                    document.getElementById('status').textContent =
                        d.fps > 0 ? '🟢 Canlı' : '🔴 Bağlantı yok';
                } catch(e) {
                    document.getElementById('status').textContent = '🔴 Bağlantı yok';
                }
            }
            setInterval(update, 2000);
            update();
        </script>
    </body>
    </html>
    """