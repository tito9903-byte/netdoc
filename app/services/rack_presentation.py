from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


HALF_UNIT = Decimal("0.5")


def nested_label(value: Any, fallback: str = "—") -> str:
    if isinstance(value, dict):
        return str(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("value")
            or fallback
        )
    if value not in (None, ""):
        return str(value)
    return fallback


def decimal_value(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def normalize_half_unit(value: Any, *, minimum: Decimal = Decimal("0")) -> Decimal:
    number = decimal_value(value)
    if number < minimum:
        return minimum
    return (number / HALF_UNIT).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * HALF_UNIT


def format_u(value: Any) -> str:
    number = normalize_half_unit(value)
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def face_value(device: dict[str, Any]) -> str:
    face = device.get("face")
    if isinstance(face, dict):
        return str(face.get("value") or "")
    return str(face or "")


def device_type_identifier(device: dict[str, Any]) -> int | None:
    device_type = device.get("device_type") or {}
    if isinstance(device_type, dict) and isinstance(device_type.get("id"), int):
        return int(device_type["id"])
    value = device.get("device_type_id")
    return int(value) if isinstance(value, int) else None


def _image_proxy(device_type: dict[str, Any], face: str) -> str:
    image_value = device_type.get(f"{face}_image")
    device_type_id = device_type.get("id")
    if image_value and isinstance(device_type_id, int):
        return f"/media/device-types/{device_type_id}/{face}"
    return ""


def prepare_device(device: dict[str, Any]) -> dict[str, Any]:
    device_type = device.get("device_type") or {}
    if not isinstance(device_type, dict):
        device_type = {}

    height = normalize_half_unit(device_type.get("u_height"))
    current_face = face_value(device)
    full_depth = bool(
        device_type.get("is_full_depth")
        if device_type.get("is_full_depth") is not None
        else device_type.get("full_depth")
    )
    front_image = _image_proxy(device_type, "front")
    rear_image = _image_proxy(device_type, "rear")

    return {
        **device,
        "_model": nested_label(device_type),
        "_manufacturer": nested_label(device_type.get("manufacturer"), ""),
        "_status": nested_label(device.get("status")),
        "_face": current_face or "sin definir",
        "_u_height": float(height),
        "_u_height_label": f"{format_u(height)}U",
        "_full_depth": full_depth,
        "_front_image": front_image,
        "_rear_image": rear_image,
        "_has_image": bool(front_image or rear_image),
    }


def _unit_labels(
    *,
    rack_height: int,
    starting_unit: int,
    descending: bool,
) -> list[dict[str, int | str]]:
    highest = starting_unit + rack_height - 1
    values = (
        range(starting_unit, highest + 1)
        if descending
        else range(highest, starting_unit - 1, -1)
    )
    return [
        {
            "label": f"U{unit}",
            "grid_start": index * 2 + 1,
            "span": 2,
        }
        for index, unit in enumerate(values)
    ]


def prepare_elevation(
    rack: dict[str, Any],
    devices: list[dict[str, Any]],
    selected_face: str,
) -> dict[str, Any]:
    rack_height = max(1, int(decimal_value(rack.get("u_height"), Decimal("42"))))
    starting_unit = int(decimal_value(rack.get("starting_unit"), Decimal("1")))
    descending = bool(rack.get("desc_units"))
    total_slots = rack_height * 2
    highest_boundary = Decimal(starting_unit + rack_height)

    occupied_slots: set[int] = set()
    face_slots: dict[str, dict[int, list[int]]] = {
        "front": defaultdict(list),
        "rear": defaultdict(list),
    }
    positioned_devices: list[dict[str, Any]] = []
    unpositioned_devices: list[dict[str, Any]] = []
    zero_u_devices: list[dict[str, Any]] = []

    for raw_device in devices:
        prepared = prepare_device(raw_device)
        height = normalize_half_unit(prepared.get("_u_height"))

        if height <= 0:
            zero_u_devices.append(prepared)
            continue

        position = decimal_value(raw_device.get("position"), Decimal("-999"))
        if position == Decimal("-999"):
            unpositioned_devices.append(prepared)
            continue

        position = normalize_half_unit(position)
        upper_boundary = position + height
        if position < Decimal(starting_unit) or upper_boundary > highest_boundary:
            prepared["_position_error"] = "Fuera del rango del rack"
            unpositioned_devices.append(prepared)
            continue

        start_slot = int((position - Decimal(starting_unit)) / HALF_UNIT) + 1
        height_slots = max(1, int(height / HALF_UNIT))
        upper_slot = start_slot + height_slots - 1
        if upper_slot > total_slots:
            prepared["_position_error"] = "Supera la altura del rack"
            unpositioned_devices.append(prepared)
            continue

        if descending:
            grid_start = start_slot
        else:
            grid_start = total_slots - upper_slot + 1

        device_id = raw_device.get("id")
        device_key = int(device_id) if isinstance(device_id, int) else id(raw_device)
        current_face = face_value(raw_device)
        full_depth = bool(prepared.get("_full_depth"))
        faces = (
            {"front", "rear"}
            if full_depth or current_face not in {"front", "rear"}
            else {current_face}
        )

        for slot in range(start_slot, upper_slot + 1):
            occupied_slots.add(slot)
            for face in faces:
                face_slots[face][slot].append(device_key)

        end_position = upper_boundary - HALF_UNIT
        position_label = (
            f"U{format_u(position)}"
            if height <= HALF_UNIT
            else f"U{format_u(position)}–U{format_u(end_position)}"
        )
        prepared.update({
            "_position": float(position),
            "_position_label": position_label,
            "_grid_start": grid_start,
            "_span": height_slots,
            "_start_slot": start_slot,
            "_upper_slot": upper_slot,
            "_top_percent": round(((grid_start - 1) / total_slots) * 100, 4),
            "_height_percent": round((height_slots / total_slots) * 100, 4),
            "_device_key": device_key,
        })
        positioned_devices.append(prepared)

    conflict_keys: set[int] = set()
    overlap_slots: set[tuple[str, int]] = set()
    for face, slots in face_slots.items():
        for slot, keys in slots.items():
            unique = set(keys)
            if len(unique) > 1:
                overlap_slots.add((face, slot))
                conflict_keys.update(unique)

    for device in positioned_devices:
        device["_has_conflict"] = device.get("_device_key") in conflict_keys
        selected_image = (
            device.get("_rear_image")
            if selected_face == "rear"
            else device.get("_front_image")
        )
        device["_selected_image"] = (
            selected_image
            or device.get("_front_image")
            or device.get("_rear_image")
            or ""
        )

    visible_devices = [
        device
        for device in positioned_devices
        if device.get("_full_depth")
        or device.get("_face") == selected_face
        or device.get("_face") == "sin definir"
    ]
    visible_devices.sort(
        key=lambda item: (
            int(item.get("_grid_start") or 0),
            str(item.get("name") or ""),
        )
    )

    used_units = Decimal(len(occupied_slots)) * HALF_UNIT
    free_units = max(Decimal("0"), Decimal(rack_height) - used_units)
    utilization = round((float(used_units) / rack_height) * 100, 1)

    return {
        "rack_height": rack_height,
        "rack_slots": total_slots,
        "starting_unit": starting_unit,
        "descending_units": descending,
        "unit_labels": _unit_labels(
            rack_height=rack_height,
            starting_unit=starting_unit,
            descending=descending,
        ),
        "positioned_devices": positioned_devices,
        "visible_devices": visible_devices,
        "unpositioned_devices": unpositioned_devices,
        "zero_u_devices": zero_u_devices,
        "used_units": float(used_units),
        "used_units_label": format_u(used_units),
        "free_units": float(free_units),
        "free_units_label": format_u(free_units),
        "utilization": utilization,
        "overlap_count": len(overlap_slots),
        "has_conflicts": bool(overlap_slots),
    }


def prepare_topology(
    *,
    sites: list[dict[str, Any]],
    racks: list[dict[str, Any]],
    devices: list[dict[str, Any]],
) -> dict[str, Any]:
    devices_by_rack: dict[int, list[dict[str, Any]]] = defaultdict(list)
    unracked_devices: list[dict[str, Any]] = []

    for device in devices:
        rack = device.get("rack") or {}
        rack_id = rack.get("id") if isinstance(rack, dict) else None
        if isinstance(rack_id, int):
            devices_by_rack[rack_id].append(device)
        else:
            unracked_devices.append(prepare_device(device))

    site_map = {
        item.get("id"): {
            "id": item.get("id"),
            "name": nested_label(item, "Sin sitio"),
            "racks": [],
            "device_count": 0,
            "used_units": Decimal("0"),
            "capacity_units": 0,
        }
        for item in sites
        if isinstance(item.get("id"), int)
    }

    all_racks: list[dict[str, Any]] = []
    total_used = Decimal("0")
    total_capacity = 0
    mounted_count = 0
    image_count = 0

    for rack in racks:
        rack_id = rack.get("id")
        if not isinstance(rack_id, int):
            continue
        rack_devices = devices_by_rack.get(rack_id, [])
        elevation = prepare_elevation(rack, rack_devices, "front")
        rack_site = rack.get("site") or {}
        site_id = rack_site.get("id") if isinstance(rack_site, dict) else None
        capacity = elevation["rack_height"]
        used = Decimal(str(elevation["used_units"]))
        mounted = len(elevation["positioned_devices"])
        images = sum(
            1 for device in elevation["positioned_devices"]
            if device.get("_has_image")
        )
        prepared_rack = {
            **rack,
            "_site_label": nested_label(rack_site, "Sin sitio"),
            "_location_label": nested_label(rack.get("location")),
            "_status_label": nested_label(rack.get("status")),
            "_device_count": len(rack_devices),
            "_mounted_count": mounted,
            "_u_height": capacity,
            "_used_units": float(used),
            "_used_units_label": format_u(used),
            "_free_units_label": elevation["free_units_label"],
            "_utilization": elevation["utilization"],
            "_has_conflicts": elevation["has_conflicts"],
            "_devices": elevation["positioned_devices"],
            "_zero_u_devices": elevation["zero_u_devices"],
        }
        all_racks.append(prepared_rack)
        total_used += used
        total_capacity += capacity
        mounted_count += mounted
        image_count += images

        group = site_map.get(site_id)
        if group is None:
            group = site_map.setdefault(
                site_id,
                {
                    "id": site_id,
                    "name": nested_label(rack_site, "Sin sitio"),
                    "racks": [],
                    "device_count": 0,
                    "used_units": Decimal("0"),
                    "capacity_units": 0,
                },
            )
        group["racks"].append(prepared_rack)
        group["device_count"] += len(rack_devices)
        group["used_units"] += used
        group["capacity_units"] += capacity

    site_groups = []
    for group in site_map.values():
        if not group["racks"]:
            continue
        group["racks"].sort(key=lambda item: str(item.get("name") or "").casefold())
        group["used_units_label"] = format_u(group["used_units"])
        group["utilization"] = round(
            (float(group["used_units"]) / group["capacity_units"]) * 100,
            1,
        ) if group["capacity_units"] else 0.0
        site_groups.append(group)

    site_groups.sort(key=lambda item: str(item["name"]).casefold())
    all_racks.sort(
        key=lambda item: (
            str(item.get("_site_label") or "").casefold(),
            str(item.get("name") or "").casefold(),
        )
    )

    return {
        "topology_sites": site_groups,
        "topology_racks": all_racks,
        "unracked_devices": unracked_devices,
        "topology_summary": {
            "sites": len(site_groups),
            "racks": len(all_racks),
            "devices": mounted_count,
            "capacity_units": total_capacity,
            "used_units": float(total_used),
            "used_units_label": format_u(total_used),
            "utilization": round(
                (float(total_used) / total_capacity) * 100,
                1,
            ) if total_capacity else 0.0,
            "devices_with_images": image_count,
        },
    }
