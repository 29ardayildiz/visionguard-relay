# Geçiş dönemi PWA route'ları — Faz 6/7'de vite-plugin-pwa'nın ürettiği statik
# manifest/ikon dosyaları devreye girince bu router kaldırılacak.

import io

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw

router = APIRouter()


@router.get("/manifest.json")
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


@router.get("/icon.png")
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
