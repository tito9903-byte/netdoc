from __future__ import annotations

from decimal import Decimal, InvalidOperation
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.services.connection_service import (
    ConnectionService,
    ConnectionServiceError,
)
from app.services.navigation_read_service import (
    NavigationReadError,
    NavigationReadService,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def is_authenticated(request: Request) -> bool:
    return (
        request.session.get("authenticated") is True
        and bool(request.session.get("username"))
    )


def login_redirect(request: Request) -> RedirectResponse | None:
    if is_authenticated(request):
        return None

    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    return RedirectResponse(
        url=f"/login?{urlencode({'next': next_url})}",
        status_code=303,
    )


def api_unauthorized(request: Request) -> JSONResponse | None:
    if is_authenticated(request):
        return None
    return JSONResponse(
        status_code=401,
        content={
            "ok": False,
            "error": "Debes iniciar sesión.",
        },
    )


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def valid_csrf(request: Request, submitted: str) -> bool:
    stored = request.session.get("csrf_token")
    return (
        isinstance(stored, str)
        and bool(stored)
        and secrets.compare_digest(stored, submitted)
    )


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        "current_page": "connections",
        "current_user": request.session.get("username", ""),
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


async def render_connections(
    request: Request,
    *,
    error: str | None = None,
    form_data: dict[str, str] | None = None,
    created_id: int | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    try:
        data = await NavigationReadService().connection_page_data()
        sites = data["sites"]
        choices = data["choices"]
        recent_cables = data["recent_cables"]
    except NavigationReadError as exc:
        sites = []
        choices = {
            "types": [],
            "statuses": [],
            "length_units": [],
        }
        recent_cables = []
        if error is None:
            error = exc.message

    return templates.TemplateResponse(
        request=request,
        name="connections.html",
        status_code=status_code,
        context=context(
            request,
            page_title="Conexiones",
            page_subtitle=(
                "Creación guiada de cables entre interfaces documentadas"
            ),
            sites=sites,
            cable_types=choices["types"],
            cable_statuses=choices["statuses"],
            length_units=choices["length_units"],
            recent_cables=recent_cables,
            csrf_token=csrf_token(request),
            error=error,
            form_data=form_data or {},
            created_id=created_id,
        ),
    )


@router.get("/connections", response_class=HTMLResponse)
async def connections_page(
    request: Request,
    created: int | None = None,
):
    redirect = login_redirect(request)
    if redirect:
        return redirect
    return await render_connections(request, created_id=created)


@router.get("/api/connections/devices")
async def connection_devices(request: Request, site_id: int):
    unauthorized = api_unauthorized(request)
    if unauthorized:
        return unauthorized

    try:
        devices = await ConnectionService().list_devices(site_id)
        return {
            "ok": True,
            "results": [
                {
                    "id": device.get("id"),
                    "name": (
                        device.get("name")
                        or device.get("display")
                        or "Sin nombre"
                    ),
                    "status": (
                        (device.get("status") or {}).get("label")
                        or ""
                    ),
                }
                for device in devices
            ],
        }
    except ConnectionServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": exc.message,
            },
        )


@router.get("/api/connections/interfaces")
async def connection_interfaces(request: Request, device_id: int):
    unauthorized = api_unauthorized(request)
    if unauthorized:
        return unauthorized

    try:
        interfaces = await ConnectionService().list_free_interfaces(device_id)
        return {
            "ok": True,
            "results": interfaces,
        }
    except ConnectionServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": exc.message,
            },
        )


@router.post("/connections", response_class=HTMLResponse)
async def create_connection(
    request: Request,
    csrf: str = Form(...),
    interface_a_id: int = Form(...),
    interface_b_id: int = Form(...),
    cable_type: str = Form(...),
    status: str = Form("connected"),
    label: str = Form(""),
    color: str = Form(""),
    length: str = Form(""),
    length_unit: str = Form("m"),
    description: str = Form(""),
):
    redirect = login_redirect(request)
    if redirect:
        return redirect

    form_data = {
        "interface_a_id": str(interface_a_id),
        "interface_b_id": str(interface_b_id),
        "cable_type": cable_type,
        "status": status,
        "label": label,
        "color": color,
        "length": length,
        "length_unit": length_unit,
        "description": description,
    }

    if not valid_csrf(request, csrf):
        return await render_connections(
            request,
            error=(
                "La sesión del formulario expiró. "
                "Recarga la página e inténtalo nuevamente."
            ),
            form_data=form_data,
            status_code=403,
        )

    if not settings.netbox_write_enabled:
        return await render_connections(
            request,
            error=(
                "La escritura está deshabilitada "
                "en la configuración de NetDoc."
            ),
            form_data=form_data,
            status_code=403,
        )

    if interface_a_id == interface_b_id:
        return await render_connections(
            request,
            error="No puedes conectar una interfaz consigo misma.",
            form_data=form_data,
            status_code=400,
        )

    parsed_length: Decimal | None = None
    if length.strip():
        try:
            parsed_length = Decimal(length.strip())
        except InvalidOperation:
            return await render_connections(
                request,
                error="La longitud no tiene un formato válido.",
                form_data=form_data,
                status_code=400,
            )

        if parsed_length <= 0:
            return await render_connections(
                request,
                error="La longitud debe ser mayor que cero.",
                form_data=form_data,
                status_code=400,
            )

    service = ConnectionService()
    try:
        interface_a = await service.get_interface(interface_a_id)
        interface_b = await service.get_interface(interface_b_id)

        if service.interface_is_connected(interface_a):
            raise ConnectionServiceError(
                "La interfaz del extremo A ya está conectada."
            )
        if service.interface_is_connected(interface_b):
            raise ConnectionServiceError(
                "La interfaz del extremo B ya está conectada."
            )

        created = await service.create_interface_cable(
            interface_a_id=interface_a_id,
            interface_b_id=interface_b_id,
            cable_type=cable_type,
            status=status,
            label=label,
            color=color,
            length=parsed_length,
            length_unit=length_unit,
            description=description,
            username=str(
                request.session.get("username", "desconocido")
            ),
        )
    except ConnectionServiceError as exc:
        return await render_connections(
            request,
            error=exc.message,
            form_data=form_data,
            status_code=(
                400 if exc.status_code in (400, 409) else 503
            ),
        )

    cable_id = created.get("id")
    if not isinstance(cable_id, int):
        return await render_connections(
            request,
            error=(
                "NetBox creó el cable, pero no devolvió "
                "un identificador válido."
            ),
            form_data=form_data,
            status_code=500,
        )

    return RedirectResponse(
        url=f"/connections?created={cable_id}",
        status_code=303,
    )
