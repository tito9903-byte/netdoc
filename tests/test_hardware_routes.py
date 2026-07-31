from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


MANUFACTURER = {
    "id": 1,
    "name": "ZTE",
    "display": "ZTE",
    "slug": "zte",
    "description": "Fabricante de acceso.",
    "_name": "ZTE",
    "_model_count": 1,
}
MODEL = {
    "id": 10,
    "model": "C600",
    "display": "ZTE C600",
    "manufacturer": {"id": 1, "name": "ZTE", "display": "ZTE"},
    "part_number": "C600",
    "slug": "zte-c600",
    "u_height": 6,
    "is_full_depth": True,
    "front_image": None,
    "rear_image": None,
    "_manufacturer_label": "ZTE",
    "_model_label": "C600",
    "_interface_count": 1,
    "_module_bay_count": 2,
    "_power_port_count": 2,
}
INTERFACE = {
    "id": 100,
    "name": "gei_1/1/1",
    "_type_label": "SFP+ (10G)",
    "label": "Uplink",
    "mgmt_only": False,
}
INTERFACE_TYPES = [
    {"value": "10gbase-x-sfpp", "label": "SFP+ (10G)"},
]
DEVICE = {
    "id": 200,
    "name": "OLT-SMN-01",
    "site": {"name": "Samaná"},
    "rack": {"name": "SMN01"},
    "status": {"label": "Active"},
}


class HardwareRouteTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/device-types",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch(
        "app.routers.hardware.HardwareService.manufacturer_catalog",
        new_callable=AsyncMock,
        return_value={
            "manufacturers": [MANUFACTURER],
            "total_manufacturers": 1,
            "total_models": 1,
        },
    )
    def test_manufacturer_catalog_renders(self, _catalog):
        response = self.client.get("/manufacturers")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Fabricantes", response.text)
        self.assertIn("ZTE", response.text)
        self.assertIn("Crear fabricante", response.text)

    @patch(
        "app.routers.hardware.DeviceTypeService.interface_type_choices",
        new_callable=AsyncMock,
        return_value=INTERFACE_TYPES,
    )
    @patch(
        "app.routers.hardware.DeviceTypeService.list_manufacturers",
        new_callable=AsyncMock,
        return_value=[MANUFACTURER],
    )
    @patch(
        "app.routers.hardware.HardwareService.model_detail",
        new_callable=AsyncMock,
        return_value={
            "device_type": MODEL,
            "interfaces": [INTERFACE],
            "module_bays": [],
            "power_ports": [],
            "console_ports": [],
            "front_ports": [],
            "rear_ports": [],
            "devices": [DEVICE],
            "component_summary": {
                "interfaces": 1,
                "module_bays": 0,
                "power_ports": 0,
                "console_ports": 0,
                "front_ports": 0,
                "rear_ports": 0,
                "devices": 1,
            },
        },
    )
    def test_model_detail_renders_all_workspaces(
        self,
        _detail,
        _manufacturers,
        _interface_types,
    ):
        response = self.client.get("/device-types/10")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ficha del modelo", response.text)
        self.assertIn("Información general", response.text)
        self.assertIn("Imágenes del modelo", response.text)
        self.assertIn("Crear interfaces del modelo", response.text)
        self.assertIn("Interfaces existentes", response.text)
        self.assertIn("OLT-SMN-01", response.text)
        self.assertIn(
            'action="/device-types/actions/interfaces/bulk"',
            response.text,
        )
        self.assertNotIn('href="/interface-templates', response.text)

    @patch(
        "app.routers.hardware.HardwareService.update_device_type",
        new_callable=AsyncMock,
    )
    def test_model_update_is_blocked_in_read_only_mode(self, update_model):
        response = self.client.post(
            "/device-types/10/actions/update",
            data={
                "csrf": "invalid",
                "manufacturer_id": "1",
                "model": "C600",
                "u_height": "6",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        update_model.assert_not_awaited()

    def test_manufacturer_catalog_requires_authentication(self):
        self.client.post("/logout")
        response = self.client.get(
            "/manufacturers",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("/login", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
