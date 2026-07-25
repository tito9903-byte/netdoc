from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.services.change_plan import ChangePlanError, ChangeStep


@dataclass(frozen=True)
class NetBoxCapability:
    """Operación explícitamente conocida por NetDoc."""

    key: str
    domain: str
    label: str
    endpoint_pattern: str
    methods: frozenset[str]
    required_permission: str
    ai_execution_allowed: bool
    notes: str = ""

    def matches(self, method: str, endpoint: str) -> bool:
        return (
            method.strip().upper() in self.methods
            and re.fullmatch(self.endpoint_pattern, endpoint.strip()) is not None
        )


_CAPABILITIES: tuple[NetBoxCapability, ...] = (
    NetBoxCapability(
        key="dcim.manufacturer.create_or_update",
        domain="hardware",
        label="Fabricantes",
        endpoint_pattern=r"/api/dcim/manufacturers/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Requiere revisión humana porque afecta el catálogo reutilizable.",
    ),
    NetBoxCapability(
        key="dcim.device_type.create_or_update",
        domain="hardware",
        label="Modelos de equipos",
        endpoint_pattern=r"/api/dcim/device-types/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Incluye dimensiones e imágenes que afectan elevaciones.",
    ),
    NetBoxCapability(
        key="dcim.interface_template.create_or_update",
        domain="hardware",
        label="Plantillas de interfaces",
        endpoint_pattern=r"/api/dcim/interface-templates/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="La creación masiva debe mostrar todos los nombres antes de ejecutar.",
    ),
    NetBoxCapability(
        key="dcim.rack.create_or_update",
        domain="facilities",
        label="Racks",
        endpoint_pattern=r"/api/dcim/racks/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Debe validar localidad, altura, numeración y posiciones ocupadas.",
    ),
    NetBoxCapability(
        key="dcim.device.create_or_update",
        domain="devices",
        label="Dispositivos",
        endpoint_pattern=r"/api/dcim/devices/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Debe resolver modelo, rol, sitio, rack, cara y posición exactos.",
    ),
    NetBoxCapability(
        key="dcim.cable.create",
        domain="connectivity",
        label="Cables",
        endpoint_pattern=r"/api/dcim/cables/",
        methods=frozenset({"POST"}),
        required_permission="devices.create",
        ai_execution_allowed=True,
        notes="Solo después de comprobar extremos libres, distintos y compatibles.",
    ),
    NetBoxCapability(
        key="ipam.prefix.create_or_update",
        domain="ipam",
        label="Prefijos",
        endpoint_pattern=r"/api/ipam/prefixes/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Planificado; requiere validar VRF, solapamiento y jerarquía.",
    ),
    NetBoxCapability(
        key="ipam.ip_address.create_or_update",
        domain="ipam",
        label="Direcciones IP",
        endpoint_pattern=r"/api/ipam/ip-addresses/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Planificado; requiere validar duplicados y asignación al objeto.",
    ),
    NetBoxCapability(
        key="ipam.vlan.create_or_update",
        domain="ipam",
        label="VLAN",
        endpoint_pattern=r"/api/ipam/vlans/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Planificado; requiere validar grupo, sitio, VID y tenant.",
    ),
    NetBoxCapability(
        key="circuits.circuit.create_or_update",
        domain="circuits",
        label="Circuitos",
        endpoint_pattern=r"/api/circuits/circuits/(?:\d+/)?",
        methods=frozenset({"POST", "PATCH"}),
        required_permission="devices.create",
        ai_execution_allowed=False,
        notes="Planificado; requiere proveedor, tipo y terminaciones coherentes.",
    ),
)


def list_capabilities() -> tuple[NetBoxCapability, ...]:
    return _CAPABILITIES


def capability_for(method: str, endpoint: str) -> NetBoxCapability | None:
    return next(
        (
            capability
            for capability in _CAPABILITIES
            if capability.matches(method, endpoint)
        ),
        None,
    )


def validate_step_capability(
    step: ChangeStep,
    *,
    for_ai: bool = False,
) -> NetBoxCapability:
    capability = capability_for(step.method, step.endpoint)
    if capability is None:
        raise ChangePlanError(
            f"La operación {step.method} {step.endpoint} no está permitida por NetDoc."
        )
    if step.required_permission != capability.required_permission:
        raise ChangePlanError(
            "El permiso del paso no coincide con la capacidad registrada."
        )
    if for_ai and not capability.ai_execution_allowed:
        raise ChangePlanError(
            f"La IA puede preparar '{capability.label}', pero no ejecutarlo todavía."
        )
    return capability


def validate_plan_capabilities(
    steps: Iterable[ChangeStep],
    *,
    for_ai: bool = False,
) -> tuple[NetBoxCapability, ...]:
    return tuple(
        validate_step_capability(step, for_ai=for_ai)
        for step in steps
    )
