from __future__ import annotations

import asyncio
from typing import Any

from app.services.device_type_service import (
    DeviceTypeService,
    DeviceTypeServiceError,
    nested_label,
)


INTERFACE_COPY_FIELDS = (
    "label",
    "type",
    "enabled",
    "mgmt_only",
    "description",
    "poe_mode",
    "poe_type",
    "rf_role",
    "wireless_role",
    "mark_connected",
    "speed",
    "duplex",
    "custom_fields",
)


class DeviceInterfaceSyncService:
    """Compara el dispositivo con su modelo y crea solo interfaces faltantes.

    No elimina, renombra ni sobrescribe interfaces existentes. La coincidencia se
    realiza por nombre ignorando mayúsculas/minúsculas para evitar duplicados
    accidentales. Las relaciones que dependen de IDs de interfaces reales (LAG,
    bridge o parent) no se copian automáticamente.
    """

    def __init__(self) -> None:
        self.client = DeviceTypeService()

    @staticmethod
    def _nested_id(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, dict) and isinstance(value.get("id"), int):
            return int(value["id"])
        return None

    @staticmethod
    def _choice_value(value: Any) -> Any:
        if isinstance(value, dict):
            for key in ("value", "id", "slug", "name"):
                candidate = value.get(key)
                if candidate not in (None, ""):
                    return candidate
            return None
        return value

    @classmethod
    def _template_payload(
        cls,
        template: dict[str, Any],
        *,
        device_id: int,
    ) -> dict[str, Any]:
        name = str(template.get("name") or "").strip()
        if not name:
            raise DeviceTypeServiceError(
                "El modelo contiene una plantilla de interfaz sin nombre.",
                400,
            )

        payload: dict[str, Any] = {
            "device": device_id,
            "name": name,
        }
        for field in INTERFACE_COPY_FIELDS:
            if field not in template:
                continue
            raw_value = template.get(field)
            if raw_value in (None, ""):
                continue
            if field == "custom_fields":
                if isinstance(raw_value, dict) and raw_value:
                    payload[field] = dict(raw_value)
                continue
            value = cls._choice_value(raw_value)
            if value not in (None, ""):
                payload[field] = value

        if not payload.get("type"):
            raise DeviceTypeServiceError(
                f"La plantilla {name} no tiene un tipo de interfaz válido.",
                400,
            )
        return payload

    async def preview(self, device_id: int) -> dict[str, Any]:
        device = await self.client.request(
            "GET",
            f"/api/dcim/devices/{device_id}/",
        )
        if not isinstance(device, dict):
            raise DeviceTypeServiceError(
                "NetBox devolvió un dispositivo inesperado.",
                502,
            )

        device_type = device.get("device_type") or {}
        device_type_id = self._nested_id(device_type)
        if device_type_id is None:
            raise DeviceTypeServiceError(
                "El dispositivo no tiene un modelo asociado.",
                400,
            )

        templates, interfaces = await asyncio.gather(
            self.client.get_all(
                "/api/dcim/interface-templates/",
                params={
                    "device_type_id": device_type_id,
                    "ordering": "name",
                },
            ),
            self.client.get_all(
                "/api/dcim/interfaces/",
                params={
                    "device_id": device_id,
                    "ordering": "name",
                },
            ),
        )

        existing_by_name = {
            str(item.get("name") or "").strip().casefold(): item
            for item in interfaces
            if str(item.get("name") or "").strip()
        }
        missing: list[dict[str, Any]] = []
        matching: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []

        for template in templates:
            name = str(template.get("name") or "").strip()
            if not name:
                continue
            existing = existing_by_name.get(name.casefold())
            if existing is None:
                missing.append(template)
                continue

            template_type_value = str(
                self._choice_value(template.get("type")) or ""
            )
            existing_type_value = str(
                self._choice_value(existing.get("type")) or ""
            )
            comparison = {
                "name": name,
                "template_type": nested_label(template.get("type"), "Sin tipo"),
                "existing_type": nested_label(existing.get("type"), "Sin tipo"),
            }
            if (
                template_type_value
                and existing_type_value
                and template_type_value != existing_type_value
            ):
                conflicts.append(comparison)
            else:
                matching.append(comparison)

        for template in missing:
            template["_type_label"] = nested_label(template.get("type"), "Sin tipo")

        return {
            "device": device,
            "device_type": device_type,
            "device_type_id": device_type_id,
            "templates": templates,
            "interfaces": interfaces,
            "missing": missing,
            "matching": matching,
            "conflicts": conflicts,
            "template_count": len(templates),
            "existing_count": len(interfaces),
            "missing_count": len(missing),
            "matching_count": len(matching),
            "conflict_count": len(conflicts),
        }

    async def synchronize(self, device_id: int) -> dict[str, Any]:
        preview = await self.preview(device_id)
        missing = preview["missing"]
        if not missing:
            return {
                **preview,
                "created": [],
                "created_count": 0,
            }

        payload = [
            self._template_payload(template, device_id=device_id)
            for template in missing
        ]
        result = await self.client.request(
            "POST",
            "/api/dcim/interfaces/",
            json_body=payload,
        )
        if isinstance(result, list):
            created = [item for item in result if isinstance(item, dict)]
        elif isinstance(result, dict):
            created = [result]
        else:
            raise DeviceTypeServiceError(
                "NetBox creó las interfaces, pero devolvió un formato inesperado.",
                502,
            )

        return {
            **preview,
            "created": created,
            "created_count": len(created),
        }
