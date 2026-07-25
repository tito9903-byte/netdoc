from __future__ import annotations

import asyncio
from collections import defaultdict
from ipaddress import ip_address, ip_interface, ip_network
from time import monotonic
from typing import Any

from app.services.netbox_client import NetBoxClient, NetBoxError


Interval = tuple[int, int]
InventoryKey = tuple[int, int | None]


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


def choice_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(
            value.get("value")
            or value.get("slug")
            or value.get("name")
            or ""
        )

    return str(value or "")


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


def vrf_identifier(value: dict[str, Any]) -> int | None:
    vrf = value.get("vrf")

    if isinstance(vrf, dict) and isinstance(vrf.get("id"), int):
        return int(vrf["id"])

    vrf_id = value.get("vrf_id")
    return int(vrf_id) if isinstance(vrf_id, int) else None


def prefix_network(prefix: dict[str, Any]):
    value = prefix.get("prefix") or prefix.get("display")

    if not isinstance(value, str) or "/" not in value:
        return None

    try:
        return ip_network(value, strict=False)
    except ValueError:
        return None


def prefix_capacity(prefix: dict[str, Any]) -> int | None:
    network = prefix_network(prefix)

    if network is None:
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
    """Normaliza un porcentaje numérico cuando está disponible."""

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


def host_integer(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        host = (
            ip_interface(value.strip()).ip
            if "/" in value
            else ip_address(value.strip())
        )
    except ValueError:
        return None

    return host.version, int(host)


def range_interval(value: dict[str, Any]) -> tuple[int, int, int] | None:
    start = host_integer(value.get("start_address"))
    end = host_integer(value.get("end_address"))

    if start is None or end is None or start[0] != end[0]:
        return None

    first = min(start[1], end[1])
    last = max(start[1], end[1])
    return start[0], first, last


def merged_interval_size(intervals: list[Interval]) -> int:
    if not intervals:
        return 0

    ordered = sorted(intervals)
    current_start, current_end = ordered[0]
    total = 0

    for start, end in ordered[1:]:
        if start <= current_end + 1:
            current_end = max(current_end, end)
            continue

        total += current_end - current_start + 1
        current_start, current_end = start, end

    total += current_end - current_start + 1
    return total


def build_occupancy_indexes(
    *,
    ip_addresses: list[dict[str, Any]],
    ip_ranges: list[dict[str, Any]],
    prefixes: list[dict[str, Any]],
) -> tuple[
    dict[InventoryKey, list[Interval]],
    dict[InventoryKey, list[Interval]],
    dict[InventoryKey, list[tuple[int | None, Interval]]],
]:
    address_intervals: dict[InventoryKey, list[Interval]] = defaultdict(list)
    reserved_ranges: dict[InventoryKey, list[Interval]] = defaultdict(list)
    prefix_intervals: dict[
        InventoryKey,
        list[tuple[int | None, Interval]],
    ] = defaultdict(list)

    for item in ip_addresses:
        parsed = host_integer(item.get("address"))
        if parsed is None:
            continue

        family, host = parsed
        key = (family, vrf_identifier(item))
        address_intervals[key].append((host, host))

    for item in ip_ranges:
        if not (
            item.get("mark_populated") is True
            or item.get("mark_utilized") is True
        ):
            continue

        parsed = range_interval(item)
        if parsed is None:
            continue

        family, start, end = parsed
        key = (family, vrf_identifier(item))
        reserved_ranges[key].append((start, end))

    for item in prefixes:
        network = prefix_network(item)
        if network is None:
            continue

        key = (network.version, vrf_identifier(item))
        prefix_id = item.get("id")
        prefix_intervals[key].append((
            int(prefix_id) if isinstance(prefix_id, int) else None,
            (int(network.network_address), int(network.broadcast_address)),
        ))

    return address_intervals, reserved_ranges, prefix_intervals


def calculate_pool_availability(
    pool: dict[str, Any],
    *,
    address_intervals: dict[InventoryKey, list[Interval]],
    reserved_ranges: dict[InventoryKey, list[Interval]],
    prefix_intervals: dict[
        InventoryKey,
        list[tuple[int | None, Interval]],
    ],
) -> tuple[int | None, int | None, float | None]:
    network = prefix_network(pool)
    capacity = prefix_capacity(pool)

    if network is None or capacity is None:
        return None, None, None

    if pool.get("mark_utilized") is True:
        return capacity, 0, 100.0

    first = int(network.network_address)
    last = int(network.broadcast_address)
    key = (network.version, vrf_identifier(pool))
    pool_id = pool.get("id")
    intervals: list[Interval] = []

    for start, end in address_intervals.get(key, []):
        if first <= start <= last:
            intervals.append((start, start))

    for start, end in reserved_ranges.get(key, []):
        if end < first or start > last:
            continue
        intervals.append((max(first, start), min(last, end)))

    for child_id, (start, end) in prefix_intervals.get(key, []):
        if child_id == pool_id:
            continue
        if start >= first and end <= last:
            intervals.append((start, end))

    used = min(capacity, merged_interval_size(intervals))
    available = max(0, capacity - used)
    utilization = (
        round((used / capacity) * 100, 1)
        if capacity
        else 0.0
    )
    return used, available, utilization


class IPAMService:
    _inventory_cache: tuple[
        float,
        list[dict[str, Any]],
        list[dict[str, Any]],
    ] | None = None
    _inventory_cache_seconds = 60.0

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

    async def list_ip_addresses(self) -> list[dict[str, Any]]:
        return await self.client.get_all(
            "/api/ipam/ip-addresses/",
            params={"ordering": "address"},
            page_limit=500,
            maximum_pages=200,
        )

    async def list_ip_ranges(self) -> list[dict[str, Any]]:
        return await self.client.get_all(
            "/api/ipam/ip-ranges/",
            params={"ordering": "start_address"},
            page_limit=500,
            maximum_pages=100,
        )

    async def load_ip_inventory(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        str | None,
    ]:
        cached = self._inventory_cache
        now = monotonic()

        if cached is not None and cached[0] > now:
            return cached[1], cached[2], None

        results = await asyncio.gather(
            self.list_ip_addresses(),
            self.list_ip_ranges(),
            return_exceptions=True,
        )
        addresses_result, ranges_result = results
        warnings: list[str] = []

        if isinstance(addresses_result, Exception):
            ip_addresses: list[dict[str, Any]] = []
            warnings.append(
                "No fue posible cargar las direcciones IP registradas."
            )
        else:
            ip_addresses = addresses_result

        if isinstance(ranges_result, Exception):
            ip_ranges: list[dict[str, Any]] = []
            warnings.append(
                "No fue posible cargar los rangos IP registrados."
            )
        else:
            ip_ranges = ranges_result

        warning = " ".join(warnings) or None

        if warning is None:
            type(self)._inventory_cache = (
                now + self._inventory_cache_seconds,
                ip_addresses,
                ip_ranges,
            )

        return ip_addresses, ip_ranges, warning

    @staticmethod
    def prepare_pool(
        prefix: dict[str, Any],
        *,
        address_intervals: dict[InventoryKey, list[Interval]],
        reserved_ranges: dict[InventoryKey, list[Interval]],
        prefix_intervals: dict[
            InventoryKey,
            list[tuple[int | None, Interval]],
        ],
        inventory_warning: str | None,
    ) -> dict[str, Any]:
        capacity = prefix_capacity(prefix)
        used: int | None = None
        available: int | None = None
        utilization: float | None = None

        if inventory_warning is None:
            used, available, utilization = calculate_pool_availability(
                prefix,
                address_intervals=address_intervals,
                reserved_ranges=reserved_ranges,
                prefix_intervals=prefix_intervals,
            )

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
            "_availability_error": inventory_warning,
            "_availability_estimated": (
                inventory_warning is None
                and capacity is not None
                and utilization is not None
            ),
            "_health": (
                "unknown"
                if utilization is None
                else "full"
                if available == 0
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
        has_filters = bool(
            query.strip()
            or status.strip()
            or family in {4, 6}
            or role_id
        )

        try:
            if has_filters:
                prefixes, all_prefixes, roles = await asyncio.gather(
                    self.list_prefixes(
                        query=query,
                        status=status,
                        family=family,
                        role_id=role_id,
                    ),
                    self.list_prefixes(),
                    self.list_roles(),
                )
            else:
                prefixes, roles = await asyncio.gather(
                    self.list_prefixes(),
                    self.list_roles(),
                )
                all_prefixes = prefixes
        except NetBoxError as exc:
            raise IPAMServiceError(exc.message) from exc

        ip_addresses, ip_ranges, inventory_warning = (
            await self.load_ip_inventory()
        )
        (
            address_intervals,
            reserved_ranges,
            prefix_intervals,
        ) = build_occupancy_indexes(
            ip_addresses=ip_addresses,
            ip_ranges=ip_ranges,
            prefixes=all_prefixes,
        )

        pools = [
            prefix
            for prefix in prefixes
            if prefix.get("is_pool") is True
        ]
        prepared_pools = [
            self.prepare_pool(
                prefix,
                address_intervals=address_intervals,
                reserved_ranges=reserved_ranges,
                prefix_intervals=prefix_intervals,
                inventory_warning=inventory_warning,
            )
            for prefix in pools
        ]

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
            "inventory_warning": inventory_warning,
            "summary": {
                "prefixes": len(prefixes),
                "pools": len(prepared_pools),
                "full_pools": full_pools,
                "critical_pools": critical_pools,
                "pools_with_capacity": pools_with_capacity,
                "scopes": len(scopes),
            },
        }
