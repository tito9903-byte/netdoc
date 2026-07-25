from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
)
from app.core.config import get_settings
from app.services.navigation_read_service import (
    NavigationReadError,
    NavigationReadService,
)
from app.services.rack_presentation import nested_label, prepare_elevation
from app.services.rack_report_detailed_service import (
    RackReportError,
    build_rack_report,
)
from app.services.rack_service import RackService, RackServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def is_authenticated(request: Request) -> bool:
    return (
        request.session.get("authenticated") is True
        and bool(request.session.get("username"))
    )


def login_redirect(request: Request) -> RedirectResponse | None:
    if is_authenticated(request):
        return None

    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    return RedirectResponse(
        url=f"/login?{urlencode({'next': next_url})}",
        status_code=303,
    )


def context(
    request: Request,
    *,
    current_page: str = "racks",
    **extra: object,
) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": current_page,
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def parse_optional_int(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


@router.get("/racks", response_class=HTMLResponse)
async def racks_page(
    request: Request,
    site_id: str = "",
    q: str = "",
):
    redirect = access_redirect(request, "racks.view")
    if redirect:
        return redirect

    selected_site_id = parse_optional_int(site_id)
    try:
        sites, racks = await NavigationReadService().rack_catalog(
            site_id=selected_site_id,
            query=q,
        )
    except NavigationReadError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                page_title="Racks",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudieron cargar los racks",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="racks.html",
        context=context(
            request,
            page_title="Racks",
            page_subtitle=(
                "Catálogo rápido; la ocupación física se calcula al abrir cada rack"
            ),
            sites=sites,
            racks=racks,
            selected_site_id=selected_site_id,
            query=q,
        ),
    )


@router.get("/topology")
async def legacy_topology_redirect(
    request: Request,
    site_id: str = "",
):
    """Compatibilidad: la vista 3D solo se selecciona dentro de un rack."""

    redirect = access_redirect(request, "racks.view")
    if redirect:
        return redirect

    query = urlencode({"site_id": site_id}) if site_id.strip() else ""
    target = "/racks"
    if query:
        target = f"{target}?{query}"
    return RedirectResponse(target, status_code=303)


@router.get("/media/device-types/{device_type_id}/{face}")
async def device_type_image(
    request: Request,
    device_type_id: int,
    face: str,
):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied

    try:
        content, content_type, digest = await RackService().get_device_type_image(
            device_type_id,
            face,
        )
    except RackServiceError as exc:
        return Response(
            status_code=exc.status_code or 503,
            content=b"",
            headers={"Cache-Control": "no-store"},
        )

    etag = f'"{digest}"'
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "Cache-Control": "private, no-cache",
                "ETag": etag,
            },
        )

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, no-cache",
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/racks/{rack_id}/report.pdf")
async def rack_inventory_report(
    request: Request,
    rack_id: int,
    face: str = "front",
):
    redirect = access_redirect(request, "racks.view")
    if redirect:
        return redirect

    selected_face = "rear" if face == "rear" else "front"
    service = RackService()
    try:
        rack, devices = await asyncio.gather(
            service.get_rack(rack_id),
            service.list_rack_devices(rack_id),
        )
        elevation = prepare_elevation(rack, devices, selected_face)
        pdf, filename = await run_in_threadpool(
            build_rack_report,
            rack=rack,
            elevation=elevation,
            face=selected_face,
        )
    except RackServiceError as exc:
        return Response(
            status_code=404 if exc.status_code == 404 else 503,
            media_type="text/plain; charset=utf-8",
            content=exc.message,
        )
    except RackReportError as exc:
        return Response(
            status_code=500,
            media_type="text/plain; charset=utf-8",
            content=str(exc),
        )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/racks/{rack_id}", response_class=HTMLResponse)
async def rack_detail_page(
    request: Request,
    rack_id: int,
    face: str = "front",
    view: str = "2d",
):
    redirect = access_redirect(request, "racks.view")
    if redirect:
        return redirect

    selected_face = face if face in {"front", "rear"} else "front"
    selected_view = view if view in {"2d", "3d"} else "2d"
    service = RackService()

    try:
        rack, devices = await asyncio.gather(
            service.get_rack(rack_id),
            service.list_rack_devices(rack_id),
        )
    except RackServiceError as exc:
        status_code = 404 if exc.status_code == 404 else 503
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=status_code,
            context=context(
                request,
                page_title="Rack no disponible",
                page_subtitle="No fue posible cargar el rack",
                error_title="No se pudo consultar el rack",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    elevation = prepare_elevation(rack, devices, selected_face)
    return templates.TemplateResponse(
        request=request,
        name="rack_detail.html",
        context=context(
            request,
            page_title=(
                rack.get("name")
                or rack.get("display")
                or "Rack"
            ),
            page_subtitle=(
                "Vista 2D o 3D basada en posición, cara, imagen y altura del modelo"
            ),
            rack=rack,
            devices=devices,
            selected_face=selected_face,
            selected_view=selected_view,
            rack_site_label=nested_label(rack.get("site"), "Sin sitio"),
            **elevation,
        ),
    )
