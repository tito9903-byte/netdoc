from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.connection_service import (
    ConnectionService,
    ConnectionServiceError,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


class ConnectionBatchItem(BaseModel):
    interface_a_id: int = Field(gt=0)
    interface_b_id: int = Field(gt=0)
    label: str = Field(default="", max_length=100)


class ConnectionBatchRequest(BaseModel):
    csrf: str
    connections: list[ConnectionBatchItem] = Field(
        min_length=1,
        max_length=50,
    )
    cable_type: str = Field(min_length=1, max_length=50)
    status: str = Field(default="connected", max_length=50)
    color: str = Field(default="", max_length=20)
    length: str = Field(default="", max_length=30)
    length_unit: str = Field(default="m", max_length=20)
    description: str = Field(default="", max_length=500)


def is_authenticated(request: Request) -> bool:
    return (
        request.session.get("authenticated") is True
        and bool(request.session.get("username"))
    )


def login_redirect(
    request: Request,
) -> RedirectResponse | None:
    if is_authenticated(request):
        return None

    next_url = request.url.path

    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"

    return RedirectResponse(
        url=f"/login?{urlencode({'next': next_url})}",
        status_code=303,
    )


def api_unauthorized(
    request: Request,
) -> JSONResponse | None:
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


def valid_csrf(
    request: Request,
    submitted: str,
) -> bool:
    stored = request.session.get("csrf_token")

    return (
        isinstance(stored, str)
        and bool(stored)
        and secrets.compare_digest(stored, submitted)
    )


def parse_cable_length(value: str) -> Decimal | None:
    if not value.strip():
        return None

    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(
            "La longitud no tiene un formato válido."
        ) from exc

    if parsed <= 0:
        raise ValueError(
            "La longitud debe ser mayor que cero."
        )

    return parsed


def context(
    request: Request,
    **extra: object,
) -> dict[str, object]:
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
    return templates.TemplateResponse(
        request=request,
        name="connections.html",
        status_code=status_code,
        context=context(
            request,
            page_title="Conexiones",
            page_subtitle=(
                "Creación guiada de cables entre "
                "interfaces documentadas"
            ),
            csrf_token=csrf_token(request),
            error=error,
            form_data=form_data or {},
            created_id=created_id,
        ),
    )


@router.get(
    "/connections",
    response_class=HTMLResponse,
)
async def connections_page(
    request: Request,
    created: int | None = None,
):
    redirect = login_redirect(request)

    if redirect:
        return redirect

    return await render_connections(
        request,
        created_id=created,
    )


@router.get("/api/connections/bootstrap")
async def connection_bootstrap(
    request: Request,
):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    try:
        async with ConnectionService() as service:
            sites, choices = await asyncio.gather(
                service.list_sites(),
                service.get_cable_choices(),
            )

        return {
            "ok": True,
            "sites": [
                {
                    "id": site.get("id"),
                    "name": (
                        site.get("display")
                        or site.get("name")
                        or "Sin nombre"
                    ),
                }
                for site in sites
            ],
            "cable_types": choices["types"],
            "cable_statuses": choices["statuses"],
            "length_units": choices["length_units"],
        }

    except ConnectionServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": exc.message,
            },
        )


@router.get("/api/connections/recent")
async def recent_connections(
    request: Request,
    limit: int = 20,
):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    safe_limit = max(1, min(limit, 50))

    try:
        async with ConnectionService() as service:
            cables = await service.list_recent_cables(safe_limit)

        return {
            "ok": True,
            "results": cables,
            "count": len(cables),
        }

    except ConnectionServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": exc.message,
            },
        )


@router.get("/api/connections/devices")
async def connection_devices(
    request: Request,
    site_id: int,
):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    try:
        async with ConnectionService() as service:
            devices = await service.list_devices(site_id)

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
async def connection_interfaces(
    request: Request,
    device_id: int,
):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    try:
        async with ConnectionService() as service:
            interfaces = await service.list_free_interfaces(device_id)

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


@router.post("/api/connections/bulk")
async def create_connection_batch(
    request: Request,
    payload: ConnectionBatchRequest,
):
    unauthorized = api_unauthorized(request)

    if unauthorized:
        return unauthorized

    if not valid_csrf(request, payload.csrf):
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": (
                    "La sesión del formulario expiró. "
                    "Recarga la página e inténtalo nuevamente."
                ),
            },
        )

    if not settings.netbox_write_enabled:
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": (
                    "La escritura está deshabilitada "
                    "en la configuración de NetDoc."
                ),
            },
        )

    connections = [
        item.model_dump()
        for item in payload.connections
    ]
    interface_ids: list[int] = []

    for index, item in enumerate(connections, start=1):
        interface_a_id = int(item["interface_a_id"])
        interface_b_id = int(item["interface_b_id"])

        if interface_a_id == interface_b_id:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": (
                        f"La conexión {index} usa la misma "
                        "interfaz en ambos extremos."
                    ),
                },
            )

        interface_ids.extend([
            interface_a_id,
            interface_b_id,
        ])

    if len(set(interface_ids)) != len(interface_ids):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "Una interfaz no puede repetirse dentro "
                    "del mismo lote."
                ),
            },
        )

    try:
        parsed_length = parse_cable_length(payload.length)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(exc),
            },
        )

    try:
        async with ConnectionService() as service:
            interfaces = await asyncio.gather(*(
                service.get_interface(interface_id)
                for interface_id in interface_ids
            ))

            for index, interface in enumerate(interfaces):
                if service.interface_is_connected(interface):
                    row = (index // 2) + 1
                    side = "A" if index % 2 == 0 else "B"
                    raise ConnectionServiceError(
                        "La interfaz del extremo "
                        f"{side} en la conexión {row} "
                        "ya está conectada.",
                        status_code=409,
                    )

            created = await service.create_interface_cables(
                connections=connections,
                cable_type=payload.cable_type,
                status=payload.status,
                color=payload.color,
                length=parsed_length,
                length_unit=payload.length_unit,
                description=payload.description,
                username=str(
                    request.session.get(
                        "username",
                        "desconocido",
                    )
                ),
            )

    except ConnectionServiceError as exc:
        return JSONResponse(
            status_code=(
                400
                if exc.status_code in (400, 409)
                else 503
            ),
            content={
                "ok": False,
                "error": exc.message,
            },
        )

    if len(created) != len(connections):
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": (
                    "NetBox no confirmó todas las conexiones "
                    "solicitadas. Revisa el historial antes "
                    "de repetir el lote."
                ),
            },
        )

    cable_ids = [
        item.get("id")
        for item in created
        if isinstance(item.get("id"), int)
    ]

    return {
        "ok": True,
        "created_count": len(created),
        "cable_ids": cable_ids,
    }


@router.post(
    "/connections",
    response_class=HTMLResponse,
)
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
            error=(
                "No puedes conectar una interfaz consigo misma."
            ),
            form_data=form_data,
            status_code=400,
        )

    try:
        parsed_length = parse_cable_length(length)
    except ValueError as exc:
        return await render_connections(
            request,
            error=str(exc),
            form_data=form_data,
            status_code=400,
        )

    try:
        async with ConnectionService() as service:
            interface_a, interface_b = await asyncio.gather(
                service.get_interface(interface_a_id),
                service.get_interface(interface_b_id),
            )

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
                    request.session.get(
                        "username",
                        "desconocido",
                    )
                ),
            )

    except ConnectionServiceError as exc:
        return await render_connections(
            request,
            error=exc.message,
            form_data=form_data,
            status_code=(
                400
                if exc.status_code in (400, 409)
                else 503
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
