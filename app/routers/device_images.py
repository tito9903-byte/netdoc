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


def audit(
    request: Request,
    *,
    device_type_id: int,
    detail: str,
    success: bool,
) -> None:
    user_id = request.session.get("user_id")
    ip_address, user_agent = request_client_data(request)
    with session_scope() as session:
        record_audit(
            session,
            action="DEVICE_TYPE_IMAGE_UPDATE",
            resource="device_type",
            resource_id=str(device_type_id),
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
        return redirect

    if not verify_csrf(request, csrf):
        audit(
            request,
            device_type_id=device_type_id,
            detail="Actualización de imágenes rechazada por CSRF inválido.",
            success=False,
        )
        return redirect_message(
            device_type_id,
            error="La sesión del formulario expiró. Recarga la página.",
        )

    if not settings.netbox_write_enabled:
        audit(
            request,
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
    images = {}
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
        audit(
            request,
            device_type_id=device_type_id,
            detail=exc.message,
            success=False,
        )
        return redirect_message(device_type_id, error=exc.message)
    finally:
        if front_image is not None:
            await front_image.close()
        if rear_image is not None:
            await rear_image.close()

    faces = []
    if front:
        faces.append("frontal")
    if rear:
        faces.append("trasera")
    audit(
        request,
        device_type_id=device_type_id,
        detail=f"Imagen {' y '.join(faces)} actualizada en NetBox.",
        success=True,
    )
    return redirect_message(
        device_type_id,
        notice="Las imágenes del modelo se actualizaron correctamente.",
    )
