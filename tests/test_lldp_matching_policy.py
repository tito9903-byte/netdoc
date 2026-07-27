from __future__ import annotations

import unittest

from app.services.lldp_discovery_service import (
    LldpDiscoveryService,
    LldpObservation,
)
from app.services.lldp_matching_support import install_lldp_matching_support


class FakeClient:
    def __init__(self) -> None:
        self.devices = [
            {
                "id": 2,
                "name": "REMOTE-BY-NAME",
                "primary_ip4": {"address": "10.0.0.2/32"},
            },
            {
                "id": 3,
                "name": "REMOTE-BY-IP",
                "primary_ip4": {"address": "192.0.2.30/32"},
            },
        ]
        self.interfaces = {
            1: [{"id": 11, "name": "Ethernet1", "cable": None, "connected_endpoints": []}],
            2: [{"id": 21, "name": "Ethernet2", "cable": None, "connected_endpoints": []}],
            3: [{"id": 31, "name": "Ethernet2", "cable": None, "connected_endpoints": []}],
        }

    async def get_all(self, endpoint, params=None, **kwargs):
        if endpoint == "/api/dcim/devices/":
            return [dict(item) for item in self.devices]
        if endpoint == "/api/dcim/interfaces/":
            device_id = int((params or {}).get("device_id") or 0)
            return [dict(item) for item in self.interfaces.get(device_id, [])]
        raise AssertionError(f"Endpoint inesperado: {endpoint}")


class LldpMatchingPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        install_lldp_matching_support()
        self.service = object.__new__(LldpDiscoveryService)
        self.service.client = FakeClient()
        self.local_device = {"id": 1, "name": "LOCAL"}

    async def test_name_match_has_priority_over_conflicting_management_ip(self):
        rows = await self.service._match_observations(
            local_device=self.local_device,
            observations=[LldpObservation(
                local_interface="Ethernet1",
                remote_system_name="REMOTE-BY-NAME",
                remote_port_id="Ethernet2",
                management_ip="192.0.2.30",
            )],
        )

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(2, row["remote_device_id"])
        self.assertEqual("name_exact", row["match_method"])
        self.assertEqual("Nombre exacto", row["match_source_label"])
        self.assertFalse(row["management_ip_matches_primary"])
        self.assertTrue(row["ready"])
        self.assertIn("identificado por nombre", row["match_warning"])

    async def test_unique_ip_is_valid_fallback_and_can_be_confirmed(self):
        rows = await self.service._match_observations(
            local_device=self.local_device,
            observations=[LldpObservation(
                local_interface="Ethernet1",
                remote_system_name="NOMBRE-DIFERENTE",
                remote_port_id="Ethernet2",
                management_ip="192.0.2.30",
            )],
        )

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(3, row["remote_device_id"])
        self.assertEqual("management_ip", row["match_method"])
        self.assertEqual("IP anunciada", row["match_source_label"])
        self.assertTrue(row["management_ip_matches_primary"])
        self.assertTrue(row["ready"])
        self.assertIn("únicamente por la IP", row["match_warning"])


if __name__ == "__main__":
    unittest.main()
