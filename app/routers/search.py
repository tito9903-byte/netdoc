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
from app.services.search_service import global_search


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
