import asyncio
import secrets
from typing import Any

import httpx
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

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


def get_csrf(request: Request) -> str:
    token = request.session.get("create_device_csrf")

    if not token:
        token = secrets.token_urlsafe(32)
        request.session["create_device_csrf"] = token

    return token


def verify_csrf(request: Request, submitted: str) -> None:
    expected = request.session.get("create_device_csrf")

    if (
        not isinstance(expected, str)
        or not secrets.compare_digest(expected, submitted)
    ):
        raise HTTPException(
            status_code=403,
            detail="Solicitud de seguridad inválida.",
        )


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
        "User-Agent": "NetDoc/0.6.0",
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
        "current_page": "devices",
        "current_user": request.session.get("username", ""),
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "csrf_token": get_csrf(request),
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

    verify_csrf(request, csrf_token)

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
        raise HTTPException(
            status_code=502,
            detail="NetBox devolvió una respuesta inválida.",
        )

    device_id = response_payload.get("id")

    if not isinstance(device_id, int):
        raise HTTPException(
            status_code=502,
            detail="NetBox no devolvió el ID del equipo.",
        )

    return RedirectResponse(
        f"/devices/{device_id}",
        status_code=303,
    )
