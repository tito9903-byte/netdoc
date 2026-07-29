from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.netbox_client import NetBoxClient, NetBoxError


logger = logging.getLogger(__name__)


def _label(value: Any, fallback: str = "—") -> str:
    if isinstance(value, dict):
        return str(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("model")
            or fallback
        )

    if value not in (None, ""):
        return str(value)

    return fallback


def _safe_id(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


def _device_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    device_id = _safe_id(item.get("id"))
    site = _label(item.get("site"))
    role = _label(item.get("role") or item.get("device_role"))
    model = _label(item.get("device_type"))
    return {
        "id": device_id,
        "title": _label(item, "Dispositivo sin nombre"),
        "subtitle": f"{role} · {model} · {site}",
        "url": f"/devices/{device_id}" if device_id else "/devices",
        "badge": "Dispositivo",
    }


def _interface_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    device = item.get("device") or {}
    device_id = (
        _safe_id(device.get("id"))
        if isinstance(device, dict)
        else None
    )
    device_name = _label(device, "Dispositivo")
    interface_name = _label(item, "Interfaz")
    interface_type = _label(item.get("type"), "Sin tipo")
    return {
        "id": _safe_id(item.get("id")),
        "title": f"{device_name} · {interface_name}",
        "subtitle": interface_type,
        "url": f"/devices/{device_id}" if device_id else "/devices",
        "badge": "Interfaz",
    }


def _rack_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    rack_id = _safe_id(item.get("id"))
    site = _label(item.get("site"))
    location = _label(item.get("location"), "Sin ubicación")
    return {
        "id": rack_id,
        "title": _label(item, "Rack sin nombre"),
        "subtitle": f"{site} · {location}",
        "url": f"/racks/{rack_id}" if rack_id else "/racks",
        "badge": "Rack",
    }


def _site_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    site_id = _safe_id(item.get("id"))
    region = _label(item.get("region"), "Sin región")
    status = _label(item.get("status"), "Sin estado")
    return {
        "id": site_id,
        "title": _label(item, "Sitio sin nombre"),
        "subtitle": f"{region} · {status}",
        "url": f"/devices?site_id={site_id}" if site_id else "/devices",
        "badge": "Sitio",
    }


def _cable_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    label = str(item.get("label") or item.get("display") or "Cable")
    status = _label(item.get("status"), "Sin estado")
    cable_type = _label(item.get("type"), "Sin tipo")
    return {
        "id": _safe_id(item.get("id")),
        "title": label,
        "subtitle": f"{cable_type} · {status}",
        "url": "/connections",
        "badge": "Cable",
    }


SEARCH_TARGETS = (
    (
        "devices",
        "Dispositivos",
        "/api/dcim/devices/",
        "name",
        _device_result,
    ),
    (
        "interfaces",
        "Interfaces",
        "/api/dcim/interfaces/",
        "device,name",
        _interface_result,
    ),
    (
        "racks",
        "Racks",
        "/api/dcim/racks/",
        "name",
        _rack_result,
    ),
    (
        "sites",
        "Sitios",
        "/api/dcim/sites/",
        "name",
        _site_result,
    ),
    (
        "cables",
        "Cables",
        "/api/dcim/cables/",
        "-last_updated",
        _cable_result,
    ),
)


async def global_search(
    query: str,
    *,
    limit_per_section: int = 8,
    client: NetBoxClient | None = None,
) -> dict[str, object]:
    clean_query = query.strip()

    if len(clean_query) < 2:
        return {
            "query": clean_query,
            "sections": [],
            "total": 0,
            "searched": False,
        }

    search_client = client or NetBoxClient()
    safe_limit = min(max(limit_per_section, 1), 25)

    async def load_section(target):
        code, label, endpoint, ordering, formatter = target

        try:
            payload = await search_client.get_list(
                endpoint,
                params={
                    "q": clean_query,
                    "limit": safe_limit,
                    "ordering": ordering,
                },
            )
            if not isinstance(payload, dict):
                raise TypeError(
                    f"NetBox devolvió {type(payload).__name__} para {endpoint}"
                )

            raw_results = payload.get("results", [])
            if not isinstance(raw_results, list):
                raise TypeError(
                    f"NetBox devolvió resultados inválidos para {endpoint}"
                )

            results = [
                formatter(item)
                for item in raw_results
                if isinstance(item, dict)
            ]
            raw_count = payload.get("count")
            try:
                count = int(raw_count if raw_count is not None else len(results))
            except (TypeError, ValueError):
                count = len(results)

            return {
                "code": code,
                "label": label,
                "results": results,
                "count": count,
                "error": None,
            }
        except NetBoxError as exc:
            return {
                "code": code,
                "label": label,
                "results": [],
                "count": 0,
                "error": exc.message,
            }
        except Exception:
            logger.exception(
                "La búsqueda global falló en la sección %s (%s)",
                code,
                endpoint,
            )
            return {
                "code": code,
                "label": label,
                "results": [],
                "count": 0,
                "error": (
                    f"No fue posible procesar la sección {label.lower()}. "
                    "Las demás categorías continúan disponibles."
                ),
            }

    sections = list(
        await asyncio.gather(
            *(load_section(target) for target in SEARCH_TARGETS)
        )
    )
    total = sum(len(section["results"]) for section in sections)

    return {
        "query": clean_query,
        "sections": sections,
        "total": total,
        "searched": True,
    }
