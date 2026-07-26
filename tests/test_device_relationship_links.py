from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


DEVICE_WITH_RELATIONSHIPS = {
    "id": 214,
    "name": "MKT-NATBOX-SPR-01",
    "display": "MKT-NATBOX-SPR-01",
    "status": {"value": "active", "label": "Activo"},
    "serial": "D4F10CDCDFD27",
    "position": 27,
    "face": {"value": "front", "label": "Frontal"},
    "device_type": {
        "id": 501,
        "display": "CCR2004-1G-12S+2XS",
        "model": "CCR2004-1G-12S+2XS",
        "manufacturer": {
            "id": 44,
            "display": "MikroTik",
            "name": "MikroTik",
        },
    },
    "rack": {
        "id": 4,
        "display": "1NSPR",
        "name": "1NSPR",
    },
    "site": {
        "id": 10,
        "display": "SPIRIT OF TERRENAS",
    },
    "role": {"display": "Access"},
}


class DeviceRelationshipLinkTests(unittest.TestCase):
    @staticmethod
    def login(client: TestClient) -> None:
        response = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/devices/214",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    @patch(
        "app.main.NetBoxClient.get_device_interfaces",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.get_device",
        new_callable=AsyncMock,
        return_value=DEVICE_WITH_RELATIONSHIPS,
    )
    def test_device_detail_links_to_model_and_rack(
        self,
        _get_device,
        _get_interfaces,
    ):
        with TestClient(app) as client:
            self.login(client)
            response = client.get("/devices/214")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            2,
            response.text.count('href="/device-types/501"'),
        )
        self.assertIn('href="/racks/4"', response.text)
        self.assertIn("CCR2004-1G-12S+2XS", response.text)
        self.assertIn("1NSPR", response.text)

    @patch(
        "app.main.NetBoxClient.get_device_interfaces",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.get_device",
        new_callable=AsyncMock,
        return_value={
            **DEVICE_WITH_RELATIONSHIPS,
            "device_type": {
                "display": "Modelo sin identificador",
                "manufacturer": {"display": "MikroTik"},
            },
            "rack": {"display": "Rack sin identificador"},
        },
    )
    def test_device_detail_keeps_plain_text_without_relation_ids(
        self,
        _get_device,
        _get_interfaces,
    ):
        with TestClient(app) as client:
            self.login(client)
            response = client.get("/devices/214")

        self.assertEqual(200, response.status_code)
        self.assertNotIn('href="/device-types/', response.text)
        self.assertNotIn('href="/racks/', response.text)
        self.assertIn("Modelo sin identificador", response.text)
        self.assertIn("Rack sin identificador", response.text)


if __name__ == "__main__":
    unittest.main()
