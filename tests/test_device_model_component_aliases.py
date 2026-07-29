from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.services.device_model_builder_service import DeviceModelBuilderService


class ComponentKindAliasTests(unittest.IsolatedAsyncioTestCase):
    def test_plural_rear_ports_alias_resolves_to_canonical_definition(self):
        definition = DeviceModelBuilderService.definition("rear_ports")

        self.assertEqual("rear_port", definition.key)
        self.assertEqual("/api/dcim/rear-port-templates/", definition.endpoint)

    def test_hyphenated_plural_alias_is_normalized(self):
        definition = DeviceModelBuilderService.definition("rear-ports")

        self.assertEqual("rear_port", definition.key)

    async def test_create_twelve_fdp_rear_ports_from_plural_alias(self):
        request = AsyncMock(
            return_value=[{"id": number} for number in range(1, 13)]
        )
        service = object.__new__(DeviceModelBuilderService)
        service.client = SimpleNamespace(request=request)
        service.component_fields = AsyncMock(
            return_value=[
                {
                    "name": "type",
                    "label": "Tipo",
                    "required": True,
                    "input_type": "select",
                    "choices": [{"value": "8p8c", "label": "8P8C"}],
                    "multiple": False,
                }
            ]
        )

        created = await service.create_components(
            "rear_ports",
            device_type_id=12,
            form={
                "name_pattern": "R{n}",
                "start": "1",
                "count": "12",
                "type": "8p8c",
            },
        )

        self.assertEqual(12, len(created))
        request.assert_awaited_once()
        _, kwargs = request.await_args
        self.assertEqual(
            "/api/dcim/rear-port-templates/",
            request.await_args.args[1],
        )
        payload = kwargs["json_body"]
        self.assertEqual(12, len(payload))
        self.assertEqual("R1", payload[0]["name"])
        self.assertEqual("R12", payload[-1]["name"])
        self.assertTrue(all(item["device_type"] == 12 for item in payload))
        self.assertTrue(all(item["type"] == "8p8c" for item in payload))


if __name__ == "__main__":
    unittest.main()
