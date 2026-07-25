from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class RackCreateServiceError(Exception):
    """Error controlado al consultar o crear racks en NetBox."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RackCreateService:
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
            "Content-Type": "application/json",
            "User-Agent": "NetDoc/0.10.0",
        }

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"NetBox respondió con HTTP {response.status_code}."

        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail

            messages: list[str] = []
            for field, value in payload.items():
                rendered = (
                    ", ".join(str(item) for item in value)
                    if isinstance(value, list)
                    else str(value)
                )
                messages.append(f"{field}: {rendered}")
            if messages:
                return " | ".join(messages)

        return f"NetBox respondió con HTTP {response.status_code}."

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
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
            raise RackCreateServiceError(
                f"No fue posible conectar con NetBox en {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise RackCreateServiceError(
                "NetBox no respondió dentro del tiempo configurado."
            ) from exc

        if response.is_error:
            raise RackCreateServiceError(
                self._error_message(response),
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise RackCreateServiceError(
                "NetBox no devolvió una respuesta JSON válida."
            ) from exc

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

            if not isinstance(payload, dict):
                raise RackCreateServiceError(
                    "NetBox devolvió un listado inesperado."
                )

            page_results = payload.get("results")
            if not isinstance(page_results, list):
                raise RackCreateServiceError(
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
            params={"ordering": "name", "status": "active"},
        )

    async def list_locations(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/locations/",
            params={"ordering": "site,name"},
        )

    async def list_roles(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/rack-roles/",
            params={"ordering": "name"},
        )

    async def list_rack_types(self) -> list[dict[str, Any]]:
        return await self.get_all(
            "/api/dcim/rack-types/",
            params={"ordering": "manufacturer,model"},
        )

    async def rack_choices(self) -> dict[str, list[dict[str, str]]]:
        try:
            payload = await self.request("OPTIONS", "/api/dcim/racks/")
            fields = payload.get("actions", {}).get("POST", {})

            def choices(name: str) -> list[dict[str, str]]:
                raw = fields.get(name, {}).get("choices", [])
                result: list[dict[str, str]] = []
                for item in raw:
                    value = item.get("value")
                    label = (
                        item.get("display_name")
                        or item.get("label")
                        or value
                    )
                    if value not in (None, ""):
                        result.append({
                            "value": str(value),
                            "label": str(label),
                        })
                return result

            statuses = choices("status")
            widths = choices("width")
            return {
                "statuses": statuses or [
                    {"value": "active", "label": "Activo"},
                    {"value": "planned", "label": "Planificado"},
                    {"value": "reserved", "label": "Reservado"},
                    {"value": "deprecated", "label": "Deprecado"},
                ],
                "widths": widths or [
                    {"value": "19", "label": "19 pulgadas"},
                    {"value": "23", "label": "23 pulgadas"},
                ],
            }
        except RackCreateServiceError:
            return {
                "statuses": [
                    {"value": "active", "label": "Activo"},
                    {"value": "planned", "label": "Planificado"},
                    {"value": "reserved", "label": "Reservado"},
                    {"value": "deprecated", "label": "Deprecado"},
                ],
                "widths": [
                    {"value": "19", "label": "19 pulgadas"},
                    {"value": "23", "label": "23 pulgadas"},
                ],
            }

    async def create_rack(
        self,
        *,
        name: str,
        site_id: int,
        location_id: int | None,
        rack_type_id: int | None,
        role_id: int | None,
        status: str,
        facility_id: str,
        serial: str,
        asset_tag: str,
        u_height: int,
        width: int,
        starting_unit: int,
        desc_units: bool,
        description: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name.strip(),
            "site": site_id,
            "status": status,
            "u_height": u_height,
            "width": width,
            "starting_unit": starting_unit,
            "desc_units": desc_units,
        }

        optional_values: dict[str, Any] = {
            "location": location_id,
            "rack_type": rack_type_id,
            "role": role_id,
            "facility_id": facility_id.strip(),
            "serial": serial.strip(),
            "asset_tag": asset_tag.strip(),
            "description": description.strip(),
        }
        for key, value in optional_values.items():
            if value not in (None, ""):
                payload[key] = value

        result = await self.request(
            "POST",
            "/api/dcim/racks/",
            json_body=payload,
        )
        if not isinstance(result, dict):
            raise RackCreateServiceError(
                "NetBox creó el rack, pero devolvió un formato inesperado."
            )
        return result
