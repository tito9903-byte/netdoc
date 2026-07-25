from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
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
from app.services.device_image_service import DeviceImageService
from app.services.device_type_service import (
    DeviceTypeService,
    DeviceTypeServiceError,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")


def redirect_message(
    device_type_id: int,
    *,
    notice: str = "",
    error: str = "",
) -> RedirectResponse:
    params: dict[str, str] = {}
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(
        url=f"/device-types/{device_type_id}/images{query}",
        status_code=303,
    )


def creation_redirect(
    *,
    notice: str = "",
    error: str = "",
    device_type_id: int | None = None,
) -> RedirectResponse:
    params: dict[str, str | int] = {}
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    if device_type_id:
        params["device_type_id"] = device_type_id

    target = "/device-types" if device_type_id else "/device-types/new"
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(url=f"{target}{query}", status_code=303)


def audit_event(
    request: Request,
    *,
    action: str,
    device_type_id: int | None,
    detail: str,
    success: bool,
) -> None:
    user_id = request.session.get("user_id")
    ip_address, user_agent = request_client_data(request)
    with session_scope() as session:
        record_audit(
            session,
            action=action,
            resource="device_type",
            resource_id=(
                str(device_type_id)
                if isinstance(device_type_id, int)
                else None
            ),
            user_id=user_id if isinstance(user_id, int) else None,
            username=str(request.session.get("username") or "desconocido"),
            detail=detail,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )


async def read_optional_image(
    upload: UploadFile | None,
) -> tuple[str, bytes, str] | None:
    if upload is None or not upload.filename:
        return None
    content = await upload.read()
    return (
        upload.filename,
        content,
        upload.content_type or "application/octet-stream",
    )


async def close_uploads(*uploads: UploadFile | None) -> None:
    for upload in uploads:
        if upload is not None:
            await upload.close()


@router.post("/device-types/actions/create-with-images")
@router.post("/device-types/new-with-images")
async def create_device_type_with_images(
    request: Request,
    csrf: str = Form(""),
    manufacturer_id: int = Form(...),
    model: str = Form(...),
    slug: str = Form(""),
    part_number: str = Form(""),
    u_height: float = Form(1),
    full_depth: str = Form(""),
    description: str = Form(""),
    front_image: UploadFile | None = File(None),
    rear_image: UploadFile | None = File(None),
):
    """Crea el modelo y adjunta sus vistas físicas en un solo flujo."""

    redirect = access_redirect(request, "devices.create")
    if redirect:
        await close_uploads(front_image, rear_image)
        return redirect

    if not verify_csrf(request, csrf):
        await close_uploads(front_image, rear_image)
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            device_type_id=None,
            detail="Creación rechazada por token CSRF inválido.",
            success=False,
        )
        return creation_redirect(
            error="La sesión del formulario expiró. Recarga la página."
        )

    if not settings.netbox_write_enabled:
        await close_uploads(front_image, rear_image)
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            device_type_id=None,
            detail="Creación rechazada porque la escritura está deshabilitada.",
            success=False,
        )
        return creation_redirect(
            error="La escritura en NetBox está deshabilitada."
        )

    front: tuple[str, bytes, str] | None = None
    rear: tuple[str, bytes, str] | None = None
    images: dict[str, tuple[str, bytes, str]] = {}
    image_service = DeviceImageService()

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
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            device_type_id=None,
            detail=f"Creación rechazada por imagen inválida: {exc.message}",
            success=False,
        )
        return creation_redirect(error=exc.message)
    finally:
        await close_uploads(front_image, rear_image)

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
            device_type_id=None,
            detail=exc.message,
            success=False,
        )
        return creation_redirect(error=exc.message)

    raw_id = created.get("id")
    if not isinstance(raw_id, int):
        audit_event(
            request,
            action="DEVICE_TYPE_CREATE",
            device_type_id=None,
            detail=(
                "NetBox creó el modelo, pero no devolvió un identificador válido."
            ),
            success=False,
        )
        return creation_redirect(
            error=(
                "NetBox creó el modelo, pero no devolvió un ID válido. "
                "Revísalo directamente en NetBox."
            )
        )

    audit_event(
        request,
        action="DEVICE_TYPE_CREATE",
        device_type_id=raw_id,
        detail=f"Modelo {model.strip()} creado en NetBox.",
        success=True,
    )

    if images:
        try:
            await image_service.upload_images(
                device_type_id=raw_id,
                images=images,
            )
        except DeviceTypeServiceError as exc:
            audit_event(
                request,
                action="DEVICE_TYPE_IMAGE_UPDATE",
                device_type_id=raw_id,
                detail=exc.message,
                success=False,
            )
            return redirect_message(
                raw_id,
                error=(
                    "El modelo fue creado correctamente, pero las imágenes no "
                    f"pudieron guardarse: {exc.message}"
                ),
            )

        faces: list[str] = []
        if front:
            faces.append("frontal")
        if rear:
            faces.append("trasera")
        audit_event(
            request,
            action="DEVICE_TYPE_IMAGE_UPDATE",
            device_type_id=raw_id,
            detail=f"Imagen {' y '.join(faces)} guardada al crear el modelo.",
            success=True,
        )

    notice = "Modelo creado correctamente."
    if images:
        notice = (
            "Modelo e imágenes creados correctamente. "
            "Ahora puedes preparar sus plantillas de puertos."
        )

    return creation_redirect(
        notice=notice,
        device_type_id=raw_id,
    )


@router.get(
    "/device-types/{device_type_id}/images",
    response_class=HTMLResponse,
)
async def device_type_images_page(
    request: Request,
    device_type_id: int,
    notice: str = "",
    error: str = "",
):
    redirect = access_redirect(request, "devices.view")
    if redirect:
        return redirect

    try:
        device_type = await DeviceTypeService().get_device_type(device_type_id)
    except DeviceTypeServiceError as exc:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            status_code=404 if exc.status_code == 404 else 503,
            context={
                **common_session_context(request),
                "current_page": "device_types",
                "netbox_connected": exc.status_code != 503,
                "netbox_url": settings.netbox_url,
                "write_enabled": settings.netbox_write_enabled,
                "page_title": "Imágenes del modelo",
                "page_subtitle": "No fue posible consultar el modelo",
                "error_title": "No se pudo abrir la galería del modelo",
                "error_message": exc.message,
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="device_type_images.html",
        context={
            **common_session_context(request),
            "current_page": "device_types",
            "netbox_connected": True,
            "netbox_url": settings.netbox_url,
            "write_enabled": settings.netbox_write_enabled,
            "page_title": "Imágenes del modelo",
            "page_subtitle": (
                "Frente y parte trasera reutilizados en racks y topología"
            ),
            "device_type": device_type,
            "csrf_token": csrf_token(request),
            "notice": notice,
            "error": error,
        },
    )


@router.post("/device-types/{device_type_id}/images")
async def update_device_type_images(
    request: Request,
    device_type_id: int,
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
        audit_event(
            request,
            action="DEVICE_TYPE_IMAGE_UPDATE",
            device_type_id=device_type_id,
            detail="Actualización de imágenes rechazada por CSRF inválido.",
            success=False,
        )
        return redirect_message(
            device_type_id,
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        await close_uploads(front_image, rear_image)
        audit_event(
            request,
            action="DEVICE_TYPE_IMAGE_UPDATE",
            device_type_id=device_type_id,
            detail="Actualización rechazada porque la escritura está deshabilitada.",
            success=False,
        )
        return redirect_message(
            device_type_id,
            error="La escritura en NetBox está deshabilitada.",
        )

    front = await read_optional_image(front_image)
    rear = await read_optional_image(rear_image)
    images: dict[str, tuple[str, bytes, str]] = {}
    if front:
        images["front_image"] = front
    if rear:
        images["rear_image"] = rear

    try:
        await DeviceImageService().upload_images(
            device_type_id=device_type_id,
            images=images,
        )
    except DeviceTypeServiceError as exc:
        audit_event(
            request,
            action="DEVICE_TYPE_IMAGE_UPDATE",
            device_type_id=device_type_id,
            detail=exc.message,
            success=False,
        )
        return redirect_message(device_type_id, error=exc.message)
    finally:
        await close_uploads(front_image, rear_image)

    faces: list[str] = []
    if front:
        faces.append("frontal")
    if rear:
        faces.append("trasera")
    audit_event(
        request,
        action="DEVICE_TYPE_IMAGE_UPDATE",
        device_type_id=device_type_id,
        detail=f"Imagen {' y '.join(faces)} actualizada en NetBox.",
        success=True,
    )
    return redirect_message(
        device_type_id,
        notice="Las imágenes del modelo se actualizaron correctamente.",
    )
