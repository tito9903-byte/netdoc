from __future__ import annotations

import asyncio
from copy import deepcopy
from time import monotonic
from typing import Any, Awaitable, Callable

import httpx

from app.services.connection_service import ConnectionService
from app.services.netbox_client import get_shared_netbox_client
from app.services.rack_presentation import nested_label


class NavigationReadError(RuntimeError):
    """Error controlado al cargar datos de navegación desde NetBox."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NavigationReadService:
    """Lecturas rápidas, reutilizables y cacheadas para pantallas de catálogo."""

    _cache: dict[str, tuple[float, Any]] = {}
    _locks: dict[str, asyncio.Lock] = {}

    @classmethod
    async def _cached(
        cls,
        key: str,
        ttl_seconds: float,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        now = monotonic()
        cached = cls._cache.get(key)
        if cached and cached[0] > now:
            return deepcopy(cached[1])

        lock = cls._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            cls._locks[key] = lock

        async with lock:
            now = monotonic()
            cached = cls._cache.get(key)
            if cached and cached[0] > now:
                return deepcopy(cached[1])

            value = await loader()
            cls._cache[key] = (now + ttl_seconds, deepcopy(value))
            return value

    @staticmethod
    def _response_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"NetBox respondió con HTTP {response.status_code}."

        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()

        return f"NetBox respondió con HTTP {response.status_code}."

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> dict[str, Any]:
        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value not in (None, "")
        }

        try:
            client = await get_shared_netbox_client()
            response = await client.request(
                method,
                endpoint.lstrip("/"),
                params=clean_params,
                headers={"Accept": accept},
            )
        except httpx.ConnectError as exc:
            raise NavigationReadError("No fue posible conectar con NetBox.") from exc
        except httpx.TimeoutException as exc:
            raise NavigationReadError(
                "NetBox no respondió dentro del tiempo configurado."
            ) from exc

        if response.is_error:
            raise NavigationReadError(
                self._response_message(response),
                response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise NavigationReadError(
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

        if not isinstance(payload, dict):
            raise NavigationReadError(
                "NetBox devolvió un formato de respuesta inesperado."
            )
        return payload

    async def _get_all(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        page_limit: int = 200,
        maximum_pages: int = 50,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        offset = 0

        for _ in range(maximum_pages):
            payload = await self._request(
                "GET",
                endpoint,
                params={
                    **(params or {}),
                    "limit": page_limit,
                    "offset": offset,
                },
            )
            page_results = payload.get("results")
            if not isinstance(page_results, list):
                raise NavigationReadError(
                    "NetBox no devolvió un listado válido."
                )

            normalized = [
                item for item in page_results if isinstance(item, dict)
            ]
            results.extend(normalized)

            if not payload.get("next") or not normalized:
                break
            offset += page_limit

        return results

    async def list_sites(self) -> list[dict[str, Any]]:
        return await self._cached(
            "sites",
            60.0,
            lambda: self._get_all(
                "/api/dcim/sites/",
                params={"ordering": "name"},
            ),
        )

    @staticmethod
    def _choice_rows(
        fields: dict[str, Any],
        name: str,
        translations: dict[str, str],
    ) -> list[dict[str, str]]:
        raw = fields.get(name, {}).get("choices", [])
        if not isinstance(raw, list):
            return []

        output: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if value in (None, ""):
                continue
            label = (
                item.get("display_name")
                or item.get("label")
                or value
            )
            output.append({
                "value": str(value),
                "label": (
                    translations.get(str(value).lower())
                    or translations.get(str(label).lower())
                    or str(label)
                ),
            })
        return output

    async def get_cable_choices(self) -> dict[str, list[dict[str, str]]]:
        async def load() -> dict[str, list[dict[str, str]]]:
            try:
                payload = await self._request(
                    "OPTIONS",
                    "/api/dcim/cables/",
                )
                fields = payload.get("actions", {}).get("POST", {})
                if not isinstance(fields, dict):
                    raise NavigationReadError(
                        "NetBox no devolvió las opciones de cables."
                    )
                return {
                    "types": self._choice_rows(
                        fields,
                        "type",
                        ConnectionService.CABLE_TYPE_LABELS,
                    ),
                    "statuses": self._choice_rows(
                        fields,
                        "status",
                        ConnectionService.STATUS_LABELS,
                    ),
                    "length_units": self._choice_rows(
                        fields,
                        "length_unit",
                        ConnectionService.UNIT_LABELS,
                    ),
                }
            except NavigationReadError:
                return {
                    "types": [
                        {"value": "cat6", "label": "Cobre CAT6"},
                        {"value": "dac-passive", "label": "DAC pasivo"},
                        {"value": "mmf-om4", "label": "Fibra multimodo OM4"},
                        {"value": "smf-os2", "label": "Fibra monomodo OS2"},
                    ],
                    "statuses": [
                        {"value": "connected", "label": "Conectado"},
                        {"value": "planned", "label": "Planificado"},
                    ],
                    "length_units": [
                        {"value": "m", "label": "m"},
                        {"value": "ft", "label": "pies"},
                    ],
                }

        return await self._cached("cable-choices", 300.0, load)

    @staticmethod
    def _first_termination(cable: dict[str, Any], side: str) -> dict[str, Any]:
        values = cable.get(side) or []
        if isinstance(values, list) and values and isinstance(values[0], dict):
            return values[0]
        return {}

    async def list_recent_cables(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 50))

        async def load() -> list[dict[str, Any]]:
            payload = await self._request(
                "GET",
                "/api/dcim/cables/",
                params={
                    "limit": safe_limit,
                    "ordering": "-created",
                },
            )
            raw_results = payload.get("results")
            cables = raw_results if isinstance(raw_results, list) else []
            prepared: list[dict[str, Any]] = []

            for raw_cable in cables:
                if not isinstance(raw_cable, dict):
                    continue
                cable = dict(raw_cable)
                a_term = self._first_termination(cable, "a_terminations")
                b_term = self._first_termination(cable, "b_terminations")
                length = cable.get("length")
                unit_label = ConnectionService._translated_choice(
                    cable.get("length_unit"),
                    ConnectionService.UNIT_LABELS,
                    "",
                )
                cable.update({
                    "_a_label": ConnectionService._termination_label(a_term),
                    "_b_label": ConnectionService._termination_label(b_term),
                    "_type_label": ConnectionService._translated_choice(
                        cable.get("type"),
                        ConnectionService.CABLE_TYPE_LABELS,
                    ),
                    "_status_label": ConnectionService._translated_choice(
                        cable.get("status"),
                        ConnectionService.STATUS_LABELS,
                    ),
                    "_length_label": (
                        f"{length} {unit_label}".strip()
                        if length not in (None, "")
                        else "—"
                    ),
                })
                prepared.append(cable)

            return prepared

        return await self._cached(
            f"recent-cables:{safe_limit}",
            15.0,
            load,
        )

    async def connection_page_data(self) -> dict[str, Any]:
        sites, choices, recent_cables = await asyncio.gather(
            self.list_sites(),
            self.get_cable_choices(),
            self.list_recent_cables(),
        )
        return {
            "sites": sites,
            "choices": choices,
            "recent_cables": recent_cables,
        }

    async def list_racks(
        self,
        *,
        site_id: int | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()
        key = f"racks:{site_id or 0}:{clean_query.casefold()}"

        async def load() -> list[dict[str, Any]]:
            params: dict[str, Any] = {"ordering": "site,name"}
            if site_id:
                params["site_id"] = site_id
            if clean_query:
                params["q"] = clean_query

            racks = await self._get_all(
                "/api/dcim/racks/",
                params=params,
            )
            prepared: list[dict[str, Any]] = []

            for raw_rack in racks:
                rack = dict(raw_rack)
                site = rack.get("site") or {}
                device_count = rack.get("device_count")
                rack["_site_label"] = nested_label(site, "Sin sitio")
                rack["_location_label"] = nested_label(
                    rack.get("location")
                )
                rack["_status_label"] = nested_label(rack.get("status"))
                rack["_u_height"] = int(rack.get("u_height") or 42)
                rack["_device_count"] = (
                    int(device_count)
                    if isinstance(device_count, int)
                    else 0
                )
                prepared.append(rack)

            return prepared

        return await self._cached(key, 30.0, load)

    async def rack_catalog(
        self,
        *,
        site_id: int | None = None,
        query: str = "",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        sites, racks = await asyncio.gather(
            self.list_sites(),
            self.list_racks(site_id=site_id, query=query),
        )
        return sites, racks
