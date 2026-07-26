from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
)
from app.core.config import get_settings
from app.routers.lldp_discovery import router as lldp_discovery_router
from app.services.system_service import collect_system_health


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

# El módulo de sistema ya está registrado directamente en app.main y actúa como
# punto estable para montar el descubrimiento LLDP sin acoplarlo a racks/modelos.
router.include_router(lldp_discovery_router)


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "system",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


@router.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    redirect = access_redirect(request, "system.view")
    if redirect:
        return redirect

    health = collect_system_health()
    return templates.TemplateResponse(
        request=request,
        name="system.html",
        context=context(
            request,
            page_title="Sistema",
            page_subtitle="Salud del servidor y del proceso de NetDoc",
            health=health,
        ),
    )


@router.get("/api/system")
async def system_api(request: Request):
    unauthorized = api_access_response(request, "system.view")
    if unauthorized:
        return unauthorized

    return {
        "ok": True,
        "health": collect_system_health(),
    }
