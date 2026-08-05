from __future__ import annotations

import re
from typing import Any

from app.services.rack_create_service import (
    RackCreateService,
    RackCreateServiceError,
)


class SiteServiceError(RackCreateServiceError):
    """Error controlado al administrar sitios en NetBox."""


class SiteService:
    def __init__(self) -> None:
        self.client = RackCreateService()

    async def list_sites(
        self,
        *,
        query: str = "",
        status: str = "",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"ordering": "name"}
        if query.strip():
            params["q"] = query.strip()
        if status.strip():
            params["status"] = status.strip()
        try:
            return await self.client.get_all("/api/dcim/sites/", params=params)
        except RackCreateServiceError as exc:
            raise SiteServiceError(exc.message, exc.status_code) from exc

    async def get_site(self, site_id: int) -> dict[str, Any]:
        try:
            result = await self.client.request(
                "GET",
                f"/api/dcim/sites/{site_id}/",
            )
        except RackCreateServiceError as exc:
            raise SiteServiceError(exc.message, exc.status_code) from exc
        if not isinstance(result, dict):
            raise SiteServiceError("NetBox devolvió un sitio inválido.")
        return result

    async def site_choices(self) -> dict[str, list[dict[str, str]]]:
        try:
            payload = await self.client.request("OPTIONS", "/api/dcim/sites/")
            fields = payload.get("actions", {}).get("POST", {})
            raw = fields.get("status", {}).get("choices", [])
            statuses = [
                {
                    "value": str(item.get("value")),
                    "label": str(
                        item.get("display_name")
                        or item.get("label")
                        or item.get("value")
                    ),
                }
                for item in raw
                if item.get("value") not in (None, "")
            ]
        except (AttributeError, RackCreateServiceError):
            statuses = []
        return {
            "statuses": statuses or [
                {"value": "planned", "label": "Planificado"},
                {"value": "staging", "label": "En preparación"},
                {"value": "active", "label": "Activo"},
                {"value": "decommissioning", "label": "En retiro"},
                {"value": "retired", "label": "Retirado"},
            ]
        }

    async def duplicate_exists(
        self,
        *,
        name: str,
        slug: str,
        exclude_id: int | None = None,
    ) -> bool:
        for field, value in (("name", name.strip()), ("slug", slug.strip())):
            if not value:
                continue
            try:
                results = await self.client.get_all(
                    "/api/dcim/sites/",
                    params={field: value, "limit": 10},
                    maximum_pages=1,
                )
            except RackCreateServiceError as exc:
                raise SiteServiceError(exc.message, exc.status_code) from exc
            if any(item.get("id") != exclude_id for item in results):
                return True
        return False

    async def save_site(
        self,
        *,
        site_id: int | None,
        name: str,
        slug: str,
        status: str,
        facility: str,
        physical_address: str,
        shipping_address: str,
        latitude: str,
        longitude: str,
        description: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name.strip(),
            "slug": slug.strip(),
            "status": status.strip(),
            "facility": facility.strip(),
            "physical_address": physical_address.strip(),
            "shipping_address": shipping_address.strip(),
            "description": description.strip(),
        }
        if latitude.strip():
            payload["latitude"] = latitude.strip()
        if longitude.strip():
            payload["longitude"] = longitude.strip()
        method = "PATCH" if site_id is not None else "POST"
        endpoint = (
            f"/api/dcim/sites/{site_id}/"
            if site_id is not None
            else "/api/dcim/sites/"
        )
        try:
            result = await self.client.request(
                method,
                endpoint,
                json_body=payload,
            )
        except RackCreateServiceError as exc:
            raise SiteServiceError(exc.message, exc.status_code) from exc
        if not isinstance(result, dict):
            raise SiteServiceError(
                "NetBox guardó el sitio, pero devolvió un formato inesperado."
            )
        return result

    async def deactivate_site(self, site_id: int) -> dict[str, Any]:
        site = await self.get_site(site_id)
        def text(key: str) -> str:
            value = site.get(key)
            return "" if value is None else str(value)

        return await self.save_site(
            site_id=site_id,
            name=text("name"),
            slug=text("slug"),
            status="retired",
            facility=text("facility"),
            physical_address=text("physical_address"),
            shipping_address=text("shipping_address"),
            latitude=text("latitude"),
            longitude=text("longitude"),
            description=text("description"),
        )


def validate_site_form(data: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not data["name"].strip():
        errors.append("El nombre del site es obligatorio.")
    slug = data["slug"].strip()
    if not slug:
        errors.append("El código del site es obligatorio.")
    elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        errors.append(
            "El código solo admite minúsculas, números y guiones simples."
        )
    for key, label, minimum, maximum in (
        ("latitude", "latitud", -90, 90),
        ("longitude", "longitud", -180, 180),
    ):
        value = data[key].strip()
        if not value:
            continue
        try:
            number = float(value)
        except ValueError:
            errors.append(f"La {label} debe ser numérica.")
            continue
        if not minimum <= number <= maximum:
            errors.append(
                f"La {label} debe estar entre {minimum} y {maximum}."
            )
    return errors
