from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.auth import access_redirect
from app.routers.interface_workspace import render_workspace


router = APIRouter()


@router.get("/devices/{device_id}/interfaces/new", response_class=HTMLResponse)
async def interface_workspace_create_alias(
    request: Request,
    device_id: int,
    error: str = "",
    notice: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await render_workspace(
        request,
        device_id=device_id,
        error=error,
        notice=notice,
    )


@router.get(
    "/devices/{device_id}/interfaces/{interface_id}/edit",
    response_class=HTMLResponse,
)
async def interface_workspace_edit_alias(
    request: Request,
    device_id: int,
    interface_id: int,
    error: str = "",
    notice: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    return await render_workspace(
        request,
        device_id=device_id,
        interface_id=interface_id,
        error=error,
        notice=notice,
    )
