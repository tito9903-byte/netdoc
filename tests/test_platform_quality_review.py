from __future__ import annotations

from pathlib import Path
import unittest


class PlatformQualityReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.polish = Path(
            "app/static/css/platform_quality_polish.css"
        ).read_text(encoding="utf-8")
        self.modal_css = Path(
            "app/static/css/create_modal.css"
        ).read_text(encoding="utf-8")
        self.modal_js = Path(
            "app/static/js/create_modal.js"
        ).read_text(encoding="utf-8")

    def test_global_polish_is_loaded_from_the_shared_modal_stylesheet(self):
        self.assertIn(
            'platform_quality_polish.css?v=20260729-video-review-1',
            self.modal_css,
        )

    def test_modal_uses_adaptive_height_instead_of_the_old_fixed_canvas(self):
        self.assertIn("--create-modal-height", self.modal_css)
        self.assertIn('data-size="compact"', self.modal_css)
        self.assertIn('data-size="wide"', self.modal_css)
        self.assertNotIn("height: min(880px", self.modal_css)

        self.assertIn("fitDialogToContent", self.modal_js)
        self.assertIn("childDocumentHeight", self.modal_js)
        self.assertIn("ResizeObserver", self.modal_js)
        self.assertIn("modalSizeFor", self.modal_js)
        self.assertIn('"--create-modal-height"', self.modal_js)

    def test_short_admin_forms_use_the_full_available_modal_width(self):
        self.assertIn(
            ".admin-form-grid > .admin-panel:only-child",
            self.polish,
        )
        self.assertIn(
            "body.modal-page .admin-form-grid",
            self.polish,
        )
        self.assertIn("grid-template-columns: 1fr", self.polish)

    def test_device_creation_is_compacted_into_a_two_column_modal_workflow(self):
        self.assertIn(
            "body.modal-page .create-device-form",
            self.polish,
        )
        self.assertIn(
            "grid-template-columns: repeat(2, minmax(0, 1fr))",
            self.polish,
        )
        self.assertIn(
            ".create-device-form > .create-submit-bar",
            self.polish,
        )

    def test_tables_forms_navigation_and_mobile_layout_receive_quality_rules(self):
        for expected in (
            "html body tbody tr:hover",
            "font-size: 12.5px",
            "html body .nav-subitem.active",
            "html body input:not([type=\"checkbox\"])",
            "@media (max-width: 700px)",
            "html body .profile-summary",
            "html body .role-card",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.polish)


if __name__ == "__main__":
    unittest.main()
