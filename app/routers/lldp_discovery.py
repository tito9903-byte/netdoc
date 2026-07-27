from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.auth import (
    access_redirect,
    common_session_context,
    request_client_data,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.routers.device_create import signed_form_token, verify_signed_form_token
from app.services.access_service import record_audit
from app.services.connection_service import ConnectionService, ConnectionServiceError
from app.services.lldp_discovery_service import (
    LldpDiscoveryError,
    LldpDiscoveryService,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "devices",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "ssh_discovery_enabled": settings.netdoc_ssh_discovery_enabled,
        **extra,
    }


def audit_event(
    request: Request,
    *,
    action: str,
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
            resource="lldp_discovery",
            resource_id=resource_id,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def candidate_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.session_secret,
        salt="netdoc-lldp-candidate-v1",
    )


def candidate_token(row: dict[str, object]) -> str:
    payload = {
        "local_device_id": row.get("local_device_id"),
        "local_device_name": row.get("local_device_name"),
        "local_interface_id": row.get("local_interface_id"),
        "local_interface": row.get("local_interface_netbox") or row.get("local_interface"),
        "remote_device_id": row.get("remote_device_id"),
        "remote_device_name": row.get("remote_device_name"),
        "remote_interface_id": row.get("remote_interface_id"),
        "remote_interface": row.get("remote_interface_netbox") or row.get("remote_port_id"),
        "management_ip": row.get("management_ip"),
        "chassis_id": row.get("chassis_id"),
    }
    return candidate_serializer().dumps(payload)


def load_candidate(token: str) -> dict[str, object]:
    try:
        payload = candidate_serializer().loads(token, max_age=900)
    except SignatureExpired as exc:
        raise LldpDiscoveryError(
            "La propuesta LLDP venció. Ejecuta nuevamente el descubrimiento.",
            400,
        ) from exc
    except BadSignature as exc:
        raise LldpDiscoveryError(
            "La propuesta LLDP no es válida o fue modificada.",
            400,
        ) from exc
    if not isinstance(payload, dict):
        raise LldpDiscoveryError("La propuesta LLDP no tiene un formato válido.", 400)
    return payload


async def render_page(
    request: Request,
    *,
    device_id: int,
    discovery: dict[str, object] | None = None,
    error: str = "",
    status_code: int = 200,
):
    service = LldpDiscoveryService()
    try:
        device_context = await service.device_context(device_id)
    except LldpDiscoveryError as exc:
        device_context = {
            "device": {"id": device_id, "name": f"Dispositivo #{device_id}"},
            "host": "",
            "platform": None,
            "profile_key": "",
            "command": "",
        }
        if not error:
            error = exc.message
        status_code = exc.status_code if exc.status_code >= 400 else status_code

    try:
        choices = await ConnectionService().get_cable_choices()
    except ConnectionServiceError:
        choices = {
            "types": [],
            "statuses": [],
            "length_units": [],
        }

    if discovery:
        for row in discovery.get("observations", []):
            if isinstance(row, dict) and row.get("ready"):
                row["candidate_token"] = candidate_token(row)

    return templates.TemplateResponse(
        request=request,
        name="lldp_discovery.html",
        status_code=status_code,
        context=context(
            request,
            page_title="Descubrimiento LLDP",
            page_subtitle="Comparar vecinos anunciados con la documentación de NetBox",
            device_id=device_id,
            device_context=device_context,
            discovery=discovery,
            error=error,
            cable_types=choices.get("types", []),
            run_token=signed_form_token(request, f"lldp-discovery:{device_id}"),
            confirm_token=signed_form_token(request, f"lldp-confirm:{device_id}"),
            supported_platforms=service.supported_platforms(),
        ),
    )


@router.get(
    "/devices/{device_id}/lldp-discovery",
    response_class=HTMLResponse,
)
async def lldp_discovery_page(
    request: Request,
    device_id: int,
    run_method: str = "",
):
    redirect = access_redirect(request, "connections.view")
    if redirect:
        return redirect

    error = ""
    if run_method == "get":
        error = (
            "La ejecución LLDP no se inició porque la dirección /run fue abierta "
            "mediante GET. Usa el botón Ejecutar LLDP por SSH desde esta pantalla."
        )

    return await render_page(
        request,
        device_id=device_id,
        error=error,
    )


@router.post(
    "/devices/{device_id}/lldp-discovery/run",
    response_class=HTMLResponse,
)
async def lldp_discovery_run(
    request: Request,
    device_id: int,
    csrf_token: str = Form(""),
):
    redirect = access_redirect(request, "connections.view")
    if redirect:
        return redirect
    if not verify_signed_form_token(
        request,
        csrf_token,
        f"lldp-discovery:{device_id}",
    ):
        return await render_page(
            request,
            device_id=device_id,
            error="La sesión de seguridad venció. Abre nuevamente el descubrimiento.",
            status_code=403,
        )

    try:
        discovery = await LldpDiscoveryService().discover(device_id)
    except LldpDiscoveryError as exc:
        audit_event(
            request,
            action="LLDP_DISCOVERY_RUN",
            resource_id=str(device_id),
            detail=exc.message,
            success=False,
        )
        return await render_page(
            request,
            device_id=device_id,
            error=exc.message,
            status_code=exc.status_code,
        )

    audit_event(
        request,
        action="LLDP_DISCOVERY_RUN",
        resource_id=str(device_id),
        detail=(
            f"LLDP consultado: {discovery.get('neighbor_count', 0)} vecinos; "
            f"{discovery.get('ready_count', 0)} listos para confirmar; "
            f"{discovery.get('conflict_count', 0)} conflictos."
        ),
        success=True,
    )
    return await render_page(
        request,
        device_id=device_id,
        discovery=discovery,
    )


@router.post(
    "/devices/{device_id}/lldp-discovery/confirm",
    response_class=HTMLResponse,
)
async def lldp_discovery_confirm(
    request: Request,
    device_id: int,
    csrf_token: str = Form(""),
    candidate: str = Form(""),
    cable_type: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    if not verify_signed_form_token(
        request,
        csrf_token,
        f"lldp-confirm:{device_id}",
    ):
        return await render_page(
            request,
            device_id=device_id,
            error="La sesión de seguridad venció. Ejecuta nuevamente el descubrimiento.",
            status_code=403,
        )
    if not settings.netbox_write_enabled:
        return await render_page(
            request,
            device_id=device_id,
            error="La escritura en NetBox está deshabilitada.",
            status_code=403,
        )
    if not cable_type:
        return await render_page(
            request,
            device_id=device_id,
            error="Selecciona el tipo físico del cable antes de documentarlo.",
            status_code=400,
        )

    try:
        proposal = load_candidate(candidate)
        local_device_id = int(proposal.get("local_device_id") or 0)
        local_interface_id = int(proposal.get("local_interface_id") or 0)
        remote_interface_id = int(proposal.get("remote_interface_id") or 0)
        if local_device_id != device_id or min(local_interface_id, remote_interface_id) < 1:
            raise LldpDiscoveryError("La propuesta LLDP no coincide con el dispositivo.", 400)

        service = ConnectionService()
        local_interface = await service.get_interface(local_interface_id)
        remote_interface = await service.get_interface(remote_interface_id)
        if service.interface_is_connected(local_interface):
            raise LldpDiscoveryError(
                "La interfaz local ya tiene una conexión documentada en NetBox.",
                409,
            )
        if service.interface_is_connected(remote_interface):
            raise LldpDiscoveryError(
                "La interfaz remota ya tiene una conexión documentada en NetBox.",
                409,
            )

        local_name = str(proposal.get("local_interface") or local_interface_id)
        remote_name = str(proposal.get("remote_interface") or remote_interface_id)
        remote_device = str(proposal.get("remote_device_name") or "vecino LLDP")
        created = await service.create_interface_cable(
            interface_a_id=local_interface_id,
            interface_b_id=remote_interface_id,
            cable_type=cable_type,
            status="connected",
            label="",
            color="",
            length=None,
            length_unit="m",
            description=(
                f"Confirmado desde descubrimiento LLDP: {local_name} ↔ "
                f"{remote_device} {remote_name}."
            ),
            username=str(request.session.get("username") or "desconocido"),
        )
    except (LldpDiscoveryError, ConnectionServiceError) as exc:
        message = exc.message if hasattr(exc, "message") else str(exc)
        audit_event(
            request,
            action="LLDP_CABLE_CONFIRM",
            resource_id=str(device_id),
            detail=message,
            success=False,
        )
        return await render_page(
            request,
            device_id=device_id,
            error=message,
            status_code=getattr(exc, "status_code", 400) or 400,
        )

    cable_id = created.get("id") if isinstance(created, dict) else None
    audit_event(
        request,
        action="LLDP_CABLE_CONFIRM",
        resource_id=str(device_id),
        detail=(
            f"Cable #{cable_id or 'nuevo'} creado desde propuesta LLDP entre "
            f"interfaces #{local_interface_id} y #{remote_interface_id}."
        ),
        success=True,
    )
    params = urlencode({"lldp_documented": 1, "cable_id": cable_id or ""})
    return RedirectResponse(
        f"/devices/{device_id}?{params}#interfaces",
        status_code=303,
    )
