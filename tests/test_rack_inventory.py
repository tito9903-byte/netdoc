from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RackInventoryTests(unittest.TestCase):
    def test_inventory_lists_operational_device_fields(self):
        template = (
            ROOT / "app/templates/rack_detail.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Inventario operativo", template)
        self.assertIn("Equipos instalados", template)
        self.assertIn("Número de serie", template)
        self.assertIn("IP principal", template)
        self.assertIn('device.get("primary_ip4")', template)
        self.assertIn('device.get("primary_ip6")', template)
        self.assertIn("Sin asignar", template)
        self.assertIn("Abrir", template)

    def test_inventory_preserves_position_and_height_sources(self):
        template = (
            ROOT / "app/templates/rack_detail.html"
        ).read_text(encoding="utf-8")
        presentation = (
            ROOT / "app/services/rack_presentation.py"
        ).read_text(encoding="utf-8")

        self.assertIn("device.get('_position_label')", template)
        self.assertIn("device.get('_face')", template)
        self.assertIn("device.get('_u_height_label')", template)
        self.assertIn('raw_device.get("position")', presentation)
        self.assertIn('device_type.get("u_height")', presentation)


if __name__ == "__main__":
    unittest.main()
