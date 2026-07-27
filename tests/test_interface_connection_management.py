from __future__ import annotations

from importlib import import_module
from pathlib import Path
import inspect
import unittest

from fastapi.routing import iter_route_contexts

from app.routers.interface_connection_management import (
    cable_contains_interface,
    delete_cable,
)


class InterfaceConnectionManagementTests(unittest.TestCase):
    def test_connection_delete_routes_are_registered(self):
        app = import_module("app.main").app
        expected = {
            "/devices/{device_id}/interfaces/{interface_id}/connection/delete": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/connection/actions/delete": {"POST"},
        }

        routes = list(iter_route_contexts(app.routes))
        for path, methods in expected.items():
            with self.subTest(path=path):
                matches = [route for route in routes if route.path == path]
                actual = set().union(*(set(route.methods or set()) for route in matches))
                self.assertEqual(methods, actual)

    def test_cable_validation_requires_the_selected_interface(self):
        cable = {
            "a_terminations": [
                {
                    "object_type": "dcim.interface",
                    "object_id": 21551,
                }
            ],
            "b_terminations": [
                {
                    "object_type": {"value": "dcim.interface"},
                    "object": {"id": 9001},
                }
            ],
        }

        self.assertTrue(cable_contains_interface(cable, 21551))
        self.assertTrue(cable_contains_interface(cable, 9001))
        self.assertFalse(cable_contains_interface(cable, 77))

    def test_delete_operation_targets_only_the_cable_api(self):
        source = inspect.getsource(delete_cable)

        self.assertIn("/api/dcim/cables/{cable_id}/", source)
        self.assertNotIn("/api/dcim/interfaces/", source)
        self.assertNotIn("/api/ipam/ip-addresses/", source)

    def test_interface_editor_separates_connection_and_interface_deletion(self):
        template = Path("app/templates/device_interface_form.html").read_text(
            encoding="utf-8"
        )
        confirmation = Path(
            "app/templates/interface_connection_delete.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Eliminar conexión", template)
        self.assertIn("Eliminar interfaz", template)
        self.assertIn("elimina únicamente el cable documentado", confirmation)
        self.assertIn("sus interfaces y sus direcciones IP permanecerán intactos", confirmation)
        self.assertIn('name="cable_id"', confirmation)
        self.assertIn('method="post"', confirmation)

    def test_interface_editor_loads_professional_workspace_styles(self):
        management_css = Path("app/static/css/device_management.css").read_text(
            encoding="utf-8"
        )
        editor_css = Path("app/static/css/interface_editor.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("interface_editor.css", management_css)
        self.assertIn(".interface-editor-layout", editor_css)
        self.assertIn(".interface-connection-summary", editor_css)
        self.assertIn(".connection-delete-confirmation", editor_css)


if __name__ == "__main__":
    unittest.main()
