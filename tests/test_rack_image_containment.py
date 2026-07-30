from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RACK_DATACENTER_CSS = ROOT / "app/static/css/rack_datacenter.css"
RACK_DEVICES_CSS = ROOT / "app/static/css/rack_devices.css"
RACK_VIEW_MODES_CSS = ROOT / "app/static/css/rack_view_modes.css"
RACK_TEMPLATE = ROOT / "app/templates/rack_detail.html"
RACKS_TEMPLATE = ROOT / "app/templates/racks.html"


def rule(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}", css)
    if not match:
        raise AssertionError(f"No se encontró la regla CSS: {selector}")
    return match.group("body")


def assert_fills_device(test: unittest.TestCase, image_rule: str) -> None:
    test.assertIn("inset: 0", image_rule)
    test.assertIn("width: 100%", image_rule)
    test.assertIn("height: 100%", image_rule)
    test.assertIn("object-fit: fill", image_rule)
    test.assertIn("object-position: center", image_rule)
    test.assertNotIn("object-fit: contain", image_rule)
    test.assertNotIn("object-fit: cover", image_rule)


class RackImageFillTests(unittest.TestCase):
    def test_3d_photos_fill_the_physical_device_in_fit_and_detail(self):
        css = RACK_DATACENTER_CSS.read_text(encoding="utf-8")
        image_rule = rule(css, ".rack-single-topology .topology-device img")
        detail_rule = rule(
            css,
            '.rack-single-topology[data-scale="detail"] .topology-device img',
        )

        assert_fills_device(self, image_rule)
        self.assertIn("inset: 0", detail_rule)
        self.assertIn("width: 100%", detail_rule)
        self.assertNotIn("transform:", image_rule)
        self.assertNotIn("transform:", detail_rule)
        self.assertNotRegex(css, r"topology-device[^}]*transform\s*:[^;}]*scale\(")

    def test_2d_photos_fill_the_exact_rack_unit_area(self):
        base_css = RACK_DEVICES_CSS.read_text(encoding="utf-8")
        override_css = RACK_VIEW_MODES_CSS.read_text(encoding="utf-8")
        base_rule = rule(base_css, ".rack-device-image")
        override_rule = rule(
            override_css,
            ".rack-device-block.has-image .rack-device-image",
        )

        assert_fills_device(self, base_rule)
        assert_fills_device(self, override_rule)
        self.assertIn("transform: none", override_rule)

    def test_photos_do_not_receive_labels_or_decorative_overlays(self):
        css = RACK_VIEW_MODES_CSS.read_text(encoding="utf-8")
        self.assertIn(
            ".rack-device-block.has-image .rack-device-name,\n"
            ".rack-device-block.has-image .rack-device-position {\n"
            "    display: none !important;",
            css,
        )
        self.assertIn(
            ".rack-single-topology .topology-device:has(img:not([hidden])) "
            ".topology-device-label {\n    display: none !important;",
            css,
        )
        self.assertIn(
            ".rack-device-block.has-image::before,\n"
            ".rack-device-block.has-image::after {\n"
            "    display: none !important;",
            css,
        )

    def test_rack_stylesheets_have_cache_busting_version(self):
        template = RACK_TEMPLATE.read_text(encoding="utf-8")
        racks_template = RACKS_TEMPLATE.read_text(encoding="utf-8")
        version = "?v=20260729-image-fill-1"
        for stylesheet in (
            "css/rack_devices.css",
            "css/rack_view_modes.css",
            "css/rack_datacenter.css",
        ):
            self.assertRegex(
                template,
                rf"path='{re.escape(stylesheet)}'\)\s*}}}}{re.escape(version)}",
            )
        self.assertRegex(
            racks_template,
            rf"path='css/rack_devices\.css'\)\s*}}}}{re.escape(version)}",
        )

    def test_rack_service_serves_original_bytes_without_normalizer(self):
        source = (ROOT / "app/services/rack_service.py").read_text(encoding="utf-8")
        self.assertNotIn("rack_image_normalizer", source)
        self.assertNotIn("normalize_rack_image", source)
        self.assertIn("if local is not None:\n            return local", source)
        self.assertIn("sha256(response.content).hexdigest()", source)


if __name__ == "__main__":
    unittest.main()
