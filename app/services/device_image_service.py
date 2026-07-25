from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.services.device_type_service import DeviceTypeServiceError
from app.services.rack_service import RackService


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAXIMUM_IMAGE_BYTES = 5 * 1024 * 1024


class DeviceImageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.netbox_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        token_type = self.settings.netbox_token_type.strip().lower()
        authorization = (
            f"Bearer {self.settings.netbox_token}"
            if token_type == "bearer"
            else f"Token {self.settings.netbox_token}"
        )
        return {
            "Authorization": authorization,
            "Accept": "application/json",
            "User-Agent": "NetDoc/0.10.0",
        }

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"NetBox respondió con HTTP {response.status_code}."
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            messages = []
            for field, value in payload.items():
                rendered = (
                    ", ".join(str(item) for item in value)
                    if isinstance(value, list)
                    else str(value)
                )
                messages.append(f"{field}: {rendered}")
            if messages:
                return " | ".join(messages)
        return f"NetBox respondió con HTTP {response.status_code}."

    @staticmethod
    def validate_image(
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> None:
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise DeviceTypeServiceError(
                "La imagen debe ser JPG, PNG, WEBP o GIF."
            )
        if not content:
            raise DeviceTypeServiceError("La imagen está vacía.")
        if len(content) > MAXIMUM_IMAGE_BYTES:
            raise DeviceTypeServiceError(
                "Cada imagen debe pesar 5 MB o menos."
            )
        if not filename.strip():
            raise DeviceTypeServiceError(
                "La imagen debe tener un nombre de archivo."
            )

    async def upload_images(
        self,
        *,
        device_type_id: int,
        images: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        files: dict[str, tuple[str, bytes, str]] = {}
        for face, image in images.items():
            if face not in {"front_image", "rear_image"}:
                raise DeviceTypeServiceError(
                    "La cara indicada para la imagen no es válida."
                )
            filename, content, content_type = image
            self.validate_image(
                filename=filename,
                content_type=content_type,
                content=content,
            )
            files[face] = (filename, content, content_type)

        if not files:
            raise DeviceTypeServiceError(
                "Selecciona al menos una imagen frontal o trasera."
            )

        url = f"{self.base_url}/api/dcim/device-types/{device_type_id}/"
        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                verify=self.settings.netbox_verify_ssl,
                timeout=max(self.settings.netbox_timeout, 30.0),
                follow_redirects=True,
            ) as client:
                response = await client.patch(url, files=files)
        except httpx.ConnectError as exc:
            raise DeviceTypeServiceError(
                "No fue posible conectar con NetBox para subir la imagen."
            ) from exc
        except httpx.TimeoutException as exc:
            raise DeviceTypeServiceError(
                "NetBox tardó demasiado en recibir la imagen."
            ) from exc

        if response.is_error:
            raise DeviceTypeServiceError(
                self._error_message(response),
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise DeviceTypeServiceError(
                "NetBox actualizó el modelo, pero devolvió una respuesta inválida."
            ) from exc
        if not isinstance(payload, dict):
            raise DeviceTypeServiceError(
                "NetBox devolvió un formato inesperado al actualizar la imagen."
            )

        RackService._device_type_cache.pop(device_type_id, None)
        return payload
