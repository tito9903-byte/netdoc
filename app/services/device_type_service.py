from __future__ import annotations

import re
from time import monotonic
import unicodedata
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.netbox_client import get_shared_netbox_client


class DeviceTypeServiceError(Exception):
    """Error controlado al administrar modelos y plantillas."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def nested_label(value: Any, fallback: str = "—") -> str:
    if isinstance(value, dict):
        return str(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("value")
            or fallback
        )

    if value not in (None, ""):
        return str(value)

    return fallback


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-")
    return slug.lower()


def build_interface_names(
    pattern: str,
    *,
    start: int,
    count: int,
) -> list[str]:
    clean_pattern = pattern.strip()

    if not clean_pattern:
        raise DeviceTypeServiceError(
            "Escribe un patrón de nombre para las interfaces."
        )

    if "{n" not in clean_pattern:
        raise DeviceTypeServiceError(
            "El patrón debe incluir {n}; por ejemplo, ge-0/0/{n}."
        )

    if start < 0:
        raise DeviceTypeServiceError(
            "El número inicial no puede ser negativo."
        )

    if count < 1 or count > 256:
        raise DeviceTypeServiceError(
            "La cantidad debe estar entre 1 y 256 interfaces."
        )

    names: list[str] = []

    for number in range(start, start + count):
        try:
            name = clean_pattern.format(n=number)
        except (KeyError, ValueError, IndexError) as exc:
            raise DeviceTypeServiceError(
                "El patrón no es válido. Usa {n} o formatos como {n:02}."
            ) from exc

        name = name.strip()

        if not name:
            raise DeviceTypeServiceError(
                "El patrón produjo un nombre de interfaz vacío."
            )

        names.append(name)

    if len(set(names)) != len(names):
        raise DeviceTypeServiceError(
            "El patrón produjo nombres de interfaz duplicados."
        )

    return names


class DeviceTypeService:
    _get_all_cache: dict[
        tuple[str, tuple[tuple[str, str], ...], int, int],
        tuple[float, list[dict[str, Any]]],
    ] = {}
    _get_all_cache_seconds = 30.0
    _get_all_cache_limit = 128
    _interface_choices_cache: tuple[
        float,
        list[dict[str, str]],
    ] | None = None
    _interface_choices_cache_seconds = 300.0

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.netbox_url.rstrip("/")

    @classmethod
    def clear_read_caches(cls) -> None:
        cls._get_all_cache.clear()
        cls._interface_choices_cache = None

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
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

            messages: list[str] = []
            for field, value in payload.items():
                if isinstance(value, list):
                    rendered = ", ".join(str(item) for item in value)
                else:
                    rendered = str(value)
                messages.append(f"{field}: {rendered}")

            if messages:
                return " | ".join(messages)

        if isinstance(payload, list):
            return "NetBox rechazó uno o más elementos del lote."

        return f"NetBox respondió con HTTP {response.status_code}."

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> Any:
        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value not in (None, "")
        }

        try:
            client = await get_shared_netbox_client()
            response = await client.request(
                method=method,
                url=endpoint.lstrip("/"),
                params=clean_params,
                json=json_body,
                headers=self._headers(),
            )
        except httpx.ConnectError as exc:
            raise DeviceTypeServiceError(
                f"No fue posible conectar con NetBox en {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise DeviceTypeServiceError(
                "NetBox no respondió dentro del tiempo configurado."
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
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            type(self).clear_read_caches()

        return payload

    @staticmethod
    def _cache_key(
        endpoint: str,
        params: dict[str, Any] | None,
        page_limit: int,
        maximum_pages: int,
    ) -> tuple[str, tuple[tuple[str, str], ...], int, int]:
        normalized = tuple(sorted(
            (str(key), repr(value))
            for key, value in (params or {}).items()
            if value not in (None, "")
        ))
        return endpoint, normalized, page_limit, maximum_pages

    async def get_all(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        page_limit: int = 200,
        maximum_pages: int = 50,
    ) -> list[dict[str, Any]]:
        key = self._cache_key(
            endpoint,
            params,
            page_limit,
            maximum_pages,
        )
        now = monotonic()
        cached = type(self)._get_all_cache.get(key)
        if cached is not None and cached[0] > now:
            return [dict(item) for item in cached[1]]

        results: list[dict[str, Any]] = []
        offset = 0

        for _ in range(maximum_pages):
            payload = await self.request(
                "GET",
                endpoint,
                params={
                    **(params or {}),
                    "limit": page_limit,
                    "offset": offset,
                },
            )

            if not isinstance(payload, dict):
                raise DeviceTypeServiceError(
                    "NetBox devolvió un listado inesperado."
                )

            page_results = payload.get("results")
            if not isinstance(page_results, list):
                raise DeviceTypeServiceError(
                    "NetBox no devolvió un listado válido."
                )

            results.extend(page_results)

            if not payload.get("next") or not page_results:
                break

            offset += page_limit

        cache = type(self)._get_all_cache
        expired = [cache_key for cache_key, value in cache.items() if value[0] <= now]
        for cache_key in expired:
            cache.pop(cache_key, None)
        if len(cache) >= self._get_all_cache_limit:
            cache.clear()
        cache[key] = (
            monotonic() + self._get_all_cache_seconds,
            [dict(item) for item in results],
        )
        return results

    async def list_manufacturers(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/manufacturers/",
            params={"ordering": "name"},
        )

    async def list_device_types(
        self,
        *,
        query: str = "",
        manufacturer_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"ordering": "manufacturer,model"}
        if query.strip():
            params["q"] = query.strip()
        if manufacturer_id:
            params["manufacturer_id"] = manufacturer_id

        rows = await self.get_all(
            "/api/dcim/device-types/",
            params=params,
        )

        prepared: list[dict[str, Any]] = []
        for item in rows:
            manufacturer = item.get("manufacturer") or {}
            prepared.append({
                **item,
                "_manufacturer_label": nested_label(
                    manufacturer,
                    "Sin fabricante",
                ),
                "_model_label": str(
                    item.get("model")
                    or item.get("display")
                    or "Sin modelo"
                ),
                "_interface_count": int(
                    item.get("interface_template_count") or 0
                ),
                "_module_bay_count": int(
                    item.get("module_bay_template_count") or 0
                ),
                "_power_port_count": int(
                    item.get("power_port_template_count") or 0
                ),
            })

        # Importación local para evitar un ciclo durante la definición del error
        # compartido por ambos servicios.
        from app.services.device_image_service import DeviceImageService

        return DeviceImageService().decorate_device_types(prepared)

    async def get_device_type(self, device_type_id: int) -> dict[str, Any]:
        payload = await self.request(
            "GET",
            f"/api/dcim/device-types/{device_type_id}/",
        )
        if not isinstance(payload, dict):
            raise DeviceTypeServiceError(
                "NetBox devolvió un modelo inesperado."
            )

        from app.services.device_image_service import DeviceImageService

        return DeviceImageService().decorate_device_type(payload)

    async def list_interface_templates(
        self,
        device_type_id: int,
    ) -> list[dict[str, Any]]:
        rows = await self.get_all(
            "/api/dcim/interface-templates/",
            params={
                "device_type_id": device_type_id,
                "ordering": "name",
            },
        )

        for row in rows:
            row["_type_label"] = nested_label(
                row.get("type"),
                "Sin tipo",
            )

        return rows

    async def interface_type_choices(self) -> list[dict[str, str]]:
        cached = type(self)._interface_choices_cache
        now = monotonic()
        if cached is not None and cached[0] > now:
            return [dict(item) for item in cached[1]]

        try:
            payload = await self.request(
                "OPTIONS",
                "/api/dcim/interface-templates/",
            )
            fields = payload.get("actions", {}).get("POST", {})
            raw_choices = fields.get("type", {}).get("choices", [])
            choices: list[dict[str, str]] = []

            for item in raw_choices:
                value = item.get("value")
                label = (
                    item.get("display_name")
                    or item.get("label")
                    or value
                )
                if value:
                    choices.append({
                        "value": str(value),
                        "label": str(label),
                    })

            if choices:
                type(self)._interface_choices_cache = (
                    monotonic() + self._interface_choices_cache_seconds,
                    [dict(item) for item in choices],
                )
                return choices
        except DeviceTypeServiceError:
            pass

        fallback = [
            {"value": "1000base-t", "label": "1GBASE-T"},
            {"value": "10gbase-t", "label": "10GBASE-T"},
            {"value": "1000base-x-sfp", "label": "SFP (1G)"},
            {"value": "10gbase-x-sfpp", "label": "SFP+ (10G)"},
            {"value": "25gbase-x-sfp28", "label": "SFP28 (25G)"},
            {"value": "40gbase-x-qsfpp", "label": "QSFP+ (40G)"},
            {"value": "100gbase-x-qsfp28", "label": "QSFP28 (100G)"},
            {"value": "virtual", "label": "Virtual"},
        ]
        type(self)._interface_choices_cache = (
            monotonic() + self._interface_choices_cache_seconds,
            [dict(item) for item in fallback],
        )
        return fallback

    async def create_device_type(
        self,
        *,
        manufacturer_id: int,
        model: str,
        slug: str,
        part_number: str,
        u_height: float,
        is_full_depth: bool,
        description: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "manufacturer": manufacturer_id,
            "model": model.strip(),
            "slug": slugify(slug or model),
            "u_height": u_height,
            "is_full_depth": is_full_depth,
        }

        if part_number.strip():
            payload["part_number"] = part_number.strip()
        if description.strip():
            payload["description"] = description.strip()

        result = await self.request(
            "POST",
            "/api/dcim/device-types/",
            json_body=payload,
        )

        if not isinstance(result, dict):
            raise DeviceTypeServiceError(
                "NetBox creó el modelo, pero devolvió un formato inesperado."
            )

        return result

    async def create_interface_templates(
        self,
        *,
        device_type_id: int,
        names: list[str],
        interface_type: str,
        label_pattern: str,
        description: str,
        mgmt_only: bool,
    ) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []

        for index, name in enumerate(names):
            label = ""
            if label_pattern.strip():
                try:
                    label = label_pattern.strip().format(
                        n=index + 1,
                        name=name,
                    )
                except (KeyError, ValueError, IndexError) as exc:
                    raise DeviceTypeServiceError(
                        "El patrón de etiqueta no es válido."
                    ) from exc

            item: dict[str, Any] = {
                "device_type": device_type_id,
                "name": name,
                "type": interface_type,
                "mgmt_only": mgmt_only,
            }
            if label:
                item["label"] = label
            if description.strip():
                item["description"] = description.strip()
            payload.append(item)

        result = await self.request(
            "POST",
            "/api/dcim/interface-templates/",
            json_body=payload,
        )

        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]

        if isinstance(result, dict):
            return [result]

        raise DeviceTypeServiceError(
            "NetBox creó las plantillas, pero devolvió un formato inesperado."
        )
