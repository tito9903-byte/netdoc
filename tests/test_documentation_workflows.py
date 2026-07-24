from __future__ import annotations

import unittest

from app.services.connection_service import ConnectionService
from app.services.device_type_service import (
    DeviceTypeServiceError,
    build_interface_names,
    slugify,
)
from app.services.ipam_service import (
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
