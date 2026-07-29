from __future__ import annotations

import re
from typing import Any

from app.services.lldp_discovery_service import (
    LldpDiscoveryService,
    LldpObservation,
)


_ORIGINAL_FROM_TEXT = LldpDiscoveryService._from_text.__func__
_PATCH_MARKER = "_netdoc_eos_parser_installed"


def _clean_text(output: Any) -> str:
    text = str(output or "").replace("\r", "")
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)
    text = text.replace("--More--", "")
    text = text.replace("\x08", "")
    return text


def _strip_quotes(value: str) -> str:
    clean = str(value or "").strip()
    if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {'"', "'"}:
        return clean[1:-1].strip()
    return clean


def _field(block: str, label: str) -> str:
    match = re.search(
        rf"(?im)^\s*(?:-\s*)?{re.escape(label)}\s*:\s*(.+?)\s*$",
        block,
    )
    return _strip_quotes(match.group(1)) if match else ""


def parse_arista_lldp_detail(output: Any) -> list[LldpObservation]:
    text = _clean_text(output)
    header_pattern = re.compile(
        r"(?im)^Interface\s+(\S+)\s+detected\s+(\d+)\s+LLDP\s+neighbors?:\s*$"
    )
    headers = list(header_pattern.finditer(text))
    if not headers:
        return []

    observations: list[LldpObservation] = []
    for index, header in enumerate(headers):
        local_interface = header.group(1).strip()
        neighbor_count = int(header.group(2))
        if neighbor_count < 1:
            continue

        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        interface_block = text[start:end]
        neighbor_markers = list(
            re.finditer(r"(?im)^\s*Neighbor\s+.+?\s*$", interface_block)
        )
        if not neighbor_markers:
            neighbor_markers = [re.match(r"", interface_block)]

        for neighbor_index, marker in enumerate(neighbor_markers):
            if marker is None:
                continue
            block_start = marker.start()
            block_end = (
                neighbor_markers[neighbor_index + 1].start()
                if neighbor_index + 1 < len(neighbor_markers)
                else len(interface_block)
            )
            block = interface_block[block_start:block_end]
            remote_name = _field(block, "System Name")
            remote_port = _field(block, "Port ID")
            chassis_id = _field(block, "Chassis ID")

            if not remote_port:
                marker_text = marker.group(0)
                marker_match = re.search(r'/"?([^"\s]+)"?', marker_text)
                if marker_match:
                    remote_port = marker_match.group(1).strip()

            observations.append(
                LldpObservation(
                    local_interface=local_interface,
                    remote_system_name=remote_name,
                    remote_port_id=remote_port,
                    remote_port_description=_field(block, "Port Description"),
                    management_ip=_field(block, "Management Address"),
                    chassis_id=chassis_id,
                    system_description=_field(block, "System Description"),
                )
            )

    return observations


def _from_text_with_eos(
    cls: type[LldpDiscoveryService],
    output: str,
) -> list[LldpObservation]:
    parsed = parse_arista_lldp_detail(output)
    if parsed:
        return parsed
    return _ORIGINAL_FROM_TEXT(cls, output)


def install_lldp_eos_support() -> None:
    if getattr(LldpDiscoveryService, _PATCH_MARKER, False):
        return
    LldpDiscoveryService._from_text = classmethod(_from_text_with_eos)
    setattr(LldpDiscoveryService, _PATCH_MARKER, True)
