from __future__ import annotations

import asyncio
from typing import Any

from app.services.change_plan import ChangePlanError, ChangeStep
from app.services.device_type_service import (
    DeviceTypeService,
    DeviceTypeServiceError,
    nested_label,
    slugify,
)
from app.services.netbox_capabilities import validate_step_capability


class HardwareServiceError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _prepared_manufacturer(
    manufacturer: dict[str, Any],
    model_count: int,
) -> dict[str, Any]:
    return {
        **manufacturer,
        "_name": str(
            manufacturer.get("name")
            or manufacturer.get("display")
            or "Sin nombre"
        ),
        "_model_count": model_count,
    }


def _count(model: dict[str, Any], field: str) -> int:
    try:
        return int(model.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def _prepared_model(model: dict[str, Any]) -> dict[str, Any]:
    manufacturer = model.get("manufacturer") or {}
    return {
        **model,
        "_manufacturer_label": nested_label(
            manufacturer,
            "Sin fabricante",
        ),
        "_model_label": str(
            model.get("model")
            or model.get("display")
            or "Sin modelo"
        ),
        "_interface_count": _count(model, "interface_template_count"),
        "_module_bay_count": _count(model, "module_bay_template_count"),
        "_power_port_count": _count(model, "power_port_template_count"),
        "_power_outlet_count": _count(model, "power_outlet_template_count"),
        "_console_port_count": _count(model, "console_port_template_count"),
        "_console_server_port_count": _count(
            model,
            "console_server_port_template_count",
        ),
        "_front_port_count": _count(model, "front_port_template_count"),
        "_rear_port_count": _count(model, "rear_port_template_count"),
        "_device_bay_count": _count(model, "device_bay_template_count"),
        "_inventory_item_count": _count(model, "inventory_item_template_count"),
    }


class HardwareService:
    """Consultas y escrituras controladas del catálogo físico."""

    def __init__(self) -> None:
        self.client = DeviceTypeService()

    @staticmethod
    def _translate_error(exc: Exception) -> HardwareServiceError:
        if isinstance(exc, HardwareServiceError):
            return exc
        if isinstance(exc, DeviceTypeServiceError):
            return HardwareServiceError(exc.message, exc.status_code)
        if isinstance(exc, ChangePlanError):
            return HardwareServiceError(str(exc), 400)
        return HardwareServiceError("Ocurrió un error inesperado en hardware.")

    async def manufacturer_catalog(
        self,
        *,
        query: str = "",
    ) -> dict[str, Any]:
        try:
            manufacturers, models = await asyncio.gather(
                self.client.list_manufacturers(),
                self.client.list_device_types(),
            )
        except DeviceTypeServiceError as exc:
            raise self._translate_error(exc) from exc

        counts: dict[int, int] = {}
        for model in models:
            manufacturer = model.get("manufacturer") or {}
            manufacturer_id = (
                manufacturer.get("id")
                if isinstance(manufacturer, dict)
                else None
            )
            if isinstance(manufacturer_id, int):
                counts[manufacturer_id] = counts.get(manufacturer_id, 0) + 1

        clean_query = query.strip().casefold()
        rows = [
            _prepared_manufacturer(
                item,
                counts.get(item.get("id"), 0),
            )
            for item in manufacturers
        ]
        if clean_query:
            rows = [
                item
                for item in rows
                if clean_query in (
                    f"{item.get('_name', '')} "
                    f"{item.get('slug', '')} "
                    f"{item.get('description', '')}"
                ).casefold()
            ]

        rows.sort(key=lambda item: str(item.get("_name") or "").casefold())
        return {
            "manufacturers": rows,
            "total_manufacturers": len(rows),
            "total_models": sum(item["_model_count"] for item in rows),
        }

    async def manufacturer_detail(
        self,
        manufacturer_id: int,
    ) -> dict[str, Any]:
        try:
            manufacturer, models = await asyncio.gather(
                self.client.request(
                    "GET",
                    f"/api/dcim/manufacturers/{manufacturer_id}/",
                ),
                self.client.list_device_types(
                    manufacturer_id=manufacturer_id,
                ),
            )
        except DeviceTypeServiceError as exc:
            raise self._translate_error(exc) from exc

        if not isinstance(manufacturer, dict):
            raise HardwareServiceError(
                "NetBox devolvió un fabricante inesperado.",
                502,
            )
        return {
            "manufacturer": _prepared_manufacturer(
                manufacturer,
                len(models),
            ),
            "models": [_prepared_model(item) for item in models],
        }

    async def model_detail(self, device_type_id: int) -> dict[str, Any]:
        try:
            model = await self.client.get_device_type(device_type_id)
            (
                interfaces,
                module_bays,
                power_ports,
                power_outlets,
                console_ports,
                console_server_ports,
                front_ports,
                rear_ports,
                device_bays,
                inventory_items,
                devices,
            ) = await asyncio.gather(
                self.client.list_interface_templates(device_type_id),
                self.client.get_all(
                    "/api/dcim/module-bay-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/power-port-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/power-outlet-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/console-port-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/console-server-port-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/front-port-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/rear-port-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/device-bay-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/inventory-item-templates/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
                self.client.get_all(
                    "/api/dcim/devices/",
                    params={
                        "device_type_id": device_type_id,
                        "ordering": "name",
                    },
                ),
            )
        except DeviceTypeServiceError as exc:
            raise self._translate_error(exc) from exc

        return {
            "device_type": _prepared_model(model),
            "interfaces": interfaces,
            "module_bays": module_bays,
            "power_ports": power_ports,
            "power_outlets": power_outlets,
            "console_ports": console_ports,
            "console_server_ports": console_server_ports,
            "front_ports": front_ports,
            "rear_ports": rear_ports,
            "device_bays": device_bays,
            "inventory_items": inventory_items,
            "devices": devices,
            "component_summary": {
                "interfaces": len(interfaces),
                "module_bays": len(module_bays),
                "power_ports": len(power_ports),
                "power_outlets": len(power_outlets),
                "console_ports": len(console_ports),
                "console_server_ports": len(console_server_ports),
                "front_ports": len(front_ports),
                "rear_ports": len(rear_ports),
                "device_bays": len(device_bays),
                "inventory_items": len(inventory_items),
                "devices": len(devices),
            },
        }

    async def create_manufacturer(
        self,
        *,
        name: str,
        slug: str,
        description: str,
        username: str,
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise HardwareServiceError(
                "Escribe el nombre del fabricante.",
                400,
            )
        payload: dict[str, Any] = {
            "name": clean_name,
            "slug": slugify(slug or clean_name),
            "changelog_message": (
                f"Fabricante creado desde NetDoc por {username}."
            ),
        }
        if description.strip():
            payload["description"] = description.strip()

        step = ChangeStep(
            step_id="create-manufacturer",
            action="MANUFACTURER_CREATE",
            resource="manufacturer",
            method="POST",
            endpoint="/api/dcim/manufacturers/",
            payload=payload,
            summary=f"Crear fabricante {clean_name}.",
            required_permission="devices.create",
            change_reason="Alta del catálogo de hardware.",
        )
        try:
            validate_step_capability(step)
            result = await self.client.request(
                step.method,
                step.endpoint,
                json_body=step.payload,
            )
        except (DeviceTypeServiceError, ChangePlanError) as exc:
            raise self._translate_error(exc) from exc

        if not isinstance(result, dict):
            raise HardwareServiceError(
                "NetBox creó el fabricante, pero devolvió un formato inesperado.",
                502,
            )
        return result

    async def update_manufacturer(
        self,
        manufacturer_id: int,
        *,
        name: str,
        slug: str,
        description: str,
        username: str,
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise HardwareServiceError(
                "Escribe el nombre del fabricante.",
                400,
            )
        payload = {
            "name": clean_name,
            "slug": slugify(slug or clean_name),
            "description": description.strip(),
            "changelog_message": (
                f"Fabricante actualizado desde NetDoc por {username}."
            ),
        }
        endpoint = f"/api/dcim/manufacturers/{manufacturer_id}/"
        step = ChangeStep(
            step_id="update-manufacturer",
            action="MANUFACTURER_UPDATE",
            resource="manufacturer",
            method="PATCH",
            endpoint=endpoint,
            payload=payload,
            summary=f"Actualizar fabricante {clean_name}.",
            required_permission="devices.create",
            change_reason="Mantenimiento del catálogo de hardware.",
            expected_object_id=manufacturer_id,
        )
        try:
            validate_step_capability(step)
            result = await self.client.request(
                step.method,
                step.endpoint,
                json_body=step.payload,
            )
        except (DeviceTypeServiceError, ChangePlanError) as exc:
            raise self._translate_error(exc) from exc

        if not isinstance(result, dict):
            raise HardwareServiceError(
                "NetBox actualizó el fabricante, pero devolvió un formato inesperado.",
                502,
            )
        return result

    async def update_device_type(
        self,
        device_type_id: int,
        *,
        manufacturer_id: int,
        model: str,
        slug: str,
        part_number: str,
        u_height: float,
        is_full_depth: bool,
        description: str,
        username: str,
    ) -> dict[str, Any]:
        clean_model = model.strip()
        if not clean_model:
            raise HardwareServiceError("Escribe el nombre del modelo.", 400)
        if manufacturer_id < 1:
            raise HardwareServiceError("Selecciona un fabricante.", 400)
        if u_height < 0:
            raise HardwareServiceError("La altura no puede ser negativa.", 400)

        payload: dict[str, Any] = {
            "manufacturer": manufacturer_id,
            "model": clean_model,
            "slug": slugify(slug or clean_model),
            "part_number": part_number.strip(),
            "u_height": u_height,
            "is_full_depth": is_full_depth,
            "description": description.strip(),
            "changelog_message": (
                f"Modelo actualizado desde NetDoc por {username}."
            ),
        }
        endpoint = f"/api/dcim/device-types/{device_type_id}/"
        step = ChangeStep(
            step_id="update-device-type",
            action="DEVICE_TYPE_UPDATE",
            resource="device_type",
            method="PATCH",
            endpoint=endpoint,
            payload=payload,
            summary=f"Actualizar modelo {clean_model}.",
            required_permission="devices.create",
            change_reason="Mantenimiento de la ficha física del modelo.",
            expected_object_id=device_type_id,
        )
        try:
            validate_step_capability(step)
            result = await self.client.request(
                step.method,
                step.endpoint,
                json_body=step.payload,
            )
        except (DeviceTypeServiceError, ChangePlanError) as exc:
            raise self._translate_error(exc) from exc

        if not isinstance(result, dict):
            raise HardwareServiceError(
                "NetBox actualizó el modelo, pero devolvió un formato inesperado.",
                502,
            )
        return result
