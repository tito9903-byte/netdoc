from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from app.services.change_plan import ChangePlan, ChangePlanError, ChangeStep
from app.services.netbox_capabilities import validate_plan_capabilities


_ALLOWED_TERMINATION_TYPES = {
    "dcim.interface",
    "dcim.consoleport",
    "dcim.consoleserverport",
    "dcim.frontport",
    "dcim.rearport",
    "dcim.powerport",
    "dcim.poweroutlet",
    "circuits.circuittermination",
    "dcim.powerfeed",
}
_COLOR_PATTERN = re.compile(r"^[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class CableEndpoint:
    object_type: str
    object_id: int
    display: str
    cable_id: int | None = None
    connected_endpoints: tuple[Any, ...] = ()
    enabled: bool | None = None

    @property
    def connected(self) -> bool:
        return self.cable_id is not None or bool(self.connected_endpoints)


def endpoint_from_netbox(
    payload: dict[str, Any],
    *,
    object_type: str = "dcim.interface",
) -> CableEndpoint:
    object_id = payload.get("id")
    if not isinstance(object_id, int):
        raise ChangePlanError("NetBox no devolvió un ID válido para el extremo.")

    device = payload.get("device") or payload.get("parent") or {}
    device_name = ""
    if isinstance(device, dict):
        device_name = str(
            device.get("display") or device.get("name") or ""
        ).strip()
    name = str(
        payload.get("display")
        or payload.get("name")
        or payload.get("label")
        or f"#{object_id}"
    ).strip()
    display = (
        name
        if not device_name or device_name.casefold() in name.casefold()
        else f"{device_name} · {name}"
    )

    cable = payload.get("cable")
    cable_id = cable.get("id") if isinstance(cable, dict) else None
    connected_endpoints = payload.get("connected_endpoints") or ()
    if not isinstance(connected_endpoints, (list, tuple)):
        connected_endpoints = ()

    return CableEndpoint(
        object_type=object_type,
        object_id=object_id,
        display=display,
        cable_id=cable_id if isinstance(cable_id, int) else None,
        connected_endpoints=tuple(connected_endpoints),
        enabled=(
            payload.get("enabled")
            if isinstance(payload.get("enabled"), bool)
            else None
        ),
    )


def _validated_length(value: Decimal | int | float | str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ChangePlanError("La longitud del cable no es válida.") from exc
    if number < 0:
        raise ChangePlanError("La longitud del cable no puede ser negativa.")
    return format(number.normalize(), "f")


def _validate_endpoint(endpoint: CableEndpoint, label: str) -> None:
    if endpoint.object_type not in _ALLOWED_TERMINATION_TYPES:
        raise ChangePlanError(
            f"El tipo de terminación del extremo {label} no está permitido."
        )
    if endpoint.object_id < 1:
        raise ChangePlanError(f"El extremo {label} no tiene un ID válido.")
    if endpoint.connected:
        raise ChangePlanError(
            f"El extremo {label} ({endpoint.display}) ya tiene una conexión."
        )


def build_cable_plan(
    *,
    requested_by: str,
    endpoint_a: CableEndpoint,
    endpoint_b: CableEndpoint,
    status: str = "connected",
    cable_type: str = "",
    label: str = "",
    color: str = "",
    length: Decimal | int | float | str | None = None,
    length_unit: str = "m",
    description: str = "",
    source: str = "user",
) -> ChangePlan:
    """Construye un plan; no realiza ninguna solicitud de escritura."""

    _validate_endpoint(endpoint_a, "A")
    _validate_endpoint(endpoint_b, "B")

    if (
        endpoint_a.object_type == endpoint_b.object_type
        and endpoint_a.object_id == endpoint_b.object_id
    ):
        raise ChangePlanError("Un cable no puede conectar un objeto consigo mismo.")

    clean_status = status.strip() or "connected"
    clean_color = color.strip().lstrip("#")
    if clean_color and not _COLOR_PATTERN.fullmatch(clean_color):
        raise ChangePlanError("El color debe contener seis caracteres hexadecimales.")

    normalized_length = _validated_length(length)
    payload: dict[str, Any] = {
        "a_terminations": [{
            "object_type": endpoint_a.object_type,
            "object_id": endpoint_a.object_id,
        }],
        "b_terminations": [{
            "object_type": endpoint_b.object_type,
            "object_id": endpoint_b.object_id,
        }],
        "status": clean_status,
        "changelog_message": (
            "Conexión preparada y confirmada en NetDoc por "
            f"{requested_by.strip()}."
        ),
    }

    if cable_type.strip():
        payload["type"] = cable_type.strip()
    if label.strip():
        payload["label"] = label.strip()
    if clean_color:
        payload["color"] = clean_color.lower()
    if normalized_length is not None:
        payload["length"] = normalized_length
        payload["length_unit"] = length_unit.strip() or "m"
    if description.strip():
        payload["description"] = description.strip()

    warnings: list[str] = []
    if endpoint_a.enabled is False or endpoint_b.enabled is False:
        warnings.append(
            "Uno de los extremos está deshabilitado; confirma que la conexión es intencional."
        )
    if not cable_type.strip():
        warnings.append("El cable se creará sin tipo físico documentado.")

    summary = f"Conectar {endpoint_a.display} con {endpoint_b.display}."
    step = ChangeStep(
        step_id="create-cable",
        action="CABLE_CREATE",
        resource="cable",
        method="POST",
        endpoint="/api/dcim/cables/",
        payload=payload,
        summary=summary,
        required_permission="devices.create",
        change_reason=summary,
    )
    plan = ChangePlan(
        intent=summary,
        requested_by=requested_by.strip(),
        steps=(step,),
        warnings=tuple(warnings),
        metadata={
            "source": source,
            "endpoint_a": endpoint_a.display,
            "endpoint_b": endpoint_b.display,
        },
    )
    validate_plan_capabilities(plan.steps, for_ai=source == "ai")
    return plan
