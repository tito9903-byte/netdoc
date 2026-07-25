from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.rack_presentation import prepare_elevation
from app.services.rack_report_detailed_service import build_rack_report


RACK = {
    "id": 1,
    "name": "SMN05",
    "u_height": 42,
    "starting_unit": 1,
    "site": {"id": 10, "name": "Samaná", "display": "Samaná"},
    "location": {"id": 11, "name": "Datacenter", "display": "Datacenter"},
    "status": {"value": "active", "label": "Activo"},
    "width": {"value": 19, "label": "19 pulgadas"},
    "serial": "RACK-SMN05",
    "asset_tag": "DC-SMN-05",
}

DEVICES = [
    {
        "id": 100,
        "name": "SW-SMN-01",
        "position": 30,
        "face": {"value": "front"},
        "status": {"label": "Activo"},
        "serial": "FGT123",
        "asset_tag": "NET-100",
        "device_type": {
            "id": 200,
            "model": "FortiSwitch S148F",
            "display": "FortiSwitch S148F",
            "u_height": 1,
            "is_full_depth": False,
            "front_image": "/media/device-types/200/front",
        },
    },
    {
        "id": 101,
        "name": "OLT-SMN-01",
        "position": 20,
        "face": {"value": "front"},
        "status": {"label": "Activo"},
        "serial": "ZTE600",
        "asset_tag": "OLT-01",
        "device_type": {
            "id": 201,
            "model": "ZTE C600",
            "display": "ZTE C600",
            "u_height": 6,
            "is_full_depth": True,
        },
    },
]


class RackReportTests(unittest.TestCase):
    @staticmethod
    def sample_image() -> bytes:
        image = Image.new("RGB", (640, 96), (220, 225, 228))
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def test_report_builder_returns_valid_pdf_container(self):
        elevation = prepare_elevation(RACK, DEVICES, "front")

        pdf, filename = build_rack_report(
            rack=RACK,
            elevation=elevation,
            face="front",
        )

        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertGreater(len(pdf), 5000)
        self.assertEqual(filename, "rack-smn05-inventario.pdf")
        self.assertIn(b"/Type /Pages", pdf)
        self.assertIn(b"/Title", pdf)
        self.assertGreaterEqual(pdf.count(b"/Type /Page"), 5)

    def test_report_embeds_device_photo(self):
        elevation = prepare_elevation(RACK, DEVICES, "front")

        pdf, _ = build_rack_report(
            rack=RACK,
            elevation=elevation,
            face="front",
            image_assets={
                200: (
                    self.sample_image(),
                    "image/png",
                    "test-image",
                )
            },
        )

        self.assertIn(b"/Subtype /Image", pdf)
        self.assertGreater(len(pdf), 7000)

    @patch(
        "app.routers.racks.RackService.list_rack_devices",
        new_callable=AsyncMock,
        return_value=DEVICES,
    )
    @patch(
        "app.routers.racks.RackService.get_rack",
        new_callable=AsyncMock,
        return_value=RACK,
    )
    def test_report_route_downloads_pdf(self, _get_rack, _list_devices):
        with TestClient(app) as client:
            login = client.post(
                "/login",
                data={
                    "username": "admin",
                    "password": "AdminPassword123",
                    "next_url": "/racks/1",
                },
                follow_redirects=False,
            )
            self.assertEqual(303, login.status_code)

            response = client.get(
                "/racks/1/report.pdf?face=front",
                follow_redirects=False,
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("application/pdf", response.headers["content-type"])
        self.assertIn(
            'attachment; filename="rack-smn05-inventario.pdf"',
            response.headers["content-disposition"],
        )
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))


if __name__ == "__main__":
    unittest.main()
