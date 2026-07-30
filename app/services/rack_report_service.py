from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

from app.core.config import get_settings
from app.services.device_image_service import DeviceImageService
from app.services.device_type_service import DeviceTypeServiceError

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
MARGIN = 32.0

BG = HexColor("#061018")
BG_SOFT = HexColor("#0B1922")
PANEL = HexColor("#0E2430")
PANEL_ALT = HexColor("#12303D")
FRAME = HexColor("#213D4B")
FRAME_LIGHT = HexColor("#596F7A")
CYAN = HexColor("#20C8D2")
TEXT = HexColor("#EDF8FA")
MUTED = HexColor("#88A6B3")
GRID = HexColor("#18313D")
RED = HexColor("#EA4F59")
GREEN = HexColor("#43DB94")
BLACK = HexColor("#020608")


class RackReportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReportImage:
    content: bytes
    content_type: str
    digest: str


@dataclass
class PreparedImage:
    reader: ImageReader
    width: int
    height: int


def _clean_text(value: Any, fallback: str = "-") -> str:
    text = " ".join(
        str(value or fallback).replace("\r", " ").replace("\n", " ").split()
    )
    return text or fallback


def _label(value: Any, fallback: str = "-") -> str:
    if isinstance(value, dict):
        return _clean_text(
            value.get("display")
            or value.get("name")
            or value.get("label")
            or value.get("value"),
            fallback,
        )
    return _clean_text(value, fallback)


def _safe_filename(value: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "rack"


def _device_type_id(device: Mapping[str, Any]) -> int | None:
    device_type = device.get("device_type") or {}
    if isinstance(device_type, Mapping) and isinstance(
        device_type.get("id"), int
    ):
        return int(device_type["id"])
    value = device.get("device_type_id")
    return int(value) if isinstance(value, int) else None


def _inventory_rows(elevation: Mapping[str, Any]) -> list[dict[str, Any]]:
    positioned = sorted(
        elevation.get("positioned_devices", []),
        key=lambda item: float(item.get("_position") or 0),
        reverse=True,
    )
    rows = [
        dict(item, _inventory_state="Posicionado")
        for item in positioned
    ]
    rows.extend(
        dict(item, _inventory_state="0U")
        for item in elevation.get("zero_u_devices", [])
    )
    rows.extend(
        dict(item, _inventory_state="Sin posición")
        for item in elevation.get("unpositioned_devices", [])
    )
    return rows


def _collect_image_assets(
    elevation: Mapping[str, Any],
    face: str,
) -> dict[int, ReportImage]:
    assets: dict[int, ReportImage] = {}
    pending_remote: dict[int, str] = {}
    service = DeviceImageService()

    for device in _inventory_rows(elevation):
        device_type_id = _device_type_id(device)
        if device_type_id is None or device_type_id in assets:
            continue

        try:
            result = service.get_local_image(device_type_id, face)
        except DeviceTypeServiceError:
            result = None

        if result is not None:
            content, content_type, digest = result
            assets[device_type_id] = ReportImage(
                content,
                content_type,
                digest,
            )
            continue

        device_type = device.get("device_type") or {}
        if not isinstance(device_type, Mapping):
            continue

        raw_url = device_type.get(f"{face}_image")
        if isinstance(raw_url, Mapping):
            raw_url = raw_url.get("url") or raw_url.get("value")

        if (
            isinstance(raw_url, str)
            and raw_url.strip()
            and not raw_url.startswith("/media/device-types/")
        ):
            pending_remote[device_type_id] = raw_url.strip()

    if not pending_remote:
        return assets

    settings = get_settings()
    base_url = settings.netbox_url.rstrip("/")
    expected = urlparse(base_url)
    token_type = settings.netbox_token_type.strip().lower()
    authorization = (
        f"Bearer {settings.netbox_token}"
        if token_type == "bearer"
        else f"Token {settings.netbox_token}"
    )

    try:
        with httpx.Client(
            headers={
                "Authorization": authorization,
                "Accept": "image/*",
                "User-Agent": (
                    f"NetDoc/{settings.app_version} rack-report"
                ),
            },
            verify=settings.netbox_verify_ssl,
            timeout=settings.netbox_timeout,
            follow_redirects=True,
        ) as client:
            for device_type_id, raw_url in pending_remote.items():
                resolved = urljoin(f"{base_url}/", raw_url)
                candidate = urlparse(resolved)
                if (
                    candidate.scheme not in {"http", "https"}
                    or candidate.scheme != expected.scheme
                    or candidate.netloc != expected.netloc
                ):
                    continue

                try:
                    response = client.get(resolved)
                except httpx.HTTPError:
                    continue

                content_type = response.headers.get(
                    "content-type",
                    "",
                ).split(";", 1)[0]
                if (
                    response.is_error
                    or not content_type.startswith("image/")
                    or not response.content
                    or len(response.content) > 5 * 1024 * 1024
                ):
                    continue

                digest = response.headers.get("etag", "").strip('"')
                assets[device_type_id] = ReportImage(
                    bytes(response.content),
                    content_type,
                    digest or f"remote-{device_type_id}-{face}",
                )
    except httpx.HTTPError:
        pass

    return assets


def _normalize_assets(
    image_assets: Mapping[
        int,
        ReportImage | tuple[bytes, str, str],
    ]
    | None,
) -> dict[int, ReportImage]:
    normalized: dict[int, ReportImage] = {}
    for key, value in (image_assets or {}).items():
        if not isinstance(key, int) or key <= 0:
            continue
        if isinstance(value, ReportImage):
            normalized[key] = value
            continue
        if (
            isinstance(value, tuple)
            and len(value) == 3
            and isinstance(value[0], (bytes, bytearray))
        ):
            normalized[key] = ReportImage(
                bytes(value[0]),
                str(value[1]),
                str(value[2]),
            )
    return normalized


def _prepare_image(asset: ReportImage) -> PreparedImage | None:
    try:
        with Image.open(BytesIO(asset.content)) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            if (
                image.mode in {"RGBA", "LA"}
                or "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new(
                    "RGBA",
                    rgba.size,
                    (2, 6, 8, 255),
                )
                image = Image.alpha_composite(
                    background,
                    rgba,
                ).convert("RGB")
            else:
                image = image.convert("RGB")

            image.thumbnail(
                (1800, 600),
                Image.Resampling.LANCZOS,
            )
            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=88,
                optimize=True,
            )
            return PreparedImage(
                ImageReader(BytesIO(output.getvalue())),
                image.width,
                image.height,
            )
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def _draw_text(
    pdf: pdfcanvas.Canvas,
    x: float,
    y: float,
    value: Any,
    *,
    size: float = 8,
    color: Color = TEXT,
    bold: bool = False,
    max_width: float | None = None,
) -> None:
    original = _clean_text(value)
    text = original
    font = "Helvetica-Bold" if bold else "Helvetica"

    if max_width is not None:
        while (
            len(text) > 3
            and stringWidth(text, font, size) > max_width
        ):
            text = text[:-1]
        if text != original:
            text = (
                text[:-3].rstrip() + "..."
                if len(text) > 3
                else text
            )

    pdf.setFillColor(color)
    pdf.setFont(font, size)
    pdf.drawString(x, y, text)


def _draw_background(pdf: pdfcanvas.Canvas) -> None:
    pdf.setFillColor(BG)
    pdf.rect(
        0,
        0,
        PAGE_WIDTH,
        PAGE_HEIGHT,
        fill=1,
        stroke=0,
    )

    floor_top = 110
    pdf.setStrokeColor(GRID)
    pdf.setLineWidth(0.35)
    for x in range(-120, 980, 38):
        pdf.line(PAGE_WIDTH / 2, floor_top, x, 0)
    for y in range(0, floor_top, 18):
        pdf.line(0, y, PAGE_WIDTH, y)

    pdf.setFillColor(HexColor("#071722"))
    pdf.rect(
        0,
        floor_top,
        PAGE_WIDTH,
        PAGE_HEIGHT - floor_top,
        fill=1,
        stroke=0,
    )


def _draw_header(
    pdf: pdfcanvas.Canvas,
    *,
    title: str,
    subtitle: str,
    page_number: int,
) -> None:
    pdf.setFillColor(BG_SOFT)
    pdf.setStrokeColor(FRAME)
    pdf.rect(
        0,
        PAGE_HEIGHT - 70,
        PAGE_WIDTH,
        70,
        fill=1,
        stroke=1,
    )

    pdf.setFillColor(CYAN)
    pdf.rect(
        MARGIN,
        PAGE_HEIGHT - 51,
        8,
        31,
        fill=1,
        stroke=0,
    )
    _draw_text(
        pdf,
        MARGIN + 19,
        PAGE_HEIGHT - 33,
        title,
        size=18,
        bold=True,
    )
    _draw_text(
        pdf,
        MARGIN + 19,
        PAGE_HEIGHT - 50,
        subtitle,
        size=8.5,
        color=MUTED,
    )

    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(CYAN)
    pdf.roundRect(
        PAGE_WIDTH - 104,
        PAGE_HEIGHT - 52,
        70,
        28,
        7,
        fill=1,
        stroke=1,
    )
    _draw_text(
        pdf,
        PAGE_WIDTH - 91,
        PAGE_HEIGHT - 42,
        f"Página {page_number}",
        size=8,
        color=CYAN,
        bold=True,
    )


def _draw_footer(
    pdf: pdfcanvas.Canvas,
    generated_at: str,
) -> None:
    pdf.setStrokeColor(FRAME)
    pdf.setLineWidth(0.5)
    pdf.line(MARGIN, 24, PAGE_WIDTH - MARGIN, 24)
    _draw_text(
        pdf,
        MARGIN,
        10,
        "NetDoc · Inventario físico de datacenter",
        size=7,
        color=MUTED,
    )
    _draw_text(
        pdf,
        PAGE_WIDTH - 230,
        10,
        f"Generado: {generated_at} UTC",
        size=7,
        color=MUTED,
    )


def _draw_summary_card(
    pdf: pdfcanvas.Canvas,
    x: float,
    y: float,
    label: str,
    value: str,
) -> None:
    width = 145
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(x, y, width, 46, 7, fill=1, stroke=1)
    pdf.setFillColor(CYAN)
    pdf.roundRect(x, y, 5, 46, 3, fill=1, stroke=0)
    _draw_text(
        pdf,
        x + 14,
        y + 28,
        label,
        size=7.2,
        color=MUTED,
    )
    _draw_text(
        pdf,
        x + 14,
        y + 10,
        value,
        size=14,
        bold=True,
    )


def _draw_image_contain(
    pdf: pdfcanvas.Canvas,
    prepared: PreparedImage,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    if width <= 0 or height <= 0:
        return

    scale = min(
        width / prepared.width,
        height / prepared.height,
    )
    draw_width = max(1.0, prepared.width * scale)
    draw_height = max(1.0, prepared.height * scale)
    draw_x = x + (width - draw_width) / 2
    draw_y = y + (height - draw_height) / 2

    pdf.drawImage(
        prepared.reader,
        draw_x,
        draw_y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )


def _draw_rack(
    pdf: pdfcanvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    rack_height: int,
    devices: Iterable[dict[str, Any]],
    face: str,
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    depth = 22
    frame = 12

    pdf.setFillColor(HexColor("#09131A"))
    pdf.setStrokeColor(FRAME_LIGHT)
    side = pdf.beginPath()
    side.moveTo(x + width, y + 8)
    side.lineTo(x + width + depth, y + 21)
    side.lineTo(x + width + depth, y + height + 6)
    side.lineTo(x + width, y + height)
    side.close()
    pdf.drawPath(side, fill=1, stroke=1)

    pdf.setFillColor(HexColor("#132630"))
    pdf.setStrokeColor(FRAME_LIGHT)
    pdf.setLineWidth(1.3)
    pdf.roundRect(
        x,
        y,
        width,
        height,
        7,
        fill=1,
        stroke=1,
    )

    inner_x = x + frame
    inner_y = y + frame
    inner_width = width - frame * 2
    inner_height = height - frame * 2

    pdf.setFillColor(BLACK)
    pdf.rect(
        inner_x,
        inner_y,
        inner_width,
        inner_height,
        fill=1,
        stroke=0,
    )
    pdf.setFillColor(FRAME_LIGHT)
    pdf.rect(
        inner_x + 4,
        inner_y,
        4,
        inner_height,
        fill=1,
        stroke=0,
    )
    pdf.rect(
        inner_x + inner_width - 8,
        inner_y,
        4,
        inner_height,
        fill=1,
        stroke=0,
    )

    rack_units = max(1, rack_height)
    unit_height = inner_height / rack_units
    pdf.setStrokeColor(GRID)
    pdf.setLineWidth(0.35)
    for unit in range(1, rack_units):
        unit_y = inner_y + unit * unit_height
        pdf.line(
            inner_x + 9,
            unit_y,
            inner_x + inner_width - 9,
            unit_y,
        )

    _draw_text(
        pdf,
        x,
        y + height + 11,
        f"Elevación {face}",
        size=8.5,
        color=CYAN,
        bold=True,
    )
    for unit in range(rack_units, 0, -2):
        _draw_text(
            pdf,
            x - 25,
            inner_y + unit * unit_height - 3,
            f"U{unit}",
            size=5.8,
            color=MUTED,
        )

    for device in devices:
        top = float(device.get("_top_percent") or 0) / 100
        ratio_height = (
            float(device.get("_height_percent") or 0) / 100
        )
        device_height = max(
            3.2,
            ratio_height * inner_height,
        )
        device_y = (
            inner_y
            + inner_height
            - top * inner_height
            - device_height
        )

        box_x = inner_x + 11
        box_y = device_y + 0.7
        box_width = inner_width - 22
        box_height = max(1.8, device_height - 1.4)
        conflict = bool(device.get("_has_conflict"))

        pdf.setFillColor(
            HexColor("#5C171D")
            if conflict
            else HexColor("#071319")
        )
        pdf.setStrokeColor(RED if conflict else CYAN)
        pdf.setLineWidth(0.75)
        pdf.rect(
            box_x,
            box_y,
            box_width,
            box_height,
            fill=1,
            stroke=1,
        )

        device_type_id = _device_type_id(device)
        image = (
            prepared_images.get(device_type_id)
            if device_type_id is not None
            else None
        )
        if image is not None and box_height >= 2.5:
            _draw_image_contain(
                pdf,
                image,
                x=box_x + 3,
                y=box_y + 1,
                width=box_width - 6,
                height=max(1, box_height - 2),
            )
        elif device_height >= 11:
            _draw_text(
                pdf,
                box_x + 13,
                device_y + device_height / 2 - 2,
                device.get("name")
                or device.get("display")
                or "Equipo",
                size=6.2,
                bold=True,
                max_width=box_width - 27,
            )

        pdf.setFillColor(GREEN)
        pdf.circle(
            box_x + 4,
            box_y + box_height / 2,
            1.6,
            fill=1,
            stroke=0,
        )

    pdf.setFillColor(FRAME)
    pdf.rect(x + 18, y - 8, 20, 8, fill=1, stroke=0)
    pdf.rect(
        x + width - 38,
        y - 8,
        20,
        8,
        fill=1,
        stroke=0,
    )


def _draw_first_page(
    pdf: pdfcanvas.Canvas,
    rack: Mapping[str, Any],
    elevation: Mapping[str, Any],
    *,
    face: str,
    generated_at: str,
    prepared_images: Mapping[int, PreparedImage],
) -> None:
    _draw_background(pdf)
    rack_name = _clean_text(
        rack.get("name")
        or rack.get("display")
        or "Rack"
    )
    site = _label(rack.get("site"), "Sin sitio")
    location = _label(
        rack.get("location"),
        "Sin ubicación",
    )

    _draw_header(
        pdf,
        title=f"Rack {rack_name}",
        subtitle=(
            f"Reporte datacenter · {site} · {location}"
        ),
        page_number=1,
    )

    card_y = PAGE_HEIGHT - 128
    cards = [
        ("Altura", f"{elevation.get('rack_height', 0)}U"),
        (
            "Ocupadas",
            f"{elevation.get('used_units_label', '0')}U",
        ),
        (
            "Libres",
            f"{elevation.get('free_units_label', '0')}U",
        ),
        (
            "Utilización",
            f"{elevation.get('utilization', 0)}%",
        ),
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

    _draw_rack(
        pdf,
        x=78,
        y=65,
        width=236,
        height=342,
        rack_height=int(
            elevation.get("rack_height") or 42
        ),
        devices=elevation.get("visible_devices", []),
        face="frontal" if face == "front" else "trasera",
        prepared_images=prepared_images,
    )

    info_x = 374
    info_y = 392
    _draw_text(
        pdf,
        info_x,
        info_y,
        "Información del rack",
        size=13,
        bold=True,
    )
    info = [
        ("Sitio", site),
        ("Ubicación", location),
        (
            "Estado",
            _label(rack.get("status"), "Sin estado"),
        ),
        ("Ancho", _label(rack.get("width"), "-")),
        ("Serial", rack.get("serial") or "-"),
        (
            "Etiqueta de activo",
            rack.get("asset_tag") or "-",
        ),
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

    cursor = info_y - 24
    for index, (label, value) in enumerate(info):
        pdf.setFillColor(
            PANEL if index % 2 == 0 else PANEL_ALT
        )
        pdf.setStrokeColor(FRAME)
        pdf.rect(
            info_x,
            cursor - 12,
            405,
            27,
            fill=1,
            stroke=1,
        )
        _draw_text(
            pdf,
            info_x + 10,
            cursor - 1,
            label,
            size=7.2,
            color=MUTED,
        )
        _draw_text(
            pdf,
            info_x + 145,
            cursor - 1,
            value,
            size=8.2,
            bold=True,
            max_width=245,
        )
        cursor -= 31

    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(FRAME)
    pdf.roundRect(
        info_x,
        65,
        405,
        87,
        8,
        fill=1,
        stroke=1,
    )
    _draw_text(
        pdf,
        info_x + 12,
        134,
        "Lectura del reporte",
        size=10,
        color=CYAN,
        bold=True,
    )
    notes = [
        "Las fotografías corresponden a la cara seleccionada del modelo.",
        "La posición y la altura provienen del inventario de NetBox.",
        "Los equipos con conflicto físico se presentan en rojo.",
        "Los equipos de 0U o sin posición aparecen en el inventario.",
    ]
    note_y = 117
    for note in notes:
        pdf.setFillColor(CYAN)
        pdf.circle(
            info_x + 14,
            note_y,
            2,
            fill=1,
            stroke=0,
        )
        _draw_text(
            pdf,
            info_x + 25,
            note_y - 3,
            note,
            size=7.2,
            color=MUTED,
        )
        note_y -= 16

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
        subtitle=(
            "Inventario físico con fotografía del modelo"
        ),
        page_number=page_number,
    )

    columns = [
        ("Foto", 82),
        ("Equipo", 132),
        ("Modelo", 120),
        ("Posición", 68),
        ("Altura", 46),
        ("Cara", 58),
        ("Estado", 72),
        ("Serial", 94),
        ("Activo", 92),
    ]
    table_x = MARGIN
    table_top = PAGE_HEIGHT - 91
    row_height = 43
    header_height = 28
    total_width = sum(width for _, width in columns)

    pdf.setFillColor(HexColor("#123842"))
    pdf.setStrokeColor(CYAN)
    pdf.rect(
        table_x,
        table_top - header_height,
        total_width,
        header_height,
        fill=1,
        stroke=1,
    )

    x = table_x
    for label, width in columns:
        _draw_text(
            pdf,
            x + 5,
            table_top - 18,
            label,
            size=7.2,
            bold=True,
        )
        x += width

    y = table_top - header_height
    for row_offset, device in enumerate(rows):
        row_index = start_index + row_offset + 1
        y -= row_height

        pdf.setFillColor(
            PANEL if row_index % 2 else PANEL_ALT
        )
        pdf.setStrokeColor(FRAME)
        pdf.rect(
            table_x,
            y,
            total_width,
            row_height,
            fill=1,
            stroke=1,
        )

        device_type_id = _device_type_id(device)
        image = (
            prepared_images.get(device_type_id)
            if device_type_id is not None
            else None
        )
        if image is not None:
            _draw_image_contain(
                pdf,
                image,
                x=table_x + 4,
                y=y + 4,
                width=74,
                height=35,
            )
        else:
            _draw_text(
                pdf,
                table_x + 16,
                y + 17,
                "Sin foto",
                size=6.7,
                color=MUTED,
            )

        position = (
            device.get("_position_label")
            or device.get("_inventory_state")
            or "Sin posición"
        )
        values = [
            device.get("name") or device.get("display"),
            device.get("_model"),
            position,
            device.get("_u_height_label") or "0U",
            _label(device.get("_face"), "-"),
            device.get("_status"),
            device.get("serial") or "-",
            device.get("asset_tag") or "-",
        ]

        x = table_x + columns[0][1]
        for value, (_, width) in zip(values, columns[1:]):
            _draw_text(
                pdf,
                x + 5,
                y + 17,
                value,
                size=6.7,
                max_width=width - 10,
            )
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
    image_assets: Mapping[
        int,
        ReportImage | tuple[bytes, str, str],
    ]
    | None = None,
) -> tuple[bytes, str]:
    selected_face = "rear" if face == "rear" else "front"
    rack_name = _clean_text(
        rack.get("name")
        or rack.get("display")
        or "Rack"
    )
    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )
    inventory = _inventory_rows(elevation)

    assets = _collect_image_assets(
        elevation,
        selected_face,
    )
    assets.update(_normalize_assets(image_assets))
    prepared_images = {
        device_type_id: prepared
        for device_type_id, asset in assets.items()
        if (prepared := _prepare_image(asset)) is not None
    }

    output = BytesIO()
    pdf = pdfcanvas.Canvas(
        output,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        pageCompression=1,
        pdfVersion=(1, 4),
    )
    pdf.setTitle(
        f"Rack {rack_name} - Inventario datacenter"
    )
    pdf.setAuthor("NetDoc")
    pdf.setCreator("NetDoc")

    _draw_first_page(
        pdf,
        rack,
        elevation,
        face=selected_face,
        generated_at=generated_at,
        prepared_images=prepared_images,
    )

    rows_per_page = 10
    for start in range(
        0,
        max(1, len(inventory)),
        rows_per_page,
    ):
        _draw_inventory_page(
            pdf,
            inventory[
                start : start + rows_per_page
            ],
            rack_name=rack_name,
            page_number=2 + start // rows_per_page,
            generated_at=generated_at,
            start_index=start,
            prepared_images=prepared_images,
        )

    pdf.save()
    value = output.getvalue()
    if not value.startswith(b"%PDF-"):
        raise RackReportError(
            "No se pudo preparar el reporte del rack."
        )

    filename = (
        f"rack-{_safe_filename(rack_name)}-inventario.pdf"
    )
    return value, filename
