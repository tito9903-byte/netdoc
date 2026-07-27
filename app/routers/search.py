from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
)
from app.core.config import get_settings
from app.services.lldp_eos_support import install_lldp_eos_support
from app.services.lldp_matching_support import install_lldp_matching_support
from app.services.lldp_privilege_support import install_lldp_privilege_support
from app.services.lldp_vendor_support import install_lldp_vendor_support
from app.services.search_service import global_search


# El router de búsqueda ya se monta directamente en app.main junto al resto de
# documentación. Instalar aquí los adaptadores LLDP garantiza que estén activos
# antes de registrar las rutas finales.
install_lldp_privilege_support()
install_lldp_eos_support()
install_lldp_vendor_support()
install_lldp_matching_support()


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "search",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = ""):
    redirect = access_redirect(request, "search.view")
    if redirect:
        return redirect

    result = await global_search(q)
    netbox_connected = not any(
        section.get("error")
        for section in result.get("sections", [])
    )

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            **context(
                request,
                page_title="Búsqueda global",
                page_subtitle=(
                    "Localiza equipos, interfaces, racks, sitios y cables"
                ),
                netbox_connected=netbox_connected,
            ),
            **result,
        },
    )


@router.get("/api/search")
async def search_api(request: Request, q: str = ""):
    unauthorized = api_access_response(request, "search.view")
    if unauthorized:
        return unauthorized

    if len(q.strip()) < 2:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Escribe al menos dos caracteres.",
            },
        )

    return {
        "ok": True,
        **(await global_search(q)),
    }


# Estos routers se agrupan aquí para conservar compatibilidad con la estructura
# actual. Una futura separación del bootstrap los moverá a app/main.py.
from app.routers.change_plans import router as change_plans_router
from app.routers.device_components import router as device_components_router
from app.routers.device_images import router as device_images_router
from app.routers.device_management import router as device_management_router
from app.routers.device_management_api import router as device_management_api_router
from app.routers.documentation import router as documentation_router
from app.routers.hardware import router as hardware_router
from app.routers.lldp_discovery import router as lldp_discovery_router
from app.routers.lldp_run_redirect import router as lldp_run_redirect_router
from app.routers.rack_create import router as rack_create_router


router.include_router(documentation_router)
router.include_router(device_images_router)
router.include_router(rack_create_router)
router.include_router(change_plans_router)
router.include_router(hardware_router)
router.include_router(device_management_router)
router.include_router(device_components_router)
router.include_router(device_management_api_router)
router.include_router(lldp_run_redirect_router)
router.include_router(lldp_discovery_router)
