from __future__ import annotations

import asyncio
from ipaddress import IPv4Network, IPv6Network, ip_network
from typing import Any

from app.services.change_plan import ChangePlan, ChangePlanError, ChangeStep
from app.services.connection_service import (
    ConnectionService,
    ConnectionServiceError,
)
from app.services.ipam_service import nested_label, vrf_identifier
from app.services.netbox_capabilities import validate_plan_capabilities
from app.services.netbox_schema_service import (
    ActionSchema,
    parse_action_schema,
)


Network = IPv4Network | IPv6Network
PREFIX_ENDPOINT = "/api/ipam/prefixes/"
DEFAULT_STATUSES = (
    {"value": "active", "label": "Activo"},
    {"value": "reserved", "label": "Reservado"},
    {"value": "deprecated", "label": "Deprecado"},
    {"value": "container", "label": "Contenedor"},
)
SCOPE_ENDPOINTS = (
    ("dcim.site", "Site", "/api/dcim/sites/"),
    ("dcim.location", "Ubicación", "/api/dcim/locations/"),
    ("dcim.region", "Región", "/api/dcim/regions/"),
    ("dcim.sitegroup", "Grupo de sites", "/api/dcim/site-groups/"),
)


class IPAMPoolServiceError(Exception):
    """Error controlado al validar o crear un pool en NetBox."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def default_pool_form() -> dict[str, str]:
    return {
        "prefix": "",
        "status": "active",
        "vrf_id": "",
        "role_id": "",
        "scope": "",
        "description": "",
        "change_reason": "",
        "parent_id": "",
    }


def parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def canonical_network(value: str) -> Network:
    clean_value = value.strip()
    if not clean_value:
        raise ValueError("El prefijo del pool es obligatorio.")
    if "/" not in clean_value:
        raise ValueError(
            "Escribe el pool en formato CIDR, por ejemplo 192.0.2.0/24."
        )
    try:
        return ip_network(clean_value, strict=True)
    except ValueError as exc:
        raise ValueError(
            "El CIDR no es válido o contiene bits de host. "
            "Usa la dirección de red exacta."
        ) from exc


def network_from_prefix(value: dict[str, Any]) -> Network | None:
    raw = value.get("prefix") or value.get("display")
    if not isinstance(raw, str):
        return None
    try:
        return ip_network(raw, strict=False)
    except ValueError:
        return None


def _choice_label(
    items: list[dict[str, Any]],
    selected_id: int | None,
    fallback: str,
) -> str:
    if selected_id is None:
        return fallback
    selected = next(
        (item for item in items if item.get("id") == selected_id),
        None,
    )
    if isinstance(selected, dict) and selected.get("_form_label"):
        return str(selected["_form_label"])
    return nested_label(selected, f"ID {selected_id}")


def _scope_parts(value: str) -> tuple[str, int] | None:
    clean_value = value.strip()
    if not clean_value:
        return None
    scope_type, separator, raw_id = clean_value.partition(":")
    if not separator or scope_type not in {
        item[0] for item in SCOPE_ENDPOINTS
    }:
        return None
    scope_id = parse_positive_int(raw_id)
    if scope_id is None:
        return None
    return scope_type, scope_id


def validate_pool_form(
    form_data: dict[str, str],
    *,
    form_options: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Normaliza el formulario sin decidir silenciosamente relaciones."""

    errors: list[str] = []
    try:
        network = canonical_network(form_data.get("prefix", ""))
    except ValueError as exc:
        network = None
        errors.append(str(exc))

    statuses = {
        str(item.get("value"))
        for item in form_options.get("statuses", [])
        if item.get("value") not in (None, "")
    }
    status = form_data.get("status", "").strip()
    if not status or status not in statuses:
        errors.append("Selecciona un estado aceptado por NetBox.")

    vrf_id = parse_positive_int(form_data.get("vrf_id"))
    role_id = parse_positive_int(form_data.get("role_id"))
    parent_id = parse_positive_int(form_data.get("parent_id"))

    if form_data.get("vrf_id", "").strip() and vrf_id is None:
        errors.append("La VRF seleccionada no es válida.")
    if form_data.get("role_id", "").strip() and role_id is None:
        errors.append("El rol IPAM seleccionado no es válido.")
    if form_data.get("parent_id", "").strip() and parent_id is None:
        errors.append("El prefijo padre seleccionado no es válido.")

    known_vrfs = {
        item.get("id") for item in form_options.get("vrfs", [])
    }
    known_roles = {
        item.get("id") for item in form_options.get("roles", [])
    }
    if vrf_id is not None and vrf_id not in known_vrfs:
        errors.append("La VRF seleccionada ya no existe o no es visible.")
    if role_id is not None and role_id not in known_roles:
        errors.append("El rol IPAM seleccionado ya no existe o no es visible.")

    raw_scope = form_data.get("scope", "").strip()
    scope = _scope_parts(raw_scope)
    known_scopes = {
        str(item.get("value"))
        for item in form_options.get("scopes", [])
    }
    if raw_scope and (scope is None or raw_scope not in known_scopes):
        errors.append("La localidad seleccionada ya no existe o no es visible.")

    description = form_data.get("description", "").strip()
    change_reason = form_data.get("change_reason", "").strip()
    if len(description) > 200:
        errors.append("La descripción no puede superar 200 caracteres.")
    if not change_reason:
        errors.append(
            "Indica el motivo operativo para dejar trazabilidad del pool."
        )
    elif len(change_reason) > 300:
        errors.append("El motivo no puede superar 300 caracteres.")

    normalized = {
        "network": network,
        "prefix": str(network) if network is not None else "",
        "status": status,
        "vrf_id": vrf_id,
        "role_id": role_id,
        "scope_type": scope[0] if scope else None,
        "scope_id": scope[1] if scope else None,
        "scope_value": raw_scope,
        "description": description,
        "change_reason": change_reason,
        "parent_id": parent_id,
    }
    return normalized, errors


class IPAMPoolService:
    def __init__(self) -> None:
        self.client = ConnectionService()

    async def __aenter__(self) -> IPAMPoolService:
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        await self.client.__aexit__(exc_type, exc_value, traceback)

    async def _get_all(
        self,
        endpoint: str,
        *,
        params: dict[str, Any],
        maximum_pages: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            return await self.client.get_all(
                endpoint,
                params=params,
                page_limit=200,
                maximum_pages=maximum_pages,
            )
        except ConnectionServiceError as exc:
            raise IPAMPoolServiceError(
                exc.message,
                exc.status_code,
            ) from exc

    async def load_form_options(self) -> dict[str, Any]:
        async def load_scope(
            scope_type: str,
            group: str,
            endpoint: str,
        ) -> list[dict[str, Any]]:
            params: dict[str, Any] = {
                "ordering": "name",
                "brief": "true",
            }
            if scope_type == "dcim.location":
                params = {
                    "ordering": "site,name",
                    "fields": "id,display,name,site",
                }
            items = await self._get_all(
                endpoint,
                params=params,
            )
            output: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item.get("id"), int):
                    continue
                label = nested_label(item, "Sin nombre")
                site = item.get("site") or {}
                site_label = nested_label(site, "")
                if site_label and site_label.casefold() not in label.casefold():
                    label = f"{site_label} · {label}"
                output.append({
                    "value": f"{scope_type}:{item.get('id')}",
                    "label": label,
                    "group": group,
                })
            return output

        try:
            options_payload, roles, vrfs, *scope_groups = await asyncio.gather(
                self.client.request("OPTIONS", PREFIX_ENDPOINT),
                self._get_all(
                    "/api/ipam/roles/",
                    params={"ordering": "name", "brief": "true"},
                ),
                self._get_all(
                    "/api/ipam/vrfs/",
                    params={
                        "ordering": "name",
                        "fields": "id,display,name,rd",
                    },
                ),
                *(
                    load_scope(scope_type, group, endpoint)
                    for scope_type, group, endpoint in SCOPE_ENDPOINTS
                ),
            )
        except ConnectionServiceError as exc:
            raise IPAMPoolServiceError(
                exc.message,
                exc.status_code,
            ) from exc

        try:
            schema = parse_action_schema(
                options_payload,
                endpoint=PREFIX_ENDPOINT,
                method="POST",
            )
        except ChangePlanError as exc:
            raise IPAMPoolServiceError(str(exc)) from exc

        status_field = schema.fields.get("status")
        statuses = (
            [dict(item) for item in status_field.choices]
            if status_field and status_field.choices
            else [dict(item) for item in DEFAULT_STATUSES]
        )
        scopes = [
            item
            for group in scope_groups
            for item in group
        ]
        decorated_vrfs = []
        for vrf in vrfs:
            label = nested_label(vrf, "Sin nombre")
            rd = str(vrf.get("rd") or "").strip()
            if rd and rd.casefold() not in label.casefold():
                label = f"{label} · RD {rd}"
            decorated_vrfs.append({**vrf, "_form_label": label})
        return {
            "schema": schema,
            "statuses": statuses,
            "roles": roles,
            "vrfs": decorated_vrfs,
            "scopes": scopes,
        }

    async def list_prefixes_for_analysis(
        self,
        *,
        network: Network,
        vrf_id: int | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "family": network.version,
            "ordering": "prefix",
            "fields": (
                "id,display,prefix,vrf,scope_type,scope_id,scope,status,"
                "role,is_pool,mark_utilized,description,last_updated"
            ),
        }
        if vrf_id is not None:
            params["vrf_id"] = vrf_id
        prefixes = await self._get_all(
            PREFIX_ENDPOINT,
            params=params,
            maximum_pages=25,
        )
        return [
            item
            for item in prefixes
            if vrf_identifier(item) == vrf_id
        ]

    async def get_prefix(self, prefix_id: int) -> dict[str, Any]:
        try:
            result = await self.client.request(
                "GET",
                f"/api/ipam/prefixes/{prefix_id}/",
            )
        except ConnectionServiceError as exc:
            raise IPAMPoolServiceError(
                exc.message,
                exc.status_code,
            ) from exc
        if not isinstance(result, dict):
            raise IPAMPoolServiceError(
                "NetBox devolvió un prefijo padre inválido."
            )
        return result

    async def prefill_from_parent(
        self,
        *,
        parent_id: int,
        form_data: dict[str, str],
    ) -> dict[str, Any]:
        parent = await self.get_prefix(parent_id)
        parent_vrf_id = vrf_identifier(parent)
        role = parent.get("role") or {}
        scope_type = str(parent.get("scope_type") or "")
        scope_id = parse_positive_int(parent.get("scope_id"))

        form_data["parent_id"] = str(parent_id)
        if parent_vrf_id is not None:
            form_data["vrf_id"] = str(parent_vrf_id)
        if isinstance(role, dict) and isinstance(role.get("id"), int):
            form_data["role_id"] = str(role["id"])
        if scope_type and scope_id:
            form_data["scope"] = f"{scope_type}:{scope_id}"
        return parent

    @staticmethod
    def analyze_candidate(
        *,
        network: Network,
        prefixes: list[dict[str, Any]],
        parent_id: int | None,
    ) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        exact: list[dict[str, Any]] = []
        parents: list[tuple[Network, dict[str, Any]]] = []
        children: list[tuple[Network, dict[str, Any]]] = []

        for item in prefixes:
            existing = network_from_prefix(item)
            if existing is None or existing.version != network.version:
                continue
            if existing == network:
                exact.append(item)
            elif network.subnet_of(existing):
                parents.append((existing, item))
            elif existing.subnet_of(network):
                children.append((existing, item))

        if exact:
            errors.append(
                "Ya existe el mismo prefijo en la VRF seleccionada. "
                "No se creó un pool duplicado."
            )

        selected_parent: dict[str, Any] | None = None
        if parent_id is not None:
            selected_parent = next(
                (
                    item
                    for item in prefixes
                    if item.get("id") == parent_id
                ),
                None,
            )
            selected_network = (
                network_from_prefix(selected_parent)
                if selected_parent is not None
                else None
            )
            if selected_network is None:
                errors.append(
                    "El prefijo padre ya no existe en la VRF seleccionada."
                )
            elif not network.subnet_of(selected_network):
                errors.append(
                    "El CIDR propuesto no está contenido en el prefijo padre."
                )
        elif parents:
            selected_parent = max(
                parents,
                key=lambda item: item[0].prefixlen,
            )[1]

        warnings: list[str] = []
        if selected_parent is None:
            warnings.append(
                "No se encontró un prefijo padre documentado en esta VRF. "
                "Confirma que se trata de un bloque raíz."
            )
        elif selected_parent.get("is_pool") is True:
            warnings.append(
                "El nuevo bloque quedará dentro de otro pool. "
                "Revisa que no represente el mismo rango operativo."
            )

        if children:
            child_pools = sum(
                1 for _, item in children if item.get("is_pool") is True
            )
            detail = (
                f" e incluye {child_pools} pool(s) existente(s)"
                if child_pools
                else ""
            )
            warnings.append(
                f"El bloque contiene {len(children)} prefijo(s) hijo(s){detail}. "
                "Esos objetos no serán modificados."
            )

        snapshot = [
            {
                "id": item.get("id"),
                "prefix": str(existing),
                "last_updated": item.get("last_updated"),
                "is_pool": item.get("is_pool") is True,
            }
            for existing, item in sorted(
                parents + children,
                key=lambda value: (
                    int(value[0].network_address),
                    value[0].prefixlen,
                ),
            )
        ]
        analysis = {
            "parent": selected_parent,
            "children": [item for _, item in children],
            "warnings": warnings,
            "snapshot": snapshot,
        }
        return analysis, errors

    async def prepare_plan(
        self,
        *,
        form_data: dict[str, str],
        requested_by: str,
        form_options: dict[str, Any] | None = None,
    ) -> tuple[
        ChangePlan | None,
        dict[str, Any],
        dict[str, Any],
        list[str],
    ]:
        options = form_options or await self.load_form_options()
        normalized, errors = validate_pool_form(
            form_data,
            form_options=options,
        )
        network = normalized["network"]
        if errors or network is None:
            return None, normalized, {}, errors

        prefixes = await self.list_prefixes_for_analysis(
            network=network,
            vrf_id=normalized["vrf_id"],
        )
        analysis, overlap_errors = self.analyze_candidate(
            network=network,
            prefixes=prefixes,
            parent_id=normalized["parent_id"],
        )
        errors.extend(overlap_errors)
        if errors:
            return None, normalized, analysis, errors

        payload: dict[str, Any] = {
            "prefix": normalized["prefix"],
            "status": normalized["status"],
            "is_pool": True,
            "mark_utilized": False,
            "changelog_message": (
                "Pool creado desde NetDoc por "
                f"{requested_by}: {normalized['change_reason']}"
            ),
        }
        for key in ("vrf_id", "role_id"):
            value = normalized[key]
            if value is not None:
                payload[key.removesuffix("_id")] = value
        if normalized["scope_type"] and normalized["scope_id"]:
            payload["scope_type"] = normalized["scope_type"]
            payload["scope_id"] = normalized["scope_id"]
        if normalized["description"]:
            payload["description"] = normalized["description"]

        schema = options["schema"]
        if not isinstance(schema, ActionSchema):
            return (
                None,
                normalized,
                analysis,
                ["No fue posible validar el esquema REST de NetBox."],
            )
        try:
            schema.validate_payload(payload)
            step = ChangeStep(
                step_id="create-ipam-pool",
                action="create",
                resource="ipam.prefix",
                method="POST",
                endpoint=PREFIX_ENDPOINT,
                payload=payload,
                summary=f"Crear pool {normalized['prefix']}",
                required_permission="devices.create",
                change_reason=normalized["change_reason"],
            )
            validate_plan_capabilities((step,))
            plan = ChangePlan(
                intent=f"Crear el pool {normalized['prefix']} en NetBox",
                requested_by=requested_by,
                steps=(step,),
                warnings=tuple(analysis["warnings"]),
                metadata={
                    "parent_id": (
                        analysis.get("parent") or {}
                    ).get("id"),
                    "overlap_snapshot": analysis["snapshot"],
                },
            )
        except ChangePlanError as exc:
            return None, normalized, analysis, [str(exc)]

        normalized["vrf_label"] = _choice_label(
            options["vrfs"],
            normalized["vrf_id"],
            "Global",
        )
        normalized["role_label"] = _choice_label(
            options["roles"],
            normalized["role_id"],
            "Sin rol",
        )
        normalized["scope_label"] = next(
            (
                str(item.get("label"))
                for item in options["scopes"]
                if item.get("value") == normalized["scope_value"]
            ),
            "Sin localidad",
        )
        normalized["status_label"] = next(
            (
                str(item.get("label"))
                for item in options["statuses"]
                if item.get("value") == normalized["status"]
            ),
            normalized["status"],
        )
        return plan, normalized, analysis, []

    async def create_pool(self, plan: ChangePlan) -> dict[str, Any]:
        validate_plan_capabilities(plan.steps)
        step = plan.steps[0]
        try:
            result = await self.client.request(
                step.method,
                step.endpoint,
                json_body=step.payload,
            )
        except ConnectionServiceError as exc:
            raise IPAMPoolServiceError(
                exc.message,
                exc.status_code,
            ) from exc
        if not isinstance(result, dict):
            raise IPAMPoolServiceError(
                "NetBox creó el pool, pero devolvió un formato inesperado."
            )
        return result
