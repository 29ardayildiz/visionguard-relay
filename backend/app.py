from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .core.limiter import limiter
from .routers import auth, camera, client_ws, stream

# ── App ───────────────────────────────────────────────────────────────────────
# Swagger/ReDoc/OpenAPI şeması yalnızca dahili kullanım içindi ama varsayılan
# ayarla herkese açık kalıyordu (tüm route/parametre/response şemasını
# kimlik doğrulaması olmadan ifşa ediyordu) — üçü de kapatıldı.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# İlgili route'lardaki @limiter.limit(...) dekoratörlerini gerçekten
# devreye sokan katman — Limiter instance'ı tek başına yeterli değil.
# /push ve /ws (ESP32 kanalı) hiçbir route'ta limit dekoratörü taşımıyor,
# bu yüzden bu middleware onları da etkilemez.
app.add_middleware(SlowAPIMiddleware)


class SelectiveGZipMiddleware:
    """GZipMiddleware sarmalayıcısı — `/stream` (ESP32'den gelen, zaten
    JPEG-sıkıştırılmış MJPEG canlı akışı) sıkıştırma kapsamı DIŞINDA
    tutulur: JPEG verisi gzip ile neredeyse hiç küçülmez, her frame'i
    tekrar sıkıştırmaya çalışmak canlı yayına gereksiz CPU yükü/gecikme
    ekler. Diğer tüm response'lar (JSON API'ler, HTML, statik dosyalar)
    normal şekilde sıkıştırılır."""

    def __init__(self, app: ASGIApp, **gzip_kwargs: object) -> None:
        self.app = app
        self.gzip_app = GZipMiddleware(app, **gzip_kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/stream":
            await self.app(scope, receive, send)
        else:
            await self.gzip_app(scope, receive, send)


app.add_middleware(SelectiveGZipMiddleware, minimum_size=500)


# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Render zaten HTTP->HTTPS yönlendiriyor ama HSTS olmadan tarayıcı bunu
    # "hatırlamıyor" — ilk istek hâlâ düz HTTP ile başlayabilir. max-age 2 yıl,
    # Cache-Control: no-store'dan bağımsız (HSTS ayrı bir tarayıcı state'i).
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # CLAUDE.md §5 zaten harici script/CDN/font yasakladığı için 'self' dışına
    # hiç çıkılmıyor. style-src'de 'unsafe-inline' gerekiyor: Vue'nun `:style`
    # binding'leri (safe-area inset'leri, zoom transform'ları vb.) runtime'da
    # inline style="" attribute'u üretiyor — CSP bunu "unsafe-inline" olmadan
    # bloklar. Script tarafında hiç inline/eval yok, 'self' yeterli.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    # Uygulama konum/mikrofon/kamera gibi tarayıcı API'lerini hiç kullanmıyor;
    # ekranın uyanık kalmasını sağlayan Wake Lock ise fiilen kullanılıyor
    # (ViewerView canlı izleme sırasında) — o yüzden istisna tutuluyor.
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), usb=(), payment=()"
    )
    # Kişisel/tek-kullanıcılı bir kamera uygulaması — robots.txt ve <meta
    # name="robots"> yanında, tüm response'larda (API dahil) arama motoru
    # botlarına indexleme yapmamalarını söyleyen üçüncü katman.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    # Vite'ın içerik-hash'li /assets/* dosyaları güvenle sonsuza kadar
    # cache'lenebilir (dosya adı değişmeden içerik değişmez). Diğer her şey
    # (index.html, API yanıtları) no-store kalır — özellikle login/admin
    # gibi hassas sayfaların tarayıcıda önbelleklenmemesi için.
    if not request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ── Routers (ESP32 kontratı dahil — path sırası önemli değil, hepsi statik
# mount'tan ÖNCE include edilmiş olması yeterli) ───────────────────────────────
app.include_router(auth.router)
app.include_router(stream.router)
app.include_router(camera.router)
app.include_router(client_ws.router)


class SPAStaticFiles(StaticFiles):
    """StaticFiles + SPA fallback: bilinmeyen bir path (ör. /admin'e doğrudan
    girmek/sayfa yenilemek) 404 yerine index.html'e düşer, Vue Router
    client-side devralır. Düz `StaticFiles(html=True)` bunu yapmaz — sadece
    "/" ve dizin path'lerinde index.html sunar. Starlette, dosya bulunamayınca
    bir Response değil HTTPException(404) fırlatıyor — bu yüzden except ile
    yakalayıp index.html'e düşüyoruz."""

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# Statik mount tüm API router'larından SONRA eklenir (CLAUDE.md §3, §6.3) —
# aksi halde /api/*, /ws, /ws/client, /stream, /push gibi path'ler bu
# fallback tarafından gölgelenir.
app.mount("/", SPAStaticFiles(directory="frontend/dist", html=True), name="spa")
