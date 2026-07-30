from __future__ import annotations

import asyncio
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
    TERMINATION_ENDPOINTS = {
        "dcim.interface": "/api/dcim/interfaces/{id}/",
        "dcim.frontport": "/api/dcim/front-ports/{id}/",
        "dcim.rearport": "/api/dcim/rear-ports/{id}/",
        "dcim.consoleport": "/api/dcim/console-ports/{id}/",
        "dcim.consoleserverport": "/api/dcim/console-server-ports/{id}/",
        "dcim.powerport": "/api/dcim/power-ports/{id}/",
        "dcim.poweroutlet": "/api/dcim/power-outlets/{id}/",
        "circuits.circuittermination": "/api/circuits/circuit-terminations/{id}/",
    }

    CABLE_TYPE_LABELS = {
        "cat3": "Cobre CAT3",
        "cat5e": "Cobre CAT5e",
        "cat6": "Cobre CAT6",
        "cat6a": "Cobre CAT6A",
        "cat7": "Cobre CAT7",
        "dac-active": "DAC activo",
        "dac-passive": "DAC pasivo",
        "coaxial": "Coaxial",
        "mmf-om1": "Fibra multimodo OM1",
        "mmf-om2": "Fibra multimodo OM2",
        "mmf-om3": "Fibra multimodo OM3",
        "mmf-om4": "Fibra multimodo OM4",
        "mmf-om5": "Fibra multimodo OM5",
        "smf-os1": "Fibra monomodo OS1",
        "smf-os2": "Fibra monomodo OS2",
        "aoc": "Cable óptico activo",
        "power": "Energía",
    }

    STATUS_LABELS = {
        "connected": "Conectado",
        "planned": "Planificado",
        "decommissioning": "En retiro",
    }

    UNIT_LABELS = {
        "mm": "mm",
        "cm": "cm",
        "m": "m",
        "km": "km",
        "in": "pulg",
        "ft": "pies",
        "yd": "yardas",
        "mi": "millas",
    }

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

    async def __aenter__(self) -> ConnectionService:
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
            "User-Agent": f"NetDoc/{self.settings.app_version}",
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

        if isinstance(payload, list):
            messages: list[str] = []

            for index, item in enumerate(payload, start=1):
                if not isinstance(item, dict):
                    continue

                item_messages: list[str] = []
                for field, value in item.items():
                    text = (
                        ", ".join(str(part) for part in value)
                        if isinstance(value, list)
                        else str(value)
                    )
                    item_messages.append(f"{field}: {text}")

                if item_messages:
                    messages.append(
                        f"Conexión {index}: "
                        + " | ".join(item_messages)
                    )

            return (
                " || ".join(messages)
                or f"NetBox respondió con HTTP {response.status_code}.",
                {"items": payload},
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

    async def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value not in (None, "")
        }

        try:
            if self._client is not None:
                response = await self._client.request(
                    method=method,
                    url=endpoint.lstrip("/"),
                    params=clean_params,
                    json=json_body,
                )
            else:
                async with self._build_client() as client:
                    response = await client.request(
                        method=method,
                        url=endpoint.lstrip("/"),
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

        return payload

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> dict[str, Any]:
        payload = await self._request_json(
            method,
            endpoint,
            params=params,
            json_body=json_body,
        )

        if not isinstance(payload, dict):
            raise ConnectionServiceError(
                "NetBox devolvió un formato de respuesta inesperado."
            )

        return payload

    async def request_many(
        self,
        method: str,
        endpoint: str,
        *,
        json_body: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = await self._request_json(
            method,
            endpoint,
            json_body=json_body,
        )

        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise ConnectionServiceError(
                "NetBox no devolvió el listado esperado para el lote."
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

    @staticmethod
    def _choice_value(value: Any) -> str:
        if isinstance(value, dict):
            return str(
                value.get("value")
                or value.get("slug")
                or value.get("name")
                or ""
            )
        return str(value or "")

    @staticmethod
    def _choice_display(value: Any) -> str:
        if isinstance(value, dict):
            return str(
                value.get("label")
                or value.get("display")
                or value.get("name")
                or value.get("value")
                or ""
            )
        return str(value or "")

    @classmethod
    def _translated_choice(
        cls,
        value: Any,
        translations: dict[str, str],
        fallback: str = "—",
    ) -> str:
        raw_value = cls._choice_value(value).strip()
        display = cls._choice_display(value).strip()
        return (
            translations.get(raw_value.lower())
            or translations.get(display.lower())
            or display
            or raw_value
            or fallback
        )

    async def get_cable_choices(
        self,
    ) -> dict[str, list[dict[str, str]]]:
        try:
            payload = await self.request(
                "OPTIONS",
                "/api/dcim/cables/",
            )
            fields = payload.get("actions", {}).get("POST", {})

            def choices(
                name: str,
                translations: dict[str, str] | None = None,
            ) -> list[dict[str, str]]:
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
                        translated = (
                            (translations or {}).get(str(value).lower())
                            or (translations or {}).get(str(label).lower())
                            or str(label)
                        )
                        output.append({
                            "value": str(value),
                            "label": translated,
                        })

                return output

            return {
                "types": choices("type", self.CABLE_TYPE_LABELS),
                "statuses": choices("status", self.STATUS_LABELS),
                "length_units": choices("length_unit", self.UNIT_LABELS),
            }

        except (
            ConnectionServiceError,
            ValueError,
            AttributeError,
        ):
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

    @classmethod
    def _termination_key(
        cls,
        termination: Any,
    ) -> tuple[str, int] | None:
        if not isinstance(termination, dict):
            return None

        object_type = termination.get("object_type")
        if isinstance(object_type, dict):
            object_type = (
                object_type.get("value")
                or object_type.get("model")
                or object_type.get("display")
            )

        object_id = termination.get("object_id")
        nested_object = termination.get("object")
        if not isinstance(object_id, int) and isinstance(nested_object, dict):
            object_id = nested_object.get("id")

        if not isinstance(object_type, str) or not isinstance(object_id, int):
            return None

        normalized_type = object_type.strip().lower()
        if normalized_type not in cls.TERMINATION_ENDPOINTS:
            return None

        return normalized_type, object_id

    @staticmethod
    def _meaningful_text(value: Any) -> str:
        text = str(value or "").strip()
        return "" if not text or text.isdigit() else text

    @classmethod
    def _object_label(
        cls,
        value: Any,
        object_type: str = "",
    ) -> str:
        if not isinstance(value, dict):
            return cls._meaningful_text(value)

        device = value.get("device") or value.get("parent") or {}
        device_label = ""
        if isinstance(device, dict):
            device_label = cls._meaningful_text(
                device.get("display") or device.get("name")
            )

        name = cls._meaningful_text(
            value.get("name")
            or value.get("label")
            or value.get("display")
        )

        if device_label and name:
            if device_label.casefold() in name.casefold():
                return name
            return f"{device_label} · {name}"

        circuit = value.get("circuit") or {}
        if isinstance(circuit, dict):
            circuit_label = cls._meaningful_text(
                circuit.get("display") or circuit.get("cid")
            )
            side = cls._meaningful_text(value.get("term_side"))
            if circuit_label:
                return (
                    f"{circuit_label} · extremo {side}"
                    if side
                    else circuit_label
                )

        return name or device_label

    @classmethod
    def _termination_label(
        cls,
        termination: Any,
        hydrated: dict[str, Any] | None = None,
    ) -> str:
        if not isinstance(termination, dict):
            return "—"

        key = cls._termination_key(termination)
        object_type = key[0] if key else ""
        nested = termination.get("object")

        for candidate in (
            hydrated,
            nested,
            termination,
        ):
            label = cls._object_label(candidate, object_type)
            if label:
                return label

        if key:
            friendly = {
                "dcim.interface": "Interfaz",
                "dcim.frontport": "Puerto frontal",
                "dcim.rearport": "Puerto trasero",
                "dcim.consoleport": "Puerto de consola",
                "dcim.consoleserverport": "Puerto de servidor de consola",
                "dcim.powerport": "Puerto de energía",
                "dcim.poweroutlet": "Toma de energía",
                "circuits.circuittermination": "Terminación de circuito",
            }.get(key[0], "Terminación")
            return f"{friendly} #{key[1]}"

        return "—"

    async def _load_termination_objects(
        self,
        cables: list[dict[str, Any]],
    ) -> dict[tuple[str, int], dict[str, Any]]:
        keys: set[tuple[str, int]] = set()
        for cable in cables:
            for side in ("a_terminations", "b_terminations"):
                terminations = cable.get(side) or []
                if isinstance(terminations, list) and terminations:
                    termination = terminations[0]
                    nested = (
                        termination.get("object")
                        if isinstance(termination, dict)
                        else None
                    )
                    if self._object_label(nested):
                        continue
                    key = self._termination_key(termination)
                    if key:
                        keys.add(key)

        semaphore = asyncio.Semaphore(8)

        async def load(
            key: tuple[str, int],
        ) -> tuple[tuple[str, int], dict[str, Any] | None]:
            endpoint = self.TERMINATION_ENDPOINTS[key[0]].format(id=key[1])
            try:
                async with semaphore:
                    return key, await self.request("GET", endpoint)
            except ConnectionServiceError:
                return key, None

        loaded = await asyncio.gather(*(load(key) for key in keys))
        return {
            key: value
            for key, value in loaded
            if isinstance(value, dict)
        }

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
        cables = results if isinstance(results, list) else []
        hydrated = await self._load_termination_objects(cables)
        prepared: list[dict[str, Any]] = []

        for cable in cables:
            a_terminations = cable.get("a_terminations") or []
            b_terminations = cable.get("b_terminations") or []
            a_term = a_terminations[0] if isinstance(a_terminations, list) and a_terminations else {}
            b_term = b_terminations[0] if isinstance(b_terminations, list) and b_terminations else {}
            a_key = self._termination_key(a_term)
            b_key = self._termination_key(b_term)

            length = cable.get("length")
            unit_label = self._translated_choice(
                cable.get("length_unit"),
                self.UNIT_LABELS,
                "",
            )

            prepared.append({
                **cable,
                "_a_label": self._termination_label(
                    a_term,
                    hydrated.get(a_key) if a_key else None,
                ),
                "_b_label": self._termination_label(
                    b_term,
                    hydrated.get(b_key) if b_key else None,
                ),
                "_type_label": self._translated_choice(
                    cable.get("type"),
                    self.CABLE_TYPE_LABELS,
                ),
                "_status_label": self._translated_choice(
                    cable.get("status"),
                    self.STATUS_LABELS,
                ),
                "_length_label": (
                    f"{length} {unit_label}".strip()
                    if length not in (None, "")
                    else "—"
                ),
            })

        return prepared

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
        created = await self.create_interface_cables(
            connections=[
                {
                    "interface_a_id": interface_a_id,
                    "interface_b_id": interface_b_id,
                    "label": label,
                }
            ],
            cable_type=cable_type,
            status=status,
            color=color,
            length=length,
            length_unit=length_unit,
            description=description,
            username=username,
        )

        if len(created) != 1:
            raise ConnectionServiceError(
                "NetBox no confirmó la creación de la conexión."
            )

        return created[0]

    async def create_interface_cables(
        self,
        *,
        connections: list[dict[str, Any]],
        cable_type: str,
        status: str,
        color: str,
        length: Decimal | None,
        length_unit: str,
        description: str,
        username: str,
    ) -> list[dict[str, Any]]:
        payloads = [
            self._cable_payload(
                interface_a_id=int(item["interface_a_id"]),
                interface_b_id=int(item["interface_b_id"]),
                cable_type=cable_type,
                status=status,
                label=str(item.get("label") or ""),
                color=color,
                length=length,
                length_unit=length_unit,
                description=description,
                username=username,
            )
            for item in connections
        ]

        return await self.request_many(
            "POST",
            "/api/dcim/cables/",
            json_body=payloads,
        )

    @staticmethod
    def _cable_payload(
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

        return payload
