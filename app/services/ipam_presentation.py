from __future__ import annotations

from decimal import Decimal
from ipaddress import ip_network
from math import ceil
from typing import Any


_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_HEALTH_ORDER = {
    "full": 0,
    "critical": 1,
    "warning": 2,
    "healthy": 3,
    "unknown": 4,
}


def exact_count(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}".replace(",", ".")


def compact_count(value: int | None) -> str:
    """Muestra IPv4 completo y resume cantidades IPv6 muy extensas."""

    if value is None:
        return "—"

    absolute = abs(value)
    if absolute < 1_000_000_000:
        return exact_count(value)

    exponent = len(str(absolute)) - 1
    mantissa = Decimal(value).scaleb(-exponent)
    text = f"{mantissa:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} × 10{str(exponent).translate(_SUPERSCRIPT)}"


def _prefix_sort_key(pool: dict[str, Any]) -> tuple[int, int, int, str]:
    value = pool.get("prefix") or pool.get("display") or ""
    try:
        network = ip_network(str(value), strict=False)
    except ValueError:
        return 9, 0, 0, str(value)

    return (
        network.version,
        int(network.network_address),
        network.prefixlen,
        str(value),
    )


def _decorate_pool(pool: dict[str, Any]) -> dict[str, Any]:
    capacity = pool.get("_capacity")
    used = pool.get("_used")
    available = pool.get("_available")

    return {
        **pool,
        "_capacity_compact": compact_count(capacity),
        "_capacity_exact": exact_count(capacity),
        "_used_compact": compact_count(used),
        "_used_exact": exact_count(used),
        "_available_compact": compact_count(available),
        "_available_exact": exact_count(available),
    }


def prepare_ipam_view(
    data: dict[str, Any],
    *,
    scope: str = "",
    health: str = "",
    order: str = "scope",
    page: int = 1,
    page_size: int = 40,
) -> dict[str, Any]:
    """Prepara filtros de uso, orden y paginación sin volver a consultar NetBox."""

    all_pools = [
        _decorate_pool(pool)
        for pool in data.get("pools", [])
        if isinstance(pool, dict)
    ]
    available_scopes = sorted(
        {
            str(pool.get("_scope_label") or "Sin localidad")
            for pool in all_pools
        },
        key=str.casefold,
    )

    selected_scope = scope.strip()
    selected_health = health.strip().lower()
    selected_order = order.strip().lower()

    pools = all_pools
    if selected_scope:
        pools = [
            pool
            for pool in pools
            if str(pool.get("_scope_label") or "").casefold()
            == selected_scope.casefold()
        ]

    if selected_health in _HEALTH_ORDER:
        pools = [
            pool
            for pool in pools
            if pool.get("_health") == selected_health
        ]
    elif selected_health == "available":
        pools = [
            pool
            for pool in pools
            if isinstance(pool.get("_available"), int)
            and pool["_available"] > 0
        ]
    elif selected_health == "documented":
        pools = [
            pool
            for pool in pools
            if isinstance(pool.get("_used"), int)
            and pool["_used"] > 0
        ]
    elif selected_health == "empty":
        pools = [
            pool
            for pool in pools
            if pool.get("_used") == 0
        ]

    if selected_order == "availability_desc":
        pools.sort(
            key=lambda item: (
                -(item.get("_available") or 0),
                str(item.get("_scope_label") or "").casefold(),
                _prefix_sort_key(item),
            )
        )
    elif selected_order == "scope":
        pools.sort(
            key=lambda item: (
                str(item.get("_scope_label") or "").casefold(),
                _prefix_sort_key(item),
            )
        )
    elif selected_order == "prefix":
        pools.sort(key=_prefix_sort_key)
    else:
        selected_order = "utilization_desc"
        pools.sort(
            key=lambda item: (
                _HEALTH_ORDER.get(str(item.get("_health")), 9),
                -(item.get("_utilization") or 0),
                str(item.get("_scope_label") or "").casefold(),
                _prefix_sort_key(item),
            )
        )

    total = len(pools)
    safe_page_size = max(10, min(page_size, 100))
    total_pages = max(1, ceil(total / safe_page_size))
    safe_page = max(1, min(page, total_pages))
    start_index = (safe_page - 1) * safe_page_size
    end_index = min(total, start_index + safe_page_size)
    visible = pools[start_index:end_index]

    filtered_scopes = {
        str(pool.get("_scope_label") or "Sin localidad")
        for pool in pools
    }
    filtered_full = sum(
        1 for pool in pools if pool.get("_health") == "full"
    )
    filtered_critical = sum(
        1
        for pool in pools
        if pool.get("_health") in {"critical", "full"}
    )
    filtered_available = sum(
        1
        for pool in pools
        if isinstance(pool.get("_available"), int)
        and pool["_available"] > 0
    )

    summary = dict(data.get("summary") or {})
    summary.update({
        "total_pools": len(all_pools),
        "visible_pools": total,
        "full_pools": filtered_full,
        "critical_pools": filtered_critical,
        "available_pools": filtered_available,
        "scopes": len(filtered_scopes),
    })

    return {
        **data,
        "pools": visible,
        "pool_scopes": available_scopes,
        "summary": summary,
        "pool_pagination": {
            "page": safe_page,
            "page_size": safe_page_size,
            "total": total,
            "total_pages": total_pages,
            "start": start_index + 1 if total else 0,
            "end": end_index,
        },
        "selected_scope": selected_scope,
        "selected_health": selected_health,
        "selected_order": selected_order,
    }
