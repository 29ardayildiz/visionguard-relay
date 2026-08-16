# Geçiş dönemi Jinja2 sayfa route'ları — Faz 7 (Cutover) tamamlandığında,
# frontend/dist statik mount'a devredilip bu dosya kaldırılacak.

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from ..core.security import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def index(request: Request, _: str = Depends(get_current_user)):
    return templates.TemplateResponse(request, "viewer.html")


@router.get("/admin")
async def admin_panel(request: Request, _: str = Depends(get_current_user)):
    return templates.TemplateResponse(request, "admin.html")
