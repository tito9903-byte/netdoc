from __future__ import annotations

import asyncio

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
    csrf_token,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.services.access_service import record_audit
from app.services.rack_create_service import (
    RackCreateService,
    RackCreateServiceError,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "rack_create",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def audit_rack_action(
    request: Request,
    *,
    detail: str,
    success: bool,
    resource_id: str | int | None = None,
) -> None:
    user_id = request.session.get("user_id")
    ip_address, user_agent = request_client_data(request)
    with session_scope() as session:
        record_audit(
            session,
            action="RACK_CREATE",
            resource="rack",
            resource_id=resource_id,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(
                request.session.get("username") or "desconocido"
            ),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


async def render_page(
    request: Request,
    *,
    form_data: dict[str, str] | None = None,
    errors: list[str] | None = None,
):
    service = RackCreateService()
    try:
        sites, locations, roles, rack_types, choices = await asyncio.gather(
            service.list_sites(),
            service.list_locations(),
            service.list_roles(),
            service.list_rack_types(),
            service.rack_choices(),
        )
    except RackCreateServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                page_title="Crear rack",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudieron cargar los datos del rack",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="rack_create.html",
        context=context(
            request,
            page_title="Crear rack",
            page_subtitle=(
                "Alta guiada de ubicación, capacidad e identificación física"
            ),
            sites=sites,
            locations=locations,
            roles=roles,
            rack_types=rack_types,
            rack_statuses=choices["statuses"],
            rack_widths=choices["widths"],
            form_data=form_data or {},
            errors=errors or [],
            csrf_token=csrf_token(request, "rack_create"),
        ),
    )


@router.get("/racks/actions/new", response_class=HTMLResponse)
async def new_rack_page(request: Request):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await render_page(request)


@router.get("/api/rack-locations")
async def rack_locations(request: Request, site_id: int):
    unauthorized = api_access_response(request, "devices.create")
    if unauthorized:
        return unauthorized

    try:
        locations = await RackCreateService().get_all(
            "/api/dcim/locations/",
            params={
                "site_id": site_id,
                "status": "active",
                "ordering": "name",
            },
        )
    except RackCreateServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": exc.message},
        )

    return {
        "ok": True,
        "results": [
            {
                "id": item.get("id"),
                "name": (
                    item.get("display")
                    or item.get("name")
                    or "Sin nombre"
                ),
            }
            for item in locations
        ],
    }


@router.post("/racks/actions/new")
async def create_rack(
    request: Request,
    csrf: str = Form(...),
    name: str = Form(...),
    site_id: int = Form(...),
    location_id: str = Form(""),
    rack_type_id: str = Form(""),
    role_id: str = Form(""),
    status: str = Form("active"),
    facility_id: str = Form(""),
    serial: str = Form(""),
    asset_tag: str = Form(""),
    u_height: int = Form(42),
    width: int = Form(19),
    starting_unit: int = Form(1),
    desc_units: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    form_data = {
        "name": name,
        "site_id": str(site_id),
        "location_id": location_id,
        "rack_type_id": rack_type_id,
        "role_id": role_id,
        "status": status,
        "facility_id": facility_id,
        "serial": serial,
        "asset_tag": asset_tag,
        "u_height": str(u_height),
        "width": str(width),
        "starting_unit": str(starting_unit),
        "desc_units": desc_units,
        "description": description,
    }

    errors: list[str] = []
    if not verify_csrf(request, csrf, "rack_create"):
        errors.append("La sesión del formulario expiró. Recarga la página.")
    if not settings.netbox_write_enabled:
        errors.append(
            "La escritura está desactivada en este entorno. "
            "El rack no fue enviado a NetBox."
        )
    if not name.strip():
        errors.append("El nombre del rack es obligatorio.")
    if u_height < 1 or u_height > 200:
        errors.append("La altura debe estar entre 1U y 200U.")
    if width not in {10, 19, 21, 23}:
        errors.append("El ancho de rack seleccionado no es válido.")
    if starting_unit < 0 or starting_unit > 1000:
        errors.append("La unidad inicial no es válida.")

    if errors:
        return await render_page(
            request,
            form_data=form_data,
            errors=errors,
        )

    try:
        created = await RackCreateService().create_rack(
            name=name,
            site_id=site_id,
            location_id=int(location_id) if location_id else None,
            rack_type_id=int(rack_type_id) if rack_type_id else None,
            role_id=int(role_id) if role_id else None,
            status=status,
            facility_id=facility_id,
            serial=serial,
            asset_tag=asset_tag,
            u_height=u_height,
            width=width,
            starting_unit=starting_unit,
            desc_units=desc_units == "on",
            description=description,
        )
    except (ValueError, RackCreateServiceError) as exc:
        message = (
            exc.message
            if isinstance(exc, RackCreateServiceError)
            else "Una de las referencias seleccionadas no es válida."
        )
        audit_rack_action(
            request,
            detail=message,
            success=False,
        )
        return await render_page(
            request,
            form_data=form_data,
            errors=[message],
        )

    rack_id = created.get("id")
    audit_rack_action(
        request,
        resource_id=rack_id,
        detail=f"Rack creado: {name.strip()}.",
        success=True,
    )
    return RedirectResponse(
        url=f"/racks/{rack_id}" if rack_id else "/racks",
        status_code=303,
    )
