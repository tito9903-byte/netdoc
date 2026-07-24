from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings


class ConnectionServiceError(Exception):
    """Error controlado al consultar o modificar cables en NetBox."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ConnectionService:
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
            "User-Agent": "NetDoc/0.6.0",
        }

    @staticmethod
    def _format_api_error(
        response: httpx.Response,
    ) -> tuple[str, dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError:
            return (
                f"NetBox respondió con HTTP {response.status_code}.",
                {},
            )

        if not isinstance(payload, dict):
            return (
                f"NetBox respondió con HTTP {response.status_code}.",
                {},
            )

        detail = payload.get("detail")

        if isinstance(detail, str):
            return detail, payload

        messages: list[str] = []

        for field, value in payload.items():
            if isinstance(value, list):
                text = ", ".join(str(item) for item in value)
            else:
                text = str(value)

            messages.append(f"{field}: {text}")

        return (
            " | ".join(messages)
            or f"NetBox respondió con HTTP {response.status_code}.",
            payload,
        )

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
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
                response = await client.request(
                    method=method,
                    url=url,
                    params=clean_params,
                    json=json_body,
                )

        except httpx.ConnectError as exc:
            raise ConnectionServiceError(
                f"No fue posible conectar con NetBox en {self.base_url}."
            ) from exc

        except httpx.TimeoutException as exc:
            raise ConnectionServiceError(
                "NetBox no respondió dentro del tiempo configurado."
            ) from exc

        if response.is_error:
            message, details = self._format_api_error(response)
            raise ConnectionServiceError(
                message=message,
                status_code=response.status_code,
                details=details,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectionServiceError(
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

        if not isinstance(payload, dict):
            raise ConnectionServiceError(
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
                raise ConnectionServiceError(
                    "NetBox no devolvió un listado válido."
                )

            results.extend(page_results)

            if not payload.get("next") or not page_results:
                break

            offset += page_limit

        return results

    async def get_cable_choices(
        self,
    ) -> dict[str, list[dict[str, str]]]:
        url = f"{self.base_url}/api/dcim/cables/"

        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                verify=self.settings.netbox_verify_ssl,
                timeout=self.settings.netbox_timeout,
                follow_redirects=True,
            ) as client:
                response = await client.options(url)

            response.raise_for_status()
            payload = response.json()
            fields = payload.get("actions", {}).get("POST", {})

            def choices(name: str) -> list[dict[str, str]]:
                raw = fields.get(name, {}).get("choices", [])
                output: list[dict[str, str]] = []

                for item in raw:
                    value = item.get("value")
                    label = (
                        item.get("display_name")
                        or item.get("label")
                        or value
                    )

                    if value:
                        output.append({
                            "value": str(value),
                            "label": str(label),
                        })

                return output

            return {
                "types": choices("type"),
                "statuses": choices("status"),
                "length_units": choices("length_unit"),
            }

        except (httpx.HTTPError, ValueError, AttributeError):
            return {
                "types": [
                    {"value": "cat6", "label": "CAT6"},
                    {
                        "value": "dac-passive",
                        "label": "Direct Attach Copper (Passive)",
                    },
                    {
                        "value": "mmf-om4",
                        "label": "Multimode Fiber (OM4)",
                    },
                    {
                        "value": "smf-os2",
                        "label": "Single-mode Fiber (OS2)",
                    },
                ],
                "statuses": [
                    {"value": "connected", "label": "Connected"},
                    {"value": "planned", "label": "Planned"},
                ],
                "length_units": [
                    {"value": "m", "label": "Meters"},
                    {"value": "ft", "label": "Feet"},
                ],
            }

    async def list_sites(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/sites/",
            params={"ordering": "name"},
        )

    async def list_devices(
        self,
        site_id: int,
    ) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/devices/",
            params={
                "site_id": site_id,
                "ordering": "name",
            },
        )

    async def list_free_interfaces(
        self,
        device_id: int,
    ) -> list[dict[str, Any]]:
        interfaces = await self.get_all(
            "/api/dcim/interfaces/",
            params={
                "device_id": device_id,
                "ordering": "name",
            },
        )
        excluded_types = {"virtual", "bridge", "lag", "wireless"}
        available: list[dict[str, Any]] = []

        for interface in interfaces:
            interface_type = interface.get("type") or {}
            type_value = interface_type.get("value")
            has_connection = bool(
                interface.get("cable")
                or interface.get("connected_endpoints")
            )

            if has_connection or type_value in excluded_types:
                continue

            available.append({
                "id": interface.get("id"),
                "name": interface.get("name") or "Sin nombre",
                "description": interface.get("description") or "",
                "enabled": interface.get("enabled") is True,
                "type": (
                    interface_type.get("label")
                    or type_value
                    or "Sin tipo"
                ),
            })

        return available

    async def get_interface(
        self,
        interface_id: int,
    ) -> dict[str, Any]:
        return await self.request(
            "GET",
            f"/api/dcim/interfaces/{interface_id}/",
        )

    @staticmethod
    def interface_is_connected(
        interface: dict[str, Any],
    ) -> bool:
        return bool(
            interface.get("cable")
            or interface.get("connected_endpoints")
        )

    async def list_recent_cables(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = await self.request(
            "GET",
            "/api/dcim/cables/",
            params={
                "limit": limit,
                "ordering": "-created",
            },
        )
        results = payload.get("results")
        return results if isinstance(results, list) else []

    async def create_interface_cable(
        self,
        *,
        interface_a_id: int,
        interface_b_id: int,
        cable_type: str,
        status: str,
        label: str,
        color: str,
        length: Decimal | None,
        length_unit: str,
        description: str,
        username: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "a_terminations": [
                {
                    "object_type": "dcim.interface",
                    "object_id": interface_a_id,
                }
            ],
            "b_terminations": [
                {
                    "object_type": "dcim.interface",
                    "object_id": interface_b_id,
                }
            ],
            "type": cable_type,
            "status": status,
            "changelog_message": (
                "Cable creado desde NetDoc por "
                f"{username}."
            ),
        }

        if label.strip():
            payload["label"] = label.strip()

        normalized_color = color.strip().lstrip("#")

        if normalized_color:
            payload["color"] = normalized_color

        if length is not None:
            payload["length"] = str(length)
            payload["length_unit"] = length_unit

        if description.strip():
            payload["description"] = description.strip()

        return await self.request(
            "POST",
            "/api/dcim/cables/",
            json_body=payload,
        )
