from slowapi import Limiter
from slowapi.util import get_remote_address

# Ayrı bir modülde tanımlanıyor ki router'lar (stream.py, camera.py)
# `@limiter.limit(...)` dekoratörünü kullanmak için `app.py`'yi import
# etmesin — aksi halde app.py -> routers -> app.py döngüsel import'u
# oluşurdu (app.py zaten router'ları include_router ile import ediyor).
# key_func=get_remote_address artık Procfile'daki --proxy-headers ile
# Render'ın proxy'si arkasında da gerçek istemci IP'sini görüyor (bkz.
# REMEDIATION_PLAN_LOG.md Faz 5).
limiter = Limiter(key_func=get_remote_address)
