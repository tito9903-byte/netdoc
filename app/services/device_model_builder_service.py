from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.device_type_service import (
    DeviceTypeService,
    DeviceTypeServiceError,
    build_interface_names,
    nested_label,
    slugify,
)


@dataclass(frozen=True)
class ComponentDefinition:
    key: str
    label: str
    singular: str
    endpoint: str
    icon: str
    description: str


COMPONENT_DEFINITIONS: dict[str, ComponentDefinition] = {
    "interface": ComponentDefinition(
        "interface",
        "Interfaces de red",
        "interfaz",
        "/api/dcim/interface-templates/",
        "⇆",
        "Interfaces físicas, virtuales, LAG, SFP, QSFP y demás tipos publicados por NetBox.",
    ),
    "console_port": ComponentDefinition(
        "console_port",
        "Puertos de consola",
        "puerto de consola",
        "/api/dcim/console-port-templates/",
        "⌁",
        "Puertos locales para administración fuera de banda.",
    ),
    "console_server_port": ComponentDefinition(
        "console_server_port",
        "Puertos de servidor de consola",
        "puerto de servidor de consola",
        "/api/dcim/console-server-port-templates/",
        "⌘",
        "Puertos que concentran conexiones de consola de otros equipos.",
    ),
    "power_port": ComponentDefinition(
        "power_port",
        "Entradas de energía",
        "entrada de energía",
        "/api/dcim/power-port-templates/",
        "ϟ",
        "Entradas eléctricas que heredará cada dispositivo del modelo.",
    ),
    "power_outlet": ComponentDefinition(
        "power_outlet",
        "Salidas de energía",
        "salida de energía",
        "/api/dcim/power-outlet-templates/",
        "⌁",
        "Salidas eléctricas, normalmente asociadas a una entrada de energía.",
    ),
    "front_port": ComponentDefinition(
        "front_port",
        "Puertos frontales",
        "puerto frontal",
        "/api/dcim/front-port-templates/",
        "▤",
        "Conectores visibles en la cara frontal de paneles y distribuidores.",
    ),
    "rear_port": ComponentDefinition(
        "rear_port",
        "Puertos traseros",
        "puerto trasero",
        "/api/dcim/rear-port-templates/",
        "▥",
        "Terminaciones posteriores utilizadas por paneles de parcheo.",
    ),
    "module_bay": ComponentDefinition(
        "module_bay",
        "Bahías de módulos",
        "bahía de módulo",
        "/api/dcim/module-bay-templates/",
        "▦",
        "Espacios para tarjetas, módulos, fuentes y componentes intercambiables.",
    ),
    "device_bay": ComponentDefinition(
        "device_bay",
        "Bahías de dispositivos",
        "bahía de dispositivo",
        "/api/dcim/device-bay-templates/",
        "□",
        "Espacios destinados a alojar dispositivos secundarios.",
    ),
    "inventory_item": ComponentDefinition(
        "inventory_item",
        "Elementos de inventario",
        "elemento de inventario",
        "/api/dcim/inventory-item-templates/",
        "≣",
        "Partes internas que se documentarán automáticamente en cada equipo.",
    ),
}


FIELD_LABELS = {
    "manufacturer": "Fabricante",
    "model": "Modelo",
    "slug": "Slug",
    "part_number": "Part number",
    "u_height": "Altura U",
    "is_full_depth": "Profundidad completa",
    "subdevice_role": "Rol como subdispositivo",
    "airflow": "Flujo de aire",
    "weight": "Peso",
    "weight_unit": "Unidad de peso",
    "description": "Descripción",
    "comments": "Comentarios",
    "name": "Nombre",
    "label": "Etiqueta",
    "type": "Tipo",
    "mgmt_only": "Solo administración",
    "description": "Descripción",
    "rear_port": "Puerto trasero asociado",
    "rear_port_position": "Posición del puerto trasero",
    "power_port": "Entrada de energía asociada",
    "feed_leg": "Fase eléctrica",
    "maximum_draw": "Consumo máximo",
    "allocated_draw": "Consumo asignado",
    "poe_mode": "Modo PoE",
    "poe_type": "Tipo PoE",
    "rf_role": "Rol RF",
    "parent": "Elemento padre",
    "component_type": "Tipo de componente",
    "component_id": "Componente asociado",
}


IGNORED_FIELDS = {
    "id",
    "url",
    "display_url",
    "display",
    "device_type",
    "created",
    "last_updated",
}


MODEL_CORE_FIELDS = {
    "manufacturer",
    "model",
    "slug",
    "part_number",
    "u_height",
    "is_full_depth",
    "description",
}


RELATED_FIELD_ENDPOINTS = {
    "rear_port": "/api/dcim/rear-port-templates/",
    "power_port": "/api/dcim/power-port-templates/",
    "parent": "/api/dcim/inventory-item-templates/",
    "module_bay": "/api/dcim/module-bay-templates/",
    "device_bay": "/api/dcim/device-bay-templates/",
}


class DeviceModelBuilderService:
    """Adapta los formularios de NetBox al flujo guiado de documentación."""

    def __init__(self) -> None:
        self.client = DeviceTypeService()

    @staticmethod
    def definitions() -> list[dict[str, str]]:
        return [
            {
                "key": item.key,
                "label": item.label,
                "singular": item.singular,
                "icon": item.icon,
                "description": item.description,
            }
            for item in COMPONENT_DEFINITIONS.values()
        ]

    @staticmethod
    def definition(kind: str) -> ComponentDefinition:
        definition = COMPONENT_DEFINITIONS.get(kind)
        if definition is None:
            raise DeviceTypeServiceError(
                "El tipo de componente solicitado no está permitido.",
                400,
            )
        return definition

    async def _post_fields(self, endpoint: str) -> dict[str, dict[str, Any]]:
        payload = await self.client.request("OPTIONS", endpoint)
        if not isinstance(payload, dict):
            raise DeviceTypeServiceError(
                "NetBox no devolvió las capacidades del formulario.",
                502,
            )
        actions = payload.get("actions") or {}
        fields = actions.get("POST") or {}
        if not isinstance(fields, dict):
            raise DeviceTypeServiceError(
                "NetBox no publicó los campos disponibles para crear este registro.",
                502,
            )
        return {
            str(name): dict(metadata)
            for name, metadata in fields.items()
            if isinstance(metadata, dict)
        }

    @staticmethod
    def _choice_rows(raw_choices: Any) -> list[dict[str, str]]:
        if not isinstance(raw_choices, list):
            return []
        rows: list[dict[str, str]] = []
        for item in raw_choices:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if value in (None, ""):
                continue
            label = (
                item.get("display_name")
                or item.get("label")
                or item.get("display")
                or value
            )
            rows.append({"value": str(value), "label": str(label)})
        return rows

    async def _related_choices(
        self,
        field_name: str,
        device_type_id: int | None,
    ) -> list[dict[str, str]]:
        endpoint = RELATED_FIELD_ENDPOINTS.get(field_name)
        if endpoint is None or not device_type_id:
            return []
        rows = await self.client.get_all(
            endpoint,
            params={
                "device_type_id": device_type_id,
                "ordering": "name",
            },
        )
        choices: list[dict[str, str]] = []
        for row in rows:
            raw_id = row.get("id")
            if not isinstance(raw_id, int):
                continue
            choices.append({
                "value": str(raw_id),
                "label": str(
                    row.get("display")
                    or row.get("name")
                    or f"ID {raw_id}"
                ),
            })
        return choices

    async def normalized_fields(
        self,
        endpoint: str,
        *,
        device_type_id: int | None = None,
        exclude: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        raw_fields = await self._post_fields(endpoint)
        fields: list[dict[str, Any]] = []
        excluded = IGNORED_FIELDS | (exclude or set())

        for name, metadata in raw_fields.items():
            if name in excluded or metadata.get("read_only") is True:
                continue

            field_type = str(metadata.get("type") or "string").lower()
            choices = self._choice_rows(metadata.get("choices"))
            if not choices:
                choices = await self._related_choices(name, device_type_id)

            input_type = "text"
            if choices:
                input_type = "select"
            elif field_type in {"boolean", "bool"}:
                input_type = "checkbox"
            elif field_type in {"integer", "int"}:
                input_type = "number"
            elif field_type in {"float", "decimal"}:
                input_type = "decimal"
            elif name in {"description", "comments"}:
                input_type = "textarea"

            fields.append({
                "name": name,
                "label": FIELD_LABELS.get(name) or str(
                    metadata.get("label")
                    or metadata.get("display_name")
                    or name.replace("_", " ").title()
                ),
                "required": bool(metadata.get("required")),
                "type": field_type,
                "input_type": input_type,
                "choices": choices,
                "help_text": str(metadata.get("help_text") or ""),
                "default": metadata.get("default"),
                "allow_null": bool(metadata.get("allow_null", True)),
                "multiple": bool(metadata.get("many") or metadata.get("multiple")),
            })

        return fields

    async def model_advanced_fields(self) -> list[dict[str, Any]]:
        return await self.normalized_fields(
            "/api/dcim/device-types/",
            exclude=MODEL_CORE_FIELDS,
        )

    async def component_fields(
        self,
        kind: str,
        *,
        device_type_id: int,
    ) -> list[dict[str, Any]]:
        definition = self.definition(kind)
        return await self.normalized_fields(
            definition.endpoint,
            device_type_id=device_type_id,
            exclude={"name"},
        )

    @staticmethod
    def _getlist(form: Mapping[str, Any], name: str) -> list[Any]:
        getlist = getattr(form, "getlist", None)
        if callable(getlist):
            return list(getlist(name))
        value = form.get(name)
        if isinstance(value, list):
            return value
        return [] if value in (None, "") else [value]

    @classmethod
    def _coerce_value(
        cls,
        form: Mapping[str, Any],
        field: dict[str, Any],
    ) -> Any:
        name = str(field["name"])
        input_type = str(field.get("input_type") or "text")
        multiple = bool(field.get("multiple"))

        if input_type == "checkbox":
            return name in form and str(form.get(name)).lower() not in {
                "",
                "0",
                "false",
                "off",
                "none",
            }

        if multiple:
            values = [str(value).strip() for value in cls._getlist(form, name)]
            return [value for value in values if value]

        raw = form.get(name)
        if raw in (None, ""):
            return None
        value = str(raw).strip()
        if input_type == "number":
            return int(value)
        if input_type == "decimal":
            return float(value)

        if field.get("choices"):
            for choice in field["choices"]:
                if str(choice.get("value")) == value:
                    if value.isdigit() and name in RELATED_FIELD_ENDPOINTS:
                        return int(value)
                    return value

        if name in RELATED_FIELD_ENDPOINTS and value.isdigit():
            return int(value)
        return value

    async def extra_model_payload(
        self,
        form: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in await self.model_advanced_fields():
            value = self._coerce_value(form, field)
            if value is None or value == []:
                continue
            payload[str(field["name"])] = value
        return payload

    async def create_device_type(
        self,
        form: Mapping[str, Any],
    ) -> dict[str, Any]:
        manufacturer = str(form.get("manufacturer_id") or "").strip()
        model = str(form.get("model") or "").strip()
        if not manufacturer.isdigit() or int(manufacturer) < 1:
            raise DeviceTypeServiceError("Selecciona un fabricante.", 400)
        if not model:
            raise DeviceTypeServiceError("Escribe el nombre del modelo.", 400)

        try:
            u_height = float(str(form.get("u_height") or "1"))
        except ValueError as exc:
            raise DeviceTypeServiceError("La altura U no es válida.", 400) from exc
        if u_height < 0:
            raise DeviceTypeServiceError("La altura U no puede ser negativa.", 400)

        payload: dict[str, Any] = {
            "manufacturer": int(manufacturer),
            "model": model,
            "slug": slugify(str(form.get("slug") or model)),
            "u_height": u_height,
            "is_full_depth": str(form.get("full_depth") or "").lower()
            in {"1", "true", "on", "yes"},
        }
        for name in ("part_number", "description"):
            value = str(form.get(name) or "").strip()
            if value:
                payload[name] = value
        payload.update(await self.extra_model_payload(form))

        result = await self.client.request(
            "POST",
            "/api/dcim/device-types/",
            json_body=payload,
        )
        if not isinstance(result, dict):
            raise DeviceTypeServiceError(
                "NetBox creó el modelo, pero devolvió un formato inesperado.",
                502,
            )
        return result

    async def list_components(
        self,
        kind: str,
        *,
        device_type_id: int,
    ) -> list[dict[str, Any]]:
        definition = self.definition(kind)
        rows = await self.client.get_all(
            definition.endpoint,
            params={
                "device_type_id": device_type_id,
                "ordering": "name",
            },
        )
        for row in rows:
            row["_type_label"] = nested_label(row.get("type"), "—")
        return rows

    async def create_components(
        self,
        kind: str,
        *,
        device_type_id: int,
        form: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        definition = self.definition(kind)
        pattern = str(form.get("name_pattern") or "").strip()
        if not pattern:
            raise DeviceTypeServiceError("Escribe el nombre o patrón.", 400)
        try:
            start = int(str(form.get("start") or "1"))
            count = int(str(form.get("count") or "1"))
        except ValueError as exc:
            raise DeviceTypeServiceError(
                "El inicio y la cantidad deben ser números enteros.",
                400,
            ) from exc

        if count == 1 and "{n" not in pattern:
            names = [pattern]
        else:
            names = build_interface_names(pattern, start=start, count=count)

        fields = await self.component_fields(
            kind,
            device_type_id=device_type_id,
        )
        common: dict[str, Any] = {}
        for field in fields:
            value = self._coerce_value(form, field)
            if value is None or value == []:
                if field.get("required") and field.get("input_type") != "checkbox":
                    raise DeviceTypeServiceError(
                        f"Completa el campo {field.get('label')}.",
                        400,
                    )
                continue
            common[str(field["name"])] = value

        payload: list[dict[str, Any]] = []
        for index, name in enumerate(names, start=start):
            item = {
                "device_type": device_type_id,
                "name": name,
                **common,
            }
            for field_name in ("label", "description"):
                raw_value = item.get(field_name)
                if isinstance(raw_value, str):
                    try:
                        item[field_name] = raw_value.format(n=index, name=name)
                    except (KeyError, ValueError, IndexError) as exc:
                        raise DeviceTypeServiceError(
                            f"El patrón del campo {FIELD_LABELS.get(field_name, field_name)} no es válido.",
                            400,
                        ) from exc
            payload.append(item)

        result = await self.client.request(
            "POST",
            definition.endpoint,
            json_body=payload,
        )
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            return [result]
        raise DeviceTypeServiceError(
            "NetBox creó los componentes, pero devolvió un formato inesperado.",
            502,
        )
