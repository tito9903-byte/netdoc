from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.auth import access_redirect


router = APIRouter()


@router.get("/devices/{device_id}/lldp-discovery/run")
async def lldp_discovery_run_get(request: Request, device_id: int):
    redirect = access_redirect(request, "connections.view")
    if redirect:
        return redirect

    params = urlencode({"run_method": "get"})
    return RedirectResponse(
        f"/devices/{device_id}/lldp-discovery?{params}",
        status_code=303,
    )
