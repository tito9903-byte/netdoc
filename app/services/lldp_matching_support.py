from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from app.services.lldp_discovery_service import (
    LldpDiscoveryError,
    LldpDiscoveryService,
    LldpObservation,
)


_PATCH_MARKER = "_netdoc_lldp_matching_revision"
MATCHING_REVISION = "20260727-name-first-ip-fallback-v1"


def _candidate_identity(
    service: LldpDiscoveryService,
    observation: LldpObservation,
    devices: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, list[str]]:
    remote_full = service._normalize_name(observation.remote_system_name)
    remote_short = service._short_name(observation.remote_system_name)
    management_ip = service._address_text(observation.management_ip)

    matches: list[tuple[dict[str, Any], bool, bool, bool]] = []
    for device in devices:
        name = device.get("name") or device.get("display") or ""
        full_match = bool(remote_full and service._normalize_name(name) == remote_full)
        short_match = bool(remote_short and service._short_name(name) == remote_short)
        ip_match = bool(
            management_ip
            and management_ip in service._device_primary_ips(device)
        )
        if full_match or short_match or ip_match:
            matches.append((device, full_match, short_match, ip_match))

    exact_matches = [row for row in matches if row[1]]
    short_matches = [row for row in matches if row[2]]
    ip_matches = [row for row in matches if row[3]]

    selected: tuple[dict[str, Any], bool, bool, bool] | None = None
    selected_by = ""
    if len(exact_matches) == 1:
        selected = exact_matches[0]
        selected_by = "name_exact"
    elif len(short_matches) == 1:
        selected = short_matches[0]
        selected_by = "name_short"
    elif len(ip_matches) == 1:
        selected = ip_matches[0]
        selected_by = "management_ip"

    if selected is None:
        return None, "", []

    sources: list[str] = []
    if selected[1]:
        sources.append("Nombre exacto")
    elif selected[2]:
        sources.append("Nombre corto")
    if selected[3]:
        sources.append("IP anunciada")

    return selected[0], selected_by, sources


async def _match_observations_name_first(
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

    candidate_rows = [
        _candidate_identity(self, observation, devices)
        for observation in observations
    ]
    candidate_ids = {
        int(candidate["id"])
        for candidate, _, _ in candidate_rows
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), int)
    }

    async def load_interfaces(device_id: int) -> tuple[int, list[dict[str, Any]]]:
        return device_id, await self.client.get_all(
            "/api/dcim/interfaces/",
            params={"device_id": device_id, "ordering": "name"},
        )

    loaded = await asyncio.gather(*(load_interfaces(item) for item in candidate_ids))
    remote_interfaces = {device_id: rows for device_id, rows in loaded}

    results: list[dict[str, Any]] = []
    for observation, candidate_row in zip(observations, candidate_rows):
        candidate, selected_by, match_sources = candidate_row
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
        ip_match = False
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
            ip_match = bool(
                announced_ip
                and announced_ip in self._device_primary_ips(candidate)
            )

        confidence = 0
        if name_exact:
            confidence += 70
        elif name_short:
            confidence += 60
        if ip_match:
            confidence += 25
        if local_interface:
            confidence += 5
        if remote_interface:
            confidence += 10
        confidence = min(confidence, 100)

        local_connected = self._connected(local_interface)
        remote_connected = self._connected(remote_interface)
        ready = bool(
            local_interface
            and candidate
            and remote_interface
            and not local_connected
            and not remote_connected
        )
        if ready:
            state = "ready"
            state_label = "Lista para confirmar"
        elif local_connected or remote_connected:
            state = "conflict"
            state_label = "Interfaz ocupada en NetBox"
        else:
            state = "unresolved"
            state_label = "Requiere revisión"

        match_source_label = " + ".join(match_sources) or "Sin coincidencia"
        match_warning = ""
        if isinstance(candidate, dict) and selected_by == "management_ip":
            match_warning = (
                "El equipo remoto fue identificado únicamente por la IP anunciada "
                "por LLDP. La conexión puede documentarse si ambos puertos coinciden "
                "y están libres."
            )
        elif isinstance(candidate, dict) and selected_by.startswith("name") and not ip_match:
            match_warning = (
                "El equipo remoto fue identificado por nombre. La IP anunciada por "
                "LLDP no coincide con su IP principal en NetBox, lo cual no bloquea "
                "la propuesta."
            )

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
            "match_method": selected_by,
            "match_sources": match_sources,
            "match_source_label": match_source_label,
            "management_ip_matches_primary": ip_match,
            "match_warning": match_warning,
        })

    return results


def install_lldp_matching_support() -> None:
    LldpDiscoveryService._match_observations = _match_observations_name_first
    setattr(
        LldpDiscoveryService,
        _PATCH_MARKER,
        MATCHING_REVISION,
    )
