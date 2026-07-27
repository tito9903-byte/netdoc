from __future__ import annotations

from importlib import import_module
from pathlib import Path
import unittest

from fastapi.routing import iter_route_contexts


class DeviceManagementRouteTests(unittest.TestCase):
    def test_management_routes_are_registered_once(self):
        app = import_module("app.main").app
        expected = {
            "/devices/{device_id}/edit": {"GET", "POST"},
            "/devices/{device_id}/interfaces/new": {"GET"},
            "/devices/{device_id}/interfaces/actions/create": {"POST"},
            "/devices/{device_id}/interfaces/{interface_id}/edit": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/actions/update": {"POST"},
            "/devices/{device_id}/interfaces/{interface_id}/delete": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/actions/delete": {"POST"},
            "/device-types/{device_type_id}/interfaces/{interface_id}/edit": {"GET"},
            "/device-types/{device_type_id}/interfaces/{interface_id}/actions/update": {"POST"},
            "/device-types/{device_type_id}/interfaces/{interface_id}/actions/delete": {"POST"},
        }

        routes = list(iter_route_contexts(app.routes))
        for path, methods in expected.items():
            with self.subTest(path=path):
                found = [route for route in routes if route.path == path]
                actual = set().union(*(set(route.methods or set()) for route in found))
                self.assertEqual(methods, actual)

    def test_forms_are_post_only_for_mutations(self):
        device_form = Path("app/templates/device_interface_form.html").read_text(
            encoding="utf-8"
        )
        delete_form = Path("app/templates/device_interface_delete.html").read_text(
            encoding="utf-8"
        )
        model_form = Path("app/templates/device_type_interface_edit.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('method="post"', device_form)
        self.assertIn('method="post"', delete_form)
        self.assertIn('method="post"', model_form)
        self.assertIn("csrf_token", device_form)
        self.assertIn("csrf_token", delete_form)
        self.assertIn("delete_token", model_form)

    def test_interface_form_handles_nullable_type_lag_and_mac(self):
        device_form = Path("app/templates/device_interface_form.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('{% set raw_lag = interface.get("lag")', device_form)
        self.assertIn("raw_lag is mapping", device_form)
        self.assertIn("raw_type is mapping", device_form)
        self.assertIn("raw_mac is mapping", device_form)
        self.assertIn('value="{{ current_mac }}"', device_form)

    def test_detail_pages_receive_management_actions_from_authenticated_api(self):
        script = Path("app/static/js/device_primary_ip_link.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("/api/netdoc/devices/", script)
        self.assertIn("/api/netdoc/device-types/", script)
        self.assertIn("Editar dispositivo", script)
        self.assertIn("Crear componente", script)
        self.assertIn("Editar / Eliminar", script)


if __name__ == "__main__":
    unittest.main()
