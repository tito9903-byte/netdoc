from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable, Mapping

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdfcanvas

from app.services.rack_report_service import (
    BG,
    CYAN,
    FRAME,
    FRAME_LIGHT,
    GREEN,
    MARGIN,
    MUTED,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    PANEL,
    PANEL_ALT,
    RED,
    TEXT,
    PreparedImage,
    RackReportError,
    ReportImage,
    _clean_text,
    _collect_image_assets,
    _device_type_id,
    _draw_background,
    _draw_footer,
    _draw_header,
    _draw_image_contain,
    _draw_inventory_page,
    _draw_summary_card,
    _draw_text,
    _inventory_rows,
    _label,
    _normalize_assets,
    _prepare_image,
    _safe_filename,
)

DETAIL_SEGMENT_UNITS = 14
DETAIL_SEGMENT_SLOTS = DETAIL_SEGMENT_UNITS * 2


def _prepare_images(
    elevation: Mapping[str, Any],
    face: str,
    image_assets: Mapping[
        int,
        ReportImage | tuple[bytes, str, str],
    ]
    | None,
) -> dict[int, PreparedImage]:
    assets = _collect_image_assets(elevation, face)
    assets.update(_normalize_assets(image_assets))
    return {
        device_type_id: prepared
        for device_type_id, asset in assets.items()
        if (prepared := _prepare_image(asset)) is not None
    }


def _segment_label(
    elevation: Mapping[str, Any],
    start_slot: int,
    end_slot: int,
) -> str:
    labels = [
        item
        for item in elevation.get("unit_labels", [])
        if start_slot <= int(item.get("grid_start") or 0) <= end_slot
    ]
    if not labels:
        return "Detalle del rack"
    top = _clean_text(labels[0].get("label"))
    bottom = _clean_text(labels[-1].get("label"))
    return f"{top} a {bottom}"


def _visible_segment_devices(
    devices: Iterable[dict[str, Any]],
    start_slot: int,
    end_slot: int,
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for device in devices:
        device_start = int(device.get("_grid_start") or 0)
        span = max(1, int(device.get("_span") or 1))
        device_end = device_start + span - 1
        overlap_start = max(device_start, start_slot)
        overlap_end = min(device_end, end_slot)
        if overlap_start > overlap_end:
            continue
        visible.append({
            **device,
            "_segment_start": overlap_start,
            "_segment_span": overlap_end - overlap_start + 1,
            "_continues_above": device_start < start_slot,
            "_continues_below": device_end > end_slot,
        })
    return visible


def _draw_overview_rack(
    pdf: pdfcanvas.Canvas,
    *,
    elevation: Mapping[str, Any],
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    rack_x = 64
    rack_y = 64
    rack_width = 300
    rack_height_points = 350
    frame = 12

    pdf.setFillColor(HexColor("#132630"))
    pdf.setStrokeColor(FRAME_LIGHT)
    pdf.setLineWidth(1.3)
    pdf.roundRect(
        rack_x,
        rack_y,
        rack_width,
        rack_height_points,
        7,
        fill=1,
        stroke=1,
    )

    inner_x = rack_x + frame
    inner_y = rack_y + frame
    inner_width = rack_width - frame * 2
    inner_height = rack_height_points - frame * 2

    pdf.setFillColor(HexColor("#020608"))
    pdf.rect(
        inner_x,
        inner_y,
        inner_width,
        inner_height,
        fill=1,
        stroke=0,
    )

    rack_slots = max(2, int(elevation.get("rack_slots") or 84))
    slot_height = inner_height / rack_slots
    pdf.setStrokeColor(HexColor("#18313D"))
    pdf.setLineWidth(0.25)
    for slot in range(2, rack_slots, 2):
        y = inner_y + inner_height - slot * slot_height
        pdf.line(inner_x + 7, y, inner_x + inner_width - 7, y)

    for device in elevation.get("visible_devices", []):
        grid_start = int(device.get("_grid_start") or 1)
        span = max(1, int(device.get("_span") or 1))
        box_height = max(2.0, span * slot_height - 1)
        box_y = inner_y + inner_height - (grid_start - 1) * slot_height - box_height
        box_x = inner_x + 10
        box_width = inner_width - 20

        pdf.setFillColor(HexColor("#071319"))
        pdf.setStrokeColor(
            RED if device.get("_has_conflict") else CYAN
        )
        pdf.rect(
            box_x,
            box_y,
            box_width,
            box_height,
            fill=1,
            stroke=1,
        )

        device_type_id = _device_type_id(device)
        image = prepared_images.get(device_type_id or -1)
        if image is not None and box_height >= 3:
            _draw_image_contain(
                pdf,
                image,
                x=box_x + 2,
                y=box_y + 0.5,
                width=box_width - 4,
                height=max(1, box_height - 1),
            )

        pdf.setFillColor(GREEN)
        pdf.circle(
            box_x + 4,
            box_y + box_height / 2,
            1.4,
            fill=1,
            stroke=0,
        )

    _draw_text(
        pdf,
        rack_x,
        rack_y + rack_height_points + 12,
        "Vista general del rack",
        size=9,
        color=CYAN,
        bold=True,
    )


def _draw_summary_page(
    pdf: pdfcanvas.Canvas,
    *,
    rack: Mapping[str, Any],
    elevation: Mapping[str, Any],
    face: str,
    generated_at: str,
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    _draw_background(pdf)
    rack_name = _clean_text(
        rack.get("name") or rack.get("display") or "Rack"
    )
    site = _label(rack.get("site"), "Sin sitio")
    location = _label(rack.get("location"), "Sin ubicación")

    _draw_header(
        pdf,
        title=f"Rack {rack_name}",
        subtitle=f"Inventario datacenter · {site} · {location}",
        page_number=1,
    )

    card_y = PAGE_HEIGHT - 128
    cards = [
        ("Altura", f"{elevation.get('rack_height', 0)}U"),
        ("Ocupadas", f"{elevation.get('used_units_label', '0')}U"),
        ("Libres", f"{elevation.get('free_units_label', '0')}U"),
        ("Utilización", f"{elevation.get('utilization', 0)}%"),
        ("Equipos", str(len(_inventory_rows(elevation)))),
    ]
    for index, (label, value) in enumerate(cards):
        _draw_summary_card(
            pdf,
            MARGIN + index * 155,
            card_y,
            label,
            value,
        )

    _draw_overview_rack(
        pdf,
        elevation=elevation,
        prepared_images=prepared_images,
    )

    info_x = 405
    info_top = 405
    info_width = 395
    row_height = 30
    _draw_text(
        pdf,
        info_x,
        info_top + 12,
        "Información del rack",
        size=13,
        bold=True,
    )

    info = [
        ("Sitio", site),
        ("Ubicación", location),
        ("Estado", _label(rack.get("status"), "Sin estado")),
        ("Ancho", _label(rack.get("width"), "-")),
        ("Serial", rack.get("serial") or "-"),
        ("Etiqueta de activo", rack.get("asset_tag") or "-"),
        (
            "Numeración",
            "Descendente"
            if elevation.get("descending_units")
            else "Ascendente",
        ),
        (
            "Cara del reporte",
            "Frontal" if face == "front" else "Trasera",
        ),
    ]

    cursor = info_top
    for index, (label, value) in enumerate(info):
        cursor -= row_height
        pdf.setFillColor(PANEL if index % 2 == 0 else PANEL_ALT)
        pdf.setStrokeColor(FRAME)
        pdf.rect(
            info_x,
            cursor,
            info_width,
            row_height - 3,
            fill=1,
            stroke=1,
        )
        _draw_text(
            pdf,
            info_x + 10,
            cursor + 10,
            label,
            size=7.2,
            color=MUTED,
        )
        _draw_text(
            pdf,
            info_x + 145,
            cursor + 10,
            value,
            size=8.2,
            bold=True,
            max_width=235,
        )

    callout_y = 70
    callout_height = 82
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(
        info_x,
        callout_y,
        info_width,
        callout_height,
        8,
        fill=1,
        stroke=1,
    )
    _draw_text(
        pdf,
        info_x + 12,
        callout_y + callout_height - 21,
        "Cómo leer este reporte",
        size=10,
        color=CYAN,
        bold=True,
    )
    notes = [
        "La primera página es una vista general del gabinete.",
        "Las páginas siguientes amplían 14U para mostrar las fotos.",
        "Las fotos corresponden a la cara frontal o trasera elegida.",
    ]
    note_y = callout_y + callout_height - 42
    for note in notes:
        pdf.setFillColor(CYAN)
        pdf.circle(info_x + 15, note_y + 2, 2, fill=1, stroke=0)
        _draw_text(
            pdf,
            info_x + 27,
            note_y,
            note,
            size=7.2,
            color=MUTED,
        )
        note_y -= 17

    _draw_footer(pdf, generated_at)
    pdf.showPage()


def _draw_segment_page(
    pdf: pdfcanvas.Canvas,
    *,
    rack_name: str,
    elevation: Mapping[str, Any],
    face: str,
    generated_at: str,
    page_number: int,
    start_slot: int,
    end_slot: int,
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    _draw_background(pdf)
    segment_label = _segment_label(elevation, start_slot, end_slot)
    _draw_header(
        pdf,
        title=f"Rack {rack_name} · Detalle ampliado",
        subtitle=(
            f"{segment_label} · "
            f"{'Frontal' if face == 'front' else 'Trasera'}"
        ),
        page_number=page_number,
    )

    rack_x = 92
    rack_y = 72
    rack_width = 660
    rack_height_points = 425
    frame = 13
    inner_x = rack_x + frame
    inner_y = rack_y + frame
    inner_width = rack_width - frame * 2
    inner_height = rack_height_points - frame * 2
    segment_slots = end_slot - start_slot + 1
    slot_height = inner_height / segment_slots

    pdf.setFillColor(HexColor("#132630"))
    pdf.setStrokeColor(FRAME_LIGHT)
    pdf.setLineWidth(1.4)
    pdf.roundRect(
        rack_x,
        rack_y,
        rack_width,
        rack_height_points,
        8,
        fill=1,
        stroke=1,
    )
    pdf.setFillColor(HexColor("#020608"))
    pdf.rect(
        inner_x,
        inner_y,
        inner_width,
        inner_height,
        fill=1,
        stroke=0,
    )

    unit_labels = [
        item
        for item in elevation.get("unit_labels", [])
        if start_slot <= int(item.get("grid_start") or 0) <= end_slot
    ]
    for item in unit_labels:
        grid_start = int(item.get("grid_start") or start_slot)
        relative_slot = grid_start - start_slot
        y_top = inner_y + inner_height - relative_slot * slot_height
        pdf.setStrokeColor(HexColor("#274754"))
        pdf.setLineWidth(0.45)
        pdf.line(inner_x, y_top, inner_x + inner_width, y_top)
        _draw_text(
            pdf,
            rack_x - 42,
            y_top - slot_height * 1.35,
            item.get("label"),
            size=8,
            color=MUTED,
            bold=True,
        )

    pdf.setStrokeColor(HexColor("#18313D"))
    pdf.setLineWidth(0.25)
    for slot in range(start_slot + 1, end_slot + 1):
        relative_slot = slot - start_slot
        y = inner_y + inner_height - relative_slot * slot_height
        pdf.line(inner_x, y, inner_x + inner_width, y)

    devices = _visible_segment_devices(
        elevation.get("visible_devices", []),
        start_slot,
        end_slot,
    )
    for device in devices:
        relative_start = int(device["_segment_start"]) - start_slot
        span = int(device["_segment_span"])
        box_height = max(5.0, span * slot_height - 1.6)
        box_y = (
            inner_y
            + inner_height
            - relative_start * slot_height
            - box_height
        )
        box_x = inner_x + 13
        box_width = inner_width - 26

        pdf.setFillColor(
            HexColor("#5C171D")
            if device.get("_has_conflict")
            else HexColor("#071319")
        )
        pdf.setStrokeColor(
            RED if device.get("_has_conflict") else CYAN
        )
        pdf.setLineWidth(0.9)
        pdf.rect(
            box_x,
            box_y,
            box_width,
            box_height,
            fill=1,
            stroke=1,
        )

        device_type_id = _device_type_id(device)
        image = prepared_images.get(device_type_id or -1)
        if image is not None:
            _draw_image_contain(
                pdf,
                image,
                x=box_x + 6,
                y=box_y + 2,
                width=box_width - 12,
                height=max(1, box_height - 4),
            )
        else:
            _draw_text(
                pdf,
                box_x + 14,
                box_y + box_height / 2 - 3,
                device.get("name")
                or device.get("display")
                or "Equipo",
                size=min(10, max(6.5, box_height * 0.34)),
                bold=True,
                max_width=box_width - 28,
            )

        pdf.setFillColor(GREEN)
        pdf.circle(
            box_x + 5,
            box_y + box_height / 2,
            1.8,
            fill=1,
            stroke=0,
        )

        if box_height >= 24:
            pdf.saveState()
            pdf.setFillAlpha(0.82)
            pdf.setFillColor(HexColor("#02080C"))
            label_width = min(220, box_width * 0.45)
            pdf.rect(
                box_x + 8,
                box_y + 3,
                label_width,
                14,
                fill=1,
                stroke=0,
            )
            pdf.restoreState()
            _draw_text(
                pdf,
                box_x + 14,
                box_y + 7,
                device.get("name")
                or device.get("display")
                or "Equipo",
                size=6.4,
                bold=True,
                max_width=label_width - 12,
            )

        if device.get("_continues_above"):
            _draw_text(
                pdf,
                box_x + box_width - 74,
                box_y + box_height - 9,
                "Continúa arriba",
                size=6,
                color=MUTED,
            )
        if device.get("_continues_below"):
            _draw_text(
                pdf,
                box_x + box_width - 72,
                box_y + 4,
                "Continúa abajo",
                size=6,
                color=MUTED,
            )

    _draw_text(
        pdf,
        rack_x,
        48,
        (
            "Cada página muestra 14U ampliadas. "
            "Las fotografías conservan su proporción original."
        ),
        size=7.5,
        color=MUTED,
    )
    _draw_footer(pdf, generated_at)
    pdf.showPage()


def build_rack_report(
    *,
    rack: dict[str, Any],
    elevation: dict[str, Any],
    face: str,
    image_assets: Mapping[
        int,
        ReportImage | tuple[bytes, str, str],
    ]
    | None = None,
) -> tuple[bytes, str]:
    selected_face = "rear" if face == "rear" else "front"
    rack_name = _clean_text(
        rack.get("name") or rack.get("display") or "Rack"
    )
    generated_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%d %H:%M")
    inventory = _inventory_rows(elevation)
    prepared_images = _prepare_images(
        elevation,
        selected_face,
        image_assets,
    )

    output = BytesIO()
    pdf = pdfcanvas.Canvas(
        output,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        pageCompression=1,
        pdfVersion=(1, 4),
    )
    pdf.setTitle(f"Rack {rack_name} - Inventario datacenter")
    pdf.setAuthor("NetDoc")
    pdf.setCreator("NetDoc")

    _draw_summary_page(
        pdf,
        rack=rack,
        elevation=elevation,
        face=selected_face,
        generated_at=generated_at,
        prepared_images=prepared_images,
    )

    total_slots = max(2, int(elevation.get("rack_slots") or 84))
    page_number = 2
    for start_slot in range(1, total_slots + 1, DETAIL_SEGMENT_SLOTS):
        end_slot = min(
            total_slots,
            start_slot + DETAIL_SEGMENT_SLOTS - 1,
        )
        _draw_segment_page(
            pdf,
            rack_name=rack_name,
            elevation=elevation,
            face=selected_face,
            generated_at=generated_at,
            page_number=page_number,
            start_slot=start_slot,
            end_slot=end_slot,
            prepared_images=prepared_images,
        )
        page_number += 1

    rows_per_page = 10
    for start in range(0, max(1, len(inventory)), rows_per_page):
        _draw_inventory_page(
            pdf,
            inventory[start : start + rows_per_page],
            rack_name=rack_name,
            page_number=page_number,
            generated_at=generated_at,
            start_index=start,
            prepared_images=prepared_images,
        )
        page_number += 1

    pdf.save()
    value = output.getvalue()
    if not value.startswith(b"%PDF-"):
        raise RackReportError("No se pudo preparar el reporte del rack.")

    filename = f"rack-{_safe_filename(rack_name)}-inventario.pdf"
    return value, filename
