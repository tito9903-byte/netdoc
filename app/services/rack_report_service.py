from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterable


PAGE_WIDTH = 841.89
PAGE_HEIGHT = 595.28
MARGIN = 32.0

BG = (0.025, 0.047, 0.063)
BG_SOFT = (0.043, 0.078, 0.098)
PANEL = (0.055, 0.105, 0.132)
PANEL_ALT = (0.070, 0.128, 0.155)
FRAME = (0.120, 0.190, 0.225)
FRAME_LIGHT = (0.285, 0.370, 0.405)
CYAN = (0.090, 0.750, 0.790)
CYAN_SOFT = (0.080, 0.330, 0.360)
TEXT = (0.930, 0.970, 0.980)
MUTED = (0.530, 0.650, 0.700)
GRID = (0.100, 0.170, 0.205)
RED = (0.920, 0.310, 0.350)
GREEN = (0.260, 0.860, 0.580)
BLACK = (0.008, 0.015, 0.020)


class RackReportError(RuntimeError):
    pass


def _label(value: Any, fallback: str = "-") -> str:
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


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "-").replace("\r", " ").replace("\n", " ").split())


def _pdf_string(value: Any) -> bytes:
    raw = _clean_text(value).encode("cp1252", errors="replace")
    raw = raw.replace(b"\\", b"\\\\")
    raw = raw.replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + raw + b")"


def _face_label(value: Any) -> str:
    face = value.get("value") if isinstance(value, dict) else value
    return {
        "front": "Frontal",
        "rear": "Trasera",
        "sin definir": "Sin definir",
    }.get(str(face or "").lower(), _clean_text(face))


def _safe_filename(value: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "rack"


@dataclass
class _Canvas:
    commands: list[bytes]

    def command(self, value: str | bytes) -> None:
        self.commands.append(value.encode("ascii") if isinstance(value, str) else value)

    def set_fill(self, color: tuple[float, float, float]) -> None:
        self.command(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg")

    def set_stroke(self, color: tuple[float, float, float]) -> None:
        self.command(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG")

    def line_width(self, width: float) -> None:
        self.command(f"{width:.2f} w")

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: bool = False,
        stroke: bool = True,
    ) -> None:
        operator = "B" if fill and stroke else "f" if fill else "S"
        self.command(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re {operator}")

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.command(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def polygon(
        self,
        points: list[tuple[float, float]],
        *,
        fill: bool = True,
        stroke: bool = True,
    ) -> None:
        if len(points) < 3:
            return
        first_x, first_y = points[0]
        self.command(f"{first_x:.2f} {first_y:.2f} m")
        for x, y in points[1:]:
            self.command(f"{x:.2f} {y:.2f} l")
        operator = "b" if fill and stroke else "f" if fill else "s"
        self.command(f"h {operator}")

    def text(
        self,
        x: float,
        y: float,
        value: Any,
        *,
        size: float = 9,
        bold: bool = False,
        color: tuple[float, float, float] = TEXT,
    ) -> None:
        self.set_fill(color)
        font = "F2" if bold else "F1"
        self.command(b"BT /" + font.encode("ascii") + f" {size:.2f} Tf ".encode("ascii"))
        self.command(
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ".encode("ascii")
            + _pdf_string(value)
            + b" Tj ET"
        )

    def wrapped_text(
        self,
        x: float,
        y: float,
        value: Any,
        *,
        width: float,
        size: float = 8,
        leading: float | None = None,
        max_lines: int = 3,
        bold: bool = False,
        color: tuple[float, float, float] = TEXT,
    ) -> float:
        words = _clean_text(value).split()
        if not words:
            return y
        char_limit = max(8, int(width / max(size * 0.52, 1)))
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= char_limit:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        original = " ".join(words)
        if len(lines) == max_lines and " ".join(lines) != original:
            lines[-1] = lines[-1][: max(1, char_limit - 3)].rstrip() + "..."
        cursor = y
        line_height = leading or size * 1.25
        for line in lines:
            self.text(x, cursor, line, size=size, bold=bold, color=color)
            cursor -= line_height
        return cursor

    def stream(self) -> bytes:
        return b"\n".join(self.commands) + b"\n"


def _inventory_rows(elevation: dict[str, Any]) -> list[dict[str, Any]]:
    positioned = sorted(
        elevation.get("positioned_devices", []),
        key=lambda item: float(item.get("_position") or 0),
        reverse=True,
    )
    rows = [dict(item, _inventory_state="Posicionado") for item in positioned]
    rows.extend(
        dict(item, _inventory_state="0U")
        for item in elevation.get("zero_u_devices", [])
    )
    rows.extend(
        dict(item, _inventory_state="Sin posicion")
        for item in elevation.get("unpositioned_devices", [])
    )
    return rows


def _page_background(canvas: _Canvas) -> None:
    canvas.set_fill(BG)
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)

    canvas.set_stroke(GRID)
    canvas.line_width(0.35)
    floor_top = 112.0
    for x in range(-120, 980, 38):
        canvas.line(PAGE_WIDTH / 2, floor_top, float(x), 0)
    for y in range(0, 112, 18):
        canvas.line(0, float(y), PAGE_WIDTH, float(y))

    canvas.set_fill((0.025, 0.065, 0.082))
    canvas.rect(0, floor_top, PAGE_WIDTH, PAGE_HEIGHT - floor_top, fill=True, stroke=False)


def _draw_page_header(
    canvas: _Canvas,
    *,
    title: str,
    subtitle: str,
    page_number: int,
) -> None:
    canvas.set_fill(BG_SOFT)
    canvas.set_stroke(FRAME)
    canvas.line_width(0.8)
    canvas.rect(0, PAGE_HEIGHT - 70, PAGE_WIDTH, 70, fill=True, stroke=True)

    canvas.set_fill(CYAN)
    canvas.rect(MARGIN, PAGE_HEIGHT - 51, 8, 31, fill=True, stroke=False)
    canvas.text(MARGIN + 19, PAGE_HEIGHT - 32, title, size=18, bold=True, color=TEXT)
    canvas.text(MARGIN + 19, PAGE_HEIGHT - 50, subtitle, size=8.5, color=MUTED)

    canvas.set_fill(PANEL)
    canvas.set_stroke(CYAN_SOFT)
    canvas.rect(PAGE_WIDTH - 104, PAGE_HEIGHT - 52, 70, 28, fill=True, stroke=True)
    canvas.text(PAGE_WIDTH - 91, PAGE_HEIGHT - 41, f"Pagina {page_number}", size=8, bold=True, color=CYAN)


def _draw_footer(canvas: _Canvas, generated_at: str) -> None:
    canvas.set_stroke(FRAME)
    canvas.line_width(0.5)
    canvas.line(MARGIN, 24, PAGE_WIDTH - MARGIN, 24)
    canvas.text(MARGIN, 10, "NetDoc - Inventario fisico de datacenter", size=7, color=MUTED)
    canvas.text(PAGE_WIDTH - 225, 10, f"Generado: {generated_at} UTC", size=7, color=MUTED)


def _draw_summary_card(
    canvas: _Canvas,
    x: float,
    y: float,
    width: float,
    label: str,
    value: str,
) -> None:
    canvas.set_fill(PANEL)
    canvas.set_stroke(FRAME)
    canvas.line_width(0.7)
    canvas.rect(x, y, width, 46, fill=True, stroke=True)
    canvas.set_fill(CYAN)
    canvas.rect(x, y, 4, 46, fill=True, stroke=False)
    canvas.text(x + 13, y + 28, label, size=7.2, color=MUTED)
    canvas.text(x + 13, y + 10, value, size=14, bold=True, color=TEXT)


def _draw_datacenter_rack(
    canvas: _Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rack_height: int,
    devices: Iterable[dict[str, Any]],
    face: str,
) -> None:
    depth = 22.0
    frame = 12.0

    canvas.set_fill((0.035, 0.065, 0.080))
    canvas.set_stroke(FRAME_LIGHT)
    canvas.line_width(1.0)
    canvas.polygon(
        [
            (x + width, y + 8),
            (x + width + depth, y + 21),
            (x + width + depth, y + height + 6),
            (x + width, y + height),
        ],
        fill=True,
        stroke=True,
    )

    canvas.set_fill((0.075, 0.125, 0.150))
    canvas.set_stroke(FRAME_LIGHT)
    canvas.line_width(1.3)
    canvas.rect(x, y, width, height, fill=True, stroke=True)

    canvas.set_fill(BLACK)
    inner_x = x + frame
    inner_y = y + frame
    inner_width = width - frame * 2
    inner_height = height - frame * 2
    canvas.rect(inner_x, inner_y, inner_width, inner_height, fill=True, stroke=False)

    canvas.set_fill(FRAME_LIGHT)
    for rail_x in (inner_x + 4, inner_x + inner_width - 8):
        canvas.rect(rail_x, inner_y, 4, inner_height, fill=True, stroke=False)

    canvas.set_stroke((0.080, 0.135, 0.160))
    canvas.line_width(0.35)
    rack_units = max(1, rack_height)
    unit_height = inner_height / rack_units
    for unit in range(1, rack_units):
        unit_y = inner_y + unit * unit_height
        canvas.line(inner_x + 9, unit_y, inner_x + inner_width - 9, unit_y)

    canvas.text(x, y + height + 11, f"Elevacion {face}", size=8.5, bold=True, color=CYAN)
    for unit in range(rack_units, 0, -2):
        top_from_bottom = unit * unit_height
        canvas.text(x - 25, inner_y + top_from_bottom - 3, f"U{unit}", size=5.8, color=MUTED)

    for device in devices:
        top = float(device.get("_top_percent") or 0) / 100.0
        percentage_height = float(device.get("_height_percent") or 0) / 100.0
        device_height = max(3.2, percentage_height * inner_height)
        device_y = inner_y + inner_height - (top * inner_height) - device_height
        conflict = bool(device.get("_has_conflict"))

        canvas.set_fill((0.360, 0.090, 0.115) if conflict else (0.045, 0.190, 0.220))
        canvas.set_stroke(RED if conflict else CYAN)
        canvas.line_width(0.75)
        canvas.rect(
            inner_x + 11,
            device_y + 0.7,
            inner_width - 22,
            max(1.8, device_height - 1.4),
            fill=True,
            stroke=True,
        )

        canvas.set_fill(GREEN)
        canvas.rect(inner_x + 14, device_y + max(1.5, device_height / 2 - 1.5), 3, 3, fill=True, stroke=False)

        if device_height >= 11:
            canvas.wrapped_text(
                inner_x + 23,
                device_y + device_height / 2 + 1,
                device.get("name") or device.get("display") or "Equipo",
                width=inner_width - 54,
                size=6.2,
                max_lines=1,
                bold=True,
                color=TEXT,
            )

        if device.get("_has_image"):
            canvas.set_fill(CYAN)
            canvas.rect(inner_x + inner_width - 19, device_y + max(1.5, device_height / 2 - 1.5), 3, 3, fill=True, stroke=False)

    canvas.set_fill(FRAME)
    canvas.rect(x + 18, y - 8, 20, 8, fill=True, stroke=False)
    canvas.rect(x + width - 38, y - 8, 20, 8, fill=True, stroke=False)


def _draw_first_page(
    rack: dict[str, Any],
    elevation: dict[str, Any],
    *,
    face: str,
    generated_at: str,
) -> bytes:
    canvas = _Canvas([])
    _page_background(canvas)

    rack_name = _clean_text(rack.get("name") or rack.get("display") or "Rack")
    site = _label(rack.get("site"), "Sin sitio")
    location = _label(rack.get("location"), "Sin ubicacion")
    _draw_page_header(
        canvas,
        title=f"Rack {rack_name}",
        subtitle=f"Reporte datacenter - {site} - {location}",
        page_number=1,
    )

    card_y = PAGE_HEIGHT - 128
    card_width = 145
    cards = [
        ("Altura", f"{elevation.get('rack_height', 0)}U"),
        ("Ocupadas", f"{elevation.get('used_units_label', '0')}U"),
        ("Libres", f"{elevation.get('free_units_label', '0')}U"),
        ("Utilizacion", f"{elevation.get('utilization', 0)}%"),
        ("Equipos", str(len(_inventory_rows(elevation)))),
    ]
    for index, (label, value) in enumerate(cards):
        _draw_summary_card(
            canvas,
            MARGIN + index * (card_width + 10),
            card_y,
            card_width,
            label,
            value,
        )

    rack_x = 78
    rack_y = 65
    rack_width = 236
    rack_visual_height = 342
    _draw_datacenter_rack(
        canvas,
        x=rack_x,
        y=rack_y,
        width=rack_width,
        height=rack_visual_height,
        rack_height=int(elevation.get("rack_height") or 42),
        devices=elevation.get("visible_devices", []),
        face="frontal" if face == "front" else "trasera",
    )

    info_x = 374
    info_y = 392
    canvas.text(info_x, info_y, "Informacion del rack", size=13, bold=True, color=TEXT)
    info = [
        ("Sitio", site),
        ("Ubicacion", location),
        ("Estado", _label(rack.get("status"), "Sin estado")),
        ("Ancho", _label(rack.get("width"), "-")),
        ("Serial", rack.get("serial") or "-"),
        ("Etiqueta de activo", rack.get("asset_tag") or "-"),
        ("Numeracion", "Descendente" if elevation.get("descending_units") else "Ascendente"),
        ("Cara del reporte", "Frontal" if face == "front" else "Trasera"),
    ]

    cursor = info_y - 24
    for index, (label, value) in enumerate(info):
        canvas.set_fill(PANEL if index % 2 == 0 else PANEL_ALT)
        canvas.set_stroke(FRAME)
        canvas.rect(info_x, cursor - 12, 405, 27, fill=True, stroke=True)
        canvas.text(info_x + 10, cursor - 1, label, size=7.2, color=MUTED)
        canvas.wrapped_text(
            info_x + 145,
            cursor - 1,
            value,
            width=245,
            size=8.2,
            max_lines=1,
            bold=True,
            color=TEXT,
        )
        cursor -= 31

    canvas.set_fill(PANEL)
    canvas.set_stroke(FRAME)
    canvas.rect(info_x, 65, 405, 87, fill=True, stroke=True)
    canvas.text(info_x + 12, 134, "Lectura del reporte", size=10, bold=True, color=CYAN)
    notes = [
        "La posicion y la altura provienen del inventario de NetBox.",
        "El punto cian indica que el modelo tiene una fotografia documentada.",
        "Los equipos con conflicto fisico se presentan en rojo.",
        "Los equipos de 0U o sin posicion aparecen en las paginas de inventario.",
    ]
    note_y = 117
    for note in notes:
        canvas.set_fill(CYAN)
        canvas.rect(info_x + 12, note_y - 2, 4, 4, fill=True, stroke=False)
        canvas.text(info_x + 25, note_y - 4, note, size=7.2, color=MUTED)
        note_y -= 16

    _draw_footer(canvas, generated_at)
    return canvas.stream()


def _fit_cell(value: Any, maximum: int) -> str:
    text = _clean_text(value)
    if len(text) <= maximum:
        return text
    return text[: max(1, maximum - 3)].rstrip() + "..."


def _draw_inventory_page(
    rows: list[dict[str, Any]],
    *,
    rack_name: str,
    page_number: int,
    generated_at: str,
    start_index: int,
) -> bytes:
    canvas = _Canvas([])
    _page_background(canvas)
    _draw_page_header(
        canvas,
        title=f"Rack {rack_name}",
        subtitle="Inventario fisico de equipos",
        page_number=page_number,
    )

    columns = [
        ("#", 24),
        ("Equipo", 125),
        ("Modelo", 118),
        ("Posicion", 70),
        ("Altura", 48),
        ("Cara", 58),
        ("Estado", 75),
        ("Serial", 92),
        ("Activo", 82),
        ("Foto", 42),
    ]
    table_x = MARGIN
    table_top = PAGE_HEIGHT - 91
    row_height = 25
    header_height = 28
    total_width = sum(width for _, width in columns)

    canvas.set_fill((0.070, 0.145, 0.170))
    canvas.set_stroke(CYAN_SOFT)
    canvas.rect(table_x, table_top - header_height, total_width, header_height, fill=True, stroke=True)
    x = table_x
    for label, width in columns:
        canvas.text(x + 5, table_top - 18, label, size=7.2, bold=True, color=TEXT)
        x += width

    y = table_top - header_height
    for row_offset, device in enumerate(rows):
        row_index = start_index + row_offset + 1
        y -= row_height
        canvas.set_fill(PANEL if row_index % 2 else PANEL_ALT)
        canvas.set_stroke(FRAME)
        canvas.line_width(0.4)
        canvas.rect(table_x, y, total_width, row_height, fill=True, stroke=True)

        position = (
            device.get("_position_label")
            or device.get("_inventory_state")
            or "Sin posicion"
        )
        values = [
            str(row_index),
            _fit_cell(device.get("name") or device.get("display"), 22),
            _fit_cell(device.get("_model"), 21),
            _fit_cell(position, 12),
            _fit_cell(device.get("_u_height_label") or "0U", 7),
            _fit_cell(_face_label(device.get("_face")), 10),
            _fit_cell(device.get("_status"), 12),
            _fit_cell(device.get("serial") or "-", 16),
            _fit_cell(device.get("asset_tag") or "-", 14),
            "Si" if device.get("_has_image") else "No",
        ]
        x = table_x
        for value, (_, width) in zip(values, columns):
            canvas.text(x + 5, y + 9, value, size=6.7, color=TEXT)
            x += width

    if not rows:
        canvas.text(
            table_x + 10,
            table_top - 60,
            "No hay equipos asociados a este rack.",
            size=10,
            color=MUTED,
        )

    _draw_footer(canvas, generated_at)
    return canvas.stream()


def _assemble_pdf(page_streams: list[bytes], *, title: str) -> bytes:
    if not page_streams:
        raise RackReportError("No se pudo preparar el reporte del rack.")

    objects: list[bytes] = [b""]

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects) - 1

    font_regular = add_object(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    font_bold = add_object(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    pages_object = add_object(b"")
    page_objects: list[int] = []

    for stream in page_streams:
        content_object = add_object(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"endstream"
        )
        page_object = add_object(
            (
                f"<< /Type /Page /Parent {pages_object} 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
                f"/Contents {content_object} 0 R >>"
            ).encode("ascii")
        )
        page_objects.append(page_object)

    objects[pages_object] = (
        b"<< /Type /Pages /Count "
        + str(len(page_objects)).encode("ascii")
        + b" /Kids ["
        + b" ".join(f"{item} 0 R".encode("ascii") for item in page_objects)
        + b"] >>"
    )
    catalog_object = add_object(
        f"<< /Type /Catalog /Pages {pages_object} 0 R >>".encode("ascii")
    )
    info_object = add_object(
        b"<< /Title " + _pdf_string(title) + b" /Producer (NetDoc) >>"
    )

    output = BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index in range(1, len(objects)):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode("ascii"))
        output.write(objects[index])
        output.write(b"\nendobj\n")

    xref_position = output.tell()
    output.write(f"xref\n0 {len(objects)}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        (
            f"trailer\n<< /Size {len(objects)} /Root {catalog_object} 0 R "
            f"/Info {info_object} 0 R >>\nstartxref\n{xref_position}\n%%EOF\n"
        ).encode("ascii")
    )
    return output.getvalue()


def build_rack_report(
    *,
    rack: dict[str, Any],
    elevation: dict[str, Any],
    face: str,
) -> tuple[bytes, str]:
    selected_face = "rear" if face == "rear" else "front"
    rack_name = _clean_text(rack.get("name") or rack.get("display") or "Rack")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    inventory = _inventory_rows(elevation)

    pages = [
        _draw_first_page(
            rack,
            elevation,
            face=selected_face,
            generated_at=generated_at,
        )
    ]
    rows_per_page = 18
    for start in range(0, max(1, len(inventory)), rows_per_page):
        pages.append(
            _draw_inventory_page(
                inventory[start : start + rows_per_page],
                rack_name=rack_name,
                page_number=len(pages) + 1,
                generated_at=generated_at,
                start_index=start,
            )
        )

    pdf = _assemble_pdf(pages, title=f"Rack {rack_name} - Inventario datacenter")
    filename = f"rack-{_safe_filename(rack_name)}-inventario.pdf"
    return pdf, filename
