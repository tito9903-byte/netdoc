from __future__ import annotations

import asyncio
from decimal import Decimal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.auth import api_access_response
from app.core.config import get_settings
from app.services.cable_planner import (
    build_cable_plan,
    endpoint_from_netbox,
)
from app.services.change_plan import ChangePlanError
from app.services.connection_service import (
    ConnectionService,
    ConnectionServiceError,
)


router = APIRouter(prefix="/api/change-plans", tags=["change-plans"])
settings = get_settings()


class CablePlanRequest(BaseModel):
    interface_a_id: int = Field(gt=0)
    interface_b_id: int = Field(gt=0)
    cable_type: str = Field(default="", max_length=64)
    status: str = Field(default="connected", max_length=64)
    label: str = Field(default="", max_length=200)
    color: str = Field(default="", max_length=7)
    length: Decimal | None = Field(default=None, ge=0)
    length_unit: str = Field(default="m", max_length=16)
    description: str = Field(default="", max_length=2000)


@router.post("/cable")
async def preview_cable_plan(
    request: Request,
    body: CablePlanRequest,
):
    """Prepara un plan de cable; nunca realiza una escritura."""

    denied = api_access_response(request, "devices.create")
    if denied:
        return denied

    if body.interface_a_id == body.interface_b_id:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Selecciona dos interfaces diferentes.",
            },
        )

    service = ConnectionService()
    try:
        raw_a, raw_b = await asyncio.gather(
            service.get_interface(body.interface_a_id),
            service.get_interface(body.interface_b_id),
        )
        plan = build_cable_plan(
            requested_by=str(
                request.session.get("username") or "desconocido"
            ),
            endpoint_a=endpoint_from_netbox(raw_a),
            endpoint_b=endpoint_from_netbox(raw_b),
            status=body.status,
            cable_type=body.cable_type,
            label=body.label,
            color=body.color,
            length=body.length,
            length_unit=body.length_unit,
            description=body.description,
            source="user",
        )
    except ConnectionServiceError as exc:
        return JSONResponse(
            status_code=503 if exc.status_code is None else 400,
            content={"ok": False, "error": exc.message},
        )
    except ChangePlanError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": str(exc)},
        )

    return {
        "ok": True,
        "mode": "preview",
        "write_enabled": settings.netbox_write_enabled,
        "plan": plan.public_dict(),
    }
