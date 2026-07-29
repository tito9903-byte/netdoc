from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import api_access_response, has_permission
from app.core.config import get_settings
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


router = APIRouter()
settings = get_settings()


def can_manage(request: Request) -> bool:
    return settings.netbox_write_enabled and has_permission(request, "devices.create")


def nested_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("id"), int):
        return int(value["id"])
    return None


def display_name(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value or "")
    return str(
        value.get("display")
        or value.get("name")
        or value.get("label")
        or ""
    )


def connection_metadata(interface: dict[str, Any]) -> dict[str, Any] | None:
    endpoints = interface.get("connected_endpoints") or []
    if not isinstance(endpoints, list) or not endpoints:
        return None

    endpoint = endpoints[0]
    if not isinstance(endpoint, dict):
        return None

    remote_device = endpoint.get("device") or {}
    remote_interface_name = str(
        endpoint.get("display")
        or endpoint.get("name")
        or "Interfaz remota"
    )
    remote_device_id = nested_id(remote_device)
    remote_device_name = display_name(remote_device)

    return {
        "interface_id": nested_id(endpoint),
        "interface_name": remote_interface_name,
        "device_id": remote_device_id,
        "device_name": remote_device_name,
        "navigable": remote_device_id is not None,
    }


def interface_payload(item: dict[str, Any]) -> dict[str, Any]:
    cable = item.get("cable") or {}
    return {
        "id": item.get("id"),
        "name": item.get("name") or item.get("display") or "",
        "connection": connection_metadata(item),
        "cable": {
            "id": nested_id(cable),
            "label": display_name(cable),
        }
        if cable
        else None,
    }


@router.get("/api/netdoc/devices/{device_id}/interfaces")
async def device_interfaces_api(request: Request, device_id: int):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied
    try:
        rows = await DeviceTypeService().get_all(
            "/api/dcim/interfaces/",
            params={"device_id": device_id, "ordering": "name"},
        )
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code or 503,
            content={"ok": False, "error": exc.message},
        )
    return {
        "ok": True,
        "can_manage": can_manage(request),
        "interfaces": [
            interface_payload(item)
            for item in rows
            if isinstance(item.get("id"), int)
        ],
    }


@router.get("/api/netdoc/device-types/{device_type_id}/interfaces")
async def model_interfaces_api(request: Request, device_type_id: int):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied
    try:
        rows = await DeviceTypeService().list_interface_templates(device_type_id)
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code or 503,
            content={"ok": False, "error": exc.message},
        )
    return {
        "ok": True,
        "can_manage": can_manage(request),
        "interfaces": [
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("display") or "",
            }
            for item in rows
            if isinstance(item.get("id"), int)
        ],
    }
