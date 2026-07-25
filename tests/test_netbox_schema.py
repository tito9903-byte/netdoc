from __future__ import annotations

import unittest

from app.services.change_plan import ChangePlanError
from app.services.netbox_schema_service import parse_action_schema


OPTIONS_PAYLOAD = {
    "actions": {
        "POST": {
            "name": {
                "type": "string",
                "required": True,
                "read_only": False,
                "label": "Name",
            },
            "status": {
                "type": "choice",
                "required": True,
                "read_only": False,
                "choices": [
                    {"value": "active", "display_name": "Active"},
                    {"value": "planned", "display_name": "Planned"},
                ],
            },
            "id": {
                "type": "integer",
                "required": False,
                "read_only": True,
            },
        }
    }
}


class NetBoxSchemaTests(unittest.TestCase):
    def test_parses_required_writable_fields_and_choices(self):
        schema = parse_action_schema(
            OPTIONS_PAYLOAD,
            endpoint="/api/dcim/devices/",
            method="POST",
        )
        self.assertEqual(schema.required_fields, {"name", "status"})
        self.assertEqual(schema.writable_fields, {"name", "status"})
        self.assertEqual(
            schema.fields["status"].choices[0],
            {"value": "active", "label": "Active"},
        )

    def test_accepts_valid_payload_and_virtual_changelog_field(self):
        schema = parse_action_schema(
            OPTIONS_PAYLOAD,
            endpoint="/api/dcim/devices/",
            method="POST",
        )
        schema.validate_payload({
            "name": "OLT-SMN-01",
            "status": "active",
            "changelog_message": "Creado desde NetDoc.",
        })

    def test_rejects_missing_unknown_and_invalid_choice(self):
        schema = parse_action_schema(
            OPTIONS_PAYLOAD,
            endpoint="/api/dcim/devices/",
            method="POST",
        )
        with self.assertRaises(ChangePlanError):
            schema.validate_payload({"name": "OLT-SMN-01"})
        with self.assertRaises(ChangePlanError):
            schema.validate_payload({
                "name": "OLT-SMN-01",
                "status": "active",
                "invented_field": True,
            })
        with self.assertRaises(ChangePlanError):
            schema.validate_payload({
                "name": "OLT-SMN-01",
                "status": "invalid",
            })

    def test_rejects_unannounced_method(self):
        with self.assertRaises(ChangePlanError):
            parse_action_schema(
                OPTIONS_PAYLOAD,
                endpoint="/api/dcim/devices/",
                method="PATCH",
            )


if __name__ == "__main__":
    unittest.main()
