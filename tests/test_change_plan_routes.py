from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


INTERFACE_A = {
    "id": 10,
    "name": "Ethernet1",
    "device": {"name": "CORE-01"},
    "enabled": True,
    "cable": None,
    "connected_endpoints": [],
}
INTERFACE_B = {
    "id": 20,
    "name": "uplink-1",
    "device": {"name": "OLT-SMN-01"},
    "enabled": True,
    "cable": None,
    "connected_endpoints": [],
}


class ChangePlanRouteTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/connections",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch(
        "app.routers.change_plans.ConnectionService.get_interface",
        new_callable=AsyncMock,
    )
    def test_preview_returns_immutable_cable_plan(self, get_interface):
        get_interface.side_effect = [INTERFACE_A, INTERFACE_B]

        response = self.client.post(
            "/api/change-plans/cable",
            json={
                "interface_a_id": 10,
                "interface_b_id": 20,
                "cable_type": "smf-os2",
                "label": "FO-SMN-001",
                "length": "125",
                "length_unit": "m",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "preview")
        self.assertFalse(payload["write_enabled"])
        self.assertTrue(payload["plan"]["executable"])
        self.assertTrue(
            payload["plan"]["confirmation_phrase"].startswith("CONFIRMAR ")
        )
        step = payload["plan"]["steps"][0]
        self.assertEqual(step["endpoint"], "/api/dcim/cables/")
        self.assertEqual(
            step["payload"]["a_terminations"][0]["object_id"],
            10,
        )
        self.assertEqual(
            step["payload"]["b_terminations"][0]["object_id"],
            20,
        )

    def test_preview_rejects_same_interface(self):
        response = self.client.post(
            "/api/change-plans/cable",
            json={
                "interface_a_id": 10,
                "interface_b_id": 10,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_preview_requires_authentication(self):
        self.client.post("/logout")
        response = self.client.post(
            "/api/change-plans/cable",
            json={
                "interface_a_id": 10,
                "interface_b_id": 20,
            },
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
