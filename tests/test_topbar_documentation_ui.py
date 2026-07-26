from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TopbarDocumentationUITests(unittest.TestCase):
    def test_topbar_uses_professional_identity_structure(self):
        template = (ROOT / "app/templates/base.html").read_text(
            encoding="utf-8"
        )
        css = (ROOT / "app/static/css/topbar_professional.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("topbar_professional.css", template)
        self.assertIn("environment-indicator", template)
        self.assertIn("current-user-meta", template)
        self.assertIn("logout-icon", template)
        self.assertIn(".auth-topbar-actions", css)
        self.assertIn("@media (max-width: 760px)", css)

    def test_sidebar_removes_separate_interface_template_entry(self):
        template = (ROOT / "app/templates/base.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("Plantillas de puertos", template)
        self.assertNotIn('href="/interface-templates"', template)
        self.assertIn("Modelos de equipos", template)

    def test_model_pages_are_documentation_centered_and_mobile_ready(self):
        catalog = (ROOT / "app/templates/device_types.html").read_text(
            encoding="utf-8"
        )
        detail = (ROOT / "app/templates/device_type_detail.html").read_text(
            encoding="utf-8"
        )
        css = (ROOT / "app/static/css/device_components.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("Listado de modelos documentados", catalog)
        self.assertIn("Puertos, interfaces y componentes", detail)
        self.assertIn("kind=front_port", detail)
        self.assertIn("kind=rear_port", detail)
        self.assertIn("kind=power_outlet", detail)
        self.assertIn("@media (max-width: 700px)", css)


if __name__ == "__main__":
    unittest.main()
