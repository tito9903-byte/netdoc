from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RackWorkspaceLayoutTests(unittest.TestCase):
    def test_template_places_inventory_inside_workspace_side_column(self):
        template = (
            ROOT / "app/templates/rack_detail.html"
        ).read_text(encoding="utf-8")

        self.assertIn('class="rack-workspace-grid"', template)
        self.assertIn('class="rack-workspace-side"', template)
        self.assertIn('rack-inventory-panel-embedded', template)
        self.assertIn('data-rack-inventory-search', template)
        self.assertIn('data-rack-inventory-row', template)
        self.assertIn('data-label="IP principal"', template)
        self.assertIn("{{ devices | length }}", template)

    def test_workspace_styles_describe_desktop_and_mobile_layouts(self):
        stylesheet = (
            ROOT / "app/static/css/rack_workspace.css"
        ).read_text(encoding="utf-8")

        self.assertIn("grid-template-columns: minmax(540px, 0.9fr)", stylesheet)
        self.assertIn("position: sticky", stylesheet)
        self.assertIn(".rack-inventory-table td::before", stylesheet)
        self.assertIn("content: attr(data-label)", stylesheet)
        self.assertIn("@media (max-width: 760px)", stylesheet)

    def test_inventory_search_filters_rows_and_updates_counter(self):
        javascript = (
            ROOT / "app/static/js/rack_inventory.js"
        ).read_text(encoding="utf-8")

        self.assertIn("data-rack-inventory-search", javascript)
        self.assertIn("row.hidden = !matches", javascript)
        self.assertIn("visible", javascript)
        self.assertIn("normalize(\"NFD\")", javascript)

    def test_detail_scale_control_updates_the_rack_and_persists_selection(self):
        javascript = (
            ROOT / "app/static/js/topology.js"
        ).read_text(encoding="utf-8")

        self.assertIn('querySelectorAll("[data-topology-scale]")', javascript)
        self.assertIn("const applyScale = (scale) =>", javascript)
        self.assertIn("root.dataset.scale = selected", javascript)
        self.assertIn("scaleButtons.forEach((button) =>", javascript)
        self.assertIn("applyScale(button.dataset.topologyScale", javascript)
        self.assertIn('localStorage.setItem("netdocRack3dScale"', javascript)
        self.assertIn('localStorage.getItem("netdocRack3dScale")', javascript)

        template = (
            ROOT / "app/templates/rack_detail.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "js/topology.js') }}?v=20260730-rack-scale-1",
            template,
        )

    def test_documentation_covers_workspace_and_mobile_cards(self):
        documentation = (
            ROOT / "docs/RACKS_AND_DEVICE_IMAGES.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Espacio de trabajo del rack", documentation)
        self.assertIn("buscar por nombre, modelo, dirección IP", documentation)
        self.assertIn("se transforma en tarjetas por dispositivo", documentation)


if __name__ == "__main__":
    unittest.main()
