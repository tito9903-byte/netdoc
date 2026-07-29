from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.netbox_client import NetBoxClient


class DeviceInterfaceAddressServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_groups_all_device_addresses_without_n_plus_one_queries(self):
        client = NetBoxClient()

        async def get_all(endpoint, params=None, page_limit=200, maximum_pages=50):
            if endpoint == "/api/dcim/interfaces/":
                return [
                    {"id": 10, "name": "Vlan100", "enabled": True},
                    {"id": 11, "name": "Vlan200", "enabled": True},
                    {"id": 12, "name": "Loopback0", "enabled": True},
                ]
            if endpoint == "/api/ipam/ip-addresses/":
                return [
                    {
                        "id": 101,
                        "address": "192.0.2.10/24",
                        "assigned_object": {"id": 10, "display": "Vlan100"},
                    },
                    {
                        "id": 102,
                        "address": "2001:db8::10/64",
                        "assigned_object": {"id": 10, "display": "Vlan100"},
                    },
                    {
                        "id": 103,
                        "address": "198.51.100.20/24",
                        "assigned_object_id": 11,
                    },
                ]
            self.fail(f"Endpoint inesperado: {endpoint}")

        client.get_all = AsyncMock(side_effect=get_all)

        interfaces = await client.get_device_interfaces(214)

        self.assertEqual(2, client.get_all.await_count)
        self.assertEqual(2, interfaces[0]["_ip_address_count"])
        self.assertEqual(
            ["192.0.2.10/24", "2001:db8::10/64"],
            [item["address"] for item in interfaces[0]["_ip_addresses"]],
        )
        self.assertEqual(1, interfaces[1]["_ip_address_count"])
        self.assertEqual(0, interfaces[2]["_ip_address_count"])


class DeviceInterfaceAddressRouteTests(unittest.TestCase):
    @patch(
        "app.main.NetBoxClient.get_device_interfaces",
        new_callable=AsyncMock,
        return_value=[
            {
                "id": 10,
                "name": "Vlan100",
                "type": {"value": "virtual", "label": "Virtual"},
                "enabled": True,
                "_ip_address_count": 2,
                "_ip_addresses": [
                    {
                        "id": 101,
                        "display": "192.0.2.10/24",
                        "family": {"value": 4},
                    },
                    {
                        "id": 102,
                        "display": "2001:db8::10/64",
                        "family": {"value": 6},
                    },
                ],
            },
            {
                "id": 11,
                "name": "Vlan200",
                "type": {"value": "virtual", "label": "Virtual"},
                "enabled": True,
                "_ip_address_count": 0,
                "_ip_addresses": [],
            },
        ],
    )
    @patch(
        "app.main.NetBoxClient.get_device",
        new_callable=AsyncMock,
        return_value={
            "id": 214,
            "name": "SWI-01",
            "display": "SWI-01",
            "status": {"value": "active", "label": "Activo"},
            "primary_ip4": {"id": 101, "display": "192.0.2.10/24"},
            "device_type": {
                "id": 501,
                "display": "S3900-24F4S-R",
                "manufacturer": {"display": "FiberStore"},
            },
            "site": {"display": "SPIRIT OF TERRENAS"},
            "role": {"display": "Access"},
        },
    )
    def test_device_detail_renders_addresses_and_primary_marker(
        self,
        _get_device,
        _get_interfaces,
    ):
        # Esta prueba valida únicamente el renderizado del detalle del equipo.
        # No debe depender de la contraseña configurada en el entorno donde corre.
        with (
            patch(
                "app.core.auth.PermissionMiddleware._required_permission",
                return_value=None,
            ),
            patch("app.main.access_redirect", return_value=None),
            TestClient(app) as client,
        ):
            response = client.get("/devices/214")

        self.assertEqual(200, response.status_code)
        self.assertIn("Direcciones IP", response.text)
        self.assertIn("192.0.2.10/24", response.text)
        self.assertIn("2001:db8::10/64", response.text)
        self.assertIn("interface-address-primary", response.text)
        self.assertIn("2 IPs", response.text)
        self.assertIn("Sin asignar", response.text)


if __name__ == "__main__":
    unittest.main()
