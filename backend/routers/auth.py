from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from .. import state
from ..core import config
from ..core.security import check_brute_force, create_token, pwd_context, record_failed_attempt

router = APIRouter()


# GET /login artık backend'de yok — frontend/dist SPA fallback'i (app.py)
# bu path'i Vue Router'ın LoginView'ine yönlendiriyor. Sadece form submit
# (POST) burada kalıyor.
@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    ip = request.client.host
    check_brute_force(ip)

    if username != config.ADMIN_USERNAME or not pwd_context.verify(password, config.ADMIN_PASSWORD_HASH):
        record_failed_attempt(ip)
        return RedirectResponse(url="/login?error=1", status_code=303)

    token = create_token(username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400 * 30,
    )
    return response


@router.get("/logout")
async def logout():
    # Cookie'yi silmek yeterli değil — JWT stateless olduğu için eski token
    # hâlâ geçerli kalırdı. Sürüm sayacını artırmak, o ana kadar üretilmiş
    # TÜM token'ları (bu isteğin cookie'sindeki dahil) anında geçersiz kılar.
    state.token_version += 1
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("token")
    return response
