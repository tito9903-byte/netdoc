from __future__ import annotations

from pathlib import Path
import unittest


class InterfaceWorkspaceVisualPolishTests(unittest.TestCase):
    def test_global_modal_styles_load_workspace_and_ip_editor_overrides(self):
        stylesheet = Path("app/static/css/create_modal.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("interface_workspace_polish.css", stylesheet)
        self.assertIn("interface_ip_editor.css", stylesheet)

    def test_workspace_polish_compacts_and_reorganizes_the_form(self):
        stylesheet = Path(
            "app/static/css/interface_workspace_polish.css"
        ).read_text(encoding="utf-8")

        self.assertIn("max-width: 1320px", stylesheet)
        self.assertIn("grid-template-columns: repeat(12", stylesheet)
        self.assertIn(".interface-workspace-addresses", stylesheet)
        self.assertIn(".interface-workspace-toggle-card", stylesheet)
        self.assertIn("@media (max-width: 760px)", stylesheet)

    def test_ip_editor_uses_numbered_sections_and_compact_primary_switch(self):
        template = Path("app/templates/device_interface_ip_form.html").read_text(
            encoding="utf-8"
        )
        stylesheet = Path("app/static/css/interface_ip_editor.css").read_text(
            encoding="utf-8"
        )

        for marker in (
            "interface-ip-editor-page",
            "interface-ip-editor-context",
            "interface-ip-editor-step",
            "interface-ip-editor-grid",
            "interface-ip-editor-primary",
            "interface-ip-editor-actions",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, template)
                self.assertIn(f".{marker}", stylesheet)

        self.assertIn('name="address"', template)
        self.assertIn('name="status"', template)
        self.assertIn('name="role"', template)
        self.assertIn('name="vrf_id"', template)
        self.assertIn('name="dns_name"', template)
        self.assertIn('name="description"', template)
        self.assertIn('name="make_primary"', template)
        self.assertIn("body.modal-page .interface-ip-editor-page", stylesheet)


if __name__ == "__main__":
    unittest.main()
