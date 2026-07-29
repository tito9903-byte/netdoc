from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any
from weakref import WeakKeyDictionary

import httpx

from app.core.config import get_settings


class NetBoxError(Exception):
    """Error controlado al comunicarse con la API de NetBox."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


_clients: WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient] = (
    WeakKeyDictionary()
)
_client_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
    WeakKeyDictionary()
)


def _authorization_header() -> str:
    settings = get_settings()
    token_type = settings.netbox_token_type.strip().lower()
    return (
        f"Bearer {settings.netbox_token}"
        if token_type == "bearer"
        else f"Token {settings.netbox_token}"
    )


async def get_shared_netbox_client() -> httpx.AsyncClient:
    """Reutiliza conexiones TCP/TLS dentro del loop activo de FastAPI."""

    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is not None and not client.is_closed:
        return client

    lock = _client_locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _client_locks[loop] = lock

    async with lock:
        client = _clients.get(loop)
        if client is not None and not client.is_closed:
            return client

        settings = get_settings()
        client = httpx.AsyncClient(
            base_url=f"{settings.netbox_url.rstrip('/')}/",
            headers={
                "Authorization": _authorization_header(),
                "User-Agent": f"NetDoc/{settings.app_version}",
            },
            verify=settings.netbox_verify_ssl,
            timeout=httpx.Timeout(settings.netbox_timeout),
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
                keepalive_expiry=45.0,
            ),
            follow_redirects=True,
        )
        _clients[loop] = client
        return client


async def close_shared_netbox_clients() -> None:
    """Cierra los pools creados en el proceso actual."""

    clients = list(_clients.values())
    _clients.clear()
    _client_locks.clear()
    NetBoxClient._dashboard_cache = None
    if clients:
        await asyncio.gather(
            *(client.aclose() for client in clients if not client.is_closed),
            return_exceptions=True,
        )


class NetBoxClient:
    _dashboard_cache: tuple[
        float,
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        str | None,
    ] | None = None
    _dashboard_cache_seconds = 30.0

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.netbox_url.rstrip("/")

    @staticmethod
    def _response_detail(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None

        if not isinstance(payload, dict):
            return None

        detail = payload.get("detail")
        return detail if isinstance(detail, str) else None

    @staticmethod
    def _copy_summary(
        summary: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        return {
            name: dict(metric)
            for name, metric in summary.items()
        }

    @staticmethod
    def _nested_id(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, dict) and isinstance(value.get("id"), int):
            return int(value["id"])
        return None

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value not in (None, "")
        }

        try:
            client = await get_shared_netbox_client()
            response = await client.get(
                endpoint.lstrip("/"),
                params=clean_params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                raise NetBoxError("NetBox devolvió un formato inesperado.")

            return payload

        except httpx.ConnectError as exc:
            raise NetBoxError(
                f"No fue posible conectar con NetBox en {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise NetBoxError(
                "NetBox no respondió dentro del tiempo configurado."
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            detail = self._response_detail(exc.response)

            if status_code == 401:
                message = detail or "El token de NetBox no es válido."
            elif status_code == 403:
                message = detail or (
                    "El usuario del token no tiene permiso para realizar esta consulta."
                )
            elif status_code == 404:
                message = detail or "El objeto solicitado no existe en NetBox."
            else:
                message = detail or f"NetBox respondió con HTTP {status_code}."

            raise NetBoxError(message=message, status_code=status_code) from exc
        except ValueError as exc:
            raise NetBoxError(
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

    async def get_list(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = await self.get(endpoint, params=params)
        if not isinstance(payload.get("results"), list):
            raise NetBoxError("La respuesta no contiene un listado válido.")
        return payload

    async def get_all(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        page_limit: int = 200,
        maximum_pages: int = 50,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        offset = 0
        base_params = dict(params or {})

        for _ in range(maximum_pages):
            request_params = {
                **base_params,
                "limit": page_limit,
                "offset": offset,
            }
            payload = await self.get_list(endpoint, params=request_params)
            page_results = payload.get("results", [])
            results.extend(page_results)

            if not payload.get("next") or not page_results:
                break
            offset += page_limit

        return results

    async def count(self, endpoint: str) -> int:
        payload = await self.get_list(endpoint, params={"limit": 1})
        count = payload.get("count", 0)
        return count if isinstance(count, int) else 0

    async def test_connection(self) -> dict[str, Any]:
        site_count = await self.count("/api/dcim/sites/")
        return {
            "connected": True,
            "url": self.base_url,
            "site_count": site_count,
        }

    async def dashboard_summary(self) -> dict[str, dict[str, Any]]:
        now = monotonic()
        cached = type(self)._dashboard_cache
        if cached is not None and cached[0] > now:
            return self._copy_summary(cached[1])

        endpoints = {
            "sites": "/api/dcim/sites/",
            "devices": "/api/dcim/devices/",
            "racks": "/api/dcim/racks/",
            "interfaces": "/api/dcim/interfaces/",
            "cables": "/api/dcim/cables/",
        }

        async def load_metric(
            name: str,
            endpoint: str,
        ) -> tuple[str, dict[str, Any]]:
            try:
                return name, {"value": await self.count(endpoint), "error": None}
            except NetBoxError as exc:
                return name, {"value": None, "error": exc.message}

        async def load_recent() -> tuple[list[dict[str, Any]], str | None]:
            try:
                return await self._fetch_recent_devices(8), None
            except NetBoxError as exc:
                return [], exc.message

        results = await asyncio.gather(
            *(load_metric(name, endpoint) for name, endpoint in endpoints.items()),
            load_recent(),
        )
        summary = dict(results[:-1])
        recent_devices, recent_error = results[-1]
        type(self)._dashboard_cache = (
            monotonic() + self._dashboard_cache_seconds,
            self._copy_summary(summary),
            [dict(item) for item in recent_devices],
            recent_error,
        )
        return summary

    async def _fetch_recent_devices(
        self,
        limit: int,
    ) -> list[dict[str, Any]]:
        payload = await self.get_list(
            "/api/dcim/devices/",
            params={"limit": limit, "ordering": "-last_updated"},
        )
        return payload["results"]

    async def recent_devices(self, limit: int = 8) -> list[dict[str, Any]]:
        cached = type(self)._dashboard_cache
        if cached is not None and cached[0] > monotonic() and limit == 8:
            if cached[3]:
                raise NetBoxError(cached[3])
            return [dict(item) for item in cached[2]]
        return await self._fetch_recent_devices(limit)

    async def list_sites(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/sites/",
            params={"ordering": "name"},
        )

    async def list_device_roles(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/device-roles/",
            params={"ordering": "name"},
        )

    async def list_devices(
        self,
        page: int = 1,
        page_size: int = 25,
        query: str = "",
        site_id: int | None = None,
        status: str = "",
        role_id: int | None = None,
    ) -> dict[str, Any]:
        safe_page = max(page, 1)
        params: dict[str, Any] = {
            "limit": page_size,
            "offset": (safe_page - 1) * page_size,
            "ordering": "name",
        }
        if query.strip():
            params["q"] = query.strip()
        if site_id:
            params["site_id"] = site_id
        if status.strip():
            params["status"] = status.strip()
        if role_id:
            params["role_id"] = role_id
        return await self.get_list("/api/dcim/devices/", params=params)

    async def get_device(self, device_id: int) -> dict[str, Any]:
        return await self.get(f"/api/dcim/devices/{device_id}/")

    async def get_device_interfaces(
        self,
        device_id: int,
    ) -> list[dict[str, Any]]:
        """Carga interfaces e IP asignadas en dos consultas paralelas.

        NetBox no incluye las direcciones completas dentro del serializador de
        interfaces. Consultarlas una por una causaría N+1 peticiones, por lo que
        se obtiene todo el inventario de IP del dispositivo en una sola llamada
        y se agrupa localmente por el ID de la interfaz asignada.
        """

        interfaces, addresses = await asyncio.gather(
            self.get_all(
                "/api/dcim/interfaces/",
                params={"device_id": device_id, "ordering": "name"},
                page_limit=200,
            ),
            self.get_all(
                "/api/ipam/ip-addresses/",
                params={"device_id": device_id, "ordering": "address"},
                page_limit=200,
            ),
        )

        addresses_by_interface: dict[int, list[dict[str, Any]]] = {}
        for address in addresses:
            assigned_object = address.get("assigned_object") or {}
            interface_id = self._nested_id(assigned_object)
            if interface_id is None:
                interface_id = self._nested_id(address.get("assigned_object_id"))
            if interface_id is None:
                continue
            addresses_by_interface.setdefault(interface_id, []).append(address)

        decorated: list[dict[str, Any]] = []
        for interface in interfaces:
            interface_id = self._nested_id(interface.get("id"))
            interface_addresses = (
                addresses_by_interface.get(interface_id, [])
                if interface_id is not None
                else []
            )
            decorated.append({
                **interface,
                "_ip_addresses": [dict(item) for item in interface_addresses],
                "_ip_address_count": len(interface_addresses),
            })

        return decorated
