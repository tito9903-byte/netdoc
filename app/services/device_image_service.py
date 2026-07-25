from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from app.core.database import session_scope
from app.models.device_media import DeviceTypeImage
from app.services.device_type_service import DeviceTypeServiceError


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAXIMUM_IMAGE_BYTES = 5 * 1024 * 1024
VALID_FACES = {"front", "rear"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceImageService:
    """Persistencia local de imágenes vinculadas a modelos de NetBox.

    NetBox continúa siendo la fuente oficial del modelo y de sus dimensiones. La
    base de NetDoc conserva únicamente los binarios frontal y trasero asociados al
    identificador externo ``device_type_id``.
    """

    @staticmethod
    def normalize_face(face: str) -> str:
        normalized = face.removesuffix("_image").strip().lower()
        if normalized not in VALID_FACES:
            raise DeviceTypeServiceError(
                "La cara indicada para la imagen no es válida."
            )
        return normalized

    @staticmethod
    def detect_content_type(content: bytes) -> str | None:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        ):
            return "image/webp"
        return None

    @classmethod
    def validate_image(
        cls,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> str:
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

        detected_type = cls.detect_content_type(content)
        if detected_type not in ALLOWED_IMAGE_TYPES:
            raise DeviceTypeServiceError(
                "El archivo no contiene una imagen JPG, PNG, WEBP o GIF válida."
            )

        declared_type = (content_type or "").split(";", 1)[0].strip().lower()
        if declared_type in ALLOWED_IMAGE_TYPES and declared_type != detected_type:
            raise DeviceTypeServiceError(
                "El contenido de la imagen no coincide con su tipo de archivo."
            )
        return detected_type

    @staticmethod
    def _safe_filename(filename: str, content_type: str) -> str:
        clean = Path(filename).name.strip()[:255]
        if clean:
            return clean
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }[content_type]
        return f"device-image.{extension}"

    def save_images(
        self,
        *,
        device_type_id: int,
        images: dict[str, tuple[str, bytes, str]],
        username: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        if device_type_id <= 0:
            raise DeviceTypeServiceError(
                "El modelo no tiene un identificador válido."
            )
        if not images:
            raise DeviceTypeServiceError(
                "Selecciona al menos una imagen frontal o trasera."
            )

        validated: dict[str, tuple[str, bytes, str, str]] = {}
        for raw_face, image in images.items():
            face = self.normalize_face(raw_face)
            filename, content, declared_type = image
            detected_type = self.validate_image(
                filename=filename,
                content_type=declared_type,
                content=content,
            )
            validated[face] = (
                self._safe_filename(filename, detected_type),
                bytes(content),
                detected_type,
                sha256(content).hexdigest(),
            )

        result: dict[str, dict[str, Any]] = {}
        now = utc_now()
        with session_scope() as session:
            existing = {
                item.face: item
                for item in session.scalars(
                    select(DeviceTypeImage).where(
                        DeviceTypeImage.device_type_id == device_type_id,
                        DeviceTypeImage.face.in_(validated),
                    )
                )
            }

            for face, (filename, content, content_type, digest) in validated.items():
                image = existing.get(face)
                if image is None:
                    image = DeviceTypeImage(
                        device_type_id=device_type_id,
                        face=face,
                        filename=filename,
                        content_type=content_type,
                        content=content,
                        sha256=digest,
                        size_bytes=len(content),
                        created_at=now,
                        updated_at=now,
                        updated_by=username,
                    )
                    session.add(image)
                else:
                    image.filename = filename
                    image.content_type = content_type
                    image.content = content
                    image.sha256 = digest
                    image.size_bytes = len(content)
                    image.updated_at = now
                    image.updated_by = username

                result[face] = {
                    "device_type_id": device_type_id,
                    "face": face,
                    "filename": filename,
                    "content_type": content_type,
                    "sha256": digest,
                    "size_bytes": len(content),
                    "source": "netdoc",
                }

        # El detalle de NetBox puede estar en memoria durante cinco minutos. Se
        # invalida para que la próxima elevación incorpore la nueva imagen local.
        from app.services.rack_service import RackService

        RackService._device_type_cache.pop(device_type_id, None)
        return result

    async def upload_images(
        self,
        *,
        device_type_id: int,
        images: dict[str, tuple[str, bytes, str]],
        username: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Compatibilidad con los flujos multipart existentes."""
        return self.save_images(
            device_type_id=device_type_id,
            images=images,
            username=username,
        )

    def summaries(
        self,
        device_type_ids: Iterable[int],
    ) -> dict[int, dict[str, dict[str, Any]]]:
        ids = sorted({int(item) for item in device_type_ids if int(item) > 0})
        if not ids:
            return {}

        result: dict[int, dict[str, dict[str, Any]]] = {}
        with session_scope() as session:
            rows = session.scalars(
                select(DeviceTypeImage).where(
                    DeviceTypeImage.device_type_id.in_(ids)
                )
            ).all()
            for image in rows:
                result.setdefault(image.device_type_id, {})[image.face] = {
                    "filename": image.filename,
                    "content_type": image.content_type,
                    "sha256": image.sha256,
                    "size_bytes": image.size_bytes,
                    "updated_at": image.updated_at,
                    "updated_by": image.updated_by,
                    "source": "netdoc",
                }
        return result

    def summary(self, device_type_id: int) -> dict[str, dict[str, Any]]:
        return self.summaries([device_type_id]).get(device_type_id, {})

    def decorate_device_types(
        self,
        device_types: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = [dict(item) for item in device_types]
        ids = [
            int(item["id"])
            for item in rows
            if isinstance(item.get("id"), int)
        ]
        summaries = self.summaries(ids)

        decorated: list[dict[str, Any]] = []
        for item in rows:
            device_type_id = item.get("id")
            local = (
                summaries.get(int(device_type_id), {})
                if isinstance(device_type_id, int)
                else {}
            )
            for face in VALID_FACES:
                has_local = face in local
                has_netbox = bool(item.get(f"{face}_image"))
                item[f"_local_{face}_image"] = has_local
                item[f"_{face}_image_available"] = has_local or has_netbox
                item[f"_{face}_image_source"] = (
                    "netdoc" if has_local else "netbox" if has_netbox else ""
                )
                item[f"_{face}_image_metadata"] = local.get(face)
            decorated.append(item)
        return decorated

    def decorate_device_type(
        self,
        device_type: dict[str, Any],
    ) -> dict[str, Any]:
        decorated = self.decorate_device_types([device_type])
        return decorated[0] if decorated else dict(device_type)

    def get_local_image(
        self,
        device_type_id: int,
        face: str,
    ) -> tuple[bytes, str, str] | None:
        normalized = self.normalize_face(face)
        with session_scope() as session:
            image = session.scalar(
                select(DeviceTypeImage).where(
                    DeviceTypeImage.device_type_id == device_type_id,
                    DeviceTypeImage.face == normalized,
                )
            )
            if image is None:
                return None
            return bytes(image.content), image.content_type, image.sha256
