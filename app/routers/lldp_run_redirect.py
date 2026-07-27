from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.auth import access_redirect


router = APIRouter()


@router.get("/devices/{device_id}/lldp-discovery/run")
async def lldp_discovery_run_get(request: Request, device_id: int):
    redirect = access_redirect(request, "connections.view")
    if redirect:
        return redirect
    return RedirectResponse(
        f"/devices/{device_id}/lldp-discovery",
        status_code=303,
    )
