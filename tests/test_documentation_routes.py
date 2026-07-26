from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.device_model_builder_service import ComponentDefinition


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
        "u_height": 10,
        "is_full_depth": True,
        "description": "OLT de acceso.",
        "front_image": "/media/front.png",
        "rear_image": None,
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
    def test_model_catalog_uses_documentation_table_and_contextual_creation(
        self,
        _manufacturers,
        _device_types,
    ):
        response = self.client.get("/device-types")

        self.assertEqual(200, response.status_code)
        self.assertIn("Listado de modelos documentados", response.text)
        self.assertIn("C600", response.text)
        self.assertIn("Crear modelo", response.text)
        self.assertIn("Puertos y componentes", response.text)
        self.assertIn("data-create-modal", response.text)
        self.assertNotIn(">Plantillas de puertos<", response.text)

    @patch(
        "app.routers.documentation.DeviceTypeService.list_manufacturers",
        new_callable=AsyncMock,
        return_value=MANUFACTURERS,
    )
    def test_new_model_form_uses_complete_netbox_workflow(
        self,
        _manufacturers,
    ):
        response = self.client.get("/device-types/new")

        self.assertEqual(200, response.status_code)
        self.assertIn('enctype="multipart/form-data"', response.text)
        self.assertIn('name="front_image"', response.text)
        self.assertIn('name="rear_image"', response.text)
        self.assertIn(
            '/device-types/actions/create-complete',
            response.text,
        )
        self.assertIn("data-netbox-model-fields", response.text)
        self.assertIn("Campos avanzados disponibles en NetBox", response.text)
        self.assertIn("Altura U", response.text)

    @patch(
        "app.routers.model_builder.DeviceModelBuilderService.model_advanced_fields",
        new_callable=AsyncMock,
        return_value=[
            {
                "name": "airflow",
                "label": "Flujo de aire",
                "required": False,
                "type": "choice",
                "input_type": "select",
                "choices": [
                    {"value": "front-to-rear", "label": "Frente a atrás"},
                ],
                "help_text": "Dirección de ventilación.",
                "default": None,
                "allow_null": True,
                "multiple": False,
            }
        ],
    )
    def test_model_schema_api_exposes_netbox_capabilities(self, _fields):
        response = self.client.get("/api/device-types/model-fields")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual("airflow", payload["fields"][0]["name"])
        self.assertEqual("Frente a atrás", payload["fields"][0]["choices"][0]["label"])

    @patch(
        "app.routers.model_builder.DeviceModelBuilderService.component_fields",
        new_callable=AsyncMock,
        return_value=[
            {
                "name": "type",
                "label": "Tipo",
                "required": True,
                "type": "choice",
                "input_type": "select",
                "choices": INTERFACE_TYPES,
                "help_text": "",
                "default": None,
                "allow_null": False,
                "multiple": False,
            }
        ],
    )
    @patch(
        "app.routers.model_builder.DeviceModelBuilderService.definition",
        return_value=ComponentDefinition(
            key="interface",
            label="Interfaces de red",
            singular="interfaz",
            endpoint="/api/dcim/interface-templates/",
            icon="⇆",
            description="Interfaces publicadas por NetBox.",
        ),
    )
    @patch(
        "app.routers.model_builder.DeviceTypeService.get_device_type",
        new_callable=AsyncMock,
        return_value=DEVICE_TYPES[0],
    )
    def test_component_creator_is_integrated_with_model_detail(
        self,
        _device_type,
        _definition,
        _fields,
    ):
        response = self.client.get(
            "/device-types/10/components/new?kind=interface"
        )

        self.assertEqual(200, response.status_code)
        self.assertIn("Interfaces de red", response.text)
        self.assertIn("Esquema NetBox", response.text)
        self.assertIn('name="name_pattern"', response.text)
        self.assertIn('name="type"', response.text)
        self.assertIn(
            "/device-types/10/components/actions/create",
            response.text,
        )

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
    def test_legacy_interface_workspace_remains_compatible(
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
