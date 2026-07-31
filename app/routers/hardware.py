from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    common_session_context,
    csrf_token,
    has_permission,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.services.access_service import record_audit
from app.services.device_type_service import (
    DeviceTypeService,
    DeviceTypeServiceError,
)
from app.services.hardware_service import (
    HardwareService,
    HardwareServiceError,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "device_types",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "can_manage_device_types": has_permission(
            request,
            "devices.create",
        ),
        **extra,
    }


def redirect_with_message(
    path: str,
    *,
    notice: str = "",
    error: str = "",
) -> RedirectResponse:
    params = {
        key: value
        for key, value in {"notice": notice, "error": error}.items()
        if value
    }
    target = path if not params else f"{path}?{urlencode(params)}"
    return RedirectResponse(target, status_code=303)


def audit_event(
    request: Request,
    *,
    action: str,
    resource: str,
    detail: str,
    success: bool,
    resource_id: str | None = None,
) -> None:
    ip_address, user_agent = request_client_data(request)
    user_id = request.session.get("user_id")
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource=resource,
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


def error_page(
    request: Request,
    exc: HardwareServiceError,
    *,
    title: str,
):
    status_code = 404 if exc.status_code == 404 else 503
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        status_code=status_code,
        context=context(
            request,
            page_title=title,
            page_subtitle="No fue posible consultar NetBox",
            error_title=title,
            error_message=exc.message,
            netbox_connected=exc.status_code != 503,
        ),
    )


@router.get("/manufacturers", response_class=HTMLResponse)
async def manufacturers_page(
    request: Request,
    q: str = "",
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    try:
        catalog = await HardwareService().manufacturer_catalog(query=q)
    except HardwareServiceError as exc:
        return error_page(
            request,
            exc,
            title="No se pudieron cargar los fabricantes",
        )

    return templates.TemplateResponse(
        request=request,
        name="manufacturers.html",
        context=context(
            request,
            page_title="Fabricantes",
            page_subtitle="Catálogo reutilizable para modelos de equipos",
            query=q,
            csrf_token=csrf_token(request),
            notice=notice,
            error=error,
            **catalog,
        ),
    )


@router.get("/manufacturers/{manufacturer_id}", response_class=HTMLResponse)
async def manufacturer_detail_page(
    request: Request,
    manufacturer_id: int,
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    try:
        data = await HardwareService().manufacturer_detail(manufacturer_id)
    except HardwareServiceError as exc:
        return error_page(
            request,
            exc,
            title="Fabricante no disponible",
        )

    return templates.TemplateResponse(
        request=request,
        name="manufacturer_detail.html",
        context=context(
            request,
            page_title=str(data["manufacturer"].get("_name")),
            page_subtitle="Datos del fabricante y modelos asociados",
            csrf_token=csrf_token(request),
            notice=notice,
            error=error,
            **data,
        ),
    )


@router.get("/device-types/{device_type_id}", response_class=HTMLResponse)
async def device_type_detail_page(
    request: Request,
    device_type_id: int,
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    try:
        detail, manufacturers, interface_types = await asyncio.gather(
            HardwareService().model_detail(device_type_id),
            DeviceTypeService().list_manufacturers(),
            DeviceTypeService().interface_type_choices(),
        )
    except HardwareServiceError as exc:
        return error_page(
            request,
            exc,
            title="Modelo no disponible",
        )
    except DeviceTypeServiceError as exc:
        return error_page(
            request,
            HardwareServiceError(exc.message, exc.status_code),
            title="Modelo no disponible",
        )
    except Exception as exc:
        return error_page(
            request,
            HardwareServiceError(str(exc), 503),
            title="Modelo no disponible",
        )

    return templates.TemplateResponse(
        request=request,
        name="device_type_detail.html",
        context=context(
            request,
            page_title=str(detail["device_type"].get("_model_label")),
            page_subtitle="Ficha física, imágenes, componentes y equipos asociados",
            manufacturers=manufacturers,
            interface_types=interface_types,
            csrf_token=csrf_token(request),
            notice=notice,
            error=error,
            **detail,
        ),
    )


@router.post("/manufacturers/actions/create")
async def create_manufacturer_action(
    request: Request,
    csrf: str = Form(""),
    name: str = Form(...),
    slug: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    if not verify_csrf(request, csrf):
        return redirect_with_message(
            "/manufacturers",
            error="La sesión del formulario expiró. Recarga la página.",
        )
    if not settings.netbox_write_enabled:
        return redirect_with_message(
            "/manufacturers",
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        created = await HardwareService().create_manufacturer(
            name=name,
            slug=slug,
            description=description,
            username=str(request.session.get("username") or "desconocido"),
        )
    except HardwareServiceError as exc:
        audit_event(
            request,
            action="MANUFACTURER_CREATE",
            resource="manufacturer",
            detail=exc.message,
            success=False,
        )
        return redirect_with_message("/manufacturers", error=exc.message)

    manufacturer_id = created.get("id")
    audit_event(
        request,
        action="MANUFACTURER_CREATE",
        resource="manufacturer",
        resource_id=(
            str(manufacturer_id)
            if isinstance(manufacturer_id, int)
            else None
        ),
        detail=f"Fabricante {name.strip()} creado en NetBox.",
        success=True,
    )
    target = (
        f"/manufacturers/{manufacturer_id}"
        if isinstance(manufacturer_id, int)
        else "/manufacturers"
    )
    return redirect_with_message(
        target,
        notice="Fabricante creado correctamente.",
    )


@router.post("/manufacturers/{manufacturer_id}/actions/update")
async def update_manufacturer_action(
    request: Request,
    manufacturer_id: int,
    csrf: str = Form(""),
    name: str = Form(...),
    slug: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    target = f"/manufacturers/{manufacturer_id}"
    if not verify_csrf(request, csrf):
        return redirect_with_message(
            target,
            error="La sesión del formulario expiró. Recarga la página.",
        )
    if not settings.netbox_write_enabled:
        return redirect_with_message(
            target,
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        await HardwareService().update_manufacturer(
            manufacturer_id,
            name=name,
            slug=slug,
            description=description,
            username=str(request.session.get("username") or "desconocido"),
        )
    except HardwareServiceError as exc:
        audit_event(
            request,
            action="MANUFACTURER_UPDATE",
            resource="manufacturer",
            resource_id=str(manufacturer_id),
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(target, error=exc.message)

    audit_event(
        request,
        action="MANUFACTURER_UPDATE",
        resource="manufacturer",
        resource_id=str(manufacturer_id),
        detail=f"Fabricante {name.strip()} actualizado.",
        success=True,
    )
    return redirect_with_message(
        target,
        notice="Fabricante actualizado correctamente.",
    )


@router.post("/device-types/{device_type_id}/actions/update")
async def update_device_type_action(
    request: Request,
    device_type_id: int,
    csrf: str = Form(""),
    manufacturer_id: int = Form(...),
    model: str = Form(...),
    slug: str = Form(""),
    part_number: str = Form(""),
    u_height: float = Form(1),
    is_full_depth: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    target = f"/device-types/{device_type_id}"
    if not verify_csrf(request, csrf):
        return redirect_with_message(
            target,
            error="La sesión del formulario expiró. Recarga la página.",
        )
    if not settings.netbox_write_enabled:
        return redirect_with_message(
            target,
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        await HardwareService().update_device_type(
            device_type_id,
            manufacturer_id=manufacturer_id,
            model=model,
            slug=slug,
            part_number=part_number,
            u_height=u_height,
            is_full_depth=is_full_depth == "true",
            description=description,
            username=str(request.session.get("username") or "desconocido"),
        )
    except HardwareServiceError as exc:
        audit_event(
            request,
            action="DEVICE_TYPE_UPDATE",
            resource="device_type",
            resource_id=str(device_type_id),
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(target, error=exc.message)

    audit_event(
        request,
        action="DEVICE_TYPE_UPDATE",
        resource="device_type",
        resource_id=str(device_type_id),
        detail=f"Modelo {model.strip()} actualizado.",
        success=True,
    )
    return redirect_with_message(
        target,
        notice="Modelo actualizado correctamente.",
    )
