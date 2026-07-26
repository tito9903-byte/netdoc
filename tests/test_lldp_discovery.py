from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from app.main import app
from app.services.lldp_discovery_service import (
    LldpDiscoveryService,
    LldpObservation,
)


class LldpParserTests(unittest.TestCase):
    def test_normalizes_structured_netmiko_output(self):
        observations = LldpDiscoveryService.parse_output([
            {
                "local_interface": "Ethernet1",
                "neighbor": "SW-CORE-02.telenord.local",
                "neighbor_interface": "Ethernet49",
                "management_ip": "192.168.10.20",
                "chassis_id": "001c.73aa.bbcc",
            }
        ])

        self.assertEqual(1, len(observations))
        item = observations[0]
        self.assertEqual("Ethernet1", item.local_interface)
        self.assertEqual("SW-CORE-02.telenord.local", item.remote_system_name)
        self.assertEqual("Ethernet49", item.remote_port_id)
        self.assertEqual("192.168.10.20", item.management_ip)

    def test_parses_cisco_arista_style_detail_output(self):
        output = """
------------------------------------------------
Local Intf: Gi1/0/1
Chassis id: 00:1c:73:aa:bb:cc
Port id: Ethernet49
Port Description: UPLINK-SW-ACCESS-01
System Name: SW-CORE-02
Management Address: 192.168.10.20
------------------------------------------------
"""
        observations = LldpDiscoveryService.parse_output(output)

        self.assertEqual(1, len(observations))
        self.assertEqual("Gi1/0/1", observations[0].local_interface)
        self.assertEqual("SW-CORE-02", observations[0].remote_system_name)
        self.assertEqual("Ethernet49", observations[0].remote_port_id)
        self.assertEqual(
            "UPLINK-SW-ACCESS-01",
            observations[0].remote_port_description,
        )

    def test_parses_routeros_neighbor_detail(self):
        output = (
            ' 0 interface=sfp-sfpplus1 identity=CCR-CORE '
            'interface-name=sfp-sfpplus12 address=192.168.1.1 '
            'mac-address=AA:BB:CC:DD:EE:FF\n'
        )
        observations = LldpDiscoveryService.parse_output(output)

        self.assertEqual(1, len(observations))
        self.assertEqual("sfp-sfpplus1", observations[0].local_interface)
        self.assertEqual("CCR-CORE", observations[0].remote_system_name)
        self.assertEqual("sfp-sfpplus12", observations[0].remote_port_id)


class LldpMatchingTests(unittest.IsolatedAsyncioTestCase):
    async def test_matches_neighbor_and_both_interfaces_without_writing(self):
        async def get_all(endpoint, params=None, **_kwargs):
            if endpoint == "/api/dcim/devices/":
                return [
                    {
                        "id": 10,
                        "name": "SW-ACCESS-01",
                        "primary_ip4": {"address": "192.168.10.10/24"},
                    },
                    {
                        "id": 20,
                        "name": "SW-CORE-02",
                        "primary_ip4": {"address": "192.168.10.20/24"},
                    },
                ]
            if endpoint == "/api/dcim/interfaces/" and params["device_id"] == 10:
                return [
                    {
                        "id": 101,
                        "name": "GigabitEthernet1/0/1",
                        "cable": None,
                        "connected_endpoints": [],
                    }
                ]
            if endpoint == "/api/dcim/interfaces/" and params["device_id"] == 20:
                return [
                    {
                        "id": 201,
                        "name": "Ethernet49",
                        "cable": None,
                        "connected_endpoints": [],
                    }
                ]
            self.fail(f"Consulta inesperada: {endpoint} {params}")

        service = object.__new__(LldpDiscoveryService)
        service.client = SimpleNamespace(get_all=AsyncMock(side_effect=get_all))

        rows = await service._match_observations(
            local_device={
                "id": 10,
                "name": "SW-ACCESS-01",
                "primary_ip4": {"address": "192.168.10.10/24"},
            },
            observations=[
                LldpObservation(
                    local_interface="Gi1/0/1",
                    remote_system_name="SW-CORE-02.telenord.local",
                    remote_port_id="Ethernet49",
                    management_ip="192.168.10.20",
                )
            ],
        )

        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]["ready"])
        self.assertEqual(101, rows[0]["local_interface_id"])
        self.assertEqual(20, rows[0]["remote_device_id"])
        self.assertEqual(201, rows[0]["remote_interface_id"])
        self.assertGreaterEqual(rows[0]["confidence"], 90)

    async def test_marks_existing_netbox_cable_as_conflict(self):
        async def get_all(endpoint, params=None, **_kwargs):
            if endpoint == "/api/dcim/devices/":
                return [{"id": 20, "name": "SW-CORE-02"}]
            if endpoint == "/api/dcim/interfaces/" and params["device_id"] == 10:
                return [{"id": 101, "name": "Eth1", "cable": {"id": 900}}]
            if endpoint == "/api/dcim/interfaces/" and params["device_id"] == 20:
                return [{"id": 201, "name": "Eth49", "cable": None}]
            self.fail(f"Consulta inesperada: {endpoint} {params}")

        service = object.__new__(LldpDiscoveryService)
        service.client = SimpleNamespace(get_all=AsyncMock(side_effect=get_all))
        rows = await service._match_observations(
            local_device={"id": 10, "name": "SW-ACCESS-01"},
            observations=[
                LldpObservation(
                    local_interface="Eth1",
                    remote_system_name="SW-CORE-02",
                    remote_port_id="Eth49",
                )
            ],
        )

        self.assertEqual("conflict", rows[0]["state"])
        self.assertFalse(rows[0]["ready"])


class LldpRouteRegistrationTests(unittest.TestCase):
    def test_lldp_routes_are_registered(self):
        paths = {getattr(route, "path", "") for route in app.routes}

        self.assertIn("/devices/{device_id}/lldp-discovery", paths)
        self.assertIn("/devices/{device_id}/lldp-discovery/run", paths)
        self.assertIn("/devices/{device_id}/lldp-discovery/confirm", paths)


if __name__ == "__main__":
    unittest.main()
