from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw, UnidentifiedImageError


NORMALIZER_VERSION = b"rack-image-normalizer-v1"
MAXIMUM_DECODED_PIXELS = 12_000_000
BACKGROUND_TOLERANCE = 12
MINIMUM_UNIFORM_BORDER_RATIO = 0.98


def _similar(first: tuple[int, ...], second: tuple[int, ...]) -> bool:
    return all(
        abs(left - right) <= BACKGROUND_TOLERANCE
        for left, right in zip(first[:3], second[:3], strict=True)
    )


def _uniform_background_box(image: Image.Image) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    width, height = rgb.size
    corners = (
        rgb.getpixel((0, 0)),
        rgb.getpixel((width - 1, 0)),
        rgb.getpixel((0, height - 1)),
        rgb.getpixel((width - 1, height - 1)),
    )
    background = tuple(
        round(sum(pixel[channel] for pixel in corners) / len(corners))
        for channel in range(3)
    )
    if not all(_similar(pixel, background) for pixel in corners):
        return None

    border = [
        *(rgb.getpixel((x, 0)) for x in range(width)),
        *(rgb.getpixel((x, height - 1)) for x in range(width)),
        *(rgb.getpixel((0, y)) for y in range(1, height - 1)),
        *(rgb.getpixel((width - 1, y)) for y in range(1, height - 1)),
    ]
    uniform = sum(_similar(pixel, background) for pixel in border)
    if uniform / len(border) < MINIMUM_UNIFORM_BORDER_RATIO:
        return None

    # La máscara separa el color uniforme del contenido. El flood fill marca
    # únicamente el fondo conectado a los bordes; un color igual dentro del
    # propio chasis no se elimina si está aislado por sus píxeles exteriores.
    difference = Image.new("L", rgb.size)
    difference.putdata([
        0 if _similar(pixel, background) else 255
        for pixel in rgb.get_flattened_data()
    ])
    ImageDraw.floodfill(difference, (0, 0), 128, thresh=0)
    content_mask = difference.point(lambda value: 0 if value == 128 else 255)
    return content_mask.getbbox()


def _transparent_content_box(
    image: Image.Image,
) -> tuple[int, int, int, int] | None:
    if "A" not in image.getbands():
        return None
    return image.getchannel("A").getbbox()


def _is_conservative_crop(
    box: tuple[int, int, int, int] | None,
    size: tuple[int, int],
) -> bool:
    if box is None:
        return False
    width, height = size
    left, top, right, bottom = box
    if box == (0, 0, width, height) or right <= left or bottom <= top:
        return False
    # Evita reencodificar por una sola fila o columna atribuible a compresión.
    removed = left + top + (width - right) + (height - bottom)
    return removed >= 2


def normalize_rack_image(
    content: bytes,
    content_type: str,
) -> tuple[bytes, str, str]:
    """Crea una representación sin márgenes y conserva intacto el original.

    Solo se eliminan transparencias o fondos casi uniformes conectados al borde.
    Si la decodificación o la detección no es inequívoca, se sirven los bytes
    originales. El ETag incorpora la versión del normalizador incluso en ese
    caso para invalidar representaciones anteriores.
    """

    normalized = content
    normalized_type = content_type
    try:
        with Image.open(BytesIO(content)) as source:
            if source.width * source.height > MAXIMUM_DECODED_PIXELS:
                raise ValueError("La imagen decodificada supera el límite seguro.")
            source.load()
            image = source.convert("RGBA")
            box = _transparent_content_box(image)
            if box == (0, 0, image.width, image.height):
                box = _uniform_background_box(image)
            if _is_conservative_crop(box, image.size):
                output = BytesIO()
                image.crop(box).save(output, format="PNG", optimize=True)
                normalized = output.getvalue()
                normalized_type = "image/png"
    except (OSError, UnidentifiedImageError, ValueError):
        pass

    digest = sha256(
        NORMALIZER_VERSION + b"\0" + normalized
    ).hexdigest()
    return normalized, normalized_type, digest

