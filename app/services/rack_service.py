from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class RackServiceError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RackService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.netbox_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        token_type = self.settings.netbox_token_type.strip().lower()

        authorization = (
            f"Bearer {self.settings.netbox_token}"
            if token_type == "bearer"
            else f"Token {self.settings.netbox_token}"
        )

        return {
            "Authorization": authorization,
            "Accept": "application/json",
            "User-Agent": "NetDoc/0.7.0",
        }

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"NetBox respondió con HTTP {response.status_code}."

        if not isinstance(payload, dict):
            return f"NetBox respondió con HTTP {response.status_code}."

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

        return (
            " | ".join(messages)
            or f"NetBox respondió con HTTP {response.status_code}."
        )

    async def request(
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

        except httpx.ConnectError as exc:
            raise RackServiceError(
                f"No fue posible conectar con NetBox en {self.base_url}."
            ) from exc

        except httpx.TimeoutException as exc:
            raise RackServiceError(
                "NetBox no respondió dentro del tiempo configurado."
            ) from exc

        if response.is_error:
            raise RackServiceError(
                message=self._error_message(response),
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RackServiceError(
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

        if not isinstance(payload, dict):
            raise RackServiceError(
                "NetBox devolvió un formato de respuesta inesperado."
            )

        return payload

    async def get_all(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        page_limit: int = 200,
        maximum_pages: int = 50,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        offset = 0

        for _ in range(maximum_pages):
            payload = await self.request(
                endpoint,
                params={
                    **(params or {}),
                    "limit": page_limit,
                    "offset": offset,
                },
            )

            page_results = payload.get("results")

            if not isinstance(page_results, list):
                raise RackServiceError(
                    "NetBox no devolvió un listado válido."
                )

            results.extend(page_results)

            if not payload.get("next") or not page_results:
                break

            offset += page_limit

        return results

    async def list_sites(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/sites/",
            params={"ordering": "name"},
        )

    async def list_racks(
        self,
        *,
        site_id: int | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "ordering": "name",
        }

        if site_id:
            params["site_id"] = site_id

        if query.strip():
            params["q"] = query.strip()

        return await self.get_all(
            "/api/dcim/racks/",
            params=params,
        )

    async def get_rack(
        self,
        rack_id: int,
    ) -> dict[str, Any]:
        return await self.request(
            f"/api/dcim/racks/{rack_id}/"
        )

    async def list_rack_devices(
        self,
        rack_id: int,
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/devices/",
            params={
                "rack_id": rack_id,
                "ordering": "position,name",
            },
        )
