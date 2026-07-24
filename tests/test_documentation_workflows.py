from __future__ import annotations

import unittest

from app.services.device_type_service import (
    DeviceTypeServiceError,
    build_interface_names,
    slugify,
)
from app.services.ipam_service import prefix_capacity, scope_label


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
        self.assertEqual(slugify("ZTE C600 – Línea Óptica"), "zte-c600-linea-optica")

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


if __name__ == "__main__":
    unittest.main()
