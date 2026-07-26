from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from app.services.device_model_builder_service import DeviceModelBuilderService


class DeviceModelBuilderServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_fields_follow_netbox_options(self):
        service = DeviceModelBuilderService()
        service.client.request = AsyncMock(return_value={
            "actions": {
                "POST": {
                    "manufacturer": {
                        "type": "field",
                        "required": True,
                    },
                    "model": {
                        "type": "string",
                        "required": True,
                    },
                    "u_height": {
                        "type": "float",
                        "required": False,
                    },
                    "airflow": {
                        "type": "choice",
                        "required": False,
                        "choices": [
                            {
                                "value": "front-to-rear",
                                "display_name": "Frente a atrás",
                            },
                            {
                                "value": "rear-to-front",
                                "display_name": "Atrás a frente",
                            },
                        ],
                    },
                    "weight": {
                        "type": "float",
                        "required": False,
                        "help_text": "Peso del modelo.",
                    },
                }
            }
        })

        fields = await service.model_advanced_fields()

        self.assertEqual(["airflow", "weight"], [field["name"] for field in fields])
        self.assertEqual("select", fields[0]["input_type"])
        self.assertEqual("Frente a atrás", fields[0]["choices"][0]["label"])
        self.assertEqual("decimal", fields[1]["input_type"])

    async def test_front_port_schema_loads_rear_port_choices(self):
        service = DeviceModelBuilderService()
        service.client.request = AsyncMock(return_value={
            "actions": {
                "POST": {
                    "device_type": {
                        "type": "field",
                        "required": True,
                    },
                    "name": {
                        "type": "string",
                        "required": True,
                    },
                    "type": {
                        "type": "choice",
                        "required": True,
                        "choices": [
                            {"value": "8p8c", "display_name": "8P8C"},
                        ],
                    },
                    "rear_port": {
                        "type": "field",
                        "required": True,
                    },
                    "rear_port_position": {
                        "type": "integer",
                        "required": True,
                    },
                }
            }
        })
        service.client.get_all = AsyncMock(return_value=[
            {"id": 90, "name": "R1", "display": "R1"},
            {"id": 91, "name": "R2", "display": "R2"},
        ])

        fields = await service.component_fields(
            "front_port",
            device_type_id=10,
        )

        rear_port = next(field for field in fields if field["name"] == "rear_port")
        self.assertEqual("select", rear_port["input_type"])
        self.assertEqual(
            [{"value": "90", "label": "R1"}, {"value": "91", "label": "R2"}],
            rear_port["choices"],
        )

    async def test_bulk_component_creation_uses_selected_netbox_endpoint(self):
        service = DeviceModelBuilderService()
        service.component_fields = AsyncMock(return_value=[
            {
                "name": "type",
                "label": "Tipo",
                "required": True,
                "input_type": "select",
                "choices": [
                    {"value": "1000base-t", "label": "1GBASE-T"},
                ],
                "multiple": False,
            },
            {
                "name": "mgmt_only",
                "label": "Solo administración",
                "required": False,
                "input_type": "checkbox",
                "choices": [],
                "multiple": False,
            },
            {
                "name": "label",
                "label": "Etiqueta",
                "required": False,
                "input_type": "text",
                "choices": [],
                "multiple": False,
            },
        ])
        service.client.request = AsyncMock(return_value=[
            {"id": 1, "name": "Gi1/0/01"},
            {"id": 2, "name": "Gi1/0/02"},
        ])

        created = await service.create_components(
            "interface",
            device_type_id=10,
            form={
                "name_pattern": "Gi1/0/{n:02}",
                "start": "1",
                "count": "2",
                "type": "1000base-t",
                "mgmt_only": "true",
                "label": "Puerto {n}",
            },
        )

        self.assertEqual(2, len(created))
        service.client.request.assert_awaited_once()
        method, endpoint = service.client.request.await_args.args
        payload = service.client.request.await_args.kwargs["json_body"]
        self.assertEqual("POST", method)
        self.assertEqual("/api/dcim/interface-templates/", endpoint)
        self.assertEqual("Gi1/0/01", payload[0]["name"])
        self.assertEqual("Puerto 1", payload[0]["label"])
        self.assertTrue(payload[0]["mgmt_only"])
        self.assertEqual(10, payload[0]["device_type"])


if __name__ == "__main__":
    unittest.main()
