from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    common_session_context,
    request_client_data,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.routers.device_create import signed_form_token, verify_signed_form_token
from app.services.access_service import record_audit
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError
from app.services.netbox_client import get_shared_netbox_client


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

DEVICE_STATUSES = [
    ("active", "Activo"),
    ("planned", "Planificado"),
    ("staged", "En preparación"),
    ("failed", "Con falla"),
    ("inventory", "Inventario"),
    ("decommissioning", "En retiro"),
    ("offline", "Fuera de línea"),
]


def nested_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("id"), int):
        return int(value["id"])
    return None


def nested_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("value")
            or value.get("slug")
            or value.get("name")
            or ""
        )
    return str(value or "")


def parse_optional_id(value: str, label: str) -> int | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    if not clean.isdigit() or int(clean) < 1:
        raise DeviceTypeServiceError(f"Selecciona {label} válido.", 400)
    return int(clean)


def parse_optional_int(value: str, label: str) -> int | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    try:
        parsed = int(clean)
    except ValueError as exc:
        raise DeviceTypeServiceError(f"{label} debe ser un número entero.", 400) from exc
    if parsed < 0:
        raise DeviceTypeServiceError(f"{label} no puede ser negativo.", 400)
    return parsed


def parse_optional_float(value: str, label: str) -> float | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    try:
        parsed = float(clean)
    except ValueError as exc:
        raise DeviceTypeServiceError(f"{label} debe ser un número válido.", 400) from exc
    if parsed < 0:
        raise DeviceTypeServiceError(f"{label} no puede ser negativo.", 400)
    return parsed


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "devices",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def audit_event(
    request: Request,
    *,
    action: str,
    resource: str,
    resource_id: int,
    detail: str,
    success: bool,
) -> None:
    ip_address, user_agent = request_client_data(request)
    user_id = request.session.get("user_id")
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource=resource,
            resource_id=str(resource_id),
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def redirect_with_message(
    path: str,
    *,
    notice: str = "",
    error: str = "",
    fragment: str = "",
) -> RedirectResponse:
    params = {
        key: value
        for key, value in {"notice": notice, "error": error}.items()
        if value
    }
    query = f"?{urlencode(params)}" if params else ""
    anchor = f"#{fragment}" if fragment else ""
    return RedirectResponse(f"{path}{query}{anchor}", status_code=303)


async def delete_netbox_object(endpoint: str) -> None:
    client = await get_shared_netbox_client()
    response = await client.delete(
        endpoint.lstrip("/"),
        headers={"Accept": "application/json"},
    )
    if response.is_error:
        raise DeviceTypeServiceError(
            DeviceTypeService._error_message(response),
            response.status_code,
        )
    DeviceTypeService.clear_read_caches()


async def load_device_edit_context(
    request: Request,
    device_id: int,
    *,
    error: str = "",
    status_code: int = 200,
):
    service = DeviceTypeService()
    try:
        (
            device,
            device_types,
            roles,
            sites,
            locations,
            racks,
            platforms,
        ) = await asyncio.gather(
            service.request("GET", f"/api/dcim/devices/{device_id}/"),
            service.get_all(
                "/api/dcim/device-types/",
                params={"ordering": "manufacturer,model"},
            ),
            service.get_all(
                "/api/dcim/device-roles/",
                params={"ordering": "name"},
            ),
            service.get_all("/api/dcim/sites/", params={"ordering": "name"}),
            service.get_all(
                "/api/dcim/locations/",
                params={"ordering": "site,name"},
            ),
            service.get_all(
                "/api/dcim/racks/",
                params={"ordering": "site,name"},
            ),
            service.get_all(
                "/api/dcim/platforms/",
                params={"ordering": "name"},
            ),
        )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Dispositivo no disponible",
                page_subtitle="No fue posible preparar la edición",
                error_title="No se pudo cargar el dispositivo",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_edit.html",
        status_code=status_code,
        context=context(
            request,
            page_title="Editar dispositivo",
            page_subtitle="Actualizar la ficha del equipo directamente en NetBox",
            device=device,
            device_id=device_id,
            device_types=device_types,
            roles=roles,
            sites=sites,
            locations=locations,
            racks=racks,
            platforms=platforms,
            statuses=DEVICE_STATUSES,
            csrf_token=signed_form_token(request, f"device-edit:{device_id}"),
            error=error,
        ),
    )


@router.get("/devices/{device_id}/edit", response_class=HTMLResponse)
async def device_edit_page(request: Request, device_id: int, error: str = ""):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await load_device_edit_context(request, device_id, error=error)


@router.post("/devices/{device_id}/edit", response_class=HTMLResponse)
async def device_edit_submit(
    request: Request,
    device_id: int,
    csrf_token: str = Form(""),
    name: str = Form(""),
    device_type_id: str = Form(""),
    role_id: str = Form(""),
    site_id: str = Form(""),
    status: str = Form("active"),
    platform_id: str = Form(""),
    location_id: str = Form(""),
    rack_id: str = Form(""),
    position: str = Form(""),
    face: str = Form(""),
    serial: str = Form(""),
    asset_tag: str = Form(""),
    description: str = Form(""),
    comments: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    if not verify_signed_form_token(
        request,
        csrf_token,
        f"device-edit:{device_id}",
    ):
        return await load_device_edit_context(
            request,
            device_id,
            error="La sesión de seguridad venció. Abre nuevamente la edición.",
            status_code=403,
        )
    if not settings.netbox_write_enabled:
        return await load_device_edit_context(
            request,
            device_id,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
        )

    try:
        clean_name = name.strip()
        if not clean_name:
            raise DeviceTypeServiceError("Escribe el nombre del dispositivo.", 400)
        if status not in {item[0] for item in DEVICE_STATUSES}:
            raise DeviceTypeServiceError("Selecciona un estado válido.", 400)

        selected_rack = parse_optional_id(rack_id, "un rack")
        selected_face = face if face in {"front", "rear"} else None
        selected_position = parse_optional_float(position, "La posición")
        if selected_rack is None:
            selected_face = None
            selected_position = None

        payload = {
            "name": clean_name,
            "device_type": parse_optional_id(device_type_id, "un modelo"),
            "role": parse_optional_id(role_id, "un rol"),
            "site": parse_optional_id(site_id, "un sitio"),
            "status": status,
            "platform": parse_optional_id(platform_id, "una plataforma"),
            "location": parse_optional_id(location_id, "una ubicación"),
            "rack": selected_rack,
            "position": selected_position,
            "face": selected_face,
            "serial": serial.strip(),
            "asset_tag": asset_tag.strip() or None,
            "description": description.strip(),
            "comments": comments.strip(),
        }
        result = await DeviceTypeService().request(
            "PATCH",
            f"/api/dcim/devices/{device_id}/",
            json_body=payload,
        )
        if not isinstance(result, dict):
            raise DeviceTypeServiceError(
                "NetBox actualizó el equipo, pero devolvió un formato inesperado.",
                502,
            )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_UPDATE",
            resource="device",
            resource_id=device_id,
            detail=exc.message,
            success=False,
        )
        return await load_device_edit_context(
            request,
            device_id,
            error=exc.message,
            status_code=exc.status_code or 400,
        )

    audit_event(
        request,
        action="DEVICE_UPDATE",
        resource="device",
        resource_id=device_id,
        detail=f"Dispositivo {clean_name} actualizado desde NetDoc.",
        success=True,
    )
    return redirect_with_message(
        f"/devices/{device_id}",
        notice="El dispositivo fue actualizado correctamente.",
    )


async def load_interface_form_context(
    request: Request,
    device_id: int,
    *,
    interface_id: int | None = None,
    error: str = "",
    status_code: int = 200,
):
    service = DeviceTypeService()
    try:
        device, type_choices, lags = await asyncio.gather(
            service.request("GET", f"/api/dcim/devices/{device_id}/"),
            service.interface_type_choices(),
            service.get_all(
                "/api/dcim/interfaces/",
                params={
                    "device_id": device_id,
                    "type": "lag",
                    "ordering": "name",
                },
            ),
        )
        interface = None
        if interface_id is not None:
            interface = await service.request(
                "GET",
                f"/api/dcim/interfaces/{interface_id}/",
            )
            if nested_id(interface.get("device")) != device_id:
                raise DeviceTypeServiceError(
                    "La interfaz no pertenece a este dispositivo.",
                    404,
                )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Interfaz no disponible",
                page_subtitle="No fue posible preparar el formulario",
                error_title="No se pudo cargar la interfaz",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    namespace = (
        f"device-interface-edit:{device_id}:{interface_id}"
        if interface_id is not None
        else f"device-interface-create:{device_id}"
    )
    return templates.TemplateResponse(
        request=request,
        name="device_interface_form.html",
        status_code=status_code,
        context=context(
            request,
            page_title="Editar interfaz" if interface else "Crear interfaz",
            page_subtitle=(
                "Modificar el puerto seleccionado en NetBox"
                if interface
                else "Agregar una interfaz individual al dispositivo"
            ),
            device=device,
            device_id=device_id,
            interface=interface,
            interface_id=interface_id,
            type_choices=type_choices,
            lags=lags,
            csrf_token=signed_form_token(request, namespace),
            error=error,
        ),
    )


@router.get(
    "/devices/{device_id}/interfaces/new",
    response_class=HTMLResponse,
)
async def device_interface_create_page(
    request: Request,
    device_id: int,
    error: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await load_interface_form_context(request, device_id, error=error)


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/edit",
    response_class=HTMLResponse,
)
async def device_interface_edit_page(
    request: Request,
    device_id: int,
    interface_id: int,
    error: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await load_interface_form_context(
        request,
        device_id,
        interface_id=interface_id,
        error=error,
    )


async def submit_device_interface(
    request: Request,
    *,
    device_id: int,
    interface_id: int | None,
    csrf_token: str,
    name: str,
    interface_type: str,
    label: str,
    enabled: str,
    mgmt_only: str,
    mark_connected: str,
    description: str,
    mtu: str,
    lag_id: str,
    mac_address: str,
):
    namespace = (
        f"device-interface-edit:{device_id}:{interface_id}"
        if interface_id is not None
        else f"device-interface-create:{device_id}"
    )
    if not verify_signed_form_token(request, csrf_token, namespace):
        return await load_interface_form_context(
            request,
            device_id,
            interface_id=interface_id,
            error="La sesión de seguridad venció. Abre nuevamente el formulario.",
            status_code=403,
        )
    if not settings.netbox_write_enabled:
        return await load_interface_form_context(
            request,
            device_id,
            interface_id=interface_id,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
        )

    try:
        clean_name = name.strip()
        clean_type = interface_type.strip()
        if not clean_name:
            raise DeviceTypeServiceError("Escribe el nombre de la interfaz.", 400)
        if not clean_type:
            raise DeviceTypeServiceError("Selecciona el tipo de interfaz.", 400)

        service = DeviceTypeService()
        options = await service.request("OPTIONS", "/api/dcim/interfaces/")
        allowed = set(
            (options.get("actions") or {}).get("POST", {}).keys()
            if isinstance(options, dict)
            else []
        )
        candidate_payload: dict[str, Any] = {
            "device": device_id,
            "name": clean_name,
            "type": clean_type,
            "label": label.strip(),
            "enabled": str(enabled or "").lower() in {"1", "true", "on", "yes"},
            "mgmt_only": str(mgmt_only or "").lower() in {"1", "true", "on", "yes"},
            "mark_connected": str(mark_connected or "").lower()
            in {"1", "true", "on", "yes"},
            "description": description.strip(),
            "mtu": parse_optional_int(mtu, "MTU"),
            "lag": parse_optional_id(lag_id, "un LAG"),
            "mac_address": mac_address.strip() or None,
        }
        payload = {
            key: value
            for key, value in candidate_payload.items()
            if not allowed or key in allowed
        }
        endpoint = (
            f"/api/dcim/interfaces/{interface_id}/"
            if interface_id is not None
            else "/api/dcim/interfaces/"
        )
        method = "PATCH" if interface_id is not None else "POST"
        result = await service.request(method, endpoint, json_body=payload)
        if not isinstance(result, dict):
            raise DeviceTypeServiceError(
                "NetBox guardó la interfaz, pero devolvió un formato inesperado.",
                502,
            )
    except DeviceTypeServiceError as exc:
        action = "DEVICE_INTERFACE_UPDATE" if interface_id else "DEVICE_INTERFACE_CREATE"
        audit_event(
            request,
            action=action,
            resource="interface",
            resource_id=interface_id or device_id,
            detail=exc.message,
            success=False,
        )
        return await load_interface_form_context(
            request,
            device_id,
            interface_id=interface_id,
            error=exc.message,
            status_code=exc.status_code or 400,
        )

    action = "DEVICE_INTERFACE_UPDATE" if interface_id else "DEVICE_INTERFACE_CREATE"
    saved_id = int(result.get("id") or interface_id or 0)
    audit_event(
        request,
        action=action,
        resource="interface",
        resource_id=saved_id or device_id,
        detail=f"Interfaz {clean_name} guardada en el dispositivo #{device_id}.",
        success=True,
    )
    return redirect_with_message(
        f"/devices/{device_id}",
        notice=f"La interfaz {clean_name} fue guardada correctamente.",
        fragment="interfaces",
    )


@router.post("/devices/{device_id}/interfaces/actions/create")
async def device_interface_create_submit(
    request: Request,
    device_id: int,
    csrf_token: str = Form(""),
    name: str = Form(""),
    interface_type: str = Form(""),
    label: str = Form(""),
    enabled: str = Form(""),
    mgmt_only: str = Form(""),
    mark_connected: str = Form(""),
    description: str = Form(""),
    mtu: str = Form(""),
    lag_id: str = Form(""),
    mac_address: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await submit_device_interface(
        request,
        device_id=device_id,
        interface_id=None,
        csrf_token=csrf_token,
        name=name,
        interface_type=interface_type,
        label=label,
        enabled=enabled,
        mgmt_only=mgmt_only,
        mark_connected=mark_connected,
        description=description,
        mtu=mtu,
        lag_id=lag_id,
        mac_address=mac_address,
    )


@router.post(
    "/devices/{device_id}/interfaces/{interface_id}/actions/update"
)
async def device_interface_edit_submit(
    request: Request,
    device_id: int,
    interface_id: int,
    csrf_token: str = Form(""),
    name: str = Form(""),
    interface_type: str = Form(""),
    label: str = Form(""),
    enabled: str = Form(""),
    mgmt_only: str = Form(""),
    mark_connected: str = Form(""),
    description: str = Form(""),
    mtu: str = Form(""),
    lag_id: str = Form(""),
    mac_address: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await submit_device_interface(
        request,
        device_id=device_id,
        interface_id=interface_id,
        csrf_token=csrf_token,
        name=name,
        interface_type=interface_type,
        label=label,
        enabled=enabled,
        mgmt_only=mgmt_only,
        mark_connected=mark_connected,
        description=description,
        mtu=mtu,
        lag_id=lag_id,
        mac_address=mac_address,
    )


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/delete",
    response_class=HTMLResponse,
)
async def device_interface_delete_page(
    request: Request,
    device_id: int,
    interface_id: int,
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    try:
        interface = await DeviceTypeService().request(
            "GET",
            f"/api/dcim/interfaces/{interface_id}/",
        )
        if nested_id(interface.get("device")) != device_id:
            raise DeviceTypeServiceError(
                "La interfaz no pertenece a este dispositivo.",
                404,
            )
    except DeviceTypeServiceError as exc:
        return redirect_with_message(
            f"/devices/{device_id}",
            error=exc.message,
            fragment="interfaces",
        )

    return templates.TemplateResponse(
        request=request,
        name="device_interface_delete.html",
        context=context(
            request,
            page_title="Eliminar interfaz",
            page_subtitle="Confirmación requerida antes de modificar NetBox",
            device_id=device_id,
            interface=interface,
            csrf_token=signed_form_token(
                request,
                f"device-interface-delete:{device_id}:{interface_id}",
            ),
        ),
    )


@router.post(
    "/devices/{device_id}/interfaces/{interface_id}/actions/delete"
)
async def device_interface_delete_submit(
    request: Request,
    device_id: int,
    interface_id: int,
    csrf_token: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    namespace = f"device-interface-delete:{device_id}:{interface_id}"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return redirect_with_message(
            f"/devices/{device_id}",
            error="La sesión de seguridad venció.",
            fragment="interfaces",
        )
    if not settings.netbox_write_enabled:
        return redirect_with_message(
            f"/devices/{device_id}",
            error="La escritura en NetBox está deshabilitada.",
            fragment="interfaces",
        )

    try:
        service = DeviceTypeService()
        interface, addresses = await asyncio.gather(
            service.request("GET", f"/api/dcim/interfaces/{interface_id}/"),
            service.get_all(
                "/api/ipam/ip-addresses/",
                params={"interface_id": interface_id},
            ),
        )
        if nested_id(interface.get("device")) != device_id:
            raise DeviceTypeServiceError(
                "La interfaz no pertenece a este dispositivo.",
                404,
            )
        if interface.get("cable") or interface.get("connected_endpoints"):
            raise DeviceTypeServiceError(
                "No se puede eliminar una interfaz que tiene una conexión documentada.",
                409,
            )
        if addresses:
            raise DeviceTypeServiceError(
                "No se puede eliminar una interfaz que tiene direcciones IP asignadas.",
                409,
            )
        name = str(interface.get("name") or f"#{interface_id}")
        await delete_netbox_object(f"/api/dcim/interfaces/{interface_id}/")
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_INTERFACE_DELETE",
            resource="interface",
            resource_id=interface_id,
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(
            f"/devices/{device_id}",
            error=exc.message,
            fragment="interfaces",
        )

    audit_event(
        request,
        action="DEVICE_INTERFACE_DELETE",
        resource="interface",
        resource_id=interface_id,
        detail=f"Interfaz {name} eliminada del dispositivo #{device_id}.",
        success=True,
    )
    return redirect_with_message(
        f"/devices/{device_id}",
        notice=f"La interfaz {name} fue eliminada.",
        fragment="interfaces",
    )


async def load_model_interface_context(
    request: Request,
    device_type_id: int,
    interface_id: int,
    *,
    error: str = "",
    status_code: int = 200,
):
    service = DeviceTypeService()
    try:
        device_type, interface, choices = await asyncio.gather(
            service.get_device_type(device_type_id),
            service.request(
                "GET",
                f"/api/dcim/interface-templates/{interface_id}/",
            ),
            service.interface_type_choices(),
        )
        if nested_id(interface.get("device_type")) != device_type_id:
            raise DeviceTypeServiceError(
                "La interfaz no pertenece a este modelo.",
                404,
            )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                current_page="device_types",
                page_title="Interfaz del modelo no disponible",
                page_subtitle="No fue posible preparar la edición",
                error_title="No se pudo cargar la plantilla",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_type_interface_edit.html",
        status_code=status_code,
        context=context(
            request,
            current_page="device_types",
            page_title="Editar interfaz del modelo",
            page_subtitle="Modificar la plantilla reutilizable en NetBox",
            device_type=device_type,
            device_type_id=device_type_id,
            interface=interface,
            interface_id=interface_id,
            type_choices=choices,
            csrf_token=signed_form_token(
                request,
                f"model-interface-edit:{device_type_id}:{interface_id}",
            ),
            delete_token=signed_form_token(
                request,
                f"model-interface-delete:{device_type_id}:{interface_id}",
            ),
            error=error,
        ),
    )


@router.get(
    "/device-types/{device_type_id}/interfaces/{interface_id}/edit",
    response_class=HTMLResponse,
)
async def model_interface_edit_page(
    request: Request,
    device_type_id: int,
    interface_id: int,
    error: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await load_model_interface_context(
        request,
        device_type_id,
        interface_id,
        error=error,
    )


@router.post(
    "/device-types/{device_type_id}/interfaces/{interface_id}/actions/update"
)
async def model_interface_edit_submit(
    request: Request,
    device_type_id: int,
    interface_id: int,
    csrf_token: str = Form(""),
    name: str = Form(""),
    interface_type: str = Form(""),
    label: str = Form(""),
    mgmt_only: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    namespace = f"model-interface-edit:{device_type_id}:{interface_id}"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return await load_model_interface_context(
            request,
            device_type_id,
            interface_id,
            error="La sesión de seguridad venció. Abre nuevamente la edición.",
            status_code=403,
        )
    if not settings.netbox_write_enabled:
        return await load_model_interface_context(
            request,
            device_type_id,
            interface_id,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
        )

    try:
        clean_name = name.strip()
        clean_type = interface_type.strip()
        if not clean_name:
            raise DeviceTypeServiceError("Escribe el nombre de la interfaz.", 400)
        if not clean_type:
            raise DeviceTypeServiceError("Selecciona el tipo de interfaz.", 400)
        result = await DeviceTypeService().request(
            "PATCH",
            f"/api/dcim/interface-templates/{interface_id}/",
            json_body={
                "name": clean_name,
                "type": clean_type,
                "label": label.strip(),
                "mgmt_only": str(mgmt_only or "").lower()
                in {"1", "true", "on", "yes"},
                "description": description.strip(),
            },
        )
        if not isinstance(result, dict):
            raise DeviceTypeServiceError(
                "NetBox actualizó la plantilla, pero devolvió un formato inesperado.",
                502,
            )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="MODEL_INTERFACE_UPDATE",
            resource="interface_template",
            resource_id=interface_id,
            detail=exc.message,
            success=False,
        )
        return await load_model_interface_context(
            request,
            device_type_id,
            interface_id,
            error=exc.message,
            status_code=exc.status_code or 400,
        )

    audit_event(
        request,
        action="MODEL_INTERFACE_UPDATE",
        resource="interface_template",
        resource_id=interface_id,
        detail=f"Plantilla {clean_name} actualizada en el modelo #{device_type_id}.",
        success=True,
    )
    return redirect_with_message(
        f"/device-types/{device_type_id}",
        notice=f"La interfaz {clean_name} del modelo fue actualizada.",
        fragment="components",
    )


@router.post(
    "/device-types/{device_type_id}/interfaces/{interface_id}/actions/delete"
)
async def model_interface_delete_submit(
    request: Request,
    device_type_id: int,
    interface_id: int,
    csrf_token: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    namespace = f"model-interface-delete:{device_type_id}:{interface_id}"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return redirect_with_message(
            f"/device-types/{device_type_id}",
            error="La sesión de seguridad venció.",
            fragment="components",
        )
    if not settings.netbox_write_enabled:
        return redirect_with_message(
            f"/device-types/{device_type_id}",
            error="La escritura en NetBox está deshabilitada.",
            fragment="components",
        )

    try:
        interface = await DeviceTypeService().request(
            "GET",
            f"/api/dcim/interface-templates/{interface_id}/",
        )
        if nested_id(interface.get("device_type")) != device_type_id:
            raise DeviceTypeServiceError(
                "La interfaz no pertenece a este modelo.",
                404,
            )
        name = str(interface.get("name") or f"#{interface_id}")
        await delete_netbox_object(
            f"/api/dcim/interface-templates/{interface_id}/"
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="MODEL_INTERFACE_DELETE",
            resource="interface_template",
            resource_id=interface_id,
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(
            f"/device-types/{device_type_id}",
            error=exc.message,
            fragment="components",
        )

    audit_event(
        request,
        action="MODEL_INTERFACE_DELETE",
        resource="interface_template",
        resource_id=interface_id,
        detail=f"Plantilla {name} eliminada del modelo #{device_type_id}.",
        success=True,
    )
    return redirect_with_message(
        f"/device-types/{device_type_id}",
        notice=(
            f"La interfaz {name} fue eliminada del modelo. "
            "Las interfaces ya existentes en dispositivos no fueron modificadas."
        ),
        fragment="components",
    )
