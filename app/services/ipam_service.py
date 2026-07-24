from __future__ import annotations

import asyncio
from ipaddress import ip_network
from typing import Any

from app.services.netbox_client import NetBoxClient, NetBoxError


class IPAMServiceError(Exception):
    """Error controlado al preparar la vista de direccionamiento."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


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


def scope_label(prefix: dict[str, Any]) -> str:
    for key in ("scope", "site", "location", "region", "site_group"):
        label = nested_label(prefix.get(key), "")
        if label:
            return label

    scope_type = prefix.get("scope_type")
    scope_id = prefix.get("scope_id")

    if scope_type and scope_id:
        return f"{scope_type} #{scope_id}"

    return "Sin localidad"


def prefix_capacity(prefix: dict[str, Any]) -> int | None:
    value = prefix.get("prefix") or prefix.get("display")

    if not isinstance(value, str) or "/" not in value:
        return None

    try:
        network = ip_network(value, strict=False)
    except ValueError:
        return None

    capacity = network.num_addresses

    if (
        network.version == 4
        and prefix.get("is_pool") is not True
        and network.prefixlen <= 30
    ):
        capacity = max(0, capacity - 2)

    return int(capacity)


def utilization_percentage(value: Any) -> float | None:
    """Normaliza el porcentaje que devuelve NetBox en lista o detalle."""

    if isinstance(value, dict):
        value = (
            value.get("value")
            or value.get("percentage")
            or value.get("utilization")
        )

    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, str):
        value = value.strip().removesuffix("%").strip()
        if not value:
            return None

    try:
        percentage = float(value)
    except (TypeError, ValueError):
        return None

    return round(max(0.0, min(100.0, percentage)), 1)


def format_count(value: int | None) -> str:
    if value is None:
        return "—"

    return f"{value:,}".replace(",", ".")


class IPAMService:
    def __init__(self) -> None:
        self.client = NetBoxClient()

    async def list_roles(self) -> list[dict[str, Any]]:
        return await self.client.get_all(
            "/api/ipam/roles/",
            params={"ordering": "name"},
        )

    async def list_prefixes(
        self,
        *,
        query: str = "",
        status: str = "",
        family: int | None = None,
        role_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"ordering": "prefix"}

        if query.strip():
            params["q"] = query.strip()
        if status.strip():
            params["status"] = status.strip()
        if family in {4, 6}:
            params["family"] = family
        if role_id:
            params["role_id"] = role_id

        return await self.client.get_all(
            "/api/ipam/prefixes/",
            params=params,
            page_limit=200,
            maximum_pages=25,
        )

    async def _load_utilization(
        self,
        prefix: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> tuple[float | None, str | None]:
        for key in ("utilization", "utilization_percentage"):
            percentage = utilization_percentage(prefix.get(key))
            if percentage is not None:
                return percentage, None

        prefix_id = prefix.get("id")
        if not isinstance(prefix_id, int):
            return None, "NetBox no devolvió un ID válido para el prefijo."

        try:
            async with semaphore:
                detail = await self.client.get(
                    f"/api/ipam/prefixes/{prefix_id}/"
                )
        except NetBoxError as exc:
            return None, exc.message

        for key in ("utilization", "utilization_percentage"):
            percentage = utilization_percentage(detail.get(key))
            if percentage is not None:
                return percentage, None

        return (
            None,
            "La API de NetBox no incluyó el porcentaje de utilización.",
        )

    async def _prepare_pool(
        self,
        prefix: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        capacity = prefix_capacity(prefix)
        availability_error: str | None = None

        if prefix.get("mark_utilized") is True:
            utilization = 100.0
        else:
            utilization, availability_error = await self._load_utilization(
                prefix,
                semaphore,
            )

        used: int | None = None
        available: int | None = None

        if capacity is not None and utilization is not None:
            used = min(
                capacity,
                max(0, round(capacity * utilization / 100)),
            )
            available = max(0, capacity - used)

        status_data = prefix.get("status") or {}
        role_data = prefix.get("role") or {}
        vrf_data = prefix.get("vrf") or {}

        return {
            **prefix,
            "_scope_label": scope_label(prefix),
            "_status_label": nested_label(status_data, "Sin estado"),
            "_role_label": nested_label(role_data, "Sin rol"),
            "_vrf_label": nested_label(vrf_data, "Global"),
            "_capacity": capacity,
            "_capacity_label": format_count(capacity),
            "_available": available,
            "_available_label": format_count(available),
            "_used": used,
            "_used_label": format_count(used),
            "_utilization": utilization,
            "_availability_error": availability_error,
            "_availability_estimated": (
                capacity is not None and utilization is not None
            ),
            "_health": (
                "unknown"
                if utilization is None
                else "full"
                if utilization >= 100
                else "critical"
                if utilization >= 80
                else "warning"
                if utilization >= 60
                else "healthy"
            ),
        }

    async def overview(
        self,
        *,
        query: str = "",
        status: str = "",
        family: int | None = None,
        role_id: int | None = None,
    ) -> dict[str, Any]:
        try:
            prefixes, roles = await asyncio.gather(
                self.list_prefixes(
                    query=query,
                    status=status,
                    family=family,
                    role_id=role_id,
                ),
                self.list_roles(),
            )
        except NetBoxError as exc:
            raise IPAMServiceError(exc.message) from exc

        pools = [
            prefix
            for prefix in prefixes
            if prefix.get("is_pool") is True
        ]
        semaphore = asyncio.Semaphore(8)
        prepared_pools = await asyncio.gather(
            *(
                self._prepare_pool(prefix, semaphore)
                for prefix in pools
            )
        )

        full_pools = sum(
            1
            for pool in prepared_pools
            if pool.get("_health") == "full"
        )
        critical_pools = sum(
            1
            for pool in prepared_pools
            if pool.get("_health") in {"critical", "full"}
        )
        pools_with_capacity = sum(
            1
            for pool in prepared_pools
            if pool.get("_utilization") is not None
        )

        scopes = sorted(
            {
                str(pool.get("_scope_label"))
                for pool in prepared_pools
                if pool.get("_scope_label")
            }
        )

        prefix_rows = []
        for prefix in prefixes:
            status_data = prefix.get("status") or {}
            role_data = prefix.get("role") or {}
            vrf_data = prefix.get("vrf") or {}
            prefix_rows.append({
                **prefix,
                "_scope_label": scope_label(prefix),
                "_status_label": nested_label(status_data, "Sin estado"),
                "_role_label": nested_label(role_data, "Sin rol"),
                "_vrf_label": nested_label(vrf_data, "Global"),
            })

        return {
            "prefixes": prefix_rows,
            "pools": prepared_pools,
            "roles": roles,
            "summary": {
                "prefixes": len(prefixes),
                "pools": len(prepared_pools),
                "full_pools": full_pools,
                "critical_pools": critical_pools,
                "pools_with_capacity": pools_with_capacity,
                "scopes": len(scopes),
            },
        }
