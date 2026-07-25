from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.change_plan import ChangePlanError


@dataclass(frozen=True)
class SchemaField:
    name: str
    field_type: str
    required: bool
    read_only: bool
    label: str
    help_text: str
    choices: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class ActionSchema:
    endpoint: str
    method: str
    fields: dict[str, SchemaField]

    @property
    def required_fields(self) -> set[str]:
        return {
            name
            for name, field in self.fields.items()
            if field.required and not field.read_only
        }

    @property
    def writable_fields(self) -> set[str]:
        return {
            name
            for name, field in self.fields.items()
            if not field.read_only
        }

    def validate_payload(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise ChangePlanError(
                "La validación de esquema requiere un objeto JSON individual."
            )

        allowed_virtual_fields = {"changelog_message", "custom_fields"}
        unknown = sorted(
            set(payload) - self.writable_fields - allowed_virtual_fields
        )
        if unknown:
            raise ChangePlanError(
                "El payload contiene campos no aceptados por NetBox: "
                + ", ".join(unknown)
            )

        missing = sorted(
            name
            for name in self.required_fields
            if payload.get(name) in (None, "", [])
        )
        if missing:
            raise ChangePlanError(
                "Faltan campos obligatorios según NetBox: "
                + ", ".join(missing)
            )

        for name, value in payload.items():
            field = self.fields.get(name)
            if field is None or not field.choices or value in (None, ""):
                continue
            allowed = {
                choice["value"]
                for choice in field.choices
                if choice.get("value") is not None
            }
            candidate = str(
                value.get("value")
                if isinstance(value, dict)
                else value
            )
            if allowed and candidate not in allowed:
                raise ChangePlanError(
                    f"El valor '{candidate}' no es válido para {name}."
                )


def _choice_items(value: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list):
        return ()

    choices: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        raw_value = item.get("value")
        if raw_value is None:
            continue
        label = (
            item.get("display_name")
            or item.get("label")
            or item.get("display")
            or raw_value
        )
        choices.append({
            "value": str(raw_value),
            "label": str(label),
        })
    return tuple(choices)


def parse_action_schema(
    payload: dict[str, Any],
    *,
    endpoint: str,
    method: str,
) -> ActionSchema:
    normalized_method = method.strip().upper()
    actions = payload.get("actions")
    if not isinstance(actions, dict):
        raise ChangePlanError("NetBox no devolvió la sección actions en OPTIONS.")

    raw_fields = actions.get(normalized_method)
    if not isinstance(raw_fields, dict):
        raise ChangePlanError(
            f"NetBox no anuncia soporte para {normalized_method} en {endpoint}."
        )

    fields: dict[str, SchemaField] = {}
    for name, metadata in raw_fields.items():
        if not isinstance(metadata, dict):
            continue
        fields[str(name)] = SchemaField(
            name=str(name),
            field_type=str(metadata.get("type") or "unknown"),
            required=metadata.get("required") is True,
            read_only=metadata.get("read_only") is True,
            label=str(metadata.get("label") or name),
            help_text=str(metadata.get("help_text") or ""),
            choices=_choice_items(metadata.get("choices")),
        )

    return ActionSchema(
        endpoint=endpoint,
        method=normalized_method,
        fields=fields,
    )


class NetBoxSchemaService:
    """Cliente de solo lectura para descubrir el contrato REST instalado."""

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
            "User-Agent": "NetDoc/0.10.0",
        }

    async def discover(
        self,
        endpoint: str,
        *,
        method: str,
    ) -> ActionSchema:
        clean_endpoint = endpoint.strip()
        if not clean_endpoint.startswith("/api/"):
            raise ChangePlanError("Solo se puede descubrir una ruta /api/ de NetBox.")
        if not clean_endpoint.endswith("/"):
            raise ChangePlanError("La ruta REST debe terminar en '/'.")

        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                verify=self.settings.netbox_verify_ssl,
                timeout=self.settings.netbox_timeout,
                follow_redirects=True,
            ) as client:
                response = await client.options(
                    f"{self.base_url}{clean_endpoint}"
                )
        except httpx.ConnectError as exc:
            raise ChangePlanError(
                f"No fue posible conectar con NetBox en {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ChangePlanError(
                "NetBox no respondió al consultar el esquema."
            ) from exc

        if response.is_error:
            raise ChangePlanError(
                f"NetBox rechazó OPTIONS con HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ChangePlanError(
                "NetBox no devolvió JSON válido para OPTIONS."
            ) from exc
        if not isinstance(payload, dict):
            raise ChangePlanError(
                "NetBox devolvió un esquema OPTIONS inesperado."
            )

        return parse_action_schema(
            payload,
            endpoint=clean_endpoint,
            method=method,
        )
