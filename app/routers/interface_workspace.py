from __future__ import annotations

import asyncio
from ipaddress import ip_interface
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import access_redirect, common_session_context, request_client_data
from app.core.config import get_settings
from app.core.database import session_scope
from app.routers.device_create import signed_form_token, verify_signed_form_token
from app.services.access_service import record_audit
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def nested_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, dict):
        candidate = value.get("id")
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def choice_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("label")
            or value.get("display")
            or value.get("name")
            or value.get("value")
            or "—"
        )
    return str(value or "—")


def field_choices(options: dict[str, Any], field: str) -> list[dict[str, str]]:
    actions = options.get("actions") if isinstance(options, dict) else None
    schema = actions.get("POST") if isinstance(actions, dict) else None
    definition = schema.get(field) if isinstance(schema, dict) else None
    choices = definition.get("choices") if isinstance(definition, dict) else None
    if not isinstance(choices, list):
        return []

    result: list[dict[str, str]] = []
    for item in choices:
        if isinstance(item, dict):
            value = str(item.get("value") or "")
            label = str(item.get("display_name") or item.get("label") or value)
        else:
            value = str(item)
            label = value
        if value:
            result.append({"value": value, "label": label})
    return result


def allowed_fields(options: dict[str, Any], method: str) -> set[str]:
    actions = options.get("actions") if isinstance(options, dict) else None
    schema = actions.get(method) if isinstance(actions, dict) else None
    return set(schema.keys()) if isinstance(schema, dict) else set()


def bool_value(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on", "si", "sí"}


def optional_int(value: str, label: str) -> int | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    if not clean.isdigit() or int(clean) < 1:
        raise DeviceTypeServiceError(f"Selecciona {label} válido.", 400)
    return int(clean)


def optional_non_negative_int(value: str, label: str) -> int | None:
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
    resource_id: int | None,
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
            resource_id=str(resource_id) if resource_id else None,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def workspace_redirect(
    device_id: int,
    interface_id: int,
    *,
    notice: str = "",
    error: str = "",
) -> RedirectResponse:
    params = {
        key: value
        for key, value in {"notice": notice, "error": error}.items()
        if value
    }
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(
        f"/devices/{device_id}/interfaces/{interface_id}/workspace{query}",
        status_code=303,
    )


def serialize_addresses(
    device: dict[str, Any],
    addresses: list[dict[str, Any]],
    *,
    device_id: int,
    interface_id: int,
) -> list[dict[str, Any]]:
    primary_ids = {
        value
        for value in (
            nested_id(device.get("primary_ip4")),
            nested_id(device.get("primary_ip6")),
        )
        if value is not None
    }
    rows: list[dict[str, Any]] = []
    for item in addresses:
        address_id = nested_id(item.get("id"))
        if address_id is None:
            continue
        rows.append({
            "id": address_id,
            "address": str(item.get("address") or item.get("display") or ""),
            "status": choice_label(item.get("status")),
            "role": choice_label(item.get("role")) if item.get("role") else "",
            "dns_name": str(item.get("dns_name") or ""),
            "description": str(item.get("description") or ""),
            "is_primary": address_id in primary_ids,
            "edit_url": (
                f"/devices/{device_id}/interfaces/{interface_id}/"
                f"ip-addresses/{address_id}/edit"
            ),
        })
    return rows


async def render_workspace(
    request: Request,
    *,
    device_id: int,
    interface_id: int | None = None,
    error: str = "",
    notice: str = "",
    status_code: int = 200,
    form_data: dict[str, Any] | None = None,
):
    service = DeviceTypeService()
    try:
        if interface_id is None:
            device, type_choices, lags, ip_options, vrfs = await asyncio.gather(
                service.request("GET", f"/api/dcim/devices/{device_id}/"),
                service.interface_type_choices(),
                service.get_all(
                    "/api/dcim/interfaces/",
                    params={"device_id": device_id, "type": "lag", "ordering": "name"},
                ),
                service.request("OPTIONS", "/api/ipam/ip-addresses/"),
                service.get_all("/api/ipam/vrfs/", params={"ordering": "name,rd"}),
            )
            interface = None
            addresses: list[dict[str, Any]] = []
            status_choices = field_choices(ip_options, "status")
            role_choices = field_choices(ip_options, "role")
        else:
            device, interface, type_choices, lags, raw_addresses = await asyncio.gather(
                service.request("GET", f"/api/dcim/devices/{device_id}/"),
                service.request("GET", f"/api/dcim/interfaces/{interface_id}/"),
                service.interface_type_choices(),
                service.get_all(
                    "/api/dcim/interfaces/",
                    params={"device_id": device_id, "type": "lag", "ordering": "name"},
                ),
                service.get_all(
                    "/api/ipam/ip-addresses/",
                    params={"interface_id": interface_id, "ordering": "family,address"},
                ),
            )
            if nested_id(interface.get("device")) != device_id:
                raise DeviceTypeServiceError(
                    "La interfaz no pertenece a este dispositivo.",
                    404,
                )
            addresses = serialize_addresses(
                device,
                raw_addresses,
                device_id=device_id,
                interface_id=interface_id,
            )
            status_choices = []
            role_choices = []
            vrfs = []
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Interfaz no disponible",
                page_subtitle="No fue posible preparar el espacio de trabajo",
                error_title="No se pudo cargar la interfaz",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    namespace = (
        f"device-interface-edit:{device_id}:{interface_id}"
        if interface_id is not None
        else f"interface-workspace-create:{device_id}"
    )
    return templates.TemplateResponse(
        request=request,
        name="interface_workspace.html",
        status_code=status_code,
        context=context(
            request,
            page_title="Editar interfaz" if interface else "Crear interfaz",
            page_subtitle=(
                "Propiedades, direccionamiento y conexión en un solo espacio"
                if interface
                else "Crear el puerto y asignar opcionalmente su primera dirección IP"
            ),
            device=device,
            device_id=device_id,
            interface=interface,
            interface_id=interface_id,
            type_choices=type_choices,
            lags=lags,
            addresses=addresses,
            status_choices=status_choices,
            role_choices=role_choices,
            vrfs=vrfs,
            csrf_token=signed_form_token(request, namespace),
            error=error,
            notice=notice,
            form_data=form_data or {},
        ),
    )


@router.get("/devices/{device_id}/interfaces/new-workspace", response_class=HTMLResponse)
async def interface_workspace_create_page(
    request: Request,
    device_id: int,
    error: str = "",
    notice: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await render_workspace(
        request,
        device_id=device_id,
        error=error,
        notice=notice,
    )


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/workspace",
    response_class=HTMLResponse,
)
async def interface_workspace_edit_page(
    request: Request,
    device_id: int,
    interface_id: int,
    error: str = "",
    notice: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await render_workspace(
        request,
        device_id=device_id,
        interface_id=interface_id,
        error=error,
        notice=notice,
    )


@router.post("/devices/{device_id}/interfaces/actions/create-workspace")
async def interface_workspace_create_submit(
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
    initial_ip_address: str = Form(""),
    initial_ip_status: str = Form("active"),
    initial_ip_role: str = Form(""),
    initial_ip_vrf_id: str = Form(""),
    initial_ip_dns_name: str = Form(""),
    initial_ip_description: str = Form(""),
    initial_ip_make_primary: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    form_data = {
        "name": name,
        "interface_type": interface_type,
        "label": label,
        "enabled": enabled,
        "mgmt_only": mgmt_only,
        "mark_connected": mark_connected,
        "description": description,
        "mtu": mtu,
        "lag_id": lag_id,
        "mac_address": mac_address,
        "initial_ip_address": initial_ip_address,
        "initial_ip_status": initial_ip_status,
        "initial_ip_role": initial_ip_role,
        "initial_ip_vrf_id": initial_ip_vrf_id,
        "initial_ip_dns_name": initial_ip_dns_name,
        "initial_ip_description": initial_ip_description,
        "initial_ip_make_primary": initial_ip_make_primary,
    }

    if not verify_signed_form_token(
        request,
        csrf_token,
        f"interface-workspace-create:{device_id}",
    ):
        return await render_workspace(
            request,
            device_id=device_id,
            error="La sesión de seguridad venció. Abre nuevamente el formulario.",
            status_code=403,
            form_data=form_data,
        )
    if not settings.netbox_write_enabled:
        return await render_workspace(
            request,
            device_id=device_id,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
            form_data=form_data,
        )

    clean_name = name.strip()
    clean_type = interface_type.strip()
    clean_initial_ip = initial_ip_address.strip()
    normalized_ip = ""
    try:
        if not clean_name:
            raise DeviceTypeServiceError("Escribe el nombre de la interfaz.", 400)
        if not clean_type:
            raise DeviceTypeServiceError("Selecciona el tipo de interfaz.", 400)
        if clean_initial_ip:
            try:
                normalized_ip = str(ip_interface(clean_initial_ip))
            except ValueError as exc:
                raise DeviceTypeServiceError(
                    "Escribe una dirección IP válida con su prefijo; por ejemplo 192.0.2.10/24.",
                    400,
                ) from exc

        service = DeviceTypeService()
        interface_options, ip_options = await asyncio.gather(
            service.request("OPTIONS", "/api/dcim/interfaces/"),
            service.request("OPTIONS", "/api/ipam/ip-addresses/"),
        )
        interface_allowed = allowed_fields(interface_options, "POST")
        interface_candidate: dict[str, Any] = {
            "device": device_id,
            "name": clean_name,
            "type": clean_type,
            "label": label.strip(),
            "enabled": bool_value(enabled),
            "mgmt_only": bool_value(mgmt_only),
            "mark_connected": bool_value(mark_connected),
            "description": description.strip(),
            "mtu": optional_non_negative_int(mtu, "MTU"),
            "lag": optional_int(lag_id, "un LAG"),
            "mac_address": mac_address.strip() or None,
        }
        interface_payload = {
            key: value
            for key, value in interface_candidate.items()
            if not interface_allowed or key in interface_allowed
        }
        saved_interface = await service.request(
            "POST",
            "/api/dcim/interfaces/",
            json_body=interface_payload,
        )
        interface_id = nested_id(saved_interface.get("id")) if isinstance(saved_interface, dict) else None
        if interface_id is None:
            raise DeviceTypeServiceError(
                "NetBox creó la interfaz, pero devolvió un formato inesperado.",
                502,
            )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_INTERFACE_CREATE",
            resource="interface",
            resource_id=device_id,
            detail=exc.message,
            success=False,
        )
        return await render_workspace(
            request,
            device_id=device_id,
            error=exc.message,
            status_code=exc.status_code or 400,
            form_data=form_data,
        )

    audit_event(
        request,
        action="DEVICE_INTERFACE_CREATE",
        resource="interface",
        resource_id=interface_id,
        detail=f"Interfaz {clean_name} creada en el dispositivo #{device_id}.",
        success=True,
    )

    if not normalized_ip:
        return workspace_redirect(
            device_id,
            interface_id,
            notice=f"La interfaz {clean_name} fue creada correctamente.",
        )

    try:
        ip_allowed = allowed_fields(ip_options, "POST")
        ip_candidate: dict[str, Any] = {
            "address": normalized_ip,
            "status": initial_ip_status.strip() or "active",
            "role": initial_ip_role.strip() or None,
            "vrf": optional_int(initial_ip_vrf_id, "una VRF"),
            "dns_name": initial_ip_dns_name.strip(),
            "description": initial_ip_description.strip(),
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": interface_id,
        }
        ip_payload = {
            key: value
            for key, value in ip_candidate.items()
            if not ip_allowed or key in ip_allowed
        }
        saved_ip = await service.request(
            "POST",
            "/api/ipam/ip-addresses/",
            json_body=ip_payload,
        )
        address_id = nested_id(saved_ip.get("id")) if isinstance(saved_ip, dict) else None
        if address_id is None:
            raise DeviceTypeServiceError(
                "NetBox creó la dirección, pero devolvió un formato inesperado.",
                502,
            )
        if bool_value(initial_ip_make_primary):
            family = ip_interface(normalized_ip).version
            await service.request(
                "PATCH",
                f"/api/dcim/devices/{device_id}/",
                json_body={"primary_ip4" if family == 4 else "primary_ip6": address_id},
            )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="INTERFACE_IP_CREATE",
            resource="ip_address",
            resource_id=interface_id,
            detail=(
                f"La interfaz {clean_name} fue creada, pero su direccionamiento inicial falló: "
                f"{exc.message}"
            ),
            success=False,
        )
        return workspace_redirect(
            device_id,
            interface_id,
            error=(
                f"La interfaz fue creada, pero no se pudo asignar {normalized_ip}: "
                f"{exc.message}"
            ),
        )

    audit_event(
        request,
        action="INTERFACE_IP_CREATE",
        resource="ip_address",
        resource_id=address_id,
        detail=(
            f"Dirección {normalized_ip} creada junto con la interfaz #{interface_id} "
            f"del dispositivo #{device_id}."
        ),
        success=True,
    )
    return workspace_redirect(
        device_id,
        interface_id,
        notice=f"La interfaz {clean_name} y la dirección {normalized_ip} fueron creadas.",
    )
