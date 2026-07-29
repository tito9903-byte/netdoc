from __future__ import annotations

from importlib import import_module
from pathlib import Path
import inspect
import unittest

from fastapi.routing import iter_route_contexts

from app.routers import interface_workspace


class InterfaceWorkspaceTests(unittest.TestCase):
    def test_workspace_routes_and_legacy_aliases_are_registered(self):
        app = import_module("app.main").app
        routes = list(iter_route_contexts(app.routes))

        expected = {
            "/devices/{device_id}/interfaces/new-workspace": {"GET"},
            "/devices/{device_id}/interfaces/{interface_id}/workspace": {"GET"},
            "/devices/{device_id}/interfaces/actions/create-workspace": {"POST"},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                matches = [route for route in routes if route.path == path]
                actual = set().union(*(set(route.methods or set()) for route in matches))
                self.assertEqual(methods, actual)

        edit_matches = [
            route
            for route in routes
            if route.path == "/devices/{device_id}/interfaces/{interface_id}/edit"
            and "GET" in set(route.methods or set())
        ]
        self.assertGreaterEqual(len(edit_matches), 1)
        self.assertEqual(
            "app.routers.interface_workspace_aliases",
            edit_matches[0].endpoint.__module__,
        )

    def test_workspace_renders_ip_addresses_server_side(self):
        template = Path("app/templates/interface_workspace.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("03 · Direccionamiento", template)
        self.assertIn("{% for item in addresses %}", template)
        self.assertIn("＋ Agregar IP", template)
        self.assertNotIn("Cargando direcciones IP", template)
        self.assertNotIn("device_interface_ip_management.js", template)

    def test_creation_form_accepts_optional_initial_ip(self):
        template = Path("app/templates/interface_workspace.html").read_text(
            encoding="utf-8"
        )
        source = inspect.getsource(interface_workspace.interface_workspace_create_submit)

        for field in (
            "initial_ip_address",
            "initial_ip_status",
            "initial_ip_role",
            "initial_ip_vrf_id",
            "initial_ip_dns_name",
            "initial_ip_description",
            "initial_ip_make_primary",
        ):
            with self.subTest(field=field):
                self.assertIn(f'name="{field}"', template)
                self.assertIn(field, source)

        self.assertIn('"assigned_object_type": "dcim.interface"', source)
        self.assertIn('"assigned_object_id": interface_id', source)
        self.assertIn("ip_interface(clean_initial_ip)", source)

    def test_workspace_preloads_interface_and_addresses_concurrently(self):
        source = inspect.getsource(interface_workspace.render_workspace)

        self.assertIn("await asyncio.gather", source)
        self.assertIn('"/api/ipam/ip-addresses/"', source)
        self.assertIn('"interface_id": interface_id', source)
        self.assertIn("serialize_addresses", source)

    def test_workspace_has_dedicated_professional_layout(self):
        stylesheet = Path("app/static/css/interface_workspace.css").read_text(
            encoding="utf-8"
        )

        self.assertIn(".interface-workspace-layout", stylesheet)
        self.assertIn(".interface-workspace-addresses", stylesheet)
        self.assertIn(".interface-workspace-sidebar", stylesheet)
        self.assertIn(".interface-workspace-danger", stylesheet)


if __name__ == "__main__":
    unittest.main()
