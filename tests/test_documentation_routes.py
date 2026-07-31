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
    def test_model_catalog_keeps_port_management_inside_models(
        self,
        _manufacturers,
        _device_types,
    ):
        response = self.client.get("/device-types")

        self.assertEqual(200, response.status_code)
        self.assertIn("Modelos de equipos", response.text)
        self.assertIn("C600", response.text)
        self.assertNotIn('href="/interface-templates', response.text)
        self.assertIn(
            'href="/device-types/10#interfaces"',
            response.text,
        )

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

    def test_combined_model_image_route_requires_valid_csrf(self):
        response = self.client.post(
            "/device-types/actions/create-with-images",
            data={
                "manufacturer_id": "1",
                "model": "C600",
                "u_height": "2",
            },
            follow_redirects=False,
        )

        self.assertEqual(303, response.status_code)
        self.assertIn("/device-types/new?", response.headers["location"])
        self.assertIn("error=", response.headers["location"])

    @patch(
        "app.main.NetBoxClient.list_device_roles",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_sites",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_devices",
        new_callable=AsyncMock,
        return_value={"count": 0, "results": []},
    )
    def test_device_catalog_keeps_contextual_create_action(
        self,
        _devices,
        _sites,
        _roles,
    ):
        response = self.client.get("/devices")

        self.assertEqual(200, response.status_code)
        self.assertIn("Crear equipo", response.text)
        self.assertEqual(
            1,
            response.text.count('href="/devices/actions/new"'),
        )
        self.assertNotIn("Acciones rápidas", response.text)

    def test_legacy_interface_workspace_redirects_to_model_detail(self):
        response = self.client.get(
            "/interface-templates?device_type_id=10",
            follow_redirects=False,
        )

        self.assertEqual(303, response.status_code)
        self.assertEqual(
            "/device-types/10#interfaces",
            response.headers["location"],
        )

    def test_legacy_interface_workspace_without_model_opens_catalog(self):
        response = self.client.get(
            "/interface-templates",
            follow_redirects=False,
        )

        self.assertEqual(303, response.status_code)
        self.assertEqual(
            "/device-types",
            response.headers["location"],
        )

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
