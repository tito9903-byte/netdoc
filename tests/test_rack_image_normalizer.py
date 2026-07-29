from __future__ import annotations

import unittest
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw

from app.services.rack_image_normalizer import normalize_rack_image


def png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def normalized_image(image: Image.Image) -> Image.Image:
    content, content_type, _digest = normalize_rack_image(
        png_bytes(image),
        "image/png",
    )
    if content_type != "image/png":
        raise AssertionError("La representación normalizada debe ser PNG.")
    result = Image.open(BytesIO(content))
    result.load()
    return result


class RackImageNormalizerTests(unittest.TestCase):
    def test_removes_transparent_margin_without_losing_equipment(self):
        image = Image.new("RGBA", (120, 40), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle(
            (20, 8, 99, 31),
            fill=(20, 90, 160, 255),
        )

        result = normalized_image(image)

        self.assertEqual((80, 24), result.size)
        self.assertEqual((20, 90, 160, 255), result.getpixel((0, 0)))
        self.assertEqual((20, 90, 160, 255), result.getpixel((79, 23)))

    def test_removes_uniform_white_background_connected_to_edges(self):
        image = Image.new("RGB", (140, 50), "white")
        ImageDraw.Draw(image).rectangle((25, 10, 114, 39), fill=(15, 70, 130))

        result = normalized_image(image)

        self.assertEqual((90, 30), result.size)
        self.assertEqual((15, 70, 130, 255), result.getpixel((0, 0)))
        self.assertEqual((15, 70, 130, 255), result.getpixel((89, 29)))

    def test_removes_uniform_dark_background_connected_to_edges(self):
        image = Image.new("RGB", (160, 60), (8, 10, 12))
        ImageDraw.Draw(image).rectangle((30, 12, 129, 47), fill=(180, 190, 200))

        result = normalized_image(image)

        self.assertEqual((100, 36), result.size)
        self.assertEqual((180, 190, 200, 255), result.getpixel((0, 0)))
        self.assertEqual((180, 190, 200, 255), result.getpixel((99, 35)))

    def test_image_without_clear_margin_is_not_modified(self):
        image = Image.new("RGB", (40, 24))
        pixels = image.load()
        for y in range(image.height):
            for x in range(image.width):
                pixels[x, y] = ((x * 17) % 256, (y * 29) % 256, 90)
        original = png_bytes(image)

        content, content_type, _digest = normalize_rack_image(
            original,
            "image/png",
        )

        self.assertEqual(original, content)
        self.assertEqual("image/png", content_type)

    def test_original_bytes_are_unchanged_and_etag_is_versioned(self):
        image = Image.new("RGBA", (80, 30), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10, 5, 69, 24), fill="red")
        original = png_bytes(image)

        normalized, _, digest = normalize_rack_image(original, "image/png")

        self.assertEqual(png_bytes(image), original)
        self.assertNotEqual(original, normalized)
        self.assertEqual(64, len(digest))
        self.assertNotEqual(sha256(normalized).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()

