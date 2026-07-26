from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


RACK = {
    "id": 1,
    "name": "HCO101",
    "u_height": 16,
    "starting_unit": 1,
    "site": {"id": 10, "name": "Blanco Arriba"},
    "location": None,
    "status": {"value": "active", "label": "Activo"},
    "width": {"value": 19, "label": "19 pulgadas"},
}

DEVICES = [
    {
        "id": 100,
        "name": "FDP TO-GH",
        "position": 15,
        "face": {"value": "front"},
        "status": {"value": "active", "label": "Activo"},
        "device_type": {
            "id": 200,
            "model": "FDP-24",
            "u_height": 1,
            "is_full_depth": False,
        },
    }
]


class RackThreeDimensionalOnlyTests(unittest.TestCase):
    @staticmethod
    def login(client: TestClient) -> None:
        response = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/racks/1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    def render(self, path: str):
        with (
            patch(
                "app.routers.racks.RackService.get_rack",
                new_callable=AsyncMock,
                return_value=RACK,
            ),
            patch(
                "app.routers.racks.RackService.list_rack_devices",
                new_callable=AsyncMock,
                return_value=DEVICES,
            ),
            TestClient(app) as client,
        ):
            self.login(client)
            return client.get(path)

    def test_rack_detail_defaults_to_three_dimensional_view(self):
        response = self.render("/racks/1")

        self.assertEqual(200, response.status_code)
        self.assertIn("Vista 3D estilo datacenter", response.text)
        self.assertIn("data-topology-root", response.text)
        self.assertIn("Vista 3D basada en posición", response.text)
        self.assertNotIn("Vista 2D", response.text)
        self.assertNotIn("Elevación 2D del rack", response.text)

    def test_legacy_two_dimensional_query_still_renders_three_dimensional_view(self):
        response = self.render("/racks/1?view=2d&face=rear")

        self.assertEqual(200, response.status_code)
        self.assertIn("Vista 3D estilo datacenter", response.text)
        self.assertIn('data-face="rear"', response.text)
        self.assertNotIn("Vista 2D", response.text)
        self.assertNotIn("Elevación 2D del rack", response.text)


if __name__ == "__main__":
    unittest.main()
