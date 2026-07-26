from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import ipaddress
import json
import re
from typing import Any

from app.core.config import get_settings
from app.services.device_type_service import DeviceTypeService, DeviceTypeServiceError


class LldpDiscoveryError(Exception):
    """Error controlado del descubrimiento LLDP por SSH."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    netmiko_type: str
    command: str
    label: str


@dataclass(frozen=True)
class LldpObservation:
    local_interface: str
    remote_system_name: str
    remote_port_id: str
    remote_port_description: str = ""
    management_ip: str = ""
    chassis_id: str = ""
    system_description: str = ""


PLATFORM_SPECS: dict[str, PlatformSpec] = {
    "arista_eos": PlatformSpec(
        key="arista_eos",
        netmiko_type="arista_eos",
        command="show lldp neighbors detail",
        label="Arista EOS",
    ),
    "cisco_ios": PlatformSpec(
        key="cisco_ios",
        netmiko_type="cisco_ios",
        command="show lldp neighbors detail",
        label="Cisco IOS / IOS XE",
    ),
    "cisco_nxos": PlatformSpec(
        key="cisco_nxos",
        netmiko_type="cisco_nxos",
        command="show lldp neighbors detail",
        label="Cisco NX-OS",
    ),
    "juniper_junos": PlatformSpec(
        key="juniper_junos",
        netmiko_type="juniper_junos",
        command="show lldp neighbors detail",
        label="Juniper Junos",
    ),
    "mikrotik_routeros": PlatformSpec(
        key="mikrotik_routeros",
        netmiko_type="mikrotik_routeros",
        command="/ip neighbor print detail without-paging",
        label="MikroTik RouterOS",
    ),
}


PLATFORM_ALIASES: dict[str, str] = {
    "arista": "arista_eos",
    "arista_eos": "arista_eos",
    "eos": "arista_eos",
    "cisco": "cisco_ios",
    "cisco_ios": "cisco_ios",
    "cisco_iosxe": "cisco_ios",
    "cisco_xe": "cisco_ios",
    "ios": "cisco_ios",
    "iosxe": "cisco_ios",
    "cisco_nxos": "cisco_nxos",
    "nxos": "cisco_nxos",
    "juniper": "juniper_junos",
    "juniper_junos": "juniper_junos",
    "junos": "juniper_junos",
    "mikrotik": "mikrotik_routeros",
    "mikrotik_routeros": "mikrotik_routeros",
    "routeros": "mikrotik_routeros",
}


STRUCTURED_KEYS: dict[str, tuple[str, ...]] = {
    "local_interface": (
        "local_interface",
        "local_port",
        "local_intf",
        "local_port_id",
        "interface",
    ),
    "remote_system_name": (
        "remote_system_name",
        "system_name",
        "neighbor_name",
        "neighbor",
        "device_id",
        "neighbor_id",
    ),
    "remote_port_id": (
        "remote_port_id",
        "remote_port",
        "neighbor_interface",
        "neighbor_port_id",
        "port_id",
    ),
    "remote_port_description": (
        "remote_port_description",
        "port_description",
        "neighbor_port_description",
    ),
    "management_ip": (
        "management_ip",
        "management_address",
        "mgmt_address",
        "neighbor_management_address",
    ),
    "chassis_id": (
        "chassis_id",
        "neighbor_chassis_id",
        "remote_chassis_id",
    ),
    "system_description": (
        "system_description",
        "neighbor_description",
        "remote_system_description",
    ),
}


class LldpDiscoveryService:
    """Descubre vecinos por SSH y propone terminaciones de NetBox.

    Esta primera fase es deliberadamente no destructiva. El servicio recopila LLDP,
    normaliza la salida y compara nombres e interfaces. La escritura del cable se
    realiza en una acción separada y siempre requiere confirmación humana.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = DeviceTypeService()

    @staticmethod
    def supported_platforms() -> list[dict[str, str]]:
        return [
            {"key": spec.key, "label": spec.label}
            for spec in PLATFORM_SPECS.values()
        ]

    @staticmethod
    def _choice_text(value: Any) -> str:
        if isinstance(value, dict):
            return str(
                value.get("value")
                or value.get("slug")
                or value.get("name")
                or value.get("label")
                or value.get("display")
                or ""
            )
        return str(value or "")

    @staticmethod
    def _address_text(value: Any) -> str:
        if isinstance(value, dict):
            value = value.get("address") or value.get("display") or ""
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            return str(ipaddress.ip_interface(text).ip)
        except ValueError:
            return text.split("/", 1)[0].strip()

    @staticmethod
    def _normalize_name(value: Any) -> str:
        text = str(value or "").strip().casefold().rstrip(".")
        if not text:
            return ""
        return re.sub(r"[^a-z0-9_-]+", "", text)

    @classmethod
    def _short_name(cls, value: Any) -> str:
        return cls._normalize_name(str(value or "").split(".", 1)[0])

    @staticmethod
    def _normalize_interface(value: Any) -> str:
        text = str(value or "").strip().casefold()
        text = re.sub(r"\s+", "", text)
        replacements = (
            ("twentyfivegige", "twe"),
            ("fortygigabitethernet", "fo"),
            ("hundredgigabitethernet", "hu"),
            ("tengigabitethernet", "te"),
            ("gigabitethernet", "gi"),
            ("fastethernet", "fa"),
            ("ethernet", "eth"),
            ("port-channel", "po"),
            ("portchannel", "po"),
        )
        for source, target in replacements:
            if text.startswith(source):
                text = f"{target}{text[len(source):]}"
                break
        return re.sub(r"[^a-z0-9/_.:-]+", "", text)

    @staticmethod
    def _connected(interface: dict[str, Any] | None) -> bool:
        if not isinstance(interface, dict):
            return False
        return bool(interface.get("cable") or interface.get("connected_endpoints"))

    def _profiles(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self.settings.netdoc_ssh_profiles_json or "{}")
        except json.JSONDecodeError as exc:
            raise LldpDiscoveryError(
                "NETDOC_SSH_PROFILES_JSON no contiene un JSON válido.",
                500,
            ) from exc
        if not isinstance(payload, dict):
            raise LldpDiscoveryError(
                "NETDOC_SSH_PROFILES_JSON debe contener un objeto JSON.",
                500,
            )
        profiles: dict[str, dict[str, Any]] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                profiles[str(key).strip().casefold()] = dict(value)
        return profiles

    def _resolve_platform(self, device: dict[str, Any]) -> PlatformSpec:
        custom_fields = device.get("custom_fields") or {}
        profile_hint = ""
        if isinstance(custom_fields, dict):
            profile_hint = str(custom_fields.get("netdoc_ssh_profile") or "")

        platform = device.get("platform") or {}
        device_type = device.get("device_type") or {}
        manufacturer = (
            device_type.get("manufacturer")
            if isinstance(device_type, dict)
            else {}
        ) or {}

        candidates = (
            profile_hint,
            self._choice_text(platform),
            self._choice_text(manufacturer),
        )
        for candidate in candidates:
            normalized = self._normalize_name(candidate)
            key = PLATFORM_ALIASES.get(normalized)
            if key and key in PLATFORM_SPECS:
                return PLATFORM_SPECS[key]

        readable = self._choice_text(platform) or self._choice_text(manufacturer)
        raise LldpDiscoveryError(
            "No se pudo determinar el controlador SSH del dispositivo. "
            "Configura la plataforma en NetBox o el campo personalizado "
            f"netdoc_ssh_profile. Valor detectado: {readable or 'ninguno'}.",
            400,
        )

    def _resolve_profile(
        self,
        device: dict[str, Any],
        spec: PlatformSpec,
    ) -> dict[str, Any]:
        profiles = self._profiles()
        custom_fields = device.get("custom_fields") or {}
        requested = ""
        if isinstance(custom_fields, dict):
            requested = str(custom_fields.get("netdoc_ssh_profile") or "")
        profile_key = self._normalize_name(requested) or spec.key

        merged: dict[str, Any] = {}
        merged.update(profiles.get("default", {}))
        merged.update(profiles.get(spec.key.casefold(), {}))
        if profile_key != spec.key:
            merged.update(profiles.get(profile_key.casefold(), {}))

        username = str(merged.get("username") or "").strip()
        password = str(merged.get("password") or "")
        key_file = str(
            merged.get("private_key_file")
            or merged.get("key_file")
            or ""
        ).strip()
        if not username:
            raise LldpDiscoveryError(
                f"El perfil SSH {profile_key} no tiene usuario configurado.",
                500,
            )
        if not password and not key_file:
            raise LldpDiscoveryError(
                f"El perfil SSH {profile_key} no tiene contraseña ni llave privada.",
                500,
            )

        return {
            **merged,
            "profile_key": profile_key,
            "username": username,
            "password": password,
            "key_file": key_file,
            "device_type": str(merged.get("device_type") or spec.netmiko_type),
            "command": str(merged.get("command") or spec.command),
            "port": int(merged.get("port") or 22),
        }

    def _device_host(self, device: dict[str, Any]) -> str:
        host = (
            self._address_text(device.get("primary_ip4"))
            or self._address_text(device.get("primary_ip6"))
            or self._address_text(device.get("primary_ip"))
        )
        if not host:
            raise LldpDiscoveryError(
                "El dispositivo no tiene una IP principal configurada en NetBox.",
                400,
            )
        return host

    def _collect_sync(
        self,
        *,
        host: str,
        profile: dict[str, Any],
    ) -> Any:
        try:
            from netmiko import (
                ConnectHandler,
                NetmikoAuthenticationException,
                NetmikoTimeoutException,
            )
        except ImportError as exc:
            raise LldpDiscoveryError(
                "Netmiko no está instalado en el entorno de NetDoc.",
                500,
            ) from exc

        connection_args: dict[str, Any] = {
            "device_type": profile["device_type"],
            "host": host,
            "username": profile["username"],
            "password": profile.get("password") or "",
            "secret": profile.get("secret") or "",
            "port": profile["port"],
            "conn_timeout": self.settings.netdoc_ssh_connect_timeout,
            "auth_timeout": self.settings.netdoc_ssh_connect_timeout,
            "banner_timeout": self.settings.netdoc_ssh_connect_timeout,
            "fast_cli": False,
        }
        if profile.get("key_file"):
            connection_args.update({
                "use_keys": True,
                "key_file": profile["key_file"],
                "allow_agent": False,
            })

        connection = None
        try:
            connection = ConnectHandler(**connection_args)
            return connection.send_command(
                profile["command"],
                use_textfsm=True,
                read_timeout=self.settings.netdoc_ssh_command_timeout,
            )
        except NetmikoAuthenticationException as exc:
            raise LldpDiscoveryError(
                "El equipo rechazó las credenciales SSH configuradas.",
                502,
            ) from exc
        except NetmikoTimeoutException as exc:
            raise LldpDiscoveryError(
                f"No fue posible establecer SSH con {host} dentro del tiempo límite.",
                504,
            ) from exc
        except LldpDiscoveryError:
            raise
        except Exception as exc:
            raise LldpDiscoveryError(
                f"La consulta LLDP por SSH falló: {type(exc).__name__}: {exc}",
                502,
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.disconnect()
                except Exception:
                    pass

    @staticmethod
    def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = row.get(key)
            if isinstance(value, list):
                value = next((item for item in value if item not in (None, "")), "")
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @classmethod
    def _from_structured(cls, payload: list[Any]) -> list[LldpObservation]:
        observations: list[LldpObservation] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            values = {
                field: cls._pick(raw, keys)
                for field, keys in STRUCTURED_KEYS.items()
            }
            if not values["local_interface"]:
                continue
            observations.append(LldpObservation(**values))
        return observations

    @staticmethod
    def _field(block: str, labels: tuple[str, ...]) -> str:
        joined = "|".join(re.escape(label) for label in labels)
        match = re.search(
            rf"(?im)^\s*(?:{joined})\s*[:=]\s*(.+?)\s*$",
            block,
        )
        return match.group(1).strip() if match else ""

    @classmethod
    def _from_text(cls, output: str) -> list[LldpObservation]:
        text = str(output or "").replace("\r", "")
        if not text.strip():
            return []

        # RouterOS presenta cada vecino como una línea/bloque con pares clave=valor.
        if "interface=" in text and ("identity=" in text or "interface-name=" in text):
            observations: list[LldpObservation] = []
            blocks = re.split(r"(?m)^\s*\d+\s+", text)
            for block in blocks:
                values = dict(
                    re.findall(r"([a-zA-Z0-9_-]+)=\"?([^\s\"]+)\"?", block)
                )
                local = values.get("interface", "")
                remote_name = values.get("identity", "")
                remote_port = values.get("interface-name", "") or values.get("interface-id", "")
                if not local:
                    continue
                observations.append(LldpObservation(
                    local_interface=local,
                    remote_system_name=remote_name,
                    remote_port_id=remote_port,
                    remote_port_description=values.get("system-description", ""),
                    management_ip=values.get("address", ""),
                    chassis_id=values.get("mac-address", ""),
                    system_description=values.get("system-description", ""),
                ))
            return observations

        local_pattern = re.compile(
            r"(?im)^\s*(?:Local\s+(?:Intf|Interface|Port(?:\s+ID)?)|LocalPort)\s*[:=]\s*(.+?)\s*$"
        )
        matches = list(local_pattern.finditer(text))
        observations = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[start:end]
            local = match.group(1).strip()
            remote_name = cls._field(block, (
                "System Name",
                "System name",
                "Device ID",
                "Neighbor",
            ))
            remote_port = cls._field(block, (
                "Port id",
                "Port ID",
                "Remote Port ID",
                "Port identifier",
            ))
            observations.append(LldpObservation(
                local_interface=local,
                remote_system_name=remote_name,
                remote_port_id=remote_port,
                remote_port_description=cls._field(block, (
                    "Port Description",
                    "Port description",
                )),
                management_ip=cls._field(block, (
                    "Management Address",
                    "Management address",
                    "Management IP",
                    "IP",
                )),
                chassis_id=cls._field(block, ("Chassis id", "Chassis ID")),
                system_description=cls._field(block, (
                    "System Description",
                    "System description",
                )),
            ))
        return observations

    @classmethod
    def parse_output(cls, payload: Any) -> list[LldpObservation]:
        observations = (
            cls._from_structured(payload)
            if isinstance(payload, list)
            else cls._from_text(str(payload or ""))
        )
        deduplicated: list[LldpObservation] = []
        seen: set[tuple[str, str, str]] = set()
        for item in observations:
            key = (
                cls._normalize_interface(item.local_interface),
                cls._short_name(item.remote_system_name),
                cls._normalize_interface(item.remote_port_id),
            )
            if not key[0] or key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    @classmethod
    def _device_primary_ips(cls, device: dict[str, Any]) -> set[str]:
        return {
            address
            for address in (
                cls._address_text(device.get("primary_ip4")),
                cls._address_text(device.get("primary_ip6")),
                cls._address_text(device.get("primary_ip")),
            )
            if address
        }

    async def _match_observations(
        self,
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

        device_candidates: list[dict[str, Any] | None] = []
        for observation in observations:
            remote_full = self._normalize_name(observation.remote_system_name)
            remote_short = self._short_name(observation.remote_system_name)
            management_ip = self._address_text(observation.management_ip)
            matching = []
            for device in devices:
                name = device.get("name") or device.get("display") or ""
                full_match = bool(remote_full and self._normalize_name(name) == remote_full)
                short_match = bool(remote_short and self._short_name(name) == remote_short)
                ip_match = bool(
                    management_ip
                    and management_ip in self._device_primary_ips(device)
                )
                if full_match or short_match or ip_match:
                    matching.append((device, full_match, short_match, ip_match))

            if management_ip:
                ip_matches = [row for row in matching if row[3]]
                if len(ip_matches) == 1:
                    device_candidates.append(ip_matches[0][0])
                    continue
            exact_matches = [row for row in matching if row[1]]
            if len(exact_matches) == 1:
                device_candidates.append(exact_matches[0][0])
                continue
            short_matches = [row for row in matching if row[2]]
            device_candidates.append(short_matches[0][0] if len(short_matches) == 1 else None)

        candidate_ids = {
            int(candidate["id"])
            for candidate in device_candidates
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
        for observation, candidate in zip(observations, device_candidates):
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

            confidence = 0
            candidate_name = ""
            if isinstance(candidate, dict):
                candidate_name = str(
                    candidate.get("name") or candidate.get("display") or ""
                )
                if self._normalize_name(candidate_name) == self._normalize_name(
                    observation.remote_system_name
                ):
                    confidence += 70
                elif self._short_name(candidate_name) == self._short_name(
                    observation.remote_system_name
                ):
                    confidence += 60
                if (
                    self._address_text(observation.management_ip)
                    in self._device_primary_ips(candidate)
                ):
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

            results.append({
                **asdict(observation),
                "local_device_id": local_device_id,
                "local_device_name": local_device.get("name") or local_device.get("display") or "",
                "local_interface_id": (
                    local_interface.get("id") if isinstance(local_interface, dict) else None
                ),
                "local_interface_netbox": (
                    local_interface.get("name") if isinstance(local_interface, dict) else ""
                ),
                "local_connected": local_connected,
                "remote_device_id": candidate.get("id") if isinstance(candidate, dict) else None,
                "remote_device_name": candidate_name,
                "remote_interface_id": (
                    remote_interface.get("id") if isinstance(remote_interface, dict) else None
                ),
                "remote_interface_netbox": (
                    remote_interface.get("name") if isinstance(remote_interface, dict) else ""
                ),
                "remote_connected": remote_connected,
                "confidence": confidence,
                "state": state,
                "state_label": state_label,
                "ready": ready,
            })
        return results

    async def device_context(self, device_id: int) -> dict[str, Any]:
        try:
            device = await self.client.request(
                "GET",
                f"/api/dcim/devices/{device_id}/",
            )
        except DeviceTypeServiceError as exc:
            raise LldpDiscoveryError(exc.message, exc.status_code or 503) from exc
        if not isinstance(device, dict):
            raise LldpDiscoveryError(
                "NetBox devolvió un dispositivo inesperado.",
                502,
            )
        host = self._device_host(device)
        spec = self._resolve_platform(device)
        profile = self._resolve_profile(device, spec)
        return {
            "device": device,
            "host": host,
            "platform": spec,
            "profile_key": profile["profile_key"],
            "command": profile["command"],
        }

    async def discover(self, device_id: int) -> dict[str, Any]:
        if not self.settings.netdoc_ssh_discovery_enabled:
            raise LldpDiscoveryError(
                "El descubrimiento SSH está deshabilitado. Activa "
                "NETDOC_SSH_DISCOVERY_ENABLED en el entorno.",
                403,
            )

        try:
            device = await self.client.request(
                "GET",
                f"/api/dcim/devices/{device_id}/",
            )
        except DeviceTypeServiceError as exc:
            raise LldpDiscoveryError(exc.message, exc.status_code or 503) from exc
        if not isinstance(device, dict):
            raise LldpDiscoveryError(
                "NetBox devolvió un dispositivo inesperado.",
                502,
            )

        host = self._device_host(device)
        spec = self._resolve_platform(device)
        profile = self._resolve_profile(device, spec)
        payload = await asyncio.to_thread(
            self._collect_sync,
            host=host,
            profile=profile,
        )
        observations = self.parse_output(payload)
        if not observations:
            raise LldpDiscoveryError(
                "El comando terminó, pero no se pudieron interpretar vecinos LLDP. "
                "Puede que LLDP esté vacío o que el formato requiera un parser específico.",
                422,
            )
        observations = observations[: self.settings.netdoc_ssh_max_neighbors]
        matches = await self._match_observations(
            local_device=device,
            observations=observations,
        )
        return {
            "device": device,
            "host": host,
            "platform": asdict(spec),
            "profile_key": profile["profile_key"],
            "command": profile["command"],
            "observations": matches,
            "neighbor_count": len(matches),
            "ready_count": sum(1 for item in matches if item["ready"]),
            "conflict_count": sum(1 for item in matches if item["state"] == "conflict"),
            "unresolved_count": sum(1 for item in matches if item["state"] == "unresolved"),
        }
