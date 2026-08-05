from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
    csrf_token,
    has_permission,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.services.access_service import record_audit
from app.services.change_plan import ChangePlanError, require_confirmation
from app.services.device_type_service import (
    DeviceTypeService,
    DeviceTypeServiceError,
    build_interface_names,
)
from app.services.ipam_presentation import prepare_ipam_view
from app.services.ipam_pool_service import (
    IPAMPoolService,
    IPAMPoolServiceError,
    default_pool_form,
    parse_positive_int,
)
from app.services.ipam_service import IPAMService, IPAMServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

PREFIX_STATUSES = [
    ("active", "Activo"),
    ("reserved", "Reservado"),
    ("deprecated", "Deprecado"),
    ("container", "Contenedor"),
]


def context(
    request: Request,
    *,
    current_page: str,
    **extra: object,
) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": current_page,
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        "can_manage_device_types": has_permission(
            request,
            "devices.create",
        ),
        "can_manage_ipam": has_permission(
            request,
            "devices.create",
        ),
        **extra,
    }


def parse_optional_int(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def redirect_with_message(
    path: str,
    *,
    notice: str = "",
    error: str = "",
    **params: object,
) -> RedirectResponse:
    query: dict[str, object] = {
        key: value
        for key, value in params.items()
        if value not in (None, "")
    }
    if notice:
        query["notice"] = notice
    if error:
        query["error"] = error
    url = path if not query else f"{path}?{urlencode(query)}"
    return RedirectResponse(url=url, status_code=303)


def model_interfaces_url(
    device_type_id: int,
    *,
    notice: str = "",
    error: str = "",
) -> str:
    query = {
        key: value
        for key, value in {"notice": notice, "error": error}.items()
        if value
    }
    target = f"/device-types/{device_type_id}"
    if query:
        target = f"{target}?{urlencode(query)}"
    return f"{target}#interfaces"


def redirect_to_model_interfaces(
    device_type_id: int,
    *,
    notice: str = "",
    error: str = "",
) -> RedirectResponse:
    return RedirectResponse(
        model_interfaces_url(
            device_type_id,
            notice=notice,
            error=error,
        ),
        status_code=303,
    )


def audit_event(
    request: Request,
    *,
    action: str,
    resource: str,
    detail: str,
    success: bool,
    object_id: str | None = None,
) -> None:
    user_id = request.session.get("user_id")
    ip_address, user_agent = request_client_data(request)

    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource=resource,
            resource_id=object_id,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(
                request.session.get("username") or "desconocido"
            ),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def select_device_type(
    device_types: list[dict[str, object]],
    selected_id: int | None,
) -> tuple[dict[str, object] | None, int | None]:
    if not device_types:
        return None, None

    selected = next(
        (
            item
            for item in device_types
            if item.get("id") == selected_id
        ),
        device_types[0],
    )
    return selected, parse_optional_int(selected.get("id"))


@router.get("/ipam", response_class=HTMLResponse)
async def ipam_page(
    request: Request,
    q: str = "",
    status: str = "",
    family: str = "",
    role_id: str = "",
    scope: str = "",
    health: str = "",
    order: str = "scope",
    page: str = "1",
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "search.view")
    if redirect:
        return redirect

    selected_family = parse_optional_int(family)
    if selected_family not in {4, 6}:
        selected_family = None
    selected_role_id = parse_optional_int(role_id)
    selected_page = parse_optional_int(page) or 1
    inventory_required = bool(health.strip()) or order.strip() in {
        "utilization_desc",
        "availability_desc",
    }

    try:
        async with IPAMService() as service:
            raw_data = await service.overview(
                query=q,
                status=status,
                family=selected_family,
                role_id=selected_role_id,
                include_inventory=inventory_required,
            )
        data = prepare_ipam_view(
            raw_data,
            scope=scope,
            health=health,
            order=order,
            page=selected_page,
        )
    except IPAMServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                current_page="ipam",
                page_title="Direccionamiento IP",
                page_subtitle="No fue posible consultar IPAM",
                error_title="No se pudieron cargar los prefijos",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="ipam.html",
        context=context(
            request,
            current_page="ipam",
            page_title="Direccionamiento IP",
            page_subtitle=(
                "Disponibilidad, ocupación y localidad de prefijos y pools"
            ),
            query=q,
            selected_status=status,
            selected_family=selected_family,
            selected_role_id=selected_role_id,
            prefix_statuses=PREFIX_STATUSES,
            notice=notice,
            error=error,
            **data,
        ),
    )


@router.get("/api/ipam/pools", response_class=JSONResponse)
async def ipam_pools_api(request: Request):
    denied = api_access_response(request, "search.view")
    if denied:
        return denied

    try:
        async with IPAMService() as service:
            data = await service.overview(include_inventory=True)
    except IPAMServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": exc.message},
        )

    return JSONResponse(
        content={
            "ok": True,
            "summary": data["summary"],
            "pools": data["pools"],
        }
    )


@router.get("/api/ipam/pools/availability", response_class=JSONResponse)
async def ipam_pool_availability_api(
    request: Request,
    q: str = "",
    status: str = "",
    family: str = "",
    role_id: str = "",
    scope: str = "",
    health: str = "",
    order: str = "scope",
    page: str = "1",
):
    denied = api_access_response(request, "search.view")
    if denied:
        return denied

    selected_family = parse_optional_int(family)
    if selected_family not in {4, 6}:
        selected_family = None
    selected_role_id = parse_optional_int(role_id)
    selected_page = parse_optional_int(page) or 1

    try:
        async with IPAMService() as service:
            data = await service.overview(
                query=q,
                status=status,
                family=selected_family,
                role_id=selected_role_id,
                include_inventory=True,
            )
    except IPAMServiceError as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": exc.message},
        )

    view = prepare_ipam_view(
        data,
        scope=scope,
        health=health,
        order=order,
        page=selected_page,
    )
    return JSONResponse(
        content={
            "ok": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "inventory_warning": view["inventory_warning"],
            "summary": view["summary"],
            "pools": view["pools"],
        },
    )


async def render_pool_form(
    request: Request,
    *,
    form_data: dict[str, str],
    form_options: dict[str, object],
    errors: list[str] | None = None,
    plan: dict[str, object] | None = None,
    normalized: dict[str, object] | None = None,
    analysis: dict[str, object] | None = None,
    parent: dict[str, object] | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request=request,
        name="ipam_pool_form.html",
        status_code=status_code,
        context=context(
            request,
            current_page="ipam",
            page_title="Crear pool IP",
            page_subtitle=(
                "Prevalidación de CIDR, VRF, jerarquía y solapamientos"
            ),
            form_data=form_data,
            statuses=form_options["statuses"],
            roles=form_options["roles"],
            vrfs=form_options["vrfs"],
            scopes=form_options["scopes"],
            errors=errors or [],
            plan=plan,
            normalized=normalized or {},
            analysis=analysis or {},
            parent=parent,
            csrf_token=csrf_token(request, "ipam_pool"),
        ),
    )


@router.get("/ipam/pools/new", response_class=HTMLResponse)
async def new_ipam_pool_page(
    request: Request,
    parent_id: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    form_data = default_pool_form()
    selected_parent_id = parse_positive_int(parent_id)
    parent: dict[str, object] | None = None
    errors: list[str] = []
    try:
        async with IPAMPoolService() as service:
            options = await service.load_form_options()
            if selected_parent_id is not None:
                parent = await service.prefill_from_parent(
                    parent_id=selected_parent_id,
                    form_data=form_data,
                )
    except IPAMPoolServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                current_page="ipam",
                page_title="Crear pool IP",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudo preparar el formulario",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return await render_pool_form(
        request,
        form_data=form_data,
        form_options=options,
        errors=errors,
        parent=parent,
    )


@router.post("/ipam/pools/preview", response_class=HTMLResponse)
async def preview_ipam_pool(
    request: Request,
    csrf: str = Form(""),
    prefix: str = Form(""),
    status: str = Form("active"),
    vrf_id: str = Form(""),
    role_id: str = Form(""),
    scope: str = Form(""),
    description: str = Form(""),
    change_reason: str = Form(""),
    parent_id: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    form_data = {
        "prefix": prefix,
        "status": status,
        "vrf_id": vrf_id,
        "role_id": role_id,
        "scope": scope,
        "description": description,
        "change_reason": change_reason,
        "parent_id": parent_id,
    }
    errors: list[str] = []
    plan_errors: list[str] = []
    if not verify_csrf(request, csrf, "ipam_pool"):
        errors.append("La sesión del formulario expiró. Recarga la página.")

    try:
        async with IPAMPoolService() as service:
            options = await service.load_form_options()
            plan, normalized, analysis, plan_errors = (
                await service.prepare_plan(
                    form_data=form_data,
                    requested_by=str(
                        request.session.get("username") or "desconocido"
                    ),
                    form_options=options,
                )
            )
    except IPAMPoolServiceError as exc:
        errors.append(exc.message)
        options = {
            "statuses": [],
            "roles": [],
            "vrfs": [],
            "scopes": [],
        }
        plan = None
        normalized = {}
        analysis = {}
    errors.extend(plan_errors)

    public_plan = plan.public_dict() if plan is not None and not errors else None
    if public_plan is not None:
        request.session["ipam_pool_form"] = form_data
        request.session["ipam_pool_plan_id"] = plan.fingerprint
    else:
        request.session.pop("ipam_pool_form", None)
        request.session.pop("ipam_pool_plan_id", None)

    return await render_pool_form(
        request,
        form_data=form_data,
        form_options=options,
        errors=errors,
        plan=public_plan,
        normalized=normalized,
        analysis=analysis,
        parent=(analysis.get("parent") if analysis else None),
        status_code=400 if errors else 200,
    )


@router.post("/ipam/pools/confirm", response_class=HTMLResponse)
async def confirm_ipam_pool(
    request: Request,
    csrf: str = Form(""),
    plan_id: str = Form(""),
    confirmation_phrase: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    stored_form = request.session.get("ipam_pool_form")
    stored_plan_id = request.session.get("ipam_pool_plan_id")
    if not isinstance(stored_form, dict):
        return redirect_with_message(
            "/ipam/pools/new",
            error="La vista previa expiró. Revisa el pool nuevamente.",
        )

    form_data = {
        key: str(stored_form.get(key) or "")
        for key in default_pool_form()
    }
    errors: list[str] = []
    if not verify_csrf(request, csrf, "ipam_pool"):
        errors.append("La sesión del formulario expiró. Recarga la página.")
    if not settings.netbox_write_enabled:
        errors.append(
            "La escritura está desactivada; el pool no fue enviado a NetBox."
        )

    try:
        async with IPAMPoolService() as service:
            options = await service.load_form_options()
            plan, normalized, analysis, plan_errors = (
                await service.prepare_plan(
                    form_data=form_data,
                    requested_by=str(
                        request.session.get("username") or "desconocido"
                    ),
                    form_options=options,
                )
            )
            errors.extend(plan_errors)
            if plan is None:
                pass
            elif (
                not isinstance(stored_plan_id, str)
                or plan_id != stored_plan_id
                or plan.fingerprint != stored_plan_id
            ):
                errors.append(
                    "El inventario o el formulario cambió después de la "
                    "vista previa. Revísalo nuevamente antes de crear."
                )
            else:
                try:
                    require_confirmation(plan, confirmation_phrase)
                except ChangePlanError as exc:
                    errors.append(str(exc))

            if plan is not None and not errors:
                saved = await service.create_pool(plan)
            else:
                saved = None
    except IPAMPoolServiceError as exc:
        errors.append(exc.message)
        options = {
            "statuses": [],
            "roles": [],
            "vrfs": [],
            "scopes": [],
        }
        plan = None
        normalized = {}
        analysis = {}
        saved = None

    if errors or saved is None:
        if plan is not None:
            request.session["ipam_pool_plan_id"] = plan.fingerprint
        audit_event(
            request,
            action="IPAM_POOL_CREATE",
            resource="ipam_pool",
            detail=" | ".join(errors) or "No se confirmó la creación.",
            success=False,
        )
        return await render_pool_form(
            request,
            form_data=form_data,
            form_options=options,
            errors=errors,
            plan=(plan.public_dict() if plan is not None else None),
            normalized=normalized,
            analysis=analysis,
            parent=(analysis.get("parent") if analysis else None),
            status_code=400,
        )

    saved_id = saved.get("id")
    saved_prefix = str(saved.get("prefix") or form_data["prefix"])
    audit_event(
        request,
        action="IPAM_POOL_CREATE",
        resource="ipam_pool",
        object_id=str(saved_id) if isinstance(saved_id, int) else None,
        detail=f"Pool creado en NetBox: {saved_prefix}.",
        success=True,
    )
    request.session.pop("ipam_pool_form", None)
    request.session.pop("ipam_pool_plan_id", None)
    IPAMService.clear_caches()
    return redirect_with_message(
        "/ipam",
        notice=f"Pool {saved_prefix} creado correctamente.",
    )


@router.get("/device-types", response_class=HTMLResponse)
async def device_types_page(
    request: Request,
    q: str = "",
    manufacturer_id: str = "",
    device_type_id: str = "",
    notice: str = "",
    error: str = "",
):
    """Catálogo de modelos sin mezclar formularios de plantillas."""

    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    selected_manufacturer_id = parse_optional_int(manufacturer_id)
    selected_device_type_id = parse_optional_int(device_type_id)
    service = DeviceTypeService()

    try:
        manufacturers, device_types = await asyncio.gather(
            service.list_manufacturers(),
            service.list_device_types(
                query=q,
                manufacturer_id=selected_manufacturer_id,
            ),
        )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                current_page="device_types",
                page_title="Modelos de equipos",
                page_subtitle="No fue posible consultar NetBox",
                error_title="No se pudieron cargar los modelos",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    selected_device_type, selected_device_type_id = select_device_type(
        device_types,
        selected_device_type_id,
    )

    return templates.TemplateResponse(
        request=request,
        name="device_types.html",
        context=context(
            request,
            current_page="device_types",
            page_title="Modelos de equipos",
            page_subtitle=(
                "Catálogo reutilizable de fabricantes, dimensiones y componentes"
            ),
            query=q,
            manufacturers=manufacturers,
            selected_manufacturer_id=selected_manufacturer_id,
            device_types=device_types,
            selected_device_type=selected_device_type,
            selected_device_type_id=selected_device_type_id,
            notice=notice,
            error=error,
        ),
    )


@router.get("/device-types/new", response_class=HTMLResponse)
async def new_device_type_page(
    request: Request,
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    try:
        manufacturers = await DeviceTypeService().list_manufacturers()
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=503,
            context=context(
                request,
                current_page="device_type_new",
                page_title="Crear modelo",
                page_subtitle="No fue posible consultar fabricantes",
                error_title="No se pudo preparar el formulario",
                error_message=exc.message,
                netbox_connected=False,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_type_new.html",
        context=context(
            request,
            current_page="device_type_new",
            page_title="Crear modelo",
            page_subtitle=(
                "Registra la ficha física antes de agregar puertos y componentes"
            ),
            manufacturers=manufacturers,
            csrf_token=csrf_token(request),
            notice=notice,
            error=error,
        ),
    )


@router.get("/interface-templates")
async def interface_templates_redirect(
    request: Request,
    device_type_id: str = "",
    notice: str = "",
    error: str = "",
):
    """Conserva enlaces antiguos y lleva la gestión a la ficha del modelo."""

    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    selected_device_type_id = parse_optional_int(device_type_id)
    if selected_device_type_id is None:
        return RedirectResponse("/device-types", status_code=303)

    return redirect_to_model_interfaces(
        selected_device_type_id,
        notice=notice,
        error=error,
    )


@router.get(
    "/api/device-types/interface-preview",
    response_class=JSONResponse,
)
async def interface_preview_api(
    request: Request,
    pattern: str = "",
    start: int = 1,
    count: int = 24,
):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied

    try:
        names = build_interface_names(
            pattern,
            start=start,
            count=count,
        )
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": exc.message},
        )

    return JSONResponse(
        content={
            "ok": True,
            "names": names,
            "count": len(names),
        }
    )


@router.get("/device-types/interface-templates")
async def legacy_interface_templates_redirect(
    request: Request,
    device_type_id: str = "",
):
    return await interface_templates_redirect(
        request,
        device_type_id=device_type_id,
    )


@router.post("/device-types/actions/create")
@router.post("/device-types/new")
async def create_device_type_action(
    request: Request,
    csrf: str = Form(""),
    manufacturer_id: int = Form(...),
    model: str = Form(...),
    slug: str = Form(""),
    part_number: str = Form(""),
    u_height: float = Form(1),
    full_depth: str = Form(""),
    description: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    if not verify_csrf(request, csrf):
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail="Creación rechazada por token CSRF inválido.",
            success=False,
        )
        return redirect_with_message(
            "/device-types/new",
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail="Creación rechazada porque la escritura está deshabilitada.",
            success=False,
        )
        return redirect_with_message(
            "/device-types/new",
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        created = await DeviceTypeService().create_device_type(
            manufacturer_id=manufacturer_id,
            model=model,
            slug=slug,
            part_number=part_number,
            u_height=u_height,
            is_full_depth=full_depth == "true",
            description=description,
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(
            "/device-types/new",
            error=exc.message,
        )

    object_id = str(created.get("id") or "")
    audit_event(
        request,
        action="DEVICE_TYPE_CREATE",
        resource="device_type",
        detail=f"Modelo {model.strip()} creado en NetBox.",
        success=True,
        object_id=object_id or None,
    )
    return redirect_with_message(
        "/device-types",
        notice="Modelo creado correctamente.",
        device_type_id=object_id,
    )


@router.post("/interface-templates/actions/bulk")
@router.post("/device-types/interface-templates/bulk")
@router.post("/device-types/actions/interfaces/bulk")
async def bulk_interface_templates_action(
    request: Request,
    csrf: str = Form(""),
    device_type_id: int = Form(...),
    name_pattern: str = Form(...),
    start: int = Form(1),
    count: int = Form(...),
    interface_type: str = Form(...),
    label_pattern: str = Form(""),
    description: str = Form(""),
    management_only: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    if not verify_csrf(request, csrf):
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            detail="Creación rechazada por token CSRF inválido.",
            success=False,
            object_id=str(device_type_id),
        )
        return redirect_to_model_interfaces(
            device_type_id,
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            detail="Creación rechazada porque la escritura está deshabilitada.",
            success=False,
            object_id=str(device_type_id),
        )
        return redirect_to_model_interfaces(
            device_type_id,
            error="La escritura en NetBox está deshabilitada.",
        )

    try:
        names = build_interface_names(
            name_pattern,
            start=start,
            count=count,
        )
        created = await DeviceTypeService().create_interface_templates(
            device_type_id=device_type_id,
            names=names,
            interface_type=interface_type,
            label_pattern=label_pattern,
            description=description,
            mgmt_only=management_only == "true",
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="INTERFACE_TEMPLATE_BULK_CREATE",
            resource="interface_template",
            detail=exc.message,
            success=False,
            object_id=str(device_type_id),
        )
        return redirect_to_model_interfaces(
            device_type_id,
            error=exc.message,
        )

    audit_event(
        request,
        action="INTERFACE_TEMPLATE_BULK_CREATE",
        resource="interface_template",
        detail=(
            f"Se crearon {len(created)} interfaces en el modelo "
            f"#{device_type_id}."
        ),
        success=True,
        object_id=str(device_type_id),
    )
    return redirect_to_model_interfaces(
        device_type_id,
        notice=f"Se crearon {len(created)} interfaces correctamente.",
    )
