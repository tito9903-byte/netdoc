from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.services.rack_service import (
    RackService,
    RackServiceError,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


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


def context(
    request: Request,
    **extra: object,
) -> dict[str, object]:
    return {
        "current_page": "racks",
        "current_user": request.session.get("username", ""),
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def nested_label(
    value: Any,
    fallback: str = "—",
) -> str:
    if isinstance(value, dict):
        return str(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("value")
            or fallback
        )

    if value not in (None, ""):
        return str(value)

    return fallback


def face_value(device: dict[str, Any]) -> str:
    face = device.get("face")

    if isinstance(face, dict):
        return str(face.get("value") or "")

    return str(face or "")


def prepare_rack_cards(
    racks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []

    for rack in racks:
        utilization = rack.get("utilization")

        try:
            utilization_value = float(utilization)
        except (TypeError, ValueError):
            utilization_value = 0.0

        cards.append({
            **rack,
            "_site_label": nested_label(rack.get("site")),
            "_location_label": nested_label(rack.get("location")),
            "_status_label": nested_label(rack.get("status")),
            "_utilization": max(0.0, min(utilization_value, 100.0)),
            "_device_count": int(rack.get("device_count") or 0),
            "_u_height": int(rack.get("u_height") or 0),
        })

    return cards


def prepare_elevation(
    rack: dict[str, Any],
    devices: list[dict[str, Any]],
    selected_face: str,
) -> dict[str, Any]:
    rack_height = int(rack.get("u_height") or 42)
    occupied_units: set[int] = set()
    visible_devices: list[dict[str, Any]] = []
    unpositioned_devices: list[dict[str, Any]] = []

    for device in devices:
        position = device.get("position")
        device_type = device.get("device_type") or {}

        try:
            unit_height = max(
                1,
                int(device_type.get("u_height") or 1),
            )
        except (TypeError, ValueError):
            unit_height = 1

        full_depth = bool(device_type.get("full_depth"))
        current_face = face_value(device)

        prepared = {
            **device,
            "_model": nested_label(device_type),
            "_status": nested_label(device.get("status")),
            "_face": current_face or "sin definir",
            "_u_height": unit_height,
            "_full_depth": full_depth,
        }

        if position in (None, ""):
            unpositioned_devices.append(prepared)
            continue

        try:
            numeric_position = int(float(position))
        except (TypeError, ValueError):
            unpositioned_devices.append(prepared)
            continue

        if numeric_position < 1 or numeric_position > rack_height:
            unpositioned_devices.append(prepared)
            continue

        upper_unit = min(
            rack_height,
            numeric_position + unit_height - 1,
        )

        for unit in range(numeric_position, upper_unit + 1):
            occupied_units.add(unit)

        should_display = (
            full_depth
            or current_face == selected_face
            or not current_face
        )

        if should_display:
            prepared["_position"] = numeric_position
            prepared["_grid_start"] = (
                rack_height - upper_unit + 1
            )
            prepared["_span"] = upper_unit - numeric_position + 1
            visible_devices.append(prepared)

    visible_devices.sort(
        key=lambda item: (
            int(item.get("_grid_start") or 0),
            str(item.get("name") or ""),
        )
    )

    used_units = len(occupied_units)
    free_units = max(0, rack_height - used_units)
    utilization = (
        round((used_units / rack_height) * 100, 1)
        if rack_height
        else 0.0
    )

    return {
        "rack_height": rack_height,
        "visible_devices": visible_devices,
        "unpositioned_devices": unpositioned_devices,
        "used_units": used_units,
        "free_units": free_units,
        "utilization": utilization,
    }


@router.get(
    "/racks",
    response_class=HTMLResponse,
)
async def racks_page(
    request: Request,
    site_id: str = "",
    q: str = "",
):
    redirect = login_redirect(request)

    if redirect:
        return redirect

    selected_site_id: int | None = None

    if site_id.strip():
        try:
            selected_site_id = int(site_id)
        except ValueError:
            selected_site_id = None

    service = RackService()

    try:
        sites, racks = await asyncio.gather(
            service.list_sites(),
            service.list_racks(
                site_id=selected_site_id,
                query=q,
            ),
        )

    except RackServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                page_title="Racks",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudieron cargar los racks",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="racks.html",
        context=context(
            request,
            page_title="Racks",
            page_subtitle=(
                "Vista rápida de bastidores, capacidad "
                "y ocupación documentada"
            ),
            sites=sites,
            racks=prepare_rack_cards(racks),
            selected_site_id=selected_site_id,
            query=q,
        ),
    )


@router.get(
    "/racks/{rack_id}",
    response_class=HTMLResponse,
)
async def rack_detail_page(
    request: Request,
    rack_id: int,
    face: str = "front",
):
    redirect = login_redirect(request)

    if redirect:
        return redirect

    selected_face = (
        face
        if face in {"front", "rear"}
        else "front"
    )

    service = RackService()

    try:
        rack, devices = await asyncio.gather(
            service.get_rack(rack_id),
            service.list_rack_devices(rack_id),
        )

    except RackServiceError as exc:
        status_code = 404 if exc.status_code == 404 else 503

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=status_code,
            context=context(
                request,
                page_title="Rack no disponible",
                page_subtitle="No fue posible cargar el rack",
                error_title="No se pudo consultar el rack",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    elevation = prepare_elevation(
        rack,
        devices,
        selected_face,
    )

    return templates.TemplateResponse(
        request=request,
        name="rack_detail.html",
        context=context(
            request,
            page_title=(
                rack.get("name")
                or rack.get("display")
                or "Rack"
            ),
            page_subtitle=(
                "Elevación 2D basada en las posiciones "
                "documentadas en NetBox"
            ),
            rack=rack,
            devices=devices,
            selected_face=selected_face,
            **elevation,
        ),
    )
