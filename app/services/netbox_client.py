import asyncio
from typing import Any

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


class NetBoxClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.netbox_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        token_type = self.settings.netbox_token_type.strip().lower()

        if token_type == "bearer":
            authorization = f"Bearer {self.settings.netbox_token}"
        else:
            authorization = f"Token {self.settings.netbox_token}"

        return {
            "Authorization": authorization,
            "Accept": "application/json",
            "User-Agent": "NetDoc/0.4.0",
        }

    @staticmethod
    def _response_detail(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None

        if not isinstance(payload, dict):
            return None

        detail = payload.get("detail")

        if isinstance(detail, str):
            return detail

        return None

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value not in (None, "")
        }

        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                verify=self.settings.netbox_verify_ssl,
                timeout=self.settings.netbox_timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    url,
                    params=clean_params,
                )

            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                raise NetBoxError(
                    "NetBox devolvió un formato inesperado."
                )

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
                    "El usuario del token no tiene permiso "
                    "para realizar esta consulta."
                )

            elif status_code == 404:
                message = detail or (
                    "El objeto solicitado no existe en NetBox."
                )

            else:
                message = detail or (
                    f"NetBox respondió con HTTP {status_code}."
                )

            raise NetBoxError(
                message=message,
                status_code=status_code,
            ) from exc

        except ValueError as exc:
            raise NetBoxError(
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

    async def get_list(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = await self.get(
            endpoint,
            params=params,
        )

        if not isinstance(payload.get("results"), list):
            raise NetBoxError(
                "La respuesta no contiene un listado válido."
            )

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

            payload = await self.get_list(
                endpoint,
                params=request_params,
            )

            page_results = payload.get("results", [])
            results.extend(page_results)

            if not payload.get("next"):
                break

            if not page_results:
                break

            offset += page_limit

        return results

    async def count(self, endpoint: str) -> int:
        payload = await self.get_list(
            endpoint,
            params={"limit": 1},
        )

        count = payload.get("count", 0)

        if isinstance(count, int):
            return count

        return 0

    async def test_connection(self) -> dict[str, Any]:
        site_count = await self.count("/api/dcim/sites/")

        return {
            "connected": True,
            "url": self.base_url,
            "site_count": site_count,
        }

    async def dashboard_summary(self) -> dict[str, dict[str, Any]]:
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
                value = await self.count(endpoint)

                return name, {
                    "value": value,
                    "error": None,
                }

            except NetBoxError as exc:
                return name, {
                    "value": None,
                    "error": exc.message,
                }

        tasks = [
            load_metric(name, endpoint)
            for name, endpoint in endpoints.items()
        ]

        results = await asyncio.gather(*tasks)

        return dict(results)

    async def recent_devices(
        self,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        payload = await self.get_list(
            "/api/dcim/devices/",
            params={
                "limit": limit,
                "ordering": "-last_updated",
            },
        )

        return payload["results"]

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
        offset = (safe_page - 1) * page_size

        params: dict[str, Any] = {
            "limit": page_size,
            "offset": offset,
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

        return await self.get_list(
            "/api/dcim/devices/",
            params=params,
        )

    async def get_device(
        self,
        device_id: int,
    ) -> dict[str, Any]:
        return await self.get(
            f"/api/dcim/devices/{device_id}/"
        )

    async def get_device_interfaces(
        self,
        device_id: int,
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/interfaces/",
            params={
                "device_id": device_id,
                "ordering": "name",
            },
            page_limit=200,
        )
