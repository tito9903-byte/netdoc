from __future__ import annotations

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


def display_name(value: Any, fallback: str = "") -> str:
    if isinstance(value, dict):
        return str(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("value")
            or fallback
        )
    return str(value or fallback)


def interface_cable_id(interface: dict[str, Any]) -> int | None:
    return nested_id(interface.get("cable"))


def remote_endpoint(interface: dict[str, Any]) -> dict[str, Any]:
    endpoints = interface.get("connected_endpoints") or []
    if not isinstance(endpoints, list) or not endpoints:
        return {}
    endpoint = endpoints[0]
    return endpoint if isinstance(endpoint, dict) else {}


def cable_contains_interface(cable: dict[str, Any], interface_id: int) -> bool:
    for side in ("a_terminations", "b_terminations"):
        terminations = cable.get(side) or []
        if not isinstance(terminations, list):
            continue
        for termination in terminations:
            if not isinstance(termination, dict):
                continue
            object_type = termination.get("object_type")
            if isinstance(object_type, dict):
                object_type = (
                    object_type.get("value")
                    or object_type.get("model")
                    or object_type.get("display")
                )
            object_id = termination.get("object_id")
            if not isinstance(object_id, int):
                object_id = nested_id(termination.get("object"))
            if str(object_type or "").strip().lower() == "dcim.interface" and object_id == interface_id:
                return True
    return False


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
    cable_id: int,
    detail: str,
    success: bool,
) -> None:
    ip_address, user_agent = request_client_data(request)
    user_id = request.session.get("user_id")
    with session_scope() as session:
        record_audit(
            session,
            action="DEVICE_CONNECTION_DELETE",
            resource="cable",
            resource_id=str(cable_id),
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def edit_redirect(
    device_id: int,
    interface_id: int,
    *,
    error: str = "",
) -> RedirectResponse:
    query = f"?{urlencode({'error': error})}" if error else ""
    return RedirectResponse(
        f"/devices/{device_id}/interfaces/{interface_id}/edit{query}",
        status_code=303,
    )


def device_redirect(device_id: int, notice: str) -> RedirectResponse:
    query = urlencode({"notice": notice})
    return RedirectResponse(
        f"/devices/{device_id}?{query}#interfaces",
        status_code=303,
    )


async def load_connection(
    *,
    device_id: int,
    interface_id: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    service = DeviceTypeService()
    device = await service.request("GET", f"/api/dcim/devices/{device_id}/")
    interface = await service.request("GET", f"/api/dcim/interfaces/{interface_id}/")

    if nested_id(interface.get("device")) != device_id:
        raise DeviceTypeServiceError(
            "La interfaz no pertenece a este dispositivo.",
            404,
        )

    cable_id = interface_cable_id(interface)
    if cable_id is None:
        raise DeviceTypeServiceError(
            "Esta interfaz no tiene un cable documentado que pueda eliminarse.",
            409,
        )

    cable = await service.request("GET", f"/api/dcim/cables/{cable_id}/")
    if not cable_contains_interface(cable, interface_id):
        raise DeviceTypeServiceError(
            "El cable actual no contiene esta interfaz. Recarga la ficha antes de continuar.",
            409,
        )

    return device, interface, cable, remote_endpoint(interface)


async def delete_cable(cable_id: int) -> None:
    client = await get_shared_netbox_client()
    response = await client.delete(
        f"api/dcim/cables/{cable_id}/",
        headers={"Accept": "application/json"},
    )
    if response.is_error:
        raise DeviceTypeServiceError(
            DeviceTypeService._error_message(response),
            response.status_code,
        )
    DeviceTypeService.clear_read_caches()


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/connection/delete",
    response_class=HTMLResponse,
)
async def interface_connection_delete_page(
    request: Request,
    device_id: int,
    interface_id: int,
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    try:
        device, interface, cable, endpoint = await load_connection(
            device_id=device_id,
            interface_id=interface_id,
        )
    except DeviceTypeServiceError as exc:
        return edit_redirect(
            device_id,
            interface_id,
            error=exc.message,
        )

    cable_id = int(cable.get("id") or 0)
    return templates.TemplateResponse(
        request=request,
        name="interface_connection_delete.html",
        context=context(
            request,
            page_title="Eliminar conexión",
            page_subtitle="Desconectar ambos extremos sin eliminar interfaces ni direcciones IP",
            device=device,
            device_id=device_id,
            interface=interface,
            interface_id=interface_id,
            cable=cable,
            cable_id=cable_id,
            endpoint=endpoint,
            remote_device=endpoint.get("device") if isinstance(endpoint, dict) else {},
            csrf_token=signed_form_token(
                request,
                f"interface-connection-delete:{device_id}:{interface_id}:{cable_id}",
            ),
        ),
    )


@router.post(
    "/devices/{device_id}/interfaces/{interface_id}/connection/actions/delete"
)
async def interface_connection_delete_submit(
    request: Request,
    device_id: int,
    interface_id: int,
    cable_id: int = Form(...),
    csrf_token: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    namespace = f"interface-connection-delete:{device_id}:{interface_id}:{cable_id}"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return edit_redirect(
            device_id,
            interface_id,
            error="La sesión de seguridad venció. Abre nuevamente la confirmación.",
        )
    if not settings.netbox_write_enabled:
        return edit_redirect(
            device_id,
            interface_id,
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        device, interface, cable, endpoint = await load_connection(
            device_id=device_id,
            interface_id=interface_id,
        )
        current_cable_id = interface_cable_id(interface)
        if current_cable_id != cable_id or nested_id(cable.get("id")) != cable_id:
            raise DeviceTypeServiceError(
                "La conexión cambió desde que abriste la confirmación. No se eliminó ningún cable.",
                409,
            )

        local_name = str(interface.get("name") or f"Interfaz #{interface_id}")
        remote_device = endpoint.get("device") if isinstance(endpoint, dict) else {}
        remote_device_name = display_name(remote_device, "equipo remoto")
        remote_interface_name = display_name(endpoint, "interfaz remota")
        device_name = display_name(device, f"Dispositivo #{device_id}")

        await delete_cable(cable_id)
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            cable_id=cable_id,
            detail=exc.message,
            success=False,
        )
        return edit_redirect(
            device_id,
            interface_id,
            error=exc.message,
        )

    detail = (
        f"Cable #{cable_id} eliminado entre {device_name} {local_name} y "
        f"{remote_device_name} {remote_interface_name}."
    )
    audit_event(
        request,
        cable_id=cable_id,
        detail=detail,
        success=True,
    )
    return device_redirect(
        device_id,
        (
            f"La conexión de {local_name} con {remote_device_name} "
            f"{remote_interface_name} fue eliminada."
        ),
    )
