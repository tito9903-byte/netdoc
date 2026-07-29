from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from app.services.lldp_discovery_service import (
    LldpDiscoveryError,
    LldpDiscoveryService,
    LldpObservation,
)


_PATCH_MARKER = "_netdoc_lldp_matching_revision"
MATCHING_REVISION = "20260727-name-and-assigned-ip-required-v3"


@dataclass(frozen=True)
class CandidateResolution:
    candidate: dict[str, Any] | None
    selected_by: str
    sources: tuple[str, ...]
    identity_verified: bool
    message: str = ""


def _nested_id(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and isinstance(value.get("id"), int):
        return int(value["id"])
    return None


async def _assigned_ip_map(
    service: LldpDiscoveryService,
    devices: list[dict[str, Any]],
    observations: list[LldpObservation],
) -> dict[int, set[str]]:
    """Relaciona cada equipo con todas sus IP conocidas en NetBox.

    Las IP principales se toman del propio objeto del dispositivo. Para cada IP
    anunciada por LLDP también se consulta IPAM y se acepta cuando está asignada a
    cualquier interfaz del dispositivo, aunque no sea su IP principal.
    """

    device_ips: dict[int, set[str]] = {}
    for device in devices:
        device_id = _nested_id(device.get("id"))
        if device_id is not None:
            device_ips[device_id] = set(service._device_primary_ips(device))

    announced_ips = sorted({
        service._address_text(item.management_ip)
        for item in observations
        if service._address_text(item.management_ip)
    })

    async def lookup(address: str) -> tuple[str, list[dict[str, Any]]]:
        try:
            rows = await service.client.get_all(
                "/api/ipam/ip-addresses/",
                params={"q": address, "ordering": "address"},
            )
        except Exception:
            # La validación seguirá fallando de forma segura si IPAM no responde.
            rows = []
        return address, rows

    lookups = await asyncio.gather(*(lookup(address) for address in announced_ips))
    for announced, rows in lookups:
        for row in rows:
            if service._address_text(row.get("address") or row.get("display")) != announced:
                continue
            assigned_object = row.get("assigned_object") or {}
            device_reference = (
                assigned_object.get("device")
                if isinstance(assigned_object, dict)
                else None
            ) or row.get("device") or {}
            device_id = _nested_id(device_reference)
            if device_id is not None and device_id in device_ips:
                device_ips.setdefault(device_id, set()).add(announced)

    return device_ips


def _candidate_identity(
    service: LldpDiscoveryService,
    observation: LldpObservation,
    devices: list[dict[str, Any]],
    device_ips: dict[int, set[str]],
) -> CandidateResolution:
    remote_full = service._normalize_name(observation.remote_system_name)
    remote_short = service._short_name(observation.remote_system_name)
    management_ip = service._address_text(observation.management_ip)

    matches: list[tuple[dict[str, Any], bool, bool, bool, bool]] = []
    for device in devices:
        device_id = _nested_id(device.get("id"))
        name = device.get("name") or device.get("display") or ""
        full_match = bool(remote_full and service._normalize_name(name) == remote_full)
        short_match = bool(remote_short and service._short_name(name) == remote_short)
        primary_ip_match = bool(
            management_ip
            and management_ip in service._device_primary_ips(device)
        )
        assigned_ip_match = bool(
            management_ip
            and device_id is not None
            and management_ip in device_ips.get(device_id, set())
        )
        if full_match or short_match or assigned_ip_match:
            matches.append((
                device,
                full_match,
                short_match,
                assigned_ip_match,
                primary_ip_match,
            ))

    exact_matches = [row for row in matches if row[1]]
    short_matches = [row for row in matches if row[2]]
    ip_matches = [row for row in matches if row[3]]

    name_match: tuple[dict[str, Any], bool, bool, bool, bool] | None = None
    name_method = ""
    if len(exact_matches) == 1:
        name_match = exact_matches[0]
        name_method = "name_exact"
    elif len(short_matches) == 1:
        name_match = short_matches[0]
        name_method = "name_short"

    ip_match = ip_matches[0] if len(ip_matches) == 1 else None

    if name_match is not None and ip_match is not None:
        name_device_id = _nested_id(name_match[0].get("id"))
        ip_device_id = _nested_id(ip_match[0].get("id"))
        name_label = "Nombre exacto" if name_method == "name_exact" else "Nombre corto"

        if name_device_id == ip_device_id:
            ip_label = "IP principal" if name_match[4] else "IP asignada"
            message = ""
            if not name_match[4]:
                message = (
                    "La IP anunciada está asignada a una interfaz del equipo remoto, "
                    "aunque no es su IP principal. La validación sigue siendo válida."
                )
            return CandidateResolution(
                candidate=name_match[0],
                selected_by=name_method,
                sources=(name_label, ip_label),
                identity_verified=True,
                message=message,
            )

        name_device = str(
            name_match[0].get("name") or name_match[0].get("display") or "equipo por nombre"
        )
        ip_device = str(
            ip_match[0].get("name") or ip_match[0].get("display") or "equipo por IP"
        )
        return CandidateResolution(
            candidate=name_match[0],
            selected_by="identity_conflict",
            sources=(name_label, "IP asignada a otro equipo"),
            identity_verified=False,
            message=(
                f"El nombre LLDP identifica {name_device}, pero la IP anunciada está "
                f"asignada a {ip_device}. NetDoc no permitirá documentar el cable hasta "
                "corregir esa diferencia."
            ),
        )

    if name_match is not None:
        name_label = "Nombre exacto" if name_method == "name_exact" else "Nombre corto"
        if not management_ip:
            message = (
                "El nombre coincide, pero LLDP no anunció una IP de administración. "
                "NetDoc requiere validar una IP asignada a alguna interfaz del equipo."
            )
        elif len(ip_matches) > 1:
            message = (
                "El nombre coincide, pero la IP anunciada aparece asignada a más de un "
                "equipo. Corrige la duplicidad en NetBox antes de documentar el cable."
            )
        else:
            message = (
                "El nombre coincide, pero la IP anunciada no está asignada a ninguna "
                "interfaz de ese equipo en NetBox. La propuesta queda pendiente."
            )
        return CandidateResolution(
            candidate=name_match[0],
            selected_by=f"{name_method}_ip_unverified",
            sources=(name_label, "IP sin validar"),
            identity_verified=False,
            message=message,
        )

    if ip_match is not None:
        ip_label = "IP principal" if ip_match[4] else "IP asignada"
        return CandidateResolution(
            candidate=ip_match[0],
            selected_by="management_ip",
            sources=(ip_label,),
            identity_verified=True,
            message=(
                "El equipo remoto fue identificado únicamente por una IP asignada en "
                "NetBox. La conexión puede documentarse si ambos puertos coinciden y "
                "están libres."
            ),
        )

    if not management_ip:
        message = (
            "LLDP no anunció una IP de administración y el nombre no identificó un "
            "equipo único en NetBox."
        )
    elif len(ip_matches) > 1:
        message = (
            "La IP anunciada aparece asignada a más de un equipo en NetBox y no puede "
            "utilizarse para una identificación segura."
        )
    else:
        message = (
            "La IP anunciada no está asignada a ninguna interfaz de un equipo en NetBox."
        )
    return CandidateResolution(
        candidate=None,
        selected_by="",
        sources=(),
        identity_verified=False,
        message=message,
    )


async def _match_observations_name_and_ip(
    self: LldpDiscoveryService,
    *,
    local_device: dict[str, Any],
    observations: list[LldpObservation],
) -> list[dict[str, Any]]:
    local_device_id = local_device.get("id")
    if not isinstance(local_device_id, int):
        raise LldpDiscoveryError("NetBox devolvió un dispositivo sin ID.", 502)

    all_devices, local_interfaces = await asyncio.gather(
        self.client.get_all(
            "/api/dcim/devices/",
            params={"ordering": "name"},
        ),
        self.client.get_all(
            "/api/dcim/interfaces/",
            params={"device_id": local_device_id, "ordering": "name"},
        ),
    )
    devices = [
        device
        for device in all_devices
        if isinstance(device.get("id"), int)
        and device.get("id") != local_device_id
    ]
    local_by_name = {
        self._normalize_interface(item.get("name")): item
        for item in local_interfaces
        if self._normalize_interface(item.get("name"))
    }

    device_ips = await _assigned_ip_map(self, devices, observations)
    resolutions = [
        _candidate_identity(self, observation, devices, device_ips)
        for observation in observations
    ]
    candidate_ids = {
        int(resolution.candidate["id"])
        for resolution in resolutions
        if isinstance(resolution.candidate, dict)
        and isinstance(resolution.candidate.get("id"), int)
    }

    async def load_interfaces(device_id: int) -> tuple[int, list[dict[str, Any]]]:
        return device_id, await self.client.get_all(
            "/api/dcim/interfaces/",
            params={"device_id": device_id, "ordering": "name"},
        )

    loaded = await asyncio.gather(*(load_interfaces(item) for item in candidate_ids))
    remote_interfaces = {device_id: rows for device_id, rows in loaded}

    results: list[dict[str, Any]] = []
    for observation, resolution in zip(observations, resolutions):
        candidate = resolution.candidate
        local_interface = local_by_name.get(
            self._normalize_interface(observation.local_interface)
        )
        remote_interface = None
        if isinstance(candidate, dict):
            candidate_id = candidate.get("id")
            remote_by_name = {
                self._normalize_interface(item.get("name")): item
                for item in remote_interfaces.get(candidate_id, [])
                if self._normalize_interface(item.get("name"))
            }
            remote_interface = remote_by_name.get(
                self._normalize_interface(observation.remote_port_id)
            )

        candidate_name = ""
        name_exact = False
        name_short = False
        assigned_ip_match = False
        primary_ip_match = False
        if isinstance(candidate, dict):
            candidate_name = str(
                candidate.get("name") or candidate.get("display") or ""
            )
            name_exact = bool(
                self._normalize_name(candidate_name)
                == self._normalize_name(observation.remote_system_name)
            )
            name_short = bool(
                self._short_name(candidate_name)
                == self._short_name(observation.remote_system_name)
            )
            announced_ip = self._address_text(observation.management_ip)
            candidate_id = _nested_id(candidate.get("id"))
            assigned_ip_match = bool(
                announced_ip
                and candidate_id is not None
                and announced_ip in device_ips.get(candidate_id, set())
            )
            primary_ip_match = bool(
                announced_ip
                and announced_ip in self._device_primary_ips(candidate)
            )

        confidence = 0
        if name_exact:
            confidence += 60
        elif name_short:
            confidence += 50
        if assigned_ip_match:
            confidence += 30
        if local_interface:
            confidence += 5
        if remote_interface:
            confidence += 5
        confidence = min(confidence, 100)

        local_connected = self._connected(local_interface)
        remote_connected = self._connected(remote_interface)
        ready = bool(
            local_interface
            and candidate
            and remote_interface
            and resolution.identity_verified
            and not local_connected
            and not remote_connected
        )
        if local_connected or remote_connected:
            state = "conflict"
            state_label = "Interfaz ocupada en NetBox"
        elif ready:
            state = "ready"
            state_label = "Lista para confirmar"
        else:
            state = "unresolved"
            state_label = "Requiere revisión"

        results.append({
            **asdict(observation),
            "local_device_id": local_device_id,
            "local_device_name": local_device.get("name")
            or local_device.get("display")
            or "",
            "local_interface_id": (
                local_interface.get("id")
                if isinstance(local_interface, dict)
                else None
            ),
            "local_interface_netbox": (
                local_interface.get("name")
                if isinstance(local_interface, dict)
                else ""
            ),
            "local_connected": local_connected,
            "remote_device_id": (
                candidate.get("id") if isinstance(candidate, dict) else None
            ),
            "remote_device_name": candidate_name,
            "remote_interface_id": (
                remote_interface.get("id")
                if isinstance(remote_interface, dict)
                else None
            ),
            "remote_interface_netbox": (
                remote_interface.get("name")
                if isinstance(remote_interface, dict)
                else ""
            ),
            "remote_connected": remote_connected,
            "confidence": confidence,
            "state": state,
            "state_label": state_label,
            "ready": ready,
            "identity_verified": resolution.identity_verified,
            "match_method": resolution.selected_by,
            "match_sources": list(resolution.sources),
            "match_source_label": " + ".join(resolution.sources) or "Sin coincidencia",
            "management_ip_matches_device": assigned_ip_match,
            "management_ip_matches_primary": primary_ip_match,
            "match_warning": resolution.message,
        })

    return results


def install_lldp_matching_support() -> None:
    LldpDiscoveryService._match_observations = _match_observations_name_and_ip
    setattr(
        LldpDiscoveryService,
        _PATCH_MARKER,
        MATCHING_REVISION,
    )
