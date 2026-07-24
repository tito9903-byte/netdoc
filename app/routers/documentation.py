from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
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
    build_interface_names,
)
from app.services.ipam_presentation import prepare_ipam_view
from app.services.ipam_service import IPAMService, IPAMServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

PREFIX_STATUSES = [
    ("active", "Activo"),
    ("reserved", "Reservado"),
    ("deprecated", "Deprecado"),
    ("container", "Contenedor"),
]


def context(
    request: Request,
    *,
    current_page: str,
    **extra: object,
) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": current_page,
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "can_manage_device_types": has_permission(
            request,
            "devices.create",
        ),
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


def redirect_with_message(
    path: str,
    *,
    notice: str = "",
    error: str = "",
    **params: object,
) -> RedirectResponse:
    query: dict[str, object] = {
        key: value
        for key, value in params.items()
        if value not in (None, "")
    }
    if notice:
        query["notice"] = notice
    if error:
        query["error"] = error
    url = path if not query else f"{path}?{urlencode(query)}"
    return RedirectResponse(url=url, status_code=303)


def audit_event(
    request: Request,
    *,
    action: str,
    resource: str,
    detail: str,
    success: bool,
    object_id: str | None = None,
) -> None:
    user_id = request.session.get("user_id")
    ip_address, user_agent = request_client_data(request)

    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource=resource,
            resource_id=object_id,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(
                request.session.get("username") or "desconocido"
            ),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


@router.get("/ipam", response_class=HTMLResponse)
async def ipam_page(
    request: Request,
    q: str = "",
    status: str = "",
    family: str = "",
    role_id: str = "",
    scope: str = "",
    health: str = "",
    order: str = "utilization_desc",
    page: str = "1",
):
    redirect = access_redirect(request, "search.view")
    if redirect:
        return redirect

    selected_family = parse_optional_int(family)
    if selected_family not in {4, 6}:
        selected_family = None
    selected_role_id = parse_optional_int(role_id)
    selected_page = parse_optional_int(page) or 1

    try:
        raw_data = await IPAMService().overview(
            query=q,
            status=status,
            family=selected_family,
            role_id=selected_role_id,
        )
        data = prepare_ipam_view(
            raw_data,
            scope=scope,
            health=health,
            order=order,
            page=selected_page,
        )
    except IPAMServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                current_page="ipam",
                page_title="Direccionamiento IP",
                page_subtitle="No fue posible consultar IPAM",
                error_title="No se pudieron cargar los prefijos",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="ipam.html",
        context=context(
            request,
            current_page="ipam",
            page_title="Direccionamiento IP",
            page_subtitle=(
                "Disponibilidad, ocupación y localidad de prefijos y pools"
            ),
            query=q,
            selected_status=status,
            selected_family=selected_family,
            selected_role_id=selected_role_id,
            prefix_statuses=PREFIX_STATUSES,
            **data,
        ),
    )


@router.get("/api/ipam/pools", response_class=JSONResponse)
async def ipam_pools_api(request: Request):
    denied = api_access_response(request, "search.view")
    if denied:
        return denied

    try:
        data = await IPAMService().overview()
    except IPAMServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": exc.message},
        )

    return JSONResponse(
        content={
            "ok": True,
            "summary": data["summary"],
            "pools": data["pools"],
        }
    )


@router.get("/device-types", response_class=HTMLResponse)
async def device_types_page(
    request: Request,
    q: str = "",
    manufacturer_id: str = "",
    device_type_id: str = "",
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    selected_manufacturer_id = parse_optional_int(manufacturer_id)
    selected_device_type_id = parse_optional_int(device_type_id)
    service = DeviceTypeService()

    try:
        manufacturers, device_types, interface_types = await asyncio.gather(
            service.list_manufacturers(),
            service.list_device_types(
                query=q,
                manufacturer_id=selected_manufacturer_id,
            ),
            service.get_interface_type_choices(),
        )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                current_page="device_types",
                page_title="Modelos y plantillas",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudieron cargar los modelos",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    selected_device_type = None
    interfaces: list[dict[str, object]] = []

    if device_types:
        selected_device_type = next(
            (
                item
                for item in device_types
                if item.get("id") == selected_device_type_id
            ),
            device_types[0],
        )
        selected_device_type_id = parse_optional_int(
            selected_device_type.get("id")
        )

    if selected_device_type_id:
        try:
            interfaces = await service.list_interface_templates(
                selected_device_type_id
            )
        except DeviceTypeServiceError as exc:
            error = exc.message

    return templates.TemplateResponse(
        request=request,
        name="device_types.html",
        context=context(
            request,
            current_page="device_types",
            page_title="Modelos y plantillas",
            page_subtitle=(
                "Crea modelos reutilizables y sus interfaces en pocos pasos"
            ),
            query=q,
            manufacturers=manufacturers,
            selected_manufacturer_id=selected_manufacturer_id,
            device_types=device_types,
            selected_device_type=selected_device_type,
            selected_device_type_id=selected_device_type_id,
            interface_templates=interfaces,
            interface_types=interface_types,
            csrf_token=csrf_token(request),
            notice=notice,
            error=error,
        ),
    )


@router.post("/device-types/actions/create")
async def create_device_type_action(
    request: Request,
    csrf: str = Form(""),
    manufacturer_id: int = Form(...),
    model: str = Form(...),
    slug: str = Form(""),
    part_number: str = Form(""),
    u_height: float = Form(1),
    full_depth: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    if not verify_csrf(request, csrf):
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail="Creación rechazada por token CSRF inválido.",
            success=False,
        )
        return redirect_with_message(
            "/device-types",
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail="Creación rechazada porque la escritura está deshabilitada.",
            success=False,
        )
        return redirect_with_message(
            "/device-types",
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        created = await DeviceTypeService().create_device_type(
            manufacturer_id=manufacturer_id,
            model=model,
            slug=slug,
            part_number=part_number,
            u_height=u_height,
            full_depth=full_depth == "true",
            description=description,
            username=str(request.session.get("username") or "desconocido"),
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(
            "/device-types",
            error=exc.message,
        )

    object_id = str(created.get("id") or "")
    audit_event(
        request,
        action="DEVICE_TYPE_CREATE",
        resource="device_type",
        detail=f"Modelo {model.strip()} creado en NetBox.",
        success=True,
        object_id=object_id or None,
    )
    return redirect_with_message(
        "/device-types",
        notice="Modelo creado correctamente.",
        device_type_id=object_id,
    )


@router.post("/device-types/actions/interfaces/bulk")
async def bulk_interface_templates_action(
    request: Request,
    csrf: str = Form(""),
    device_type_id: int = Form(...),
    name_pattern: str = Form(...),
    start: int = Form(1),
    count: int = Form(...),
    interface_type: str = Form(...),
    enabled: str = Form(""),
    description_prefix: str = Form(""),
    management_only: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    if not verify_csrf(request, csrf):
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            detail="Creación rechazada por token CSRF inválido.",
            success=False,
            object_id=str(device_type_id),
        )
        return redirect_with_message(
            "/device-types",
            error="La sesión del formulario expiró. Recarga la página.",
            device_type_id=device_type_id,
        )

    if not settings.netbox_write_enabled:
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            detail="Creación rechazada porque la escritura está deshabilitada.",
            success=False,
            object_id=str(device_type_id),
        )
        return redirect_with_message(
            "/device-types",
            error="La escritura en NetBox está deshabilitada.",
            device_type_id=device_type_id,
        )

    try:
        names = build_interface_names(
            name_pattern,
            start=start,
            count=count,
        )
        created = await DeviceTypeService().bulk_create_interfaces(
            device_type_id=device_type_id,
            names=names,
            interface_type=interface_type,
            enabled=enabled == "true",
            management_only=management_only == "true",
            description_prefix=description_prefix,
            username=str(request.session.get("username") or "desconocido"),
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            detail=exc.message,
            success=False,
            object_id=str(device_type_id),
        )
        return redirect_with_message(
            "/device-types",
            error=exc.message,
            device_type_id=device_type_id,
        )

    audit_event(
        request,
        action="INTERFACE_TEMPLATE_BULK_CREATE",
        resource="interface_template",
        detail=(
            f"Se crearon {len(created)} interfaces en el modelo "
            f"#{device_type_id}."
        ),
        success=True,
        object_id=str(device_type_id),
    )
    return redirect_with_message(
        "/device-types",
        notice=f"Se crearon {len(created)} interfaces correctamente.",
        device_type_id=device_type_id,
    )
