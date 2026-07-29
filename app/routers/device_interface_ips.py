from __future__ import annotations

import asyncio
from ipaddress import ip_interface
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
    has_permission,
    request_client_data,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.routers.device_create import signed_form_token, verify_signed_form_token
from app.services.access_service import record_audit
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def _nested_id(value: Any) -> int | None:
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


def _choice_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or value.get("slug") or "")
    return str(value or "")


def _choice_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("label")
            or value.get("display")
            or value.get("name")
            or value.get("value")
            or "—"
        )
    return str(value or "—")


def _field_choices(
    options: dict[str, Any],
    field: str,
    *,
    method: str = "POST",
) -> list[dict[str, str]]:
    actions = options.get("actions") if isinstance(options, dict) else None
    schema = actions.get(method) if isinstance(actions, dict) else None
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


def _allowed_fields(options: dict[str, Any], method: str) -> set[str]:
    actions = options.get("actions") if isinstance(options, dict) else None
    schema = actions.get(method) if isinstance(actions, dict) else None
    return set(schema.keys()) if isinstance(schema, dict) else set()


def _address_interface_id(address: dict[str, Any]) -> int | None:
    return (
        _nested_id(address.get("assigned_object"))
        or _nested_id(address.get("assigned_object_id"))
    )


def _context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "devices",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def _audit(
    request: Request,
    *,
    action: str,
    address_id: int | None,
    detail: str,
    success: bool,
) -> None:
    ip_address, user_agent = request_client_data(request)
    user_id = request.session.get("user_id")
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource="ip_address",
            resource_id=str(address_id) if address_id else None,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def _redirect(
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
        f"/devices/{device_id}/interfaces/{interface_id}/edit{query}",
        status_code=303,
    )


async def _load_objects(
    *,
    device_id: int,
    interface_id: int,
    address_id: int | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any] | None,
    dict[str, Any],
    list[dict[str, Any]],
]:
    service = DeviceTypeService()
    device, interface, options, vrfs = await asyncio.gather(
        service.request("GET", f"/api/dcim/devices/{device_id}/"),
        service.request("GET", f"/api/dcim/interfaces/{interface_id}/"),
        service.request("OPTIONS", "/api/ipam/ip-addresses/"),
        service.get_all("/api/ipam/vrfs/", params={"ordering": "name,rd"}),
    )

    if _nested_id(interface.get("device")) != device_id:
        raise DeviceTypeServiceError(
            "La interfaz no pertenece a este dispositivo.",
            404,
        )

    address = None
    if address_id is not None:
        address = await service.request(
            "GET",
            f"/api/ipam/ip-addresses/{address_id}/",
        )
        if _address_interface_id(address) != interface_id:
            raise DeviceTypeServiceError(
                "La dirección IP no está asignada a esta interfaz.",
                404,
            )

    return device, interface, address, options, vrfs


async def _render_form(
    request: Request,
    *,
    device_id: int,
    interface_id: int,
    address_id: int | None = None,
    error: str = "",
    status_code: int = 200,
):
    try:
        device, interface, address, options, vrfs = await _load_objects(
            device_id=device_id,
            interface_id=interface_id,
            address_id=address_id,
        )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=_context(
                request,
                page_title="Dirección IP no disponible",
                page_subtitle="No fue posible preparar la administración de IP",
                error_title="No se pudo cargar la dirección IP",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    primary_ip4_id = _nested_id(device.get("primary_ip4"))
    primary_ip6_id = _nested_id(device.get("primary_ip6"))
    is_primary = bool(
        address_id is not None
        and address_id in {primary_ip4_id, primary_ip6_id}
    )
    namespace = (
        f"device-interface-ip-edit:{device_id}:{interface_id}:{address_id}"
        if address_id is not None
        else f"device-interface-ip-create:{device_id}:{interface_id}"
    )

    return templates.TemplateResponse(
        request=request,
        name="device_interface_ip_form.html",
        status_code=status_code,
        context=_context(
            request,
            page_title="Editar dirección IP" if address else "Agregar dirección IP",
            page_subtitle=(
                "Modificar la dirección asignada a la interfaz"
                if address
                else "Asignar una dirección nueva directamente a la interfaz"
            ),
            device=device,
            device_id=device_id,
            interface=interface,
            interface_id=interface_id,
            address=address,
            address_id=address_id,
            status_choices=_field_choices(options, "status"),
            role_choices=_field_choices(options, "role"),
            vrfs=vrfs,
            is_primary=is_primary,
            csrf_token=signed_form_token(request, namespace),
            error=error,
        ),
    )


@router.get(
    "/api/netdoc/devices/{device_id}/interfaces/{interface_id}/ip-addresses"
)
async def interface_addresses_api(
    request: Request,
    device_id: int,
    interface_id: int,
):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied

    service = DeviceTypeService()
    try:
        device, interface, addresses = await asyncio.gather(
            service.request("GET", f"/api/dcim/devices/{device_id}/"),
            service.request("GET", f"/api/dcim/interfaces/{interface_id}/"),
            service.get_all(
                "/api/ipam/ip-addresses/",
                params={"interface_id": interface_id, "ordering": "family,address"},
            ),
        )
        if _nested_id(interface.get("device")) != device_id:
            raise DeviceTypeServiceError(
                "La interfaz no pertenece a este dispositivo.",
                404,
            )
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code or 503,
            content={"ok": False, "error": exc.message},
        )

    primary_ids = {
        value
        for value in (
            _nested_id(device.get("primary_ip4")),
            _nested_id(device.get("primary_ip6")),
        )
        if value is not None
    }
    rows = []
    for item in addresses:
        address_id = _nested_id(item.get("id"))
        if address_id is None:
            continue
        rows.append({
            "id": address_id,
            "address": str(item.get("address") or item.get("display") or ""),
            "status": _choice_label(item.get("status")),
            "role": _choice_label(item.get("role")) if item.get("role") else "",
            "dns_name": str(item.get("dns_name") or ""),
            "description": str(item.get("description") or ""),
            "is_primary": address_id in primary_ids,
            "edit_url": (
                f"/devices/{device_id}/interfaces/{interface_id}/"
                f"ip-addresses/{address_id}/edit"
            ),
        })

    return {
        "ok": True,
        "can_manage": (
            settings.netbox_write_enabled
            and has_permission(request, "devices.create")
        ),
        "device_id": device_id,
        "interface_id": interface_id,
        "interface_name": str(interface.get("name") or interface.get("display") or ""),
        "create_url": (
            f"/devices/{device_id}/interfaces/{interface_id}/ip-addresses/new"
        ),
        "addresses": rows,
    }


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/new",
    response_class=HTMLResponse,
)
async def interface_ip_create_page(
    request: Request,
    device_id: int,
    interface_id: int,
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await _render_form(
        request,
        device_id=device_id,
        interface_id=interface_id,
    )


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/{address_id}/edit",
    response_class=HTMLResponse,
)
async def interface_ip_edit_page(
    request: Request,
    device_id: int,
    interface_id: int,
    address_id: int,
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await _render_form(
        request,
        device_id=device_id,
        interface_id=interface_id,
        address_id=address_id,
    )


async def _save_address(
    request: Request,
    *,
    device_id: int,
    interface_id: int,
    address_id: int | None,
    csrf_token: str,
    address: str,
    status: str,
    role: str,
    vrf_id: str,
    dns_name: str,
    description: str,
    make_primary: str,
):
    namespace = (
        f"device-interface-ip-edit:{device_id}:{interface_id}:{address_id}"
        if address_id is not None
        else f"device-interface-ip-create:{device_id}:{interface_id}"
    )
    if not verify_signed_form_token(request, csrf_token, namespace):
        return await _render_form(
            request,
            device_id=device_id,
            interface_id=interface_id,
            address_id=address_id,
            error="La sesión de seguridad venció. Abre nuevamente el formulario.",
            status_code=403,
        )
    if not settings.netbox_write_enabled:
        return await _render_form(
            request,
            device_id=device_id,
            interface_id=interface_id,
            address_id=address_id,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
        )

    try:
        device, _interface, existing, options, _vrfs = await _load_objects(
            device_id=device_id,
            interface_id=interface_id,
            address_id=address_id,
        )
        try:
            normalized = str(ip_interface(address.strip()))
        except ValueError as exc:
            raise DeviceTypeServiceError(
                "Escribe una dirección válida con su prefijo; por ejemplo 192.0.2.10/24.",
                400,
            ) from exc

        family = ip_interface(normalized).version
        method = "PATCH" if address_id is not None else "POST"
        allowed = _allowed_fields(options, method)
        candidate: dict[str, Any] = {
            "address": normalized,
            "status": status.strip() or "active",
            "role": role.strip() or None,
            "vrf": int(vrf_id) if vrf_id.strip().isdigit() else None,
            "dns_name": dns_name.strip(),
            "description": description.strip(),
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": interface_id,
        }
        payload = {
            key: value
            for key, value in candidate.items()
            if not allowed or key in allowed
        }
        service = DeviceTypeService()
        endpoint = (
            f"/api/ipam/ip-addresses/{address_id}/"
            if address_id is not None
            else "/api/ipam/ip-addresses/"
        )
        saved = await service.request(method, endpoint, json_body=payload)
        if not isinstance(saved, dict) or _nested_id(saved.get("id")) is None:
            raise DeviceTypeServiceError(
                "NetBox guardó la dirección, pero devolvió un formato inesperado.",
                502,
            )
        saved_id = int(_nested_id(saved.get("id")) or 0)

        current_primary4 = _nested_id(device.get("primary_ip4"))
        current_primary6 = _nested_id(device.get("primary_ip6"))
        primary_payload: dict[str, Any] = {}
        wants_primary = str(make_primary or "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if address_id is not None and address_id == current_primary4 and family != 4:
            primary_payload["primary_ip4"] = None
        if address_id is not None and address_id == current_primary6 and family != 6:
            primary_payload["primary_ip6"] = None

        if wants_primary:
            primary_payload["primary_ip4" if family == 4 else "primary_ip6"] = saved_id
        elif address_id is not None:
            if address_id == current_primary4:
                primary_payload["primary_ip4"] = None
            if address_id == current_primary6:
                primary_payload["primary_ip6"] = None

        if primary_payload:
            await service.request(
                "PATCH",
                f"/api/dcim/devices/{device_id}/",
                json_body=primary_payload,
            )
    except DeviceTypeServiceError as exc:
        action = "INTERFACE_IP_UPDATE" if address_id else "INTERFACE_IP_CREATE"
        _audit(
            request,
            action=action,
            address_id=address_id,
            detail=exc.message,
            success=False,
        )
        return await _render_form(
            request,
            device_id=device_id,
            interface_id=interface_id,
            address_id=address_id,
            error=exc.message,
            status_code=exc.status_code or 400,
        )

    action = "INTERFACE_IP_UPDATE" if address_id else "INTERFACE_IP_CREATE"
    _audit(
        request,
        action=action,
        address_id=saved_id,
        detail=(
            f"Dirección {normalized} guardada en la interfaz #{interface_id} "
            f"del dispositivo #{device_id}."
        ),
        success=True,
    )
    return _redirect(
        device_id,
        interface_id,
        notice=f"La dirección {normalized} fue guardada correctamente.",
    )


@router.post(
    "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/actions/create"
)
async def interface_ip_create_submit(
    request: Request,
    device_id: int,
    interface_id: int,
    csrf_token: str = Form(""),
    address: str = Form(""),
    status: str = Form("active"),
    role: str = Form(""),
    vrf_id: str = Form(""),
    dns_name: str = Form(""),
    description: str = Form(""),
    make_primary: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await _save_address(
        request,
        device_id=device_id,
        interface_id=interface_id,
        address_id=None,
        csrf_token=csrf_token,
        address=address,
        status=status,
        role=role,
        vrf_id=vrf_id,
        dns_name=dns_name,
        description=description,
        make_primary=make_primary,
    )


@router.post(
    "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/"
    "{address_id}/actions/update"
)
async def interface_ip_edit_submit(
    request: Request,
    device_id: int,
    interface_id: int,
    address_id: int,
    csrf_token: str = Form(""),
    address: str = Form(""),
    status: str = Form("active"),
    role: str = Form(""),
    vrf_id: str = Form(""),
    dns_name: str = Form(""),
    description: str = Form(""),
    make_primary: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await _save_address(
        request,
        device_id=device_id,
        interface_id=interface_id,
        address_id=address_id,
        csrf_token=csrf_token,
        address=address,
        status=status,
        role=role,
        vrf_id=vrf_id,
        dns_name=dns_name,
        description=description,
        make_primary=make_primary,
    )
