from __future__ import annotations

from importlib import import_module
from pathlib import Path
import unittest

from fastapi.routing import iter_route_contexts

from app.routers.device_interface_ips import (
    _address_interface_id,
    _field_choices,
)


class DeviceInterfaceIpManagementTests(unittest.TestCase):
    def test_ip_management_routes_are_registered(self):
        app = import_module("app.main").app
        expected = {
            "/api/netdoc/devices/{device_id}/interfaces/{interface_id}/ip-addresses": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/new": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/actions/create": {"POST"},
            "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/{address_id}/edit": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/ip-addresses/{address_id}/actions/update": {"POST"},
        }

        routes = list(iter_route_contexts(app.routes))
        for path, methods in expected.items():
            with self.subTest(path=path):
                matches = [route for route in routes if route.path == path]
                actual = set().union(
                    *(set(route.methods or set()) for route in matches)
                )
                self.assertEqual(methods, actual)

    def test_interface_edit_page_loads_ip_management_client(self):
        template = Path("app/templates/device_interface_form.html").read_text(
            encoding="utf-8"
        )
        script = Path(
            "app/static/js/device_interface_ip_management.js"
        ).read_text(encoding="utf-8")

        self.assertIn("data-interface-ip-management", template)
        self.assertIn("device_interface_ip_management.js", template)
        self.assertIn("Agregar IP", script)
        self.assertIn("Editar IP", script)
        self.assertIn("escapeHtml", script)
        self.assertIn("credentials: \"same-origin\"", script)

    def test_ip_form_supports_address_vrf_metadata_and_primary_selection(self):
        template = Path("app/templates/device_interface_ip_form.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('name="address"', template)
        self.assertIn('name="status"', template)
        self.assertIn('name="role"', template)
        self.assertIn('name="vrf_id"', template)
        self.assertIn('name="dns_name"', template)
        self.assertIn('name="description"', template)
        self.assertIn('name="make_primary"', template)
        self.assertIn('name="csrf_token"', template)
        self.assertIn('method="post"', template)

    def test_address_assignment_accepts_both_netbox_shapes(self):
        self.assertEqual(
            91,
            _address_interface_id({"assigned_object": {"id": 91}}),
        )
        self.assertEqual(
            92,
            _address_interface_id({"assigned_object_id": 92}),
        )

    def test_choice_parser_reads_netbox_options(self):
        options = {
            "actions": {
                "POST": {
                    "status": {
                        "choices": [
                            {"value": "active", "display_name": "Activo"},
                            {"value": "reserved", "display_name": "Reservado"},
                        ]
                    }
                }
            }
        }

        self.assertEqual(
            [
                {"value": "active", "label": "Activo"},
                {"value": "reserved", "label": "Reservado"},
            ],
            _field_choices(options, "status"),
        )


if __name__ == "__main__":
    unittest.main()
