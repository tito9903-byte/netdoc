from __future__ import annotations

import asyncio
import hashlib
import hmac
from typing import Any

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import access_redirect, common_session_context
from app.core.config import get_settings
from app.services.netbox_client import NetBoxClient, NetBoxError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

STATUSES = [
    ("active", "Activo"),
    ("planned", "Planificado"),
    ("staged", "En preparación"),
    ("failed", "Con falla"),
    ("inventory", "Inventario"),
    ("decommissioning", "En retiro"),
    ("offline", "Fuera de línea"),
]


def require_login(request: Request):
    if (
        request.session.get("authenticated") is True
        and request.session.get("username")
    ):
        return None

    return RedirectResponse(
        "/login?next=/devices/actions/new",
        status_code=303,
    )


def signed_form_token(request: Request, namespace: str) -> str:
    """Crea un token CSRF sin escribir valores nuevos en la cookie de sesión.

    Starlette guarda la sesión completa en una cookie firmada. Cuando una ventana
    modal y la página principal cargan recursos en paralelo, una respuesta antigua
    puede sobrescribir un token CSRF agregado dinámicamente a esa cookie. Este token
    HMAC depende del usuario autenticado y del secreto del servidor, por lo que no
    sufre esa condición de carrera y continúa siendo imposible de adivinar.
    """

    user_id = request.session.get("user_id")
    username = str(request.session.get("username") or "")
    material = f"{namespace}:{user_id}:{username}".encode("utf-8")
    return hmac.new(
        settings.session_secret.encode("utf-8"),
        material,
        hashlib.sha256,
    ).hexdigest()


def verify_signed_form_token(
    request: Request,
    submitted: str,
    namespace: str,
) -> bool:
    if not isinstance(submitted, str) or not submitted:
        return False
    expected = signed_form_token(request, namespace)
    return hmac.compare_digest(expected, submitted)


def auth_headers() -> dict[str, str]:
    prefix = (
        "Bearer"
        if settings.netbox_token_type.lower() == "bearer"
        else "Token"
    )

    return {
        "Authorization": f"{prefix} {settings.netbox_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": f"NetDoc/{settings.app_version}",
    }


async def load_options() -> dict[str, list[dict[str, Any]]]:
    client = NetBoxClient()

    sites, racks, manufacturers, device_types, roles = await asyncio.gather(
        client.get_all(
            "/api/dcim/sites/",
            params={"ordering": "name"},
        ),
        client.get_all(
            "/api/dcim/racks/",
            params={"ordering": "name"},
        ),
        client.get_all(
            "/api/dcim/manufacturers/",
            params={"ordering": "name"},
        ),
        client.get_all(
            "/api/dcim/device-types/",
            params={"ordering": "model"},
        ),
        client.get_all(
            "/api/dcim/device-roles/",
            params={"ordering": "name"},
        ),
    )

    return {
        "sites": sites,
        "racks": racks,
        "manufacturers": manufacturers,
        "device_types": device_types,
        "roles": roles,
    }


def context(
    request: Request,
    options: dict[str, list[dict[str, Any]]],
    form_data: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    return {
        **common_session_context(request),
        "current_page": "devices",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "csrf_token": signed_form_token(request, "device-create"),
        "page_title": "Crear equipo",
        "page_subtitle": (
            "Registro guiado de un dispositivo nuevo en NetBox"
        ),
        "statuses": STATUSES,
        "form_data": form_data,
        "errors": errors,
        **options,
    }


async def render_form(
    request: Request,
    form_data: dict[str, str],
    errors: list[str],
    status_code: int = 200,
):
    try:
        options = await load_options()
    except NetBoxError as exc:
        return HTMLResponse(
            f"Error consultando NetBox: {exc.message}",
            status_code=503,
        )

    return templates.TemplateResponse(
        request=request,
        name="device_create.html",
        status_code=status_code,
        context=context(
            request,
            options,
            form_data,
            errors,
        ),
    )


def parse_id(
    value: str,
    label: str,
    errors: list[str],
    required: bool = False,
) -> int | None:
    value = value.strip()

    if not value:
        if required:
            errors.append(f"Debes seleccionar {label}.")
        return None

    try:
        return int(value)
    except ValueError:
        errors.append(f"El valor de {label} no es válido.")
        return None


def format_api_errors(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["NetBox rechazó los datos enviados."]

    errors: list[str] = []

    for field, messages in payload.items():
        if isinstance(messages, list):
            message = ", ".join(str(item) for item in messages)
        else:
            message = str(messages)

        errors.append(f"{field}: {message}")

    return errors


def nested_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("id"), int):
        return int(value["id"])
    return None


def nested_label(value: Any, fallback: str = "—") -> str:
    if isinstance(value, dict):
        for key in ("display", "name", "label", "address", "value"):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return str(candidate)
    if value not in (None, ""):
        return str(value)
    return fallback


def address_family(address: dict[str, Any]) -> int:
    family = address.get("family")
    if isinstance(family, dict):
        raw = family.get("value")
        if raw in (4, "4"):
            return 4
        if raw in (6, "6"):
            return 6
    raw_address = str(address.get("address") or address.get("display") or "")
    return 6 if ":" in raw_address else 4


def decorate_ip_address(address: dict[str, Any]) -> dict[str, Any]:
    assigned = address.get("assigned_object") or {}
    interface = nested_label(assigned, "Sin interfaz")
    rendered_address = str(
        address.get("display")
        or address.get("address")
        or "IP sin dirección"
    )
    return {
        **address,
        "_family": address_family(address),
        "_interface_label": interface,
        "_option_label": f"{rendered_address} — {interface}",
    }


async def load_device_primary_ip_data(
    device_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    client = NetBoxClient()
    device, addresses = await asyncio.gather(
        client.get_device(device_id),
        client.get_all(
            "/api/ipam/ip-addresses/",
            params={
                "device_id": device_id,
                "ordering": "address",
            },
            page_limit=200,
        ),
    )
    return device, [decorate_ip_address(item) for item in addresses]


def primary_ip_context(
    request: Request,
    *,
    device: dict[str, Any],
    addresses: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    return {
        **common_session_context(request),
        "current_page": "devices",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "page_title": "Configurar IP principal",
        "page_subtitle": (
            "Selecciona la dirección que NetDoc mostrará para este dispositivo"
        ),
        "device": device,
        "ipv4_addresses": [item for item in addresses if item["_family"] == 4],
        "ipv6_addresses": [item for item in addresses if item["_family"] == 6],
        "current_primary_ip4_id": nested_id(device.get("primary_ip4")),
        "current_primary_ip6_id": nested_id(device.get("primary_ip6")),
        "csrf_token": signed_form_token(request, f"device-primary:{device.get('id')}"),
        "errors": errors,
    }


async def render_primary_ip_form(
    request: Request,
    device_id: int,
    errors: list[str],
    status_code: int = 200,
):
    try:
        device, addresses = await load_device_primary_ip_data(device_id)
    except NetBoxError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context={
                **common_session_context(request),
                "current_page": "devices",
                "netbox_connected": exc.status_code != 503,
                "netbox_url": settings.netbox_url,
                "write_enabled": settings.netbox_write_enabled,
                "page_title": "IP principal no disponible",
                "page_subtitle": "No fue posible consultar el dispositivo",
                "error_title": "No se pudieron cargar sus direcciones IP",
                "error_message": exc.message,
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="device_primary_ip.html",
        status_code=status_code,
        context=primary_ip_context(
            request,
            device=device,
            addresses=addresses,
            errors=errors,
        ),
    )


async def patch_device(
    device_id: int,
    payload: dict[str, Any],
) -> tuple[int, Any]:
    url = (
        f"{settings.netbox_url.rstrip('/')}"
        f"/api/dcim/devices/{device_id}/"
    )
    try:
        async with httpx.AsyncClient(
            headers=auth_headers(),
            verify=settings.netbox_verify_ssl,
            timeout=settings.netbox_timeout,
            follow_redirects=True,
        ) as client:
            response = await client.patch(url, json=payload)
    except httpx.HTTPError as exc:
        raise NetBoxError(
            f"No fue posible conectar con NetBox: {exc}"
        ) from exc

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = None
    return response.status_code, response_payload


@router.get(
    "/devices/actions/new",
    response_class=HTMLResponse,
)
async def create_device_page(request: Request):
    redirect = require_login(request)

    if redirect:
        return redirect

    return await render_form(
        request,
        form_data={},
        errors=[],
    )


@router.post(
    "/devices/actions/new",
    response_class=HTMLResponse,
)
async def create_device_submit(
    request: Request,
    csrf_token: str = Form(...),
    name: str = Form(""),
    site_id: str = Form(""),
    manufacturer_id: str = Form(""),
    device_type_id: str = Form(""),
    role_id: str = Form(""),
    status: str = Form("active"),
    rack_id: str = Form(""),
    position: str = Form(""),
    face: str = Form(""),
    serial: str = Form(""),
):
    redirect = require_login(request)

    if redirect:
        return redirect

    form_data = {
        "name": name.strip(),
        "site_id": site_id.strip(),
        "manufacturer_id": manufacturer_id.strip(),
        "device_type_id": device_type_id.strip(),
        "role_id": role_id.strip(),
        "status": status.strip(),
        "rack_id": rack_id.strip(),
        "position": position.strip(),
        "face": face.strip(),
        "serial": serial.strip(),
    }

    if not verify_signed_form_token(
        request,
        csrf_token,
        "device-create",
    ):
        return await render_form(
            request,
            form_data,
            [
                "La sesión de seguridad del formulario venció o fue reemplazada. "
                "El formulario se recargó sin perder los datos; vuelve a pulsar Crear equipo."
            ],
            status_code=403,
        )

    errors: list[str] = []

    if not settings.netbox_write_enabled:
        errors.append(
            "La escritura está desactivada en NetDoc."
        )

    if not form_data["name"]:
        errors.append("El nombre del equipo es obligatorio.")

    site = parse_id(
        form_data["site_id"],
        "un sitio",
        errors,
        required=True,
    )

    device_type = parse_id(
        form_data["device_type_id"],
        "un tipo de dispositivo",
        errors,
        required=True,
    )

    role = parse_id(
        form_data["role_id"],
        "un rol",
        errors,
        required=True,
    )

    rack = parse_id(
        form_data["rack_id"],
        "un rack",
        errors,
    )

    rack_position: float | None = None

    if form_data["position"]:
        try:
            rack_position = float(
                form_data["position"].replace(",", ".")
            )
        except ValueError:
            errors.append(
                "La posición del rack no es válida."
            )

    if rack_position is not None and rack is None:
        errors.append(
            "Selecciona un rack antes de indicar la posición."
        )

    if form_data["face"] not in {"", "front", "rear"}:
        errors.append(
            "La cara del rack no es válida."
        )

    if form_data["status"] not in {
        value
        for value, _ in STATUSES
    }:
        errors.append(
            "El estado seleccionado no es válido."
        )

    if errors:
        return await render_form(
            request,
            form_data,
            errors,
            status_code=400,
        )

    reader = NetBoxClient()

    try:
        name_result, serial_result = await asyncio.gather(
            reader.get_list(
                "/api/dcim/devices/",
                params={
                    "name": form_data["name"],
                    "limit": 1,
                },
            ),
            reader.get_list(
                "/api/dcim/devices/",
                params={
                    "serial": form_data["serial"],
                    "limit": 1,
                },
            )
            if form_data["serial"]
            else asyncio.sleep(
                0,
                result={"count": 0},
            ),
        )
    except NetBoxError as exc:
        return await render_form(
            request,
            form_data,
            [exc.message],
            status_code=503,
        )

    if name_result.get("count"):
        errors.append(
            "Ya existe un dispositivo con ese nombre."
        )

    if serial_result.get("count"):
        errors.append(
            "Ya existe un dispositivo con ese número de serie."
        )

    if errors:
        return await render_form(
            request,
            form_data,
            errors,
            status_code=400,
        )

    payload: dict[str, Any] = {
        "name": form_data["name"],
        "site": site,
        "device_type": device_type,
        "role": role,
        "status": form_data["status"],
        "changelog_message": (
            "Equipo creado desde NetDoc por "
            f"{request.session.get('username', 'usuario')}."
        ),
    }

    if rack is not None:
        payload["rack"] = rack

    if rack_position is not None:
        payload["position"] = rack_position

    if form_data["face"]:
        payload["face"] = form_data["face"]

    if form_data["serial"]:
        payload["serial"] = form_data["serial"]

    url = (
        f"{settings.netbox_url.rstrip('/')}"
        "/api/dcim/devices/"
    )

    try:
        async with httpx.AsyncClient(
            headers=auth_headers(),
            verify=settings.netbox_verify_ssl,
            timeout=settings.netbox_timeout,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                url,
                json=payload,
            )
    except httpx.HTTPError as exc:
        return await render_form(
            request,
            form_data,
            [f"No fue posible conectar con NetBox: {exc}"],
            status_code=503,
        )

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = None

    if response.status_code != 201:
        return await render_form(
            request,
            form_data,
            format_api_errors(response_payload),
            status_code=response.status_code,
        )

    if not isinstance(response_payload, dict):
        return await render_form(
            request,
            form_data,
            ["NetBox creó el equipo, pero devolvió una respuesta inválida."],
            status_code=502,
        )

    device_id = response_payload.get("id")

    if not isinstance(device_id, int):
        return await render_form(
            request,
            form_data,
            ["NetBox creó el equipo, pero no devolvió su identificador."],
            status_code=502,
        )

    return RedirectResponse(
        f"/devices/{device_id}",
        status_code=303,
    )


@router.get(
    "/devices/{device_id}/primary-ip/new",
    response_class=HTMLResponse,
)
async def primary_ip_page(
    request: Request,
    device_id: int,
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect
    return await render_primary_ip_form(request, device_id, [])


@router.post(
    "/devices/{device_id}/primary-ip/new",
    response_class=HTMLResponse,
)
async def primary_ip_submit(
    request: Request,
    device_id: int,
    csrf_token: str = Form(...),
    primary_ip4_id: str = Form(""),
    primary_ip6_id: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    namespace = f"device-primary:{device_id}"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return await render_primary_ip_form(
            request,
            device_id,
            [
                "La sesión de seguridad del formulario venció. "
                "Vuelve a guardar la selección."
            ],
            status_code=403,
        )

    if not settings.netbox_write_enabled:
        return await render_primary_ip_form(
            request,
            device_id,
            ["La escritura está desactivada en NetDoc."],
            status_code=403,
        )

    try:
        device, addresses = await load_device_primary_ip_data(device_id)
    except NetBoxError as exc:
        return await render_primary_ip_form(
            request,
            device_id,
            [exc.message],
            status_code=503,
        )

    ipv4_ids = {
        int(item["id"])
        for item in addresses
        if item.get("_family") == 4 and isinstance(item.get("id"), int)
    }
    ipv6_ids = {
        int(item["id"])
        for item in addresses
        if item.get("_family") == 6 and isinstance(item.get("id"), int)
    }

    errors: list[str] = []
    selected_ip4 = parse_id(primary_ip4_id, "una IPv4", errors)
    selected_ip6 = parse_id(primary_ip6_id, "una IPv6", errors)

    if selected_ip4 is not None and selected_ip4 not in ipv4_ids:
        errors.append(
            "La IPv4 seleccionada no pertenece a una interfaz de este dispositivo."
        )
    if selected_ip6 is not None and selected_ip6 not in ipv6_ids:
        errors.append(
            "La IPv6 seleccionada no pertenece a una interfaz de este dispositivo."
        )

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="device_primary_ip.html",
            status_code=400,
            context=primary_ip_context(
                request,
                device=device,
                addresses=addresses,
                errors=errors,
            ),
        )

    payload = {
        "primary_ip4": selected_ip4,
        "primary_ip6": selected_ip6,
        "changelog_message": (
            "IP principal actualizada desde NetDoc por "
            f"{request.session.get('username', 'usuario')}."
        ),
    }

    try:
        status_code, response_payload = await patch_device(device_id, payload)
    except NetBoxError as exc:
        return templates.TemplateResponse(
            request=request,
            name="device_primary_ip.html",
            status_code=503,
            context=primary_ip_context(
                request,
                device=device,
                addresses=addresses,
                errors=[exc.message],
            ),
        )

    if status_code != 200:
        return templates.TemplateResponse(
            request=request,
            name="device_primary_ip.html",
            status_code=status_code,
            context=primary_ip_context(
                request,
                device=device,
                addresses=addresses,
                errors=format_api_errors(response_payload),
            ),
        )

    return RedirectResponse(
        f"/devices/{device_id}?primary_ip_saved=1",
        status_code=303,
    )
