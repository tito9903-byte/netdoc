from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import (
    access_redirect,
    api_access_response,
    common_session_context,
    csrf_token,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.routers.device_create import (
    signed_form_token,
    verify_signed_form_token,
)
from app.services.access_service import record_audit
from app.services.component_sequence_service import ComponentSequenceService
from app.services.device_image_service import DeviceImageService
from app.services.device_interface_sync_service import DeviceInterfaceSyncService
from app.services.device_model_builder_service import DeviceModelBuilderService
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def context(request: Request, **extra: object) -> dict[str, object]:
    return {
        **common_session_context(request),
        "current_page": "device_types",
        "netbox_connected": True,
        "netbox_url": settings.netbox_url,
        "write_enabled": settings.netbox_write_enabled,
        **extra,
    }


def audit_event(
    request: Request,
    *,
    action: str,
    resource: str,
    detail: str,
    success: bool,
    resource_id: str | None = None,
) -> None:
    ip_address, user_agent = request_client_data(request)
    user_id = request.session.get("user_id")
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource=resource,
            resource_id=resource_id,
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


def redirect_with_message(
    path: str,
    *,
    notice: str = "",
    error: str = "",
    fragment: str = "",
) -> RedirectResponse:
    params = {
        key: value
        for key, value in {"notice": notice, "error": error}.items()
        if value
    }
    query = f"?{urlencode(params)}" if params else ""
    anchor = f"#{fragment}" if fragment else ""
    return RedirectResponse(f"{path}{query}{anchor}", status_code=303)


async def read_optional_image(
    upload: UploadFile | None,
) -> tuple[str, bytes, str] | None:
    if upload is None or not upload.filename:
        return None
    return (
        upload.filename,
        await upload.read(),
        upload.content_type or "application/octet-stream",
    )


async def close_uploads(*uploads: UploadFile | None) -> None:
    for upload in uploads:
        if upload is not None:
            await upload.close()


@router.get("/api/device-types/model-fields", response_class=JSONResponse)
async def model_fields_api(request: Request):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied
    try:
        fields = await DeviceModelBuilderService().model_advanced_fields()
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code or 503,
            content={"ok": False, "error": exc.message},
        )
    return JSONResponse(content={"ok": True, "fields": fields})


@router.get(
    "/api/device-types/{device_type_id}/component-fields",
    response_class=JSONResponse,
)
async def component_fields_api(
    request: Request,
    device_type_id: int,
    kind: str = "interface",
):
    denied = api_access_response(request, "devices.view")
    if denied:
        return denied
    try:
        service = DeviceModelBuilderService()
        definition = service.definition(kind)
        fields = await service.component_fields(
            kind,
            device_type_id=device_type_id,
        )
    except DeviceTypeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code or 503,
            content={"ok": False, "error": exc.message},
        )
    return JSONResponse(
        content={
            "ok": True,
            "component": {
                "key": definition.key,
                "label": definition.label,
                "singular": definition.singular,
                "description": definition.description,
            },
            "fields": fields,
        }
    )


@router.post("/device-types/actions/create-complete")
async def create_complete_device_type(
    request: Request,
    csrf: str = Form(""),
    front_image: UploadFile | None = File(None),
    rear_image: UploadFile | None = File(None),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        await close_uploads(front_image, rear_image)
        return redirect

    if not verify_csrf(request, csrf):
        await close_uploads(front_image, rear_image)
        return redirect_with_message(
            "/device-types/new",
            error="La sesión del formulario expiró. Recarga la página.",
        )
    if not settings.netbox_write_enabled:
        await close_uploads(front_image, rear_image)
        return redirect_with_message(
            "/device-types/new",
            error="La escritura en NetBox está deshabilitada.",
        )

    form = await request.form()
    image_service = DeviceImageService()
    images: dict[str, tuple[str, bytes, str]] = {}

    try:
        front = await read_optional_image(front_image)
        rear = await read_optional_image(rear_image)
        if front:
            image_service.validate_image(
                filename=front[0],
                content=front[1],
                content_type=front[2],
            )
            images["front_image"] = front
        if rear:
            image_service.validate_image(
                filename=rear[0],
                content=rear[1],
                content_type=rear[2],
            )
            images["rear_image"] = rear

        created = await DeviceModelBuilderService().create_device_type(form)
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            resource="device_type",
            detail=exc.message,
            success=False,
        )
        return redirect_with_message("/device-types/new", error=exc.message)
    finally:
        await close_uploads(front_image, rear_image)

    raw_id = created.get("id")
    if not isinstance(raw_id, int):
        return redirect_with_message(
            "/device-types",
            error=(
                "NetBox creó el modelo, pero no devolvió un identificador válido."
            ),
        )

    if images:
        try:
            await image_service.upload_images(
                device_type_id=raw_id,
                images=images,
                username=str(request.session.get("username") or "desconocido"),
            )
        except DeviceTypeServiceError as exc:
            audit_event(
                request,
                action="DEVICE_TYPE_IMAGE_UPDATE",
                resource="device_type_image",
                resource_id=str(raw_id),
                detail=exc.message,
                success=False,
            )
            return redirect_with_message(
                f"/device-types/{raw_id}",
                error=(
                    "El modelo fue creado, pero sus imágenes no pudieron "
                    f"guardarse: {exc.message}"
                ),
            )

    model_name = str(created.get("model") or form.get("model") or "Modelo")
    audit_event(
        request,
        action="DEVICE_TYPE_CREATE",
        resource="device_type",
        resource_id=str(raw_id),
        detail=f"Modelo {model_name} creado con el esquema publicado por NetBox.",
        success=True,
    )
    return redirect_with_message(
        f"/device-types/{raw_id}",
        notice=(
            "Modelo documentado correctamente. Ahora puedes agregar puertos, "
            "interfaces y componentes desde esta misma ficha."
        ),
        fragment="components",
    )


@router.get(
    "/device-types/{device_type_id}/components/new",
    response_class=HTMLResponse,
)
async def new_model_component_page(
    request: Request,
    device_type_id: int,
    kind: str = "interface",
    error: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    service = DeviceModelBuilderService()
    try:
        definition = service.definition(kind)
        device_type = await DeviceTypeService().get_device_type(device_type_id)
        fields = await service.component_fields(
            kind,
            device_type_id=device_type_id,
        )
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                page_title="Componente no disponible",
                page_subtitle="No fue posible preparar el formulario de NetBox",
                error_title="No se pudo abrir el generador",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_type_component_new.html",
        context=context(
            request,
            page_title=f"Agregar {definition.label.lower()}",
            page_subtitle="Documentación reutilizable heredada por cada equipo",
            device_type=device_type,
            device_type_id=device_type_id,
            component_types=service.definitions(),
            selected_kind=definition.key,
            component_definition=definition,
            component_fields=fields,
            csrf_token=csrf_token(request),
            error=error,
        ),
    )


@router.post("/device-types/{device_type_id}/components/actions/create")
async def create_model_components_action(
    request: Request,
    device_type_id: int,
    csrf: str = Form(""),
    kind: str = Form("interface"),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect
    target = f"/device-types/{device_type_id}/components/new?kind={kind}"

    if not verify_csrf(request, csrf):
        return redirect_with_message(
            target,
            error="La sesión del formulario expiró. Recarga la página.",
        )
    if not settings.netbox_write_enabled:
        return redirect_with_message(
            target,
            error="La escritura en NetBox está deshabilitada.",
        )

    form = await request.form()
    service = ComponentSequenceService()
    try:
        definition = service.definition(kind)
        created = await service.create_components(
            kind,
            device_type_id=device_type_id,
            form=form,
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_COMPONENT_TEMPLATE_CREATE",
            resource="device_component_template",
            resource_id=str(device_type_id),
            detail=exc.message,
            success=False,
        )
        return redirect_with_message(target, error=exc.message)

    audit_event(
        request,
        action="DEVICE_COMPONENT_TEMPLATE_CREATE",
        resource="device_component_template",
        resource_id=str(device_type_id),
        detail=(
            f"Se documentaron {len(created)} elementos de tipo "
            f"{definition.label.lower()} en el modelo #{device_type_id}."
        ),
        success=True,
    )
    return redirect_with_message(
        f"/device-types/{device_type_id}",
        notice=(
            f"Se crearon {len(created)} registros de "
            f"{definition.label.lower()} correctamente."
        ),
        fragment="components",
    )


@router.get(
    "/devices/{device_id}/interfaces/sync",
    response_class=HTMLResponse,
)
async def device_interface_sync_page(
    request: Request,
    device_id: int,
    error: str = "",
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    try:
        preview = await DeviceInterfaceSyncService().preview(device_id)
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context=context(
                request,
                current_page="devices",
                page_title="Sincronización no disponible",
                page_subtitle="No fue posible comparar el dispositivo con su modelo",
                error_title="No se pudieron preparar las interfaces",
                error_message=exc.message,
                netbox_connected=exc.status_code != 503,
            ),
        )

    return templates.TemplateResponse(
        request=request,
        name="device_interface_sync.html",
        context=context(
            request,
            current_page="devices",
            page_title="Sincronizar interfaces",
            page_subtitle="Crear interfaces faltantes desde el modelo de NetBox",
            preview=preview,
            csrf_token=signed_form_token(
                request,
                f"device-interface-sync:{device_id}",
            ),
            error=error,
        ),
    )


@router.post(
    "/devices/{device_id}/interfaces/sync",
    response_class=HTMLResponse,
)
async def device_interface_sync_action(
    request: Request,
    device_id: int,
    csrf_token: str = Form(""),
):
    redirect = access_redirect(request, "devices.create")
    if redirect:
        return redirect

    namespace = f"device-interface-sync:{device_id}"
    target = f"/devices/{device_id}/interfaces/sync"
    if not verify_signed_form_token(request, csrf_token, namespace):
        return RedirectResponse(
            f"{target}?{urlencode({'error': 'La sesión de seguridad venció. Abre nuevamente la sincronización.'})}",
            status_code=303,
        )
    if not settings.netbox_write_enabled:
        return RedirectResponse(
            f"{target}?{urlencode({'error': 'La escritura en NetBox está deshabilitada.'})}",
            status_code=303,
        )

    try:
        result = await DeviceInterfaceSyncService().synchronize(device_id)
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_INTERFACE_SYNC",
            resource="device_interface",
            resource_id=str(device_id),
            detail=exc.message,
            success=False,
        )
        return RedirectResponse(
            f"{target}?{urlencode({'error': exc.message})}",
            status_code=303,
        )

    created_count = int(result.get("created_count") or 0)
    matching_count = int(result.get("matching_count") or 0)
    conflict_count = int(result.get("conflict_count") or 0)
    audit_event(
        request,
        action="DEVICE_INTERFACE_SYNC",
        resource="device_interface",
        resource_id=str(device_id),
        detail=(
            f"Sincronización desde el modelo: {created_count} creadas, "
            f"{matching_count} ya coincidentes y {conflict_count} para revisión."
        ),
        success=True,
    )

    params = urlencode({
        "interfaces_synced": created_count,
        "interfaces_existing": matching_count,
        "interfaces_conflicts": conflict_count,
    })
    return RedirectResponse(
        f"/devices/{device_id}?{params}#interfaces",
        status_code=303,
    )
