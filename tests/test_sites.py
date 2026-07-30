from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, patch

from argon2 import PasswordHasher
from fastapi.testclient import TestClient


os.environ.setdefault("NETBOX_URL", "https://netbox.invalid")
os.environ.setdefault("NETBOX_TOKEN", "test-token")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("AdminPassword123"),
)

from app.main import app
from app.services.site_service import validate_site_form


SITE = {
    "id": 12,
    "name": "San Francisco de Macorís",
    "slug": "sfm-core",
    "status": {"value": "active", "label": "Activo"},
    "facility": "TEL-SFM-01",
    "physical_address": "San Francisco de Macorís",
    "rack_count": 3,
    "device_count": 20,
}
CHOICES = {
    "statuses": [
        {"value": "active", "label": "Activo"},
        {"value": "retired", "label": "Retirado"},
    ]
}


class SiteValidationTests(unittest.TestCase):
    def test_validates_slug_and_coordinates(self):
        errors = validate_site_form({
            "name": "",
            "slug": "SFM CORE",
            "latitude": "100",
            "longitude": "invalid",
        })
        self.assertEqual(4, len(errors))

    def test_accepts_valid_site(self):
        self.assertEqual([], validate_site_form({
            "name": "SFM",
            "slug": "sfm-core",
            "latitude": "19.3",
            "longitude": "-70.25",
        }))


class SiteRouteTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/sites",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch(
        "app.routers.sites.SiteService.site_choices",
        new_callable=AsyncMock,
        return_value=CHOICES,
    )
    @patch(
        "app.routers.sites.SiteService.list_sites",
        new_callable=AsyncMock,
        return_value=[SITE],
    )
    def test_site_catalog_renders(self, _sites, _choices):
        response = self.client.get("/sites")
        self.assertEqual(200, response.status_code)
        self.assertIn("San Francisco de Macorís", response.text)
        self.assertIn("Crear site", response.text)
        self.assertIn("TEL-SFM-01", response.text)

    @patch(
        "app.routers.sites.SiteService.site_choices",
        new_callable=AsyncMock,
        return_value=CHOICES,
    )
    def test_new_site_form_renders(self, _choices):
        response = self.client.get("/sites/actions/new")
        self.assertEqual(200, response.status_code)
        self.assertIn("Información oficial almacenada en NetBox", response.text)
        self.assertIn('name="slug"', response.text)

    @patch(
        "app.routers.sites.SiteService.save_site",
        new_callable=AsyncMock,
    )
    @patch(
        "app.routers.sites.SiteService.site_choices",
        new_callable=AsyncMock,
        return_value=CHOICES,
    )
    def test_create_is_blocked_in_read_only_mode(
        self,
        _choices,
        save_site,
    ):
        response = self.client.post(
            "/sites/actions/new",
            data={
                "csrf": "invalid",
                "name": "SFM",
                "slug": "sfm",
                "status": "active",
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertIn("escritura está desactivada", response.text)
        save_site.assert_not_awaited()

    def test_sites_require_authentication(self):
        self.client.post("/logout")
        response = self.client.get("/sites", follow_redirects=False)
        self.assertEqual(303, response.status_code)
        self.assertIn("/login", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
