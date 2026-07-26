from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.main import app
from app.routers.device_create import (
    signed_form_token,
    verify_signed_form_token,
)


ROOT = Path(__file__).resolve().parents[1]


class DeviceCreationSecurityTests(unittest.TestCase):
    @staticmethod
    def request() -> Request:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/devices/actions/new",
                "headers": [],
                "query_string": b"",
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
        )
        request.scope["session"] = {
            "authenticated": True,
            "user_id": 1,
            "username": "admin",
        }
        return request

    def test_signed_token_is_stable_without_session_mutation(self):
        request = self.request()
        before = dict(request.session)

        first = signed_form_token(request, "device-create")
        second = signed_form_token(request, "device-create")

        self.assertEqual(first, second)
        self.assertEqual(before, dict(request.session))
        self.assertTrue(
            verify_signed_form_token(request, first, "device-create")
        )
        self.assertFalse(
            verify_signed_form_token(request, "incorrecto", "device-create")
        )

    def test_invalid_device_token_returns_html_form_not_raw_json(self):
        options = {
            "sites": [],
            "racks": [],
            "manufacturers": [],
            "device_types": [],
            "roles": [],
        }
        with patch(
            "app.routers.device_create.load_options",
            new_callable=AsyncMock,
            return_value=options,
        ), TestClient(app) as client:
            login = client.post(
                "/login",
                data={
                    "username": "admin",
                    "password": "AdminPassword123",
                    "next_url": "/devices",
                },
                follow_redirects=False,
            )
            self.assertEqual(303, login.status_code)

            response = client.post(
                "/devices/actions/new?modal=1",
                data={
                    "csrf_token": "token-vencido",
                    "name": "TEST-DEVICE",
                    "site_id": "1",
                    "device_type_id": "1",
                    "role_id": "1",
                },
            )

        self.assertEqual(403, response.status_code)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("sesión de seguridad", response.text)
        self.assertIn("TEST-DEVICE", response.text)
        self.assertNotIn('{"detail":', response.text)


class PrimaryIpAndRackInventoryTests(unittest.TestCase):
    def test_primary_ip_form_documents_interface_with_each_address(self):
        template = (
            ROOT / "app/templates/device_primary_ip.html"
        ).read_text(encoding="utf-8")
        router = (
            ROOT / "app/routers/device_create.py"
        ).read_text(encoding="utf-8")

        self.assertIn("_option_label", template)
        self.assertIn("primary_ip4_id", template)
        self.assertIn("primary_ip6_id", template)
        self.assertIn("/api/ipam/ip-addresses/", router)
        self.assertIn('"primary_ip4": selected_ip4', router)
        self.assertIn('"primary_ip6": selected_ip6', router)

    def test_device_detail_exposes_primary_ip_configuration_action(self):
        javascript = (
            ROOT / "app/static/js/device_primary_ip_link.js"
        ).read_text(encoding="utf-8")

        self.assertIn("IP principal", javascript)
        self.assertIn("primary-ip/new", javascript)
        self.assertIn("dataset.createModal", javascript)

    def test_rack_inventory_lists_serial_and_primary_ip(self):
        template = (
            ROOT / "app/templates/rack_detail.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Inventario del rack", template)
        self.assertIn("Número de serie", template)
        self.assertIn("IP principal", template)
        self.assertIn('device.get("primary_ip4")', template)
        self.assertIn('device.get("primary_ip6")', template)
        self.assertIn("Sin asignar", template)

    def test_documentation_covers_new_operational_flow(self):
        documentation = (
            ROOT / "docs/modelos-y-componentes.md"
        ).read_text(encoding="utf-8")

        self.assertIn("IP e interfaz principal del dispositivo", documentation)
        self.assertIn("Inventario dentro del rack", documentation)
        self.assertIn("token HMAC", documentation)


if __name__ == "__main__":
    unittest.main()
