from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from math import ceil
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

CARDS_PER_PAGE = 8
CARD_COLUMNS = 2
BLACK_SOFT = HexColor("#081218")
PHOTO_BG = HexColor("#0A171E")


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


def _draw_placeholder(
    pdf: pdfcanvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    pdf.setFillColor(PHOTO_BG)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(x, y, width, height, 5, fill=1, stroke=1)
    label = "Sin fotografía registrada"
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 6.7)
    pdf.drawCentredString(x + width / 2, y + height / 2 - 2, label)


def _draw_rack_information(
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
        y + height - 25,
        "Información del rack",
        size=11,
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

    row_height = 35
    cursor = y + height - 49
    for index, (label, value) in enumerate(rows):
        row_y = cursor - row_height
        pdf.setFillColor(PANEL_ALT if index % 2 else BLACK_SOFT)
        pdf.setStrokeColor(FRAME)
        pdf.rect(x + 10, row_y, width - 20, row_height - 4, fill=1, stroke=1)
        _draw_text(
            pdf,
            x + 20,
            row_y + 11,
            label,
            size=6.8,
            color=MUTED,
        )
        _draw_text(
            pdf,
            x + 88,
            row_y + 11,
            value,
            size=7.3,
            bold=True,
            max_width=width - 110,
        )
        cursor -= row_height

    _draw_text(
        pdf,
        x + 14,
        y + 16,
        "Las fotografías provienen del modelo documentado.",
        size=6.6,
        color=MUTED,
        max_width=width - 28,
    )


def _draw_device_card(
    pdf: pdfcanvas.Canvas,
    *,
    device: Mapping[str, Any],
    prepared_images: Mapping[int, PreparedImage],
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(CYAN if not device.get("_has_conflict") else HexColor("#EA4F59"))
    pdf.setLineWidth(0.8)
    pdf.roundRect(x, y, width, height, 7, fill=1, stroke=1)

    photo_height = max(31.0, min(56.0, height * 0.50))
    photo_x = x + 8
    photo_y = y + height - photo_height - 8
    photo_width = width - 16

    image = prepared_images.get(_device_type_id(device) or -1)
    if image is not None:
        pdf.setFillColor(PHOTO_BG)
        pdf.setStrokeColor(FRAME)
        pdf.roundRect(
            photo_x,
            photo_y,
            photo_width,
            photo_height,
            5,
            fill=1,
            stroke=1,
        )
        _draw_image_contain(
            pdf,
            image,
            x=photo_x + 4,
            y=photo_y + 3,
            width=photo_width - 8,
            height=photo_height - 6,
        )
    else:
        _draw_placeholder(
            pdf,
            x=photo_x,
            y=photo_y,
            width=photo_width,
            height=photo_height,
        )

    name = device.get("name") or device.get("display") or "Equipo"
    model = device.get("_model") or "Sin modelo"
    status = device.get("_status") or "Sin estado"
    text_y = photo_y - 14

    _draw_text(
        pdf,
        x + 10,
        text_y,
        name,
        size=8.0,
        bold=True,
        max_width=width - 20,
    )
    _draw_text(
        pdf,
        x + 10,
        text_y - 12,
        model,
        size=6.3,
        color=MUTED,
        max_width=width - 20,
    )
    _draw_text(
        pdf,
        x + 10,
        y + 9,
        f"{_report_position(device)} · {device.get('_u_height_label') or '0U'} · {status}",
        size=6.3,
        color=GREEN if str(status).lower() == "active" else MUTED,
        max_width=width - 20,
    )


def _draw_report_page(
    pdf: pdfcanvas.Canvas,
    *,
    rack: Mapping[str, Any],
    elevation: Mapping[str, Any],
    face: str,
    generated_at: str,
    prepared_images: Mapping[int, PreparedImage],
    devices: list[dict[str, Any]],
    page_number: int,
    first_page: bool,
) -> None:
    _draw_background(pdf)
    rack_name = _clean_text(rack.get("name") or rack.get("display") or "Rack")
    site = _label(rack.get("site"), "Sin sitio")
    location = _label(rack.get("location"), "Sin ubicación")

    _draw_header(
        pdf,
        title=f"Rack {rack_name}",
        subtitle=(
            f"Resumen físico y equipos documentados · {site} · {location}"
            if first_page
            else "Continuación del inventario fotográfico"
        ),
        page_number=page_number,
    )

    content_top = PAGE_HEIGHT - 92
    content_bottom = 42

    if first_page:
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
        content_top = PAGE_HEIGHT - 150

        info_x = MARGIN
        info_width = 224
        info_height = content_top - content_bottom
        _draw_rack_information(
            pdf,
            rack=rack,
            elevation=elevation,
            face=face,
            x=info_x,
            y=content_bottom,
            width=info_width,
            height=info_height,
        )
        grid_x = info_x + info_width + 14
        grid_width = PAGE_WIDTH - MARGIN - grid_x
    else:
        grid_x = MARGIN
        grid_width = PAGE_WIDTH - MARGIN * 2

    rows = max(1, ceil(len(devices) / CARD_COLUMNS))
    gap_x = 12
    gap_y = 10
    card_width = (grid_width - gap_x) / CARD_COLUMNS
    available_height = content_top - content_bottom
    card_height = (available_height - gap_y * (rows - 1)) / rows

    for index, device in enumerate(devices):
        column = index % CARD_COLUMNS
        row = index // CARD_COLUMNS
        x = grid_x + column * (card_width + gap_x)
        y = content_top - (row + 1) * card_height - row * gap_y
        _draw_device_card(
            pdf,
            device=device,
            prepared_images=prepared_images,
            x=x,
            y=y,
            width=card_width,
            height=card_height,
        )

    if not devices:
        _draw_text(
            pdf,
            grid_x + 20,
            content_top - 45,
            "No hay equipos asociados a este rack.",
            size=11,
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

    chunks = [
        inventory[index : index + CARDS_PER_PAGE]
        for index in range(0, len(inventory), CARDS_PER_PAGE)
    ] or [[]]

    for page_index, devices in enumerate(chunks, start=1):
        _draw_report_page(
            pdf,
            rack=rack,
            elevation=elevation,
            face=selected_face,
            generated_at=generated_at,
            prepared_images=prepared_images,
            devices=devices,
            page_number=page_index,
            first_page=page_index == 1,
        )

    pdf.save()
    value = output.getvalue()
    if not value.startswith(b"%PDF-"):
        raise RackReportError("No se pudo preparar el reporte del rack.")
    return value, f"rack-{_safe_filename(rack_name)}-inventario.pdf"


__all__ = ["RackReportError", "ReportImage", "build_rack_report"]
