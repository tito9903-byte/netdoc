from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Mapping

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas as pdfcanvas

from app.services.rack_report_service import (
    CYAN,
    FRAME,
    GREEN,
    MARGIN,
    MUTED,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    PANEL,
    PANEL_ALT,
    PreparedImage,
    RackReportError,
    ReportImage,
    _clean_text,
    _collect_image_assets,
    _device_type_id,
    _draw_background,
    _draw_footer,
    _draw_header,
    _draw_rack,
    _draw_summary_card,
    _draw_text,
    _inventory_rows,
    _label,
    _normalize_assets,
    _prepare_image,
    _safe_filename,
)

BLACK_SOFT = HexColor("#071118")
TABLE_HEADER = HexColor("#123842")
DANGER = HexColor("#EA4F59")


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


def _draw_image_cover(
    pdf: pdfcanvas.Canvas,
    prepared: PreparedImage,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Llena el bloque del equipo y recorta únicamente el excedente.

    En un rack completo una unidad U es muy baja. Usar `contain` reduce una foto
    frontal hasta convertirla en una miniatura. Este recorte reproduce el
    comportamiento `object-fit: cover` usado por la vista web.
    """
    if width <= 0 or height <= 0 or prepared.width <= 0 or prepared.height <= 0:
        return

    scale = max(width / prepared.width, height / prepared.height)
    draw_width = max(1.0, prepared.width * scale)
    draw_height = max(1.0, prepared.height * scale)
    draw_x = x + (width - draw_width) / 2
    draw_y = y + (height - draw_height) / 2

    pdf.saveState()
    clip = pdf.beginPath()
    clip.rect(x, y, width, height)
    pdf.clipPath(clip, stroke=0, fill=0)
    pdf.drawImage(
        prepared.reader,
        draw_x,
        draw_y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.restoreState()


def _overlay_rack_photos(
    pdf: pdfcanvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rack_height: int,
    devices: list[dict[str, Any]],
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    """Superpone fotos ajustadas sobre los bloques dibujados por `_draw_rack`."""
    frame = 12.0
    inner_x = x + frame
    inner_y = y + frame
    inner_width = width - frame * 2
    inner_height = height - frame * 2

    for device in devices:
        image = prepared_images.get(_device_type_id(device) or -1)
        if image is None:
            continue

        top = float(device.get("_top_percent") or 0) / 100
        ratio_height = float(device.get("_height_percent") or 0) / 100
        device_height = max(3.2, ratio_height * inner_height)
        device_y = inner_y + inner_height - top * inner_height - device_height

        box_x = inner_x + 11
        box_y = device_y + 0.7
        box_width = inner_width - 22
        box_height = max(1.8, device_height - 1.4)
        inset = min(0.8, box_height * 0.10)

        _draw_image_cover(
            pdf,
            image,
            x=box_x + inset,
            y=box_y + inset,
            width=max(1.0, box_width - inset * 2),
            height=max(0.8, box_height - inset * 2),
        )


def _draw_info_grid(
    pdf: pdfcanvas.Canvas,
    *,
    rack: Mapping[str, Any],
    elevation: Mapping[str, Any],
    face: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(x, y, width, height, 9, fill=1, stroke=1)

    _draw_text(
        pdf,
        x + 14,
        y + height - 24,
        "Información del rack",
        size=10.5,
        color=CYAN,
        bold=True,
    )

    rows = [
        ("Sitio", _label(rack.get("site"), "Sin sitio")),
        ("Ubicación", _label(rack.get("location"), "Sin ubicación")),
        ("Estado", _label(rack.get("status"), "Sin estado")),
        ("Ancho", _label(rack.get("width"), "-")),
        ("Serial", rack.get("serial") or "-"),
        ("Activo", rack.get("asset_tag") or "-"),
        (
            "Numeración",
            "Descendente" if elevation.get("descending_units") else "Ascendente",
        ),
        ("Cara", "Frontal" if face == "front" else "Trasera"),
    ]

    columns = 2
    row_count = 4
    gap = 8
    cell_width = (width - 28 - gap) / columns
    cell_height = (height - 46 - gap * (row_count - 1)) / row_count

    for index, (label, value) in enumerate(rows):
        column = index // row_count
        row = index % row_count
        cell_x = x + 14 + column * (cell_width + gap)
        cell_y = y + height - 42 - (row + 1) * cell_height - row * gap

        pdf.setFillColor(PANEL_ALT if index % 2 else BLACK_SOFT)
        pdf.setStrokeColor(FRAME)
        pdf.roundRect(
            cell_x,
            cell_y,
            cell_width,
            cell_height,
            5,
            fill=1,
            stroke=1,
        )
        _draw_text(
            pdf,
            cell_x + 9,
            cell_y + cell_height - 14,
            label,
            size=6.2,
            color=MUTED,
        )
        _draw_text(
            pdf,
            cell_x + 9,
            cell_y + 9,
            value,
            size=7.0,
            bold=True,
            max_width=cell_width - 18,
        )


def _device_value(device: Mapping[str, Any], key: str) -> str:
    if key == "name":
        return _clean_text(device.get("name") or device.get("display"), "Equipo")
    if key == "model":
        return _clean_text(device.get("_model"), "Sin modelo")
    if key == "position":
        return _report_position(device)
    if key == "height":
        return _clean_text(device.get("_u_height_label"), "0U")
    if key == "face":
        return _label(device.get("_face"), "-")
    if key == "status":
        return _clean_text(device.get("_status"), "Sin estado")
    if key == "serial":
        return _clean_text(device.get("serial"), "-")
    if key == "asset":
        return _clean_text(device.get("asset_tag"), "-")
    return "-"


def _draw_inventory_table(
    pdf: pdfcanvas.Canvas,
    *,
    devices: list[dict[str, Any]],
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(x, y, width, height, 9, fill=1, stroke=1)

    title_height = 24
    header_height = 21
    table_x = x + 10
    table_width = width - 20
    table_top = y + height - title_height
    body_bottom = y + 9

    _draw_text(
        pdf,
        x + 14,
        y + height - 17,
        f"Inventario de equipos · {len(devices)} registrados",
        size=9.5,
        color=CYAN,
        bold=True,
    )

    columns = [
        ("Equipo", "name", 0.16),
        ("Modelo", "model", 0.22),
        ("Posición", "position", 0.10),
        ("Altura", "height", 0.07),
        ("Cara", "face", 0.08),
        ("Estado", "status", 0.10),
        ("Serial", "serial", 0.14),
        ("Activo", "asset", 0.13),
    ]

    pdf.setFillColor(TABLE_HEADER)
    pdf.setStrokeColor(CYAN)
    pdf.rect(
        table_x,
        table_top - header_height,
        table_width,
        header_height,
        fill=1,
        stroke=1,
    )

    cursor_x = table_x
    for label, _key, ratio in columns:
        column_width = table_width * ratio
        _draw_text(
            pdf,
            cursor_x + 5,
            table_top - 14,
            label,
            size=6.5,
            bold=True,
            max_width=column_width - 10,
        )
        cursor_x += column_width

    if not devices:
        _draw_text(
            pdf,
            table_x + 10,
            table_top - 48,
            "No hay equipos asociados a este rack.",
            size=9,
            color=MUTED,
        )
        return

    body_height = table_top - header_height - body_bottom
    row_height = body_height / len(devices)
    text_size = max(4.2, min(6.2, row_height * 0.38))

    cursor_y = table_top - header_height
    for index, device in enumerate(devices):
        cursor_y -= row_height
        pdf.setFillColor(PANEL_ALT if index % 2 else BLACK_SOFT)
        pdf.setStrokeColor(FRAME)
        pdf.rect(
            table_x,
            cursor_y,
            table_width,
            row_height,
            fill=1,
            stroke=1,
        )

        cursor_x = table_x
        for _label_text, key, ratio in columns:
            column_width = table_width * ratio
            value = _device_value(device, key)
            color = GREEN if key == "status" and value.lower() == "active" else MUTED
            if device.get("_has_conflict") and key == "position":
                color = DANGER
            _draw_text(
                pdf,
                cursor_x + 5,
                cursor_y + max(3.0, (row_height - text_size) / 2),
                value,
                size=text_size,
                color=color,
                bold=key in {"name", "position"},
                max_width=column_width - 10,
            )
            cursor_x += column_width


def _draw_one_page_report(
    pdf: pdfcanvas.Canvas,
    *,
    rack: Mapping[str, Any],
    elevation: Mapping[str, Any],
    face: str,
    generated_at: str,
    prepared_images: Mapping[int, PreparedImage],
    inventory: list[dict[str, Any]],
) -> None:
    _draw_background(pdf)
    rack_name = _clean_text(rack.get("name") or rack.get("display") or "Rack")
    site = _label(rack.get("site"), "Sin sitio")
    location = _label(rack.get("location"), "Sin ubicación")

    _draw_header(
        pdf,
        title=f"Rack {rack_name}",
        subtitle=f"Elevación datacenter e inventario físico · {site} · {location}",
        page_number=1,
    )

    cards = [
        ("Altura", f"{elevation.get('rack_height', 0)}U"),
        ("Ocupadas", f"{elevation.get('used_units_label', '0')}U"),
        ("Libres", f"{elevation.get('free_units_label', '0')}U"),
        ("Utilización", f"{elevation.get('utilization', 0)}%"),
        ("Equipos", str(len(inventory))),
    ]
    card_y = PAGE_HEIGHT - 128
    for index, (label, value) in enumerate(cards):
        _draw_summary_card(pdf, MARGIN + index * 155, card_y, label, value)

    top_y = 230
    top_height = 227

    rack_panel_x = MARGIN
    rack_panel_width = 255
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(
        rack_panel_x,
        top_y,
        rack_panel_width,
        top_height,
        9,
        fill=1,
        stroke=1,
    )
    _draw_text(
        pdf,
        rack_panel_x + 14,
        top_y + top_height - 22,
        "Vista 3D del rack",
        size=10,
        color=CYAN,
        bold=True,
    )

    rack_x = rack_panel_x + 64
    rack_y = top_y + 14
    rack_width = 126
    rack_draw_height = 190
    visible_devices = list(elevation.get("visible_devices", []))
    rack_units = int(elevation.get("rack_height") or 42)

    _draw_rack(
        pdf,
        x=rack_x,
        y=rack_y,
        width=rack_width,
        height=rack_draw_height,
        rack_height=rack_units,
        devices=visible_devices,
        face="frontal" if face == "front" else "trasera",
        prepared_images=prepared_images,
    )
    _overlay_rack_photos(
        pdf,
        x=rack_x,
        y=rack_y,
        width=rack_width,
        height=rack_draw_height,
        rack_height=rack_units,
        devices=visible_devices,
        prepared_images=prepared_images,
    )

    info_x = rack_panel_x + rack_panel_width + 12
    info_width = PAGE_WIDTH - MARGIN - info_x
    _draw_info_grid(
        pdf,
        rack=rack,
        elevation=elevation,
        face=face,
        x=info_x,
        y=top_y,
        width=info_width,
        height=top_height,
    )

    _draw_inventory_table(
        pdf,
        devices=inventory,
        x=MARGIN,
        y=42,
        width=PAGE_WIDTH - MARGIN * 2,
        height=177,
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

    _draw_one_page_report(
        pdf,
        rack=rack,
        elevation=elevation,
        face=selected_face,
        generated_at=generated_at,
        prepared_images=prepared_images,
        inventory=inventory,
    )

    pdf.save()
    value = output.getvalue()
    if not value.startswith(b"%PDF-"):
        raise RackReportError("No se pudo preparar el reporte del rack.")

    filename = f"rack-{_safe_filename(rack_name)}-inventario.pdf"
    return value, filename
