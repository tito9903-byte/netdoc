from __future__ import annotations

import asyncio
from hashlib import sha256
from time import monotonic
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import get_settings
from app.services.device_image_service import DeviceImageService
from app.services.device_type_service import DeviceTypeServiceError


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
    _device_type_cache: dict[int, tuple[float, dict[str, Any]]] = {}
    _device_type_cache_seconds = 300.0
    _maximum_image_bytes = 5 * 1024 * 1024

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.netbox_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self.base_url}/",
            headers=self._headers(),
            verify=self.settings.netbox_verify_ssl,
            timeout=self.settings.netbox_timeout,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
            follow_redirects=True,
            trust_env=False,
        )

    async def __aenter__(self) -> RackService:
        self._client = self._build_client()
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        token_type = self.settings.netbox_token_type.strip().lower()
        authorization = (
            f"Bearer {self.settings.netbox_token}"
            if token_type == "bearer"
            else f"Token {self.settings.netbox_token}"
        )
        return {
            "Authorization": authorization,
            "Accept": accept,
            "User-Agent": f"NetDoc/{self.settings.app_version}",
        }

    @staticmethod
    def _local_error(exc: DeviceTypeServiceError) -> RackServiceError:
        return RackServiceError(exc.message, exc.status_code or 503)

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
            rendered = (
                ", ".join(str(item) for item in value)
                if isinstance(value, list)
                else str(value)
            )
            messages.append(f"{field}: {rendered}")
        return " | ".join(messages) or f"NetBox respondió con HTTP {response.status_code}."

    async def request(
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
            if self._client is not None:
                response = await self._client.get(
                    endpoint.lstrip("/"),
                    params=clean_params,
                    headers={"Accept": "application/json"},
                )
            else:
                async with self._build_client() as client:
                    response = await client.get(
                        endpoint.lstrip("/"),
                        params=clean_params,
                        headers={"Accept": "application/json"},
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
                raise RackServiceError("NetBox no devolvió un listado válido.")
            results.extend(
                item for item in page_results if isinstance(item, dict)
            )
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
        params: dict[str, Any] = {"ordering": "site,name"}
        if site_id:
            params["site_id"] = site_id
        if query.strip():
            params["q"] = query.strip()
        return await self.get_all("/api/dcim/racks/", params=params)

    async def get_rack(self, rack_id: int) -> dict[str, Any]:
        return await self.request(f"/api/dcim/racks/{rack_id}/")

    async def get_device_type(
        self,
        device_type_id: int,
    ) -> dict[str, Any]:
        cached = type(self)._device_type_cache.get(device_type_id)
        now = monotonic()
        if cached and cached[0] > now:
            return cached[1]

        payload = await self.request(
            f"/api/dcim/device-types/{device_type_id}/"
        )
        try:
            payload = DeviceImageService().decorate_device_type(payload)
        except DeviceTypeServiceError as exc:
            raise self._local_error(exc) from exc
        type(self)._device_type_cache[device_type_id] = (
            now + self._device_type_cache_seconds,
            payload,
        )
        return payload

    @staticmethod
    def _device_type_id(device: dict[str, Any]) -> int | None:
        device_type = device.get("device_type") or {}
        if isinstance(device_type, dict) and isinstance(
            device_type.get("id"), int
        ):
            return int(device_type["id"])
        value = device.get("device_type_id")
        return int(value) if isinstance(value, int) else None

    async def hydrate_device_types(
        self,
        devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        type_ids = sorted({
            device_type_id
            for device in devices
            if (device_type_id := self._device_type_id(device)) is not None
        })
        semaphore = asyncio.Semaphore(10)

        async def load(
            device_type_id: int,
        ) -> tuple[int, dict[str, Any] | None]:
            try:
                async with semaphore:
                    return device_type_id, await self.get_device_type(
                        device_type_id
                    )
            except RackServiceError:
                return device_type_id, None

        loaded = await asyncio.gather(*(load(item) for item in type_ids))
        details = {
            device_type_id: payload
            for device_type_id, payload in loaded
            if isinstance(payload, dict)
        }
        try:
            local_summaries = DeviceImageService().summaries(type_ids)
        except DeviceTypeServiceError as exc:
            raise self._local_error(exc) from exc

        hydrated: list[dict[str, Any]] = []
        for device in devices:
            device_type = device.get("device_type") or {}
            if not isinstance(device_type, dict):
                device_type = {}
            device_type_id = self._device_type_id(device)
            combined = {
                **device_type,
                **(details.get(device_type_id) or {}),
            }
            if device_type_id and device_type_id in local_summaries:
                local = local_summaries[device_type_id]
                for face in ("front", "rear"):
                    if face in local:
                        combined[f"_local_{face}_image"] = True
                        combined[f"_{face}_image_available"] = True
                        combined[f"_{face}_image_source"] = "netdoc"
                        combined[f"{face}_image"] = (
                            f"/media/device-types/{device_type_id}/{face}"
                        )
            hydrated.append({
                **device,
                "device_type": combined,
            })
        return hydrated

    async def list_rack_devices(
        self,
        rack_id: int,
    ) -> list[dict[str, Any]]:
        devices = await self.get_all(
            "/api/dcim/devices/",
            params={
                "rack_id": rack_id,
                "ordering": "position,name",
            },
        )
        return await self.hydrate_device_types(devices)

    async def list_devices(
        self,
        *,
        site_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "ordering": "site,rack,position,name",
        }
        if site_id:
            params["site_id"] = site_id
        devices = await self.get_all(
            "/api/dcim/devices/",
            params=params,
            page_limit=500,
            maximum_pages=100,
        )
        return await self.hydrate_device_types(devices)

    def _safe_image_url(self, raw_url: Any) -> str:
        if isinstance(raw_url, dict):
            raw_url = raw_url.get("url") or raw_url.get("value")
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise RackServiceError(
                "El modelo no tiene una imagen para esta cara.",
                status_code=404,
            )

        resolved = urljoin(f"{self.base_url}/", raw_url.strip())
        expected = urlparse(self.base_url)
        candidate = urlparse(resolved)
        if (
            candidate.scheme not in {"http", "https"}
            or candidate.scheme != expected.scheme
            or candidate.netloc != expected.netloc
        ):
            raise RackServiceError(
                "La imagen del modelo apunta fuera del servidor NetBox.",
                status_code=400,
            )
        return resolved

    async def get_device_type_image(
        self,
        device_type_id: int,
        face: str,
    ) -> tuple[bytes, str, str]:
        if face not in {"front", "rear"}:
            raise RackServiceError("La cara solicitada no es válida.", 400)

        try:
            local = DeviceImageService().get_local_image(device_type_id, face)
        except DeviceTypeServiceError as exc:
            raise self._local_error(exc) from exc
        if local is not None:
            return local

        device_type = await self.get_device_type(device_type_id)
        image_url = self._safe_image_url(
            device_type.get(f"{face}_image")
        )

        try:
            if self._client is not None:
                response = await self._client.get(
                    image_url,
                    headers={"Accept": "image/*"},
                )
            else:
                async with self._build_client() as client:
                    response = await client.get(
                        image_url,
                        headers={"Accept": "image/*"},
                    )
        except httpx.ConnectError as exc:
            raise RackServiceError(
                "No fue posible descargar la imagen desde NetBox."
            ) from exc
        except httpx.TimeoutException as exc:
            raise RackServiceError(
                "NetBox tardó demasiado en entregar la imagen."
            ) from exc

        if response.is_error:
            raise RackServiceError(
                "NetBox no pudo entregar la imagen del modelo.",
                response.status_code,
            )

        content_type = response.headers.get("content-type", "").split(";")[0]
        if not content_type.startswith("image/"):
            raise RackServiceError(
                "El archivo documentado no es una imagen válida.",
                status_code=415,
            )
        if len(response.content) > self._maximum_image_bytes:
            raise RackServiceError(
                "La imagen supera el límite de 5 MB.",
                status_code=413,
            )
        return (
            response.content,
            content_type,
            sha256(response.content).hexdigest(),
        )
