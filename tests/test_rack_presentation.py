from __future__ import annotations

import unittest

from app.services.rack_presentation import (
    format_u,
    prepare_elevation,
    prepare_topology,
)


class RackPresentationTests(unittest.TestCase):
    def test_two_u_device_occupies_two_units(self):
        rack = {"id": 1, "u_height": 42, "starting_unit": 1}
        devices = [{
            "id": 10,
            "name": "CORE-01",
            "position": 10,
            "face": {"value": "front"},
            "device_type": {
                "id": 5,
                "model": "Router 2U",
                "u_height": 2,
                "is_full_depth": False,
            },
        }]

        result = prepare_elevation(rack, devices, "front")

        self.assertEqual(result["used_units"], 2.0)
        self.assertEqual(result["free_units"], 40.0)
        self.assertEqual(result["visible_devices"][0]["_span"], 4)
        self.assertEqual(result["visible_devices"][0]["_u_height_label"], "2U")

    def test_zero_u_device_does_not_consume_vertical_capacity(self):
        rack = {"id": 1, "u_height": 42}
        devices = [{
            "id": 11,
            "name": "PDU-VERTICAL",
            "position": None,
            "device_type": {
                "id": 6,
                "model": "PDU 0U",
                "u_height": 0,
            },
        }]

        result = prepare_elevation(rack, devices, "front")

        self.assertEqual(result["used_units"], 0.0)
        self.assertEqual(result["free_units"], 42.0)
        self.assertEqual(len(result["zero_u_devices"]), 1)
        self.assertEqual(len(result["unpositioned_devices"]), 0)

    def test_half_u_device_uses_one_half_slot(self):
        rack = {"id": 1, "u_height": 6, "starting_unit": 1}
        devices = [{
            "id": 12,
            "name": "PATCH-05U",
            "position": 2.5,
            "face": {"value": "front"},
            "device_type": {
                "id": 7,
                "model": "Patch 0.5U",
                "u_height": 0.5,
            },
        }]

        result = prepare_elevation(rack, devices, "front")

        self.assertEqual(result["used_units"], 0.5)
        self.assertEqual(result["visible_devices"][0]["_span"], 1)
        self.assertEqual(result["visible_devices"][0]["_position"], 2.5)

    def test_full_depth_device_conflicts_with_rear_device(self):
        rack = {"id": 1, "u_height": 10}
        devices = [
            {
                "id": 20,
                "name": "FULL-DEPTH",
                "position": 4,
                "face": {"value": "front"},
                "device_type": {
                    "id": 8,
                    "model": "Chassis",
                    "u_height": 1,
                    "is_full_depth": True,
                },
            },
            {
                "id": 21,
                "name": "REAR-DEVICE",
                "position": 4,
                "face": {"value": "rear"},
                "device_type": {
                    "id": 9,
                    "model": "Rear appliance",
                    "u_height": 1,
                    "is_full_depth": False,
                },
            },
        ]

        result = prepare_elevation(rack, devices, "rear")

        self.assertTrue(result["has_conflicts"])
        self.assertTrue(all(
            device["_has_conflict"]
            for device in result["visible_devices"]
        ))
        self.assertEqual(result["used_units"], 1.0)

    def test_device_type_images_use_authenticated_proxy(self):
        rack = {"id": 1, "u_height": 10}
        devices = [{
            "id": 30,
            "name": "SWITCH-01",
            "position": 1,
            "face": {"value": "front"},
            "device_type": {
                "id": 77,
                "model": "Switch",
                "u_height": 1,
                "front_image": "/media/device-type-images/front.png",
                "rear_image": "/media/device-type-images/rear.png",
            },
        }]

        result = prepare_elevation(rack, devices, "front")
        device = result["visible_devices"][0]

        self.assertEqual(
            device["_front_image"],
            "/media/device-types/77/front",
        )
        self.assertEqual(
            device["_rear_image"],
            "/media/device-types/77/rear",
        )

    def test_topology_groups_racks_by_site(self):
        sites = [{"id": 1, "name": "Samaná"}]
        racks = [{
            "id": 100,
            "name": "SMN01",
            "u_height": 42,
            "site": {"id": 1, "name": "Samaná"},
            "status": {"label": "Active"},
        }]
        devices = [{
            "id": 40,
            "name": "OLT-SMN-01",
            "rack": {"id": 100, "name": "SMN01"},
            "position": 20,
            "face": {"value": "front"},
            "device_type": {
                "id": 88,
                "model": "C600",
                "u_height": 6,
            },
        }]

        result = prepare_topology(
            sites=sites,
            racks=racks,
            devices=devices,
        )

        self.assertEqual(result["topology_summary"]["sites"], 1)
        self.assertEqual(result["topology_summary"]["racks"], 1)
        self.assertEqual(result["topology_summary"]["devices"], 1)
        self.assertEqual(result["topology_summary"]["used_units"], 6.0)
        self.assertEqual(result["topology_sites"][0]["name"], "Samaná")

    def test_format_u_preserves_half_units(self):
        self.assertEqual(format_u(2), "2")
        self.assertEqual(format_u(2.5), "2.5")


if __name__ == "__main__":
    unittest.main()
