from __future__ import annotations

import re
from typing import Any, Callable

from app.services.lldp_discovery_service import (
    LldpDiscoveryService,
    LldpObservation,
)


_PATCH_MARKER = "_netdoc_lldp_vendor_revision"
VENDOR_PARSER_REVISION = "20260727-multivendor-fallback-v1"
_FALLBACK_FROM_TEXT: Callable[[type[LldpDiscoveryService], str], list[LldpObservation]] | None = None


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _field(block: str, *labels: str) -> str:
    joined = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?im)^\s*(?:{joined})\s*[:=]\s*(.+?)\s*$",
        block,
    )
    return _clean(match.group(1)) if match else ""


def _parse_block_output(
    output: str,
    *,
    header_pattern: str,
) -> list[LldpObservation]:
    text = str(output or "").replace("\r", "")
    headers = list(re.finditer(header_pattern, text, re.IGNORECASE | re.MULTILINE))
    observations: list[LldpObservation] = []
    for index, header in enumerate(headers):
        start = header.start()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[start:end]
        local_interface = _clean(header.group(1))
        if not local_interface:
            continue
        observations.append(LldpObservation(
            local_interface=local_interface,
            remote_system_name=_field(
                block,
                "System Name",
                "System name",
                "Device ID",
                "Device ID (local)",
            ),
            remote_port_id=_field(
                block,
                "Port id",
                "Port ID",
                "Port identifier",
                "Remote Port ID",
            ),
            remote_port_description=_field(
                block,
                "Port Description",
                "Port description",
                "Port info",
            ),
            management_ip=_field(
                block,
                "Management Address",
                "Management address",
                "Management IP",
                "Management address value",
            ),
            chassis_id=_field(
                block,
                "Chassis id",
                "Chassis ID",
                "Chassis ID subtype",
            ),
            system_description=_field(
                block,
                "System Description",
                "System description",
            ),
        ))
    return observations


def parse_cisco_lldp_detail(output: Any) -> list[LldpObservation]:
    text = str(output or "")
    if not re.search(r"(?im)^\s*Local\s+(?:Intf|Port\s+id)\s*:", text):
        return []
    return _parse_block_output(
        text,
        header_pattern=r"^\s*Local\s+(?:Intf|Port\s+id)\s*:\s*(.+?)\s*$",
    )


def parse_junos_lldp_detail(output: Any) -> list[LldpObservation]:
    text = str(output or "")
    if not re.search(r"(?im)^\s*Local interface\s*:", text):
        return []
    return _parse_block_output(
        text,
        header_pattern=r"^\s*Local interface\s*:\s*(.+?)\s*$",
    )


def _mikrotik_values(block: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in re.finditer(
        r"([a-zA-Z0-9_-]+)=(?:\"([^\"]*)\"|([^\s]+))",
        block,
    ):
        values[match.group(1)] = _clean(match.group(2) or match.group(3) or "")
    return values


def parse_mikrotik_neighbor_detail(output: Any) -> list[LldpObservation]:
    text = str(output or "").replace("\r", "")
    if "interface=" not in text or not any(
        marker in text for marker in ("identity=", "interface-name=", "interface-id=")
    ):
        return []

    blocks = re.split(r"(?m)^\s*\d+\s+", text)
    observations: list[LldpObservation] = []
    for block in blocks:
        values = _mikrotik_values(block)
        local_interface = values.get("interface", "")
        if not local_interface:
            continue
        observations.append(LldpObservation(
            local_interface=local_interface,
            remote_system_name=values.get("identity", ""),
            remote_port_id=(
                values.get("interface-name", "")
                or values.get("interface-id", "")
            ),
            remote_port_description=values.get("interface-description", ""),
            management_ip=values.get("address", ""),
            chassis_id=values.get("mac-address", ""),
            system_description=values.get("system-description", ""),
        ))
    return observations


def _from_text_multivendor(
    cls: type[LldpDiscoveryService],
    output: str,
) -> list[LldpObservation]:
    for parser in (
        parse_cisco_lldp_detail,
        parse_junos_lldp_detail,
        parse_mikrotik_neighbor_detail,
    ):
        parsed = parser(output)
        if parsed:
            return parsed

    if _FALLBACK_FROM_TEXT is None:
        return []
    return _FALLBACK_FROM_TEXT(cls, output)


def install_lldp_vendor_support() -> None:
    global _FALLBACK_FROM_TEXT

    current = LldpDiscoveryService._from_text
    current_function = getattr(current, "__func__", current)
    if current_function is not _from_text_multivendor:
        _FALLBACK_FROM_TEXT = current_function

    LldpDiscoveryService._from_text = classmethod(_from_text_multivendor)
    setattr(
        LldpDiscoveryService,
        _PATCH_MARKER,
        VENDOR_PARSER_REVISION,
    )
