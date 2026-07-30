from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    common_session_context,
    csrf_token,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.services.access_service import record_audit
from app.services.site_service import (
    SiteService,
    SiteServiceError,
    validate_site_form,
)


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "sites",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def audit_site(
    request: Request,
    *,
    action: str,
    detail: str,
    success: bool,
    resource_id: int | None = None,
) -> None:
    user_id = request.session.get("user_id")
    ip_address, user_agent = request_client_data(request)
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource="site",
            resource_id=resource_id,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


@router.get("/sites", response_class=HTMLResponse)
async def sites_page(
    request: Request,
    q: str = "",
    status: str = "",
):
    redirect = access_redirect(request, "sites.view")
    if redirect:
        return redirect
    try:
        service = SiteService()
        sites = await service.list_sites(query=q, status=status)
        choices = await service.site_choices()
    except SiteServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                page_title="Sites",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudo cargar el inventario de sites",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )
    return templates.TemplateResponse(
        request=request,
        name="sites.html",
        context=context(
            request,
            page_title="Sites",
            page_subtitle="Localidades que organizan racks y equipos",
            sites=sites,
            statuses=choices["statuses"],
            selected_status=status,
            query=q,
        ),
    )


async def render_form(
    request: Request,
    *,
    site_id: int | None = None,
    form_data: dict[str, str] | None = None,
    errors: list[str] | None = None,
):
    service = SiteService()
    try:
        site = await service.get_site(site_id) if site_id is not None else {}
        choices = await service.site_choices()
    except SiteServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                page_title="Sites",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudo abrir el site",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )
    values = {
        key: str(site.get(key) or "")
        for key in (
            "name", "slug", "facility", "physical_address",
            "shipping_address", "latitude", "longitude", "description",
        )
    }
    status = site.get("status") or {}
    values["status"] = str(
        status.get("value") if isinstance(status, dict) else status or "active"
    )
    values.update(form_data or {})
    return templates.TemplateResponse(
        request=request,
        name="site_form.html",
        context=context(
            request,
            page_title="Editar site" if site_id else "Crear site",
            page_subtitle="Información oficial almacenada en NetBox",
            site_id=site_id,
            form_data=values,
            statuses=choices["statuses"],
            errors=errors or [],
            csrf_token=csrf_token(request, "site_management"),
        ),
    )


@router.get("/sites/actions/new", response_class=HTMLResponse)
async def new_site_page(request: Request):
    redirect = access_redirect(request, "sites.manage")
    return redirect or await render_form(request)


@router.get("/sites/{site_id}/edit", response_class=HTMLResponse)
async def edit_site_page(request: Request, site_id: int):
    redirect = access_redirect(request, "sites.manage")
    return redirect or await render_form(request, site_id=site_id)


async def save_site_from_form(
    request: Request,
    *,
    site_id: int | None,
    csrf: str,
    name: str,
    slug: str,
    status: str,
    facility: str,
    physical_address: str,
    shipping_address: str,
    latitude: str,
    longitude: str,
    description: str,
):
    redirect = access_redirect(request, "sites.manage")
    if redirect:
        return redirect
    data = {
        "name": name,
        "slug": slug,
        "status": status,
        "facility": facility,
        "physical_address": physical_address,
        "shipping_address": shipping_address,
        "latitude": latitude,
        "longitude": longitude,
        "description": description,
    }
    errors = validate_site_form(data)
    if not verify_csrf(request, csrf, "site_management"):
        errors.append("La sesión del formulario expiró. Recarga la página.")
    if not settings.netbox_write_enabled:
        errors.append(
            "La escritura está desactivada; el site no fue enviado a NetBox."
        )
    service = SiteService()
    if not errors:
        try:
            if await service.duplicate_exists(
                name=name,
                slug=slug,
                exclude_id=site_id,
            ):
                errors.append("Ya existe un site con ese nombre o código.")
        except SiteServiceError as exc:
            errors.append(exc.message)
    if errors:
        return await render_form(
            request,
            site_id=site_id,
            form_data=data,
            errors=errors,
        )
    try:
        saved = await service.save_site(site_id=site_id, **data)
    except SiteServiceError as exc:
        audit_site(
            request,
            action="SITE_UPDATE" if site_id else "SITE_CREATE",
            detail=exc.message,
            success=False,
            resource_id=site_id,
        )
        return await render_form(
            request,
            site_id=site_id,
            form_data=data,
            errors=[exc.message],
        )
    saved_id = saved.get("id")
    audit_site(
        request,
        action="SITE_UPDATE" if site_id else "SITE_CREATE",
        detail=f"Site guardado: {name.strip()}.",
        success=True,
        resource_id=saved_id if isinstance(saved_id, int) else site_id,
    )
    return RedirectResponse(url="/sites", status_code=303)


@router.post("/sites/actions/new")
async def create_site(
    request: Request,
    csrf: str = Form(...),
    name: str = Form(...),
    slug: str = Form(...),
    status: str = Form("active"),
    facility: str = Form(""),
    physical_address: str = Form(""),
    shipping_address: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    description: str = Form(""),
):
    return await save_site_from_form(
        request,
        site_id=None,
        csrf=csrf,
        name=name,
        slug=slug,
        status=status,
        facility=facility,
        physical_address=physical_address,
        shipping_address=shipping_address,
        latitude=latitude,
        longitude=longitude,
        description=description,
    )


@router.post("/sites/{site_id}/edit")
async def update_site(
    request: Request,
    site_id: int,
    csrf: str = Form(...),
    name: str = Form(...),
    slug: str = Form(...),
    status: str = Form("active"),
    facility: str = Form(""),
    physical_address: str = Form(""),
    shipping_address: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    description: str = Form(""),
):
    return await save_site_from_form(
        request,
        site_id=site_id,
        csrf=csrf,
        name=name,
        slug=slug,
        status=status,
        facility=facility,
        physical_address=physical_address,
        shipping_address=shipping_address,
        latitude=latitude,
        longitude=longitude,
        description=description,
    )


@router.post("/sites/{site_id}/deactivate")
async def deactivate_site(request: Request, site_id: int, csrf: str = Form(...)):
    redirect = access_redirect(request, "sites.manage")
    if redirect:
        return redirect
    if not verify_csrf(request, csrf, "site_management"):
        return RedirectResponse(url=f"/sites/{site_id}/edit", status_code=303)
    if not settings.netbox_write_enabled:
        return RedirectResponse(url=f"/sites/{site_id}/edit", status_code=303)
    try:
        await SiteService().deactivate_site(site_id)
    except SiteServiceError as exc:
        audit_site(
            request,
            action="SITE_DEACTIVATE",
            detail=exc.message,
            success=False,
            resource_id=site_id,
        )
        return await render_form(request, site_id=site_id, errors=[exc.message])
    audit_site(
        request,
        action="SITE_DEACTIVATE",
        detail="Site marcado como retirado.",
        success=True,
        resource_id=site_id,
    )
    return RedirectResponse(url="/sites", status_code=303)
