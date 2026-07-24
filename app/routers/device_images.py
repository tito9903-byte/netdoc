from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.core.auth import (
    access_redirect,
    request_client_data,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.database import session_scope
from app.services.access_service import record_audit
from app.services.device_image_service import DeviceImageService
from app.services.device_type_service import DeviceTypeServiceError


router = APIRouter()
settings = get_settings()


def redirect_message(
    device_type_id: int,
    *,
    notice: str = "",
    error: str = "",
) -> RedirectResponse:
    params: dict[str, str | int] = {"device_type_id": device_type_id}
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    return RedirectResponse(
        url=f"/device-types?{urlencode(params)}",
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
