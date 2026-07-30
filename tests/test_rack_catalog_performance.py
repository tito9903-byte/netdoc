from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.services.rack_service import RackService


SITES = [
    {
        "id": 10,
        "name": "Blanco Arriba",
        "display": "Blanco Arriba",
    }
]

RACKS = [
    {
        "id": 1,
        "name": "HCO101",
        "u_height": 16,
        "device_count": 9,
        "site": {"id": 10, "name": "Blanco Arriba"},
        "location": {"id": 20, "name": "Sala principal"},
        "status": {"value": "active", "label": "Activo"},
        "width": {"value": 19, "label": "19 pulgadas"},
    }
]


class RackCatalogPerformanceTests(unittest.TestCase):
    @staticmethod
    def login(client: TestClient) -> None:
        response = client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/racks",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    @patch(
        "app.routers.racks.RackService.list_devices",
        new_callable=AsyncMock,
    )
    @patch(
        "app.routers.racks.RackService.list_racks",
        new_callable=AsyncMock,
        return_value=RACKS,
    )
    @patch(
        "app.routers.racks.RackService.list_sites",
        new_callable=AsyncMock,
        return_value=SITES,
    )
    def test_catalog_does_not_load_devices_or_device_types(
        self,
        list_sites,
        list_racks,
        list_devices,
    ):
        with TestClient(app) as client:
            self.login(client)
            response = client.get("/racks")

        self.assertEqual(200, response.status_code)
        list_sites.assert_awaited_once()
        list_racks.assert_awaited_once_with(site_id=None, query="")
        list_devices.assert_not_awaited()
        self.assertIn("HCO101", response.text)
        self.assertIn("Blanco Arriba", response.text)
        self.assertRegex(response.text, r"<strong>\s*9\s*</strong>")


class RackServiceConnectionReuseTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_requests_share_one_http_client(self):
        response = httpx.Response(
            200,
            json={"results": [], "next": None},
            request=httpx.Request("GET", "https://netbox.test/api/"),
        )

        async with RackService() as service:
            client = service._client
            assert client is not None

            with patch.object(
                client,
                "get",
                new_callable=AsyncMock,
                return_value=response,
            ) as get:
                await asyncio.gather(
                    service.list_sites(),
                    service.list_racks(),
                )

            self.assertIs(client, service._client)
            self.assertEqual(2, get.await_count)


if __name__ == "__main__":
    unittest.main()
