from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .routers import auth, camera, pages, pwa, stream

# ── App ───────────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter


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


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(stream.router)
app.include_router(camera.router)
app.include_router(pwa.router)

# NOT (Faz 7 — Cutover): frontend/dist statik mount'u burada, tüm router
# include'larından SONRA eklenecek (CLAUDE.md §3, §6.3):
#   app.mount("/", StaticFiles(directory="frontend/dist", html=True))
# O zamana kadar pages.router yukarıdaki Jinja2 sayfalarını serve eder.
