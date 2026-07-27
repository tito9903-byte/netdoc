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
            {
                "id": 4,
                "name": "REMOTE-WITH-SECONDARY-IP",
                "primary_ip4": {"address": "10.0.0.4/32"},
            },
        ]
        self.interfaces = {
            1: [{"id": 11, "name": "Ethernet1", "cable": None, "connected_endpoints": []}],
            2: [{"id": 21, "name": "Ethernet2", "cable": None, "connected_endpoints": []}],
            3: [{"id": 31, "name": "Ethernet2", "cable": None, "connected_endpoints": []}],
            4: [{"id": 41, "name": "Ethernet2", "cable": None, "connected_endpoints": []}],
        }

    async def get_all(self, endpoint, params=None, **kwargs):
        if endpoint == "/api/dcim/devices/":
            return [dict(item) for item in self.devices]
        if endpoint == "/api/dcim/interfaces/":
            device_id = int((params or {}).get("device_id") or 0)
            return [dict(item) for item in self.interfaces.get(device_id, [])]
        if endpoint == "/api/ipam/ip-addresses/":
            address = str((params or {}).get("q") or "")
            if address == "198.51.100.40":
                return [{
                    "id": 400,
                    "address": "198.51.100.40/32",
                    "assigned_object": {
                        "id": 401,
                        "name": "Management1",
                        "device": {"id": 4, "name": "REMOTE-WITH-SECONDARY-IP"},
                    },
                }]
            return []
        raise AssertionError(f"Endpoint inesperado: {endpoint}")


class LldpMatchingPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        install_lldp_matching_support()
        self.service = object.__new__(LldpDiscoveryService)
        self.service.client = FakeClient()
        self.local_device = {"id": 1, "name": "LOCAL"}

    async def test_name_and_ip_must_identify_the_same_device(self):
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
        self.assertEqual("identity_conflict", row["match_method"])
        self.assertEqual(
            "Nombre exacto + IP asignada a otro equipo",
            row["match_source_label"],
        )
        self.assertFalse(row["management_ip_matches_device"])
        self.assertFalse(row["identity_verified"])
        self.assertFalse(row["ready"])
        self.assertEqual("unresolved", row["state"])
        self.assertIn("asignada a REMOTE-BY-IP", row["match_warning"])

    async def test_name_match_without_assigned_ip_stays_unresolved(self):
        rows = await self.service._match_observations(
            local_device=self.local_device,
            observations=[LldpObservation(
                local_interface="Ethernet1",
                remote_system_name="REMOTE-BY-NAME",
                remote_port_id="Ethernet2",
                management_ip="203.0.113.20",
            )],
        )

        row = rows[0]
        self.assertEqual(2, row["remote_device_id"])
        self.assertEqual("name_exact_ip_unverified", row["match_method"])
        self.assertFalse(row["identity_verified"])
        self.assertFalse(row["ready"])
        self.assertIn("no está asignada", row["match_warning"])

    async def test_name_and_non_primary_assigned_ip_are_valid_together(self):
        rows = await self.service._match_observations(
            local_device=self.local_device,
            observations=[LldpObservation(
                local_interface="Ethernet1",
                remote_system_name="REMOTE-WITH-SECONDARY-IP",
                remote_port_id="Ethernet2",
                management_ip="198.51.100.40",
            )],
        )

        row = rows[0]
        self.assertEqual(4, row["remote_device_id"])
        self.assertEqual("name_exact", row["match_method"])
        self.assertEqual("Nombre exacto + IP asignada", row["match_source_label"])
        self.assertTrue(row["management_ip_matches_device"])
        self.assertFalse(row["management_ip_matches_primary"])
        self.assertTrue(row["identity_verified"])
        self.assertTrue(row["ready"])
        self.assertIn("alguna interfaz", row["match_warning"])

    async def test_unique_primary_ip_is_valid_fallback_and_can_be_confirmed(self):
        rows = await self.service._match_observations(
            local_device=self.local_device,
            observations=[LldpObservation(
                local_interface="Ethernet1",
                remote_system_name="NOMBRE-DIFERENTE",
                remote_port_id="Ethernet2",
                management_ip="192.0.2.30",
            )],
        )

        row = rows[0]
        self.assertEqual(3, row["remote_device_id"])
        self.assertEqual("management_ip", row["match_method"])
        self.assertEqual("IP principal", row["match_source_label"])
        self.assertTrue(row["management_ip_matches_device"])
        self.assertTrue(row["management_ip_matches_primary"])
        self.assertTrue(row["identity_verified"])
        self.assertTrue(row["ready"])

    async def test_non_primary_assigned_ip_is_also_valid_fallback(self):
        rows = await self.service._match_observations(
            local_device=self.local_device,
            observations=[LldpObservation(
                local_interface="Ethernet1",
                remote_system_name="OTRO-NOMBRE",
                remote_port_id="Ethernet2",
                management_ip="198.51.100.40",
            )],
        )

        row = rows[0]
        self.assertEqual(4, row["remote_device_id"])
        self.assertEqual("management_ip", row["match_method"])
        self.assertEqual("IP asignada", row["match_source_label"])
        self.assertTrue(row["management_ip_matches_device"])
        self.assertFalse(row["management_ip_matches_primary"])
        self.assertTrue(row["identity_verified"])
        self.assertTrue(row["ready"])


if __name__ == "__main__":
    unittest.main()
