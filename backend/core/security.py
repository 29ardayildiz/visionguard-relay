import time
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from .. import state
from . import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Brute-force protection ────────────────────────────────────────────────────
def check_brute_force(ip: str) -> None:
    now = time.monotonic()
    attempts = [t for t in state.failed_attempts.get(ip, []) if now - t < config.BAN_WINDOW]
    state.failed_attempts[ip] = attempts
    if len(attempts) >= config.MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")


def record_failed_attempt(ip: str) -> None:
    state.failed_attempts.setdefault(ip, []).append(time.monotonic())


# ── JWT helpers ───────────────────────────────────────────────────────────────
def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> str:
    try:
        data = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return data["sub"]
    except JWTError:
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
