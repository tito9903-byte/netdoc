from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterable, Mapping

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

from app.services.rack_report_service import (
    BG,
    CYAN,
    FRAME,
    FRAME_LIGHT,
    GREEN,
    GRID,
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
    _draw_summary_card,
    _draw_text,
    _inventory_rows,
    _label,
    _normalize_assets,
    _prepare_image,
    _safe_filename,
)

DETAIL_UNITS = 7
DETAIL_SLOTS = DETAIL_UNITS * 2
INVENTORY_ROWS_PER_PAGE = 8
BLACK = HexColor("#020608")
GRID_MAJOR = HexColor("#294A58")


def _format_u_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _report_position(device: Mapping[str, Any]) -> str:
    state = _clean_text(device.get("_inventory_state"), "")
    if state and state not in {"Posicionado", "-"}:
        return state
    try:
        position = float(device.get("_position"))
        height = float(device.get("_u_height") or 0)
    except (TypeError, ValueError):
        return _clean_text(device.get("_position_label"), "Sin posición")
    if height <= 1:
        return f"U{_format_u_number(position)}"
    end_position = position + height - 1
    return f"U{_format_u_number(position)}-U{_format_u_number(end_position)}"


def _prepare_images(
    elevation: Mapping[str, Any],
    face: str,
    image_assets: Mapping[int, ReportImage | tuple[bytes, str, str]] | None,
) -> dict[int, PreparedImage]:
    assets = _collect_image_assets(elevation, face)
    assets.update(_normalize_assets(image_assets))
    return {
        device_type_id: prepared
        for device_type_id, asset in assets.items()
        if (prepared := _prepare_image(asset)) is not None
    }


def _draw_centered_text(
    pdf: pdfcanvas.Canvas,
    x: float,
    y: float,
    width: float,
    value: Any,
    *,
    size: float = 8,
    color=TEXT,
    bold: bool = False,
) -> None:
    text = _clean_text(value)
    font = "Helvetica-Bold" if bold else "Helvetica"
    while len(text) > 3 and stringWidth(text, font, size) > width:
        text = text[:-1]
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawCentredString(x + width / 2, y, text)


def _draw_overview_rack(
    pdf: pdfcanvas.Canvas,
    *,
    elevation: Mapping[str, Any],
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    rack_x, rack_y, rack_width, rack_height = 68, 64, 270, 340
    frame = 12
    inner_x, inner_y = rack_x + frame, rack_y + frame
    inner_width, inner_height = rack_width - frame * 2, rack_height - frame * 2
    total_slots = max(2, int(elevation.get("rack_slots") or 84))
    slot_height = inner_height / total_slots

    pdf.setFillColor(HexColor("#132630"))
    pdf.setStrokeColor(FRAME_LIGHT)
    pdf.setLineWidth(1.4)
    pdf.roundRect(rack_x, rack_y, rack_width, rack_height, 8, fill=1, stroke=1)
    pdf.setFillColor(BLACK)
    pdf.rect(inner_x, inner_y, inner_width, inner_height, fill=1, stroke=0)
    pdf.setStrokeColor(GRID)
    pdf.setLineWidth(0.25)
    for slot in range(1, total_slots):
        y = inner_y + inner_height - slot * slot_height
        pdf.line(inner_x, y, inner_x + inner_width, y)

    for device in elevation.get("visible_devices", []):
        try:
            start = int(device.get("_grid_start") or 1)
            span = int(device.get("_span") or 1)
        except (TypeError, ValueError):
            continue
        box_height = max(2.2, span * slot_height - 0.5)
        box_y = inner_y + inner_height - (start - 1 + span) * slot_height
        box_x, box_width = inner_x + 8, inner_width - 16
        conflict = bool(device.get("_has_conflict"))
        pdf.setFillColor(HexColor("#5C171D") if conflict else HexColor("#071319"))
        pdf.setStrokeColor(RED if conflict else CYAN)
        pdf.setLineWidth(0.55)
        pdf.rect(box_x, box_y, box_width, box_height, fill=1, stroke=1)
        image = prepared_images.get(_device_type_id(device) or -1)
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
        pdf.circle(box_x + 4, box_y + box_height / 2, 1.3, fill=1, stroke=0)

    _draw_text(
        pdf,
        rack_x,
        rack_y + rack_height + 12,
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
    rack_name = _clean_text(rack.get("name") or rack.get("display") or "Rack")
    site = _label(rack.get("site"), "Sin sitio")
    location = _label(rack.get("location"), "Sin ubicación")
    _draw_header(
        pdf,
        title=f"Rack {rack_name}",
        subtitle=f"Inventario datacenter - {site} - {location}",
        page_number=1,
    )

    cards = [
        ("Altura", f"{elevation.get('rack_height', 0)}U"),
        ("Ocupadas", f"{elevation.get('used_units_label', '0')}U"),
        ("Libres", f"{elevation.get('free_units_label', '0')}U"),
        ("Utilización", f"{elevation.get('utilization', 0)}%"),
        ("Equipos", str(len(_inventory_rows(elevation)))),
    ]
    card_y = PAGE_HEIGHT - 128
    for index, (label, value) in enumerate(cards):
        _draw_summary_card(pdf, MARGIN + index * 155, card_y, label, value)

    _draw_overview_rack(pdf, elevation=elevation, prepared_images=prepared_images)

    info_x, info_top, info_width, row_height = 382, 405, 418, 28
    _draw_text(pdf, info_x, info_top + 14, "Información del rack", size=13, bold=True)
    info = [
        ("Sitio", site),
        ("Ubicación", location),
        ("Estado", _label(rack.get("status"), "Sin estado")),
        ("Ancho", _label(rack.get("width"), "-")),
        ("Serial", rack.get("serial") or "-"),
        ("Etiqueta de activo", rack.get("asset_tag") or "-"),
        ("Numeración", "Descendente" if elevation.get("descending_units") else "Ascendente"),
        ("Cara", "Frontal" if face == "front" else "Trasera"),
    ]
    cursor = info_top
    for index, (label, value) in enumerate(info):
        cursor -= row_height
        pdf.setFillColor(PANEL if index % 2 == 0 else PANEL_ALT)
        pdf.setStrokeColor(FRAME)
        pdf.rect(info_x, cursor, info_width, row_height - 3, fill=1, stroke=1)
        _draw_text(pdf, info_x + 10, cursor + 9, label, size=7.2, color=MUTED)
        _draw_text(
            pdf,
            info_x + 150,
            cursor + 9,
            value,
            size=8.2,
            bold=True,
            max_width=250,
        )

    callout_y, callout_height = 70, 78
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(info_x, callout_y, info_width, callout_height, 8, fill=1, stroke=1)
    _draw_text(
        pdf,
        info_x + 12,
        callout_y + callout_height - 21,
        "Contenido del reporte",
        size=10,
        color=CYAN,
        bold=True,
    )
    notes = [
        "La primera página resume el gabinete completo.",
        "Solo se generan detalles de rangos que contienen equipos.",
        "Cada detalle amplía 7U para que las fotografías sean legibles.",
    ]
    note_y = callout_y + callout_height - 42
    for note in notes:
        pdf.setFillColor(CYAN)
        pdf.circle(info_x + 15, note_y + 2, 2, fill=1, stroke=0)
        _draw_text(pdf, info_x + 27, note_y, note, size=7.2, color=MUTED)
        note_y -= 17

    _draw_footer(pdf, generated_at)
    pdf.showPage()


def _occupied_windows(elevation: Mapping[str, Any]) -> list[tuple[int, int]]:
    total_slots = max(2, int(elevation.get("rack_slots") or 84))
    buckets: set[int] = set()
    for device in elevation.get("visible_devices", []):
        try:
            start = int(device.get("_grid_start") or 0)
            span = max(1, int(device.get("_span") or 1))
        except (TypeError, ValueError):
            continue
        if start <= 0:
            continue
        end = min(total_slots, start + span - 1)
        buckets.update(range((start - 1) // DETAIL_SLOTS, (end - 1) // DETAIL_SLOTS + 1))
    return [
        (bucket * DETAIL_SLOTS + 1, min(total_slots, (bucket + 1) * DETAIL_SLOTS))
        for bucket in sorted(buckets)
    ]


def _segment_label(elevation: Mapping[str, Any], start_slot: int, end_slot: int) -> str:
    labels = [
        str(item.get("label"))
        for item in elevation.get("unit_labels", [])
        if start_slot <= int(item.get("grid_start") or 0) <= end_slot
    ]
    return f"{labels[0]} a {labels[-1]}" if labels else "Detalle del rack"


def _visible_segment_devices(
    devices: Iterable[Mapping[str, Any]], start_slot: int, end_slot: int
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for raw in devices:
        try:
            device_start = int(raw.get("_grid_start") or 0)
            span = max(1, int(raw.get("_span") or 1))
        except (TypeError, ValueError):
            continue
        device_end = device_start + span - 1
        if device_end < start_slot or device_start > end_slot:
            continue
        segment_start = max(device_start, start_slot)
        segment_end = min(device_end, end_slot)
        item = dict(raw)
        item["_segment_start"] = segment_start
        item["_segment_span"] = segment_end - segment_start + 1
        item["_continues_above"] = device_start < start_slot
        item["_continues_below"] = device_end > end_slot
        visible.append(item)
    return sorted(visible, key=lambda item: int(item.get("_segment_start") or 0))


def _draw_placeholder(
    pdf: pdfcanvas.Canvas, *, x: float, y: float, width: float, height: float
) -> None:
    pdf.setFillColor(HexColor("#0A171E"))
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(x, y, width, height, 4, fill=1, stroke=1)
    _draw_centered_text(
        pdf,
        x,
        y + height / 2 - 3,
        width,
        "Sin fotografía registrada",
        size=7,
        color=MUTED,
    )


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
    _draw_header(
        pdf,
        title=f"Rack {rack_name} - Detalle físico",
        subtitle=f"{_segment_label(elevation, start_slot, end_slot)} - {'Frontal' if face == 'front' else 'Trasera'}",
        page_number=page_number,
    )

    rack_x, rack_y, rack_width, rack_height = 58, 70, 742, 430
    frame = 13
    inner_x, inner_y = rack_x + frame, rack_y + frame
    inner_width, inner_height = rack_width - frame * 2, rack_height - frame * 2
    segment_slots = end_slot - start_slot + 1
    slot_height = inner_height / segment_slots

    pdf.setFillColor(HexColor("#132630"))
    pdf.setStrokeColor(FRAME_LIGHT)
    pdf.setLineWidth(1.4)
    pdf.roundRect(rack_x, rack_y, rack_width, rack_height, 8, fill=1, stroke=1)
    pdf.setFillColor(BLACK)
    pdf.rect(inner_x, inner_y, inner_width, inner_height, fill=1, stroke=0)

    for item in elevation.get("unit_labels", []):
        grid_start = int(item.get("grid_start") or 0)
        if not start_slot <= grid_start <= end_slot:
            continue
        relative = grid_start - start_slot
        y_top = inner_y + inner_height - relative * slot_height
        pdf.setStrokeColor(GRID_MAJOR)
        pdf.setLineWidth(0.55)
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
    pdf.setStrokeColor(GRID)
    pdf.setLineWidth(0.25)
    for slot in range(start_slot + 1, end_slot + 1):
        y = inner_y + inner_height - (slot - start_slot) * slot_height
        pdf.line(inner_x, y, inner_x + inner_width, y)

    for device in _visible_segment_devices(
        elevation.get("visible_devices", []), start_slot, end_slot
    ):
        relative_start = int(device["_segment_start"]) - start_slot
        span = int(device["_segment_span"])
        box_height = max(8.0, span * slot_height - 2.2)
        box_y = inner_y + inner_height - (relative_start + span) * slot_height + 1.1
        box_x, box_width = inner_x + 12, inner_width - 24
        conflict = bool(device.get("_has_conflict"))
        pdf.setFillColor(HexColor("#5C171D") if conflict else HexColor("#071319"))
        pdf.setStrokeColor(RED if conflict else CYAN)
        pdf.setLineWidth(1.0)
        pdf.roundRect(box_x, box_y, box_width, box_height, 4, fill=1, stroke=1)

        label_width = min(190.0, box_width * 0.30)
        image_x, image_width = box_x + label_width, box_width - label_width
        pdf.setFillColor(HexColor("#081218"))
        pdf.roundRect(
            box_x + 1, box_y + 1, label_width - 2, box_height - 2, 3, fill=1, stroke=0
        )

        name = device.get("name") or device.get("display") or "Equipo"
        model = device.get("_model") or "Sin modelo"
        status = device.get("_status") or "Sin estado"
        text_y = box_y + box_height - 14
        _draw_text(
            pdf, box_x + 12, text_y, name, size=8.4, bold=True, max_width=label_width - 22
        )
        if box_height >= 34:
            _draw_text(
                pdf,
                box_x + 12,
                text_y - 12,
                model,
                size=6.4,
                color=MUTED,
                max_width=label_width - 22,
            )
        if box_height >= 48:
            _draw_text(
                pdf,
                box_x + 12,
                box_y + 9,
                f"{_report_position(device)} - {status}",
                size=6.2,
                color=GREEN if status.lower() == "active" else MUTED,
                max_width=label_width - 22,
            )

        image = prepared_images.get(_device_type_id(device) or -1)
        if image is not None:
            _draw_image_contain(
                pdf,
                image,
                x=image_x + 8,
                y=box_y + 4,
                width=image_width - 16,
                height=box_height - 8,
            )
        else:
            _draw_placeholder(
                pdf,
                x=image_x + 8,
                y=box_y + 5,
                width=image_width - 16,
                height=max(8, box_height - 10),
            )

        if device.get("_continues_above"):
            _draw_text(
                pdf,
                box_x + box_width - 78,
                box_y + box_height - 10,
                "Continúa arriba",
                size=6,
                color=MUTED,
            )
        if device.get("_continues_below"):
            _draw_text(
                pdf,
                box_x + box_width - 76,
                box_y + 5,
                "Continúa abajo",
                size=6,
                color=MUTED,
            )

    _draw_text(
        pdf,
        rack_x,
        47,
        "Detalle de 7U. Las fotografías aparecen cuando el modelo tiene imagen registrada.",
        size=7.4,
        color=MUTED,
    )
    _draw_footer(pdf, generated_at)
    pdf.showPage()


def _draw_inventory_page(
    pdf: pdfcanvas.Canvas,
    rows: list[dict[str, Any]],
    *,
    rack_name: str,
    page_number: int,
    generated_at: str,
    start_index: int,
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    _draw_background(pdf)
    _draw_header(
        pdf,
        title=f"Rack {rack_name}",
        subtitle="Inventario físico y fotografías disponibles",
        page_number=page_number,
    )
    columns = [
        ("Foto", 100), ("Equipo", 130), ("Modelo", 130), ("Posición", 70),
        ("Altura", 45), ("Cara", 50), ("Estado", 60), ("Serial", 85), ("Activo", 108),
    ]
    table_x, table_top, row_height, header_height = MARGIN, PAGE_HEIGHT - 91, 50, 28
    total_width = sum(width for _, width in columns)
    pdf.setFillColor(HexColor("#123842"))
    pdf.setStrokeColor(CYAN)
    pdf.rect(table_x, table_top - header_height, total_width, header_height, fill=1, stroke=1)
    x = table_x
    for label, width in columns:
        _draw_text(pdf, x + 5, table_top - 18, label, size=7.2, bold=True)
        x += width

    y = table_top - header_height
    for offset, device in enumerate(rows):
        row_index = start_index + offset + 1
        y -= row_height
        pdf.setFillColor(PANEL if row_index % 2 else PANEL_ALT)
        pdf.setStrokeColor(FRAME)
        pdf.rect(table_x, y, total_width, row_height, fill=1, stroke=1)
        image = prepared_images.get(_device_type_id(device) or -1)
        if image is not None:
            _draw_image_contain(pdf, image, x=table_x + 5, y=y + 6, width=90, height=38)
        else:
            _draw_centered_text(pdf, table_x + 5, y + 21, 90, "Sin foto", size=6.7, color=MUTED)
        values = [
            device.get("name") or device.get("display"),
            device.get("_model"),
            _report_position(device),
            device.get("_u_height_label") or "0U",
            _label(device.get("_face"), "-"),
            device.get("_status"),
            device.get("serial") or "-",
            device.get("asset_tag") or "-",
        ]
        x = table_x + columns[0][1]
        for value, (_, width) in zip(values, columns[1:]):
            _draw_text(pdf, x + 5, y + 21, value, size=6.5, max_width=width - 10)
            x += width

    if not rows:
        _draw_text(
            pdf,
            table_x + 10,
            table_top - 60,
            "No hay equipos asociados a este rack.",
            size=10,
            color=MUTED,
        )
    _draw_footer(pdf, generated_at)
    pdf.showPage()


def build_rack_report(
    *,
    rack: dict[str, Any],
    elevation: dict[str, Any],
    face: str,
    image_assets: Mapping[int, ReportImage | tuple[bytes, str, str]] | None = None,
) -> tuple[bytes, str]:
    selected_face = "rear" if face == "rear" else "front"
    rack_name = _clean_text(rack.get("name") or rack.get("display") or "Rack")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    inventory = _inventory_rows(elevation)
    prepared_images = _prepare_images(elevation, selected_face, image_assets)

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
    page_number = 2
    for start_slot, end_slot in _occupied_windows(elevation):
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
    for start in range(0, max(1, len(inventory)), INVENTORY_ROWS_PER_PAGE):
        _draw_inventory_page(
            pdf,
            inventory[start : start + INVENTORY_ROWS_PER_PAGE],
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
    return value, f"rack-{_safe_filename(rack_name)}-inventario.pdf"


__all__ = ["RackReportError", "ReportImage", "build_rack_report"]
