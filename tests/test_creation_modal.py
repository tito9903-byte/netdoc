from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


class CreationModalTests(unittest.TestCase):
    @staticmethod
    def login(client: TestClient) -> None:
        response = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/devices",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    @staticmethod
    def devices_patches():
        return (
            patch(
                "app.main.NetBoxClient.list_devices",
                new_callable=AsyncMock,
                return_value={"count": 0, "results": []},
            ),
            patch(
                "app.main.NetBoxClient.list_sites",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.main.NetBoxClient.list_device_roles",
                new_callable=AsyncMock,
                return_value=[],
            ),
        )

    def test_devices_page_has_contextual_create_button_and_no_quick_actions(self):
        list_devices, list_sites, list_roles = self.devices_patches()
        with list_devices, list_sites, list_roles, TestClient(app) as client:
            self.login(client)
            response = client.get("/devices")

        self.assertEqual(200, response.status_code)
        self.assertIn("Crear dispositivo", response.text)
        self.assertIn('href="/devices/actions/new"', response.text)
        self.assertIn("data-create-modal", response.text)
        self.assertIn("data-create-modal-root", response.text)
        self.assertNotIn("Acciones rápidas", response.text)

    def test_modal_mode_hides_parent_modal_shell(self):
        list_devices, list_sites, list_roles = self.devices_patches()
        with list_devices, list_sites, list_roles, TestClient(app) as client:
            self.login(client)
            response = client.get("/devices?modal=1")

        self.assertEqual(200, response.status_code)
        self.assertIn('<body class="modal-page">', response.text)
        self.assertNotIn("data-create-modal-root", response.text)
        self.assertNotIn("js/create_modal.js", response.text)

    def test_create_modal_assets_are_available(self):
        with TestClient(app) as client:
            css = client.get("/static/css/create_modal.css")
            javascript = client.get("/static/js/create_modal.js")

        self.assertEqual(200, css.status_code)
        self.assertIn(".create-modal-dialog", css.text)
        self.assertEqual(200, javascript.status_code)
        self.assertIn("createPathPattern", javascript.text)
        self.assertIn("data-create-modal", javascript.text)


if __name__ == "__main__":
    unittest.main()
