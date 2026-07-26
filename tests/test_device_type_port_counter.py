from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeviceTypePortCounterTests(unittest.TestCase):
    def test_counter_reads_component_cards_and_avoids_patch_panel_double_count(self):
        javascript = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")

        self.assertIn("function showDocumentedPortCount()", javascript)
        self.assertIn('counts.get("front_port")', javascript)
        self.assertIn('counts.get("rear_port")', javascript)
        self.assertIn("Math.max(", javascript)
        self.assertIn("hardware-section-nav-count", javascript)
        self.assertIn("puertos documentados", javascript)

    def test_counter_style_is_available_on_model_detail(self):
        stylesheet = (
            ROOT / "app/static/css/device_components.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".hardware-section-nav-count", stylesheet)
        self.assertIn('.hardware-section-nav a[href="#components"]', stylesheet)

    def test_documentation_explains_counter_semantics(self):
        documentation = (
            ROOT / "docs/modelos-y-componentes.md"
        ).read_text(encoding="utf-8")

        self.assertIn("contador junto a **Puertos y componentes**", documentation)
        self.assertIn("no contar dos veces el mismo canal físico", documentation)


if __name__ == "__main__":
    unittest.main()
