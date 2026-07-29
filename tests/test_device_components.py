from __future__ import annotations

from importlib import import_module
from pathlib import Path
import unittest

from fastapi.routing import iter_route_contexts

from app.routers.device_components import COMPONENT_KINDS
from app.routers.device_management_api import connection_metadata


class DeviceComponentTests(unittest.TestCase):
    def test_component_routes_are_registered(self):
        app = import_module("app.main").app
        routes = list(iter_route_contexts(app.routes))
        expected = {
            "/devices/{device_id}/components": {"GET"},
            "/devices/{device_id}/components/new": {"GET"},
            "/devices/{device_id}/components/{kind}/new": {"GET"},
            "/devices/{device_id}/components/{kind}/actions/create": {"POST"},
        }

        for path, methods in expected.items():
            with self.subTest(path=path):
                found = [route for route in routes if route.path == path]
                actual = set().union(*(set(route.methods or set()) for route in found))
                self.assertEqual(methods, actual)

    def test_picker_includes_core_netbox_component_types(self):
        self.assertEqual(
            {
                "interface",
                "console-port",
                "console-server-port",
                "power-port",
                "power-outlet",
                "rear-port",
                "front-port",
                "module-bay",
                "device-bay",
                "inventory-item",
            },
            set(COMPONENT_KINDS),
        )

    def test_component_forms_post_with_csrf(self):
        form = Path("app/templates/device_component_form.html").read_text(
            encoding="utf-8"
        )
        picker = Path("app/templates/device_component_picker.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('method="post"', form)
        self.assertIn("csrf_token", form)
        self.assertIn("Crear componente", picker)
        self.assertIn("components/{{ item.key }}/new", picker)

    def test_connected_endpoint_exposes_remote_device_and_interface(self):
        metadata = connection_metadata({
            "connected_endpoints": [{
                "id": 900,
                "name": "Ethernet30",
                "display": "Ethernet30",
                "device": {
                    "id": 77,
                    "name": "ARISTA7050HEADEND",
                    "display": "ARISTA7050HEADEND",
                },
            }],
        })

        self.assertIsNotNone(metadata)
        self.assertEqual(77, metadata["device_id"])
        self.assertEqual("ARISTA7050HEADEND", metadata["device_name"])
        self.assertEqual("Ethernet30", metadata["interface_name"])
        self.assertTrue(metadata["navigable"])

    def test_device_script_links_connection_to_remote_device(self):
        script = Path("app/static/js/device_primary_ip_link.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("connection-device-link", script)
        self.assertIn("/devices/${connection.device_id}#interfaces", script)
        self.assertIn("Crear componente", script)
        self.assertIn("/devices/${deviceId}/components", script)


if __name__ == "__main__":
    unittest.main()
