from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MobileLayoutTests(unittest.TestCase):
    def test_base_declares_mobile_viewport_and_menu_control(self):
        template = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")

        self.assertIn('name="viewport"', template)
        self.assertIn('width=device-width, initial-scale=1.0', template)
        self.assertIn('id="menuToggle"', template)
        self.assertIn('aria-controls="sidebar"', template)

    def test_mobile_css_has_drawer_backdrop_and_touch_safe_controls(self):
        css = (ROOT / "app/static/css/navigation.css").read_text(encoding="utf-8")

        self.assertIn("body.mobile-nav-open", css)
        self.assertIn("body.mobile-nav-open::after", css)
        self.assertIn("font-size: 16px", css)
        self.assertIn("-webkit-overflow-scrolling: touch", css)
        self.assertIn("grid-template-columns: repeat(2", css)

    def test_javascript_locks_background_when_mobile_menu_opens(self):
        script = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")

        self.assertIn('"mobile-nav-open"', script)
        self.assertIn('mobileNavQuery.addEventListener("change"', script)
        self.assertIn('open ? "Cerrar menú" : "Abrir menú"', script)


if __name__ == "__main__":
    unittest.main()
