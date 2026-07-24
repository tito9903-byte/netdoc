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
):
    redirect = access_redirect(request, "search.view")
    if redirect:
        return redirect

    selected_family = parse_optional_int(family)
    if selected_family not in {4, 6}:
        selected_family = None
    selected_role_id = parse_optional_int(role_id)

    try:
        data = await IPAMService().overview(
            query=q,
            status=status,
            family=selected_family,
            role_id=selected_role_id,
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


@router.get("/api/ipam/pools")
async def ipam_pools_api(request: Request):
    unauthorized = api_access_response(request, "search.view")
    if unauthorized:
        return unauthorized

    try:
        data = await IPAMService().overview()
    except IPAMServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": exc.message},
        )

    return {
        "ok": True,
        "summary": data["summary"],
        "pools": data["pools"],
    }


async def load_device_type_page(
    request: Request,
    *,
    query: str,
    manufacturer_id: int | None,
    selected_device_type_id: int | None,
    pattern: str,
    start: int,
    count: int,
    notice: str,
    error: str,
):
    service = DeviceTypeService()

    try:
        manufacturers, device_types, interface_types = await asyncio.gather(
            service.list_manufacturers(),
            service.list_device_types(
                query=query,
                manufacturer_id=manufacturer_id,
            ),
            service.interface_type_choices(),
        )

        selected_device_type = None
        interface_templates: list[dict] = []
        if selected_device_type_id:
            selected_device_type, interface_templates = await asyncio.gather(
                service.get_device_type(selected_device_type_id),
                service.list_interface_templates(selected_device_type_id),
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

    preview: list[str] = []
    preview_error = ""
    try:
        preview = build_interface_names(
            pattern,
            start=start,
            count=count,
        )
    except DeviceTypeServiceError as exc:
        preview_error = exc.message

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
            manufacturers=manufacturers,
            device_types=device_types,
            selected_device_type=selected_device_type,
            selected_device_type_id=selected_device_type_id,
            interface_templates=interface_templates,
            interface_types=interface_types,
            query=query,
            selected_manufacturer_id=manufacturer_id,
            pattern=pattern,
            start=start,
            count=count,
            preview=preview,
            preview_error=preview_error,
            notice=notice,
            error=error,
            csrf_token=csrf_token(request, "device_types"),
        ),
    )


@router.get("/device-types", response_class=HTMLResponse)
async def device_types_page(
    request: Request,
    q: str = "",
    manufacturer_id: str = "",
    device_type_id: str = "",
    pattern: str = "GigabitEthernet0/{n}",
    start: int = 1,
    count: int = 24,
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    return await load_device_type_page(
        request,
        query=q,
        manufacturer_id=parse_optional_int(manufacturer_id),
        selected_device_type_id=parse_optional_int(device_type_id),
        pattern=pattern,
        start=max(0, start),
        count=min(max(count, 1), 256),
        notice=notice,
        error=error,
    )


@router.get("/api/device-types/interface-preview")
async def interface_preview_api(
    request: Request,
    pattern: str,
    start: int = 1,
    count: int = 24,
):
    unauthorized = api_access_response(request, "devices.view")
    if unauthorized:
        return unauthorized

    try:
        names = build_interface_names(
            pattern,
            start=start,
            count=count,
        )
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": exc.message},
        )

    return {"ok": True, "names": names}


@router.post("/device-types/new")
async def create_device_type(
    request: Request,
    csrf: str = Form(...),
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

    if not verify_csrf(request, csrf, "device_types"):
        return redirect_with_message(
            "/device-types",
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        return redirect_with_message(
            "/device-types",
            error=(
                "La escritura está desactivada en este entorno. "
                "Puedes revisar y preparar los datos sin modificar NetBox."
            ),
        )

    if not model.strip():
        return redirect_with_message(
            "/device-types",
            error="El nombre del modelo es obligatorio.",
        )

    try:
        created = await DeviceTypeService().create_device_type(
            manufacturer_id=manufacturer_id,
            model=model,
            slug=slug,
            part_number=part_number,
            u_height=max(0.0, u_height),
            is_full_depth=is_full_depth == "on",
            description=description,
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

    created_id = created.get("id")
    audit_event(
        request,
        action="DEVICE_TYPE_CREATE",
        resource="device_type",
        object_id=str(created_id) if created_id else None,
        detail=f"Modelo creado: {model.strip()}.",
        success=True,
    )
    return redirect_with_message(
        "/device-types",
        device_type_id=created_id,
        notice="Modelo creado correctamente.",
    )


@router.post("/device-types/interface-templates/bulk")
async def create_interface_templates(
    request: Request,
    csrf: str = Form(...),
    device_type_id: int = Form(...),
    pattern: str = Form(...),
    start: int = Form(1),
    count: int = Form(24),
    interface_type: str = Form(...),
    label_pattern: str = Form(""),
    description: str = Form(""),
    mgmt_only: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    if not verify_csrf(request, csrf, "device_types"):
        return redirect_with_message(
            "/device-types",
            device_type_id=device_type_id,
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        return redirect_with_message(
            "/device-types",
            device_type_id=device_type_id,
            pattern=pattern,
            start=start,
            count=count,
            error=(
                "La escritura está desactivada. La vista previa no modificó "
                "el modelo en NetBox."
            ),
        )

    try:
        names = build_interface_names(
            pattern,
            start=start,
            count=count,
        )
        created = await DeviceTypeService().create_interface_templates(
            device_type_id=device_type_id,
            names=names,
            interface_type=interface_type,
            label_pattern=label_pattern,
            description=description,
            mgmt_only=mgmt_only == "on",
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            object_id=str(device_type_id),
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(
            "/device-types",
            device_type_id=device_type_id,
            pattern=pattern,
            start=start,
            count=count,
            error=exc.message,
        )

    audit_event(
        request,
        action="INTERFACE_TEMPLATE_BULK_CREATE",
        resource="interface_template",
        object_id=str(device_type_id),
        detail=f"Se crearon {len(created)} plantillas de interfaz.",
        success=True,
    )
    return redirect_with_message(
        "/device-types",
        device_type_id=device_type_id,
        pattern=pattern,
        start=start,
        count=count,
        notice=f"Se crearon {len(created)} interfaces en el modelo.",
    )
