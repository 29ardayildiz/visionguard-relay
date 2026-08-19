import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Cookie, HTTPException, Request, status

from .. import state
from . import config


# ── Şifre doğrulama ────────────────────────────────────────────────────────────
# `passlib` yerine doğrudan `bcrypt` kullanılıyor (REMEDIATION_PLAN_LOG.md
# Faz 11) — `passlib` 2020'den beri güncellenmiyor ve `bcrypt`'in 4.1+
# sürümleriyle bilinen bir uyumsuzluğu var, bu yüzden proje `bcrypt==4.0.1`'e
# sabitlenmek zorunda kalmıştı. `ADMIN_PASSWORD_HASH` formatı ($2b$...)
# değişmedi, mevcut hash'ler aynen çalışmaya devam ediyor.
def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ── Brute-force protection ────────────────────────────────────────────────────
def check_brute_force(ip: str) -> None:
    now = time.monotonic()
    attempts = [t for t in state.failed_attempts.get(ip, []) if now - t < config.BAN_WINDOW]
    state.failed_attempts[ip] = attempts
    if len(attempts) >= config.MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")


def record_failed_attempt(ip: str) -> None:
    state.failed_attempts.setdefault(ip, []).append(time.monotonic())


# ── JWT helpers ─────────────────────────────────────────────────────────────────
# `python-jose` yerine `PyJWT` kullanılıyor (REMEDIATION_PLAN_LOG.md Faz 11) —
# daha aktif bakımlı, Python ekosisteminde JWT için yaygın standart; ayrıca
# `python-jose[cryptography]`'nin gerektirdiği ama bu uygulamada hiç
# kullanılmayan (yalnızca HS256 var, RSA/EC yok) `cryptography` bağımlılığı
# da kalkmış oluyor. API şekli neredeyse birebir aynı, davranış değişmedi.
def create_token(username: str) -> str:
    payload = {
        "sub": username,
        # Logout'ta sunucu tarafında gerçek iptal sağlayan sürüm damgası —
        # bkz. state.py'deki token_version tanımı.
        "tv": state.token_version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> str:
    try:
        data = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        if data.get("tv") != state.token_version:
            raise jwt.InvalidTokenError("Token version mismatch (logout sonrası iptal edilmiş)")
        return data["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── Auth dependency ───────────────────────────────────────────────────────────
async def get_current_user(request: Request, token: str = Cookie(default=None)) -> str:
    def _is_browser() -> bool:
        accept = request.headers.get("accept", "")
        return "text/html" in accept

    if not token:
        if _is_browser():
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        return verify_token(token)
    except HTTPException:
        if _is_browser():
            raise HTTPException(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": "/login"},
            )
        raise
