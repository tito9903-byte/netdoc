from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.auth import api_access_response, has_permission
from app.core.config import get_settings
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


router = APIRouter()
settings = get_settings()


def can_manage(request: Request) -> bool:
    return settings.netbox_write_enabled and has_permission(request, "devices.create")


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
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("display") or "",
            }
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
