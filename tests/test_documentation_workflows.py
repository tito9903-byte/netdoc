from __future__ import annotations

import unittest

from app.services.connection_service import ConnectionService
from app.services.device_type_service import (
    DeviceTypeServiceError,
    build_interface_names,
    slugify,
)
from app.services.ipam_service import (
    build_occupancy_indexes,
    calculate_pool_availability,
    prefix_capacity,
    scope_label,
    utilization_percentage,
)


class DocumentationWorkflowTests(unittest.TestCase):
    def test_build_interface_names_supports_zero_padding(self):
        self.assertEqual(
            build_interface_names(
                "Gi1/0/{n:02}",
                start=1,
                count=3,
            ),
            ["Gi1/0/01", "Gi1/0/02", "Gi1/0/03"],
        )

    def test_build_interface_names_rejects_missing_counter(self):
        with self.assertRaises(DeviceTypeServiceError):
            build_interface_names(
                "GigabitEthernet0/1",
                start=1,
                count=4,
            )

    def test_build_interface_names_limits_large_batches(self):
        with self.assertRaises(DeviceTypeServiceError):
            build_interface_names(
                "xe-0/0/{n}",
                start=0,
                count=257,
            )

    def test_slugify_normalizes_model_name(self):
        self.assertEqual(
            slugify("ZTE C600 – Línea Óptica"),
            "zte-c600-linea-optica",
        )

    def test_pool_capacity_includes_all_ipv4_addresses(self):
        self.assertEqual(
            prefix_capacity({"prefix": "192.0.2.0/30", "is_pool": True}),
            4,
        )

    def test_non_pool_ipv4_capacity_excludes_network_and_broadcast(self):
        self.assertEqual(
            prefix_capacity({"prefix": "192.0.2.0/30", "is_pool": False}),
            2,
        )

    def test_scope_label_prefers_nested_scope(self):
        self.assertEqual(
            scope_label({"scope": {"display": "Samaná"}}),
            "Samaná",
        )

    def test_utilization_percentage_accepts_number_string_and_mapping(self):
        self.assertEqual(utilization_percentage(73), 73.0)
        self.assertEqual(utilization_percentage("81.5%"), 81.5)
        self.assertEqual(
            utilization_percentage({"value": "100"}),
            100.0,
        )

    def test_utilization_percentage_is_bounded(self):
        self.assertEqual(utilization_percentage(140), 100.0)
        self.assertEqual(utilization_percentage(-10), 0.0)
        self.assertIsNone(utilization_percentage("sin dato"))

    def test_pool_availability_combines_addresses_ranges_and_child_prefixes(self):
        pool = {
            "id": 1,
            "prefix": "192.0.2.0/29",
            "is_pool": True,
            "vrf": {"id": 3},
        }
        prefixes = [
            pool,
            {
                "id": 2,
                "prefix": "192.0.2.6/31",
                "vrf": {"id": 3},
            },
        ]
        addresses = [
            {"address": "192.0.2.1/29", "vrf": {"id": 3}},
            {"address": "192.0.2.2/29", "vrf": {"id": 3}},
            {"address": "192.0.2.3/29", "vrf": {"id": 99}},
        ]
        ranges = [
            {
                "start_address": "192.0.2.4/29",
                "end_address": "192.0.2.5/29",
                "vrf": {"id": 3},
                "mark_populated": True,
            }
        ]
        indexes = build_occupancy_indexes(
            ip_addresses=addresses,
            ip_ranges=ranges,
            prefixes=prefixes,
        )

        used, available, utilization = calculate_pool_availability(
            pool,
            address_intervals=indexes[0],
            reserved_ranges=indexes[1],
            prefix_intervals=indexes[2],
        )

        self.assertEqual(used, 6)
        self.assertEqual(available, 2)
        self.assertEqual(utilization, 75.0)

    def test_unmarked_range_does_not_reserve_all_addresses(self):
        pool = {
            "id": 1,
            "prefix": "198.51.100.0/30",
            "is_pool": True,
        }
        indexes = build_occupancy_indexes(
            ip_addresses=[{"address": "198.51.100.1/30", "vrf": None}],
            ip_ranges=[{
                "start_address": "198.51.100.0/30",
                "end_address": "198.51.100.3/30",
                "vrf": None,
                "mark_populated": False,
                "mark_utilized": False,
            }],
            prefixes=[pool],
        )

        used, available, utilization = calculate_pool_availability(
            pool,
            address_intervals=indexes[0],
            reserved_ranges=indexes[1],
            prefix_intervals=indexes[2],
        )

        self.assertEqual(used, 1)
        self.assertEqual(available, 3)
        self.assertEqual(utilization, 25.0)

    def test_mark_utilized_pool_is_full(self):
        pool = {
            "id": 1,
            "prefix": "203.0.113.0/30",
            "is_pool": True,
            "mark_utilized": True,
        }
        indexes = build_occupancy_indexes(
            ip_addresses=[],
            ip_ranges=[],
            prefixes=[pool],
        )

        used, available, utilization = calculate_pool_availability(
            pool,
            address_intervals=indexes[0],
            reserved_ranges=indexes[1],
            prefix_intervals=indexes[2],
        )

        self.assertEqual(used, 4)
        self.assertEqual(available, 0)
        self.assertEqual(utilization, 100.0)

    def test_cable_endpoint_label_combines_device_and_interface(self):
        label = ConnectionService._object_label({
            "device": {"name": "OLT-SMN-01"},
            "name": "gpon-olt_1/2/6",
        })
        self.assertEqual(label, "OLT-SMN-01 · gpon-olt_1/2/6")

    def test_cable_choices_are_localized(self):
        self.assertEqual(
            ConnectionService._translated_choice(
                {"value": "connected", "label": "Connected"},
                ConnectionService.STATUS_LABELS,
            ),
            "Conectado",
        )
        self.assertEqual(
            ConnectionService._translated_choice(
                {"value": "smf-os2", "label": "Single-mode Fiber (OS2)"},
                ConnectionService.CABLE_TYPE_LABELS,
            ),
            "Fibra monomodo OS2",
        )


if __name__ == "__main__":
    unittest.main()
