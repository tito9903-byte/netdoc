from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


MANUFACTURERS = [
    {"id": 1, "name": "ZTE", "display": "ZTE"},
]

DEVICE_TYPES = [
    {
        "id": 10,
        "model": "C600",
        "display": "ZTE C600",
        "manufacturer": {"id": 1, "name": "ZTE", "display": "ZTE"},
        "part_number": "C600",
        "slug": "zte-c600",
        "u_height": 2,
        "is_full_depth": True,
        "description": "OLT de acceso.",
        "_manufacturer_label": "ZTE",
        "_model_label": "C600",
        "_interface_count": 4,
        "_module_bay_count": 2,
        "_power_port_count": 2,
    },
]

INTERFACE_TYPES = [
    {"value": "1000base-t", "label": "1GBASE-T"},
]

INTERFACES = [
    {
        "id": 100,
        "name": "GigabitEthernet0/1",
        "type": {"value": "1000base-t", "label": "1GBASE-T"},
        "_type_label": "1GBASE-T",
        "label": "Uplink",
        "mgmt_only": False,
    },
]


class DocumentationRouteTests(unittest.TestCase):
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
        self.assertEqual(303, response.status_code)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch(
        "app.routers.documentation.DeviceTypeService.list_device_types",
        new_callable=AsyncMock,
        return_value=DEVICE_TYPES,
    )
    @patch(
        "app.routers.documentation.DeviceTypeService.list_manufacturers",
        new_callable=AsyncMock,
        return_value=MANUFACTURERS,
    )
    def test_model_catalog_renders_without_loading_interface_choices(
        self,
        _manufacturers,
        _device_types,
    ):
        response = self.client.get("/device-types")

        self.assertEqual(200, response.status_code)
        self.assertIn("Modelos de equipos", response.text)
        self.assertIn("C600", response.text)
        self.assertIn("Plantillas de puertos", response.text)

    @patch(
        "app.routers.documentation.DeviceTypeService.list_manufacturers",
        new_callable=AsyncMock,
        return_value=MANUFACTURERS,
    )
    def test_new_model_form_includes_front_and_rear_images(
        self,
        _manufacturers,
    ):
        response = self.client.get("/device-types/new")

        self.assertEqual(200, response.status_code)
        self.assertIn('enctype="multipart/form-data"', response.text)
        self.assertIn('name="front_image"', response.text)
        self.assertIn('name="rear_image"', response.text)
        self.assertIn(
            '/device-types/actions/create-with-images',
            response.text,
        )
        self.assertIn("Altura U", response.text)

    @patch(
        "app.routers.documentation.DeviceTypeService.list_interface_templates",
        new_callable=AsyncMock,
        return_value=INTERFACES,
    )
    @patch(
        "app.routers.documentation.DeviceTypeService.interface_type_choices",
        new_callable=AsyncMock,
        return_value=INTERFACE_TYPES,
    )
    @patch(
        "app.routers.documentation.DeviceTypeService.list_device_types",
        new_callable=AsyncMock,
        return_value=DEVICE_TYPES,
    )
    @patch(
        "app.routers.documentation.DeviceTypeService.list_manufacturers",
        new_callable=AsyncMock,
        return_value=MANUFACTURERS,
    )
    def test_interface_template_workspace_renders(
        self,
        _manufacturers,
        _device_types,
        _interface_types,
        _interfaces,
    ):
        response = self.client.get(
            "/interface-templates?device_type_id=10"
        )

        self.assertEqual(200, response.status_code)
        self.assertIn("Plantillas de interfaces y puertos", response.text)
        self.assertIn("GigabitEthernet0/1", response.text)
        self.assertIn("Generador rápido", response.text)

    def test_interface_preview_returns_generated_names(self):
        response = self.client.get(
            "/api/device-types/interface-preview",
            params={
                "pattern": "Gi1/0/{n:02}",
                "start": 1,
                "count": 3,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            ["Gi1/0/01", "Gi1/0/02", "Gi1/0/03"],
            response.json()["names"],
        )


if __name__ == "__main__":
    unittest.main()