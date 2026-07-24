from __future__ import annotations

import asyncio
from typing import Any

from app.services.netbox_client import NetBoxClient, NetBoxError


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


def _device_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    site = _label(item.get("site"))
    role = _label(item.get("role") or item.get("device_role"))
    model = _label(item.get("device_type"))
    return {
        "id": item.get("id"),
        "title": _label(item, "Dispositivo sin nombre"),
        "subtitle": f"{role} · {model} · {site}",
        "url": f"/devices/{item.get('id')}",
        "badge": "Dispositivo",
    }


def _interface_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    device = item.get("device") or {}
    device_id = device.get("id") if isinstance(device, dict) else None
    device_name = _label(device, "Dispositivo")
    interface_name = _label(item, "Interfaz")
    interface_type = _label(item.get("type"), "Sin tipo")
    return {
        "id": item.get("id"),
        "title": f"{device_name} · {interface_name}",
        "subtitle": interface_type,
        "url": f"/devices/{device_id}" if device_id else "/devices",
        "badge": "Interfaz",
    }


def _rack_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    site = _label(item.get("site"))
    location = _label(item.get("location"), "Sin ubicación")
    return {
        "id": item.get("id"),
        "title": _label(item, "Rack sin nombre"),
        "subtitle": f"{site} · {location}",
        "url": f"/racks/{item.get('id')}",
        "badge": "Rack",
    }


def _site_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    region = _label(item.get("region"), "Sin región")
    status = _label(item.get("status"), "Sin estado")
    return {
        "id": item.get("id"),
        "title": _label(item, "Sitio sin nombre"),
        "subtitle": f"{region} · {status}",
        "url": f"/devices?site_id={item.get('id')}",
        "badge": "Sitio",
    }


def _cable_result(item: dict[str, Any]) -> dict[str, str | int | None]:
    label = str(item.get("label") or item.get("display") or "Cable")
    status = _label(item.get("status"), "Sin estado")
    cable_type = _label(item.get("type"), "Sin tipo")
    return {
        "id": item.get("id"),
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
            results = [
                formatter(item)
                for item in payload.get("results", [])
                if isinstance(item, dict)
            ]
            return {
                "code": code,
                "label": label,
                "results": results,
                "count": int(payload.get("count") or len(results)),
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
