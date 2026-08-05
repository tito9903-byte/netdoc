from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
import re
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx

from app.core.auth import PermissionMiddleware
from app.main import app
from app.routers import connections as connections_router
from app.services.connection_service import ConnectionService


SITES = [
    {
        "id": 10,
        "name": "Samaná",
        "display": "Samaná",
    }
]

CHOICES = {
    "types": [
        {"value": "smf-os2", "label": "Fibra monomodo OS2"},
    ],
    "statuses": [
        {"value": "connected", "label": "Conectado"},
    ],
    "length_units": [
        {"value": "m", "label": "m"},
    ],
}

INTERFACES = [
    {
        "id": 11,
        "name": "Ethernet1",
        "device": {"name": "CORE-01"},
        "cable": None,
        "connected_endpoints": [],
    },
    {
        "id": 21,
        "name": "xgei-1/1/1",
        "device": {"name": "OLT-01"},
        "cable": None,
        "connected_endpoints": [],
    },
    {
        "id": 12,
        "name": "Ethernet2",
        "device": {"name": "CORE-01"},
        "cable": None,
        "connected_endpoints": [],
    },
    {
        "id": 22,
        "name": "xgei-1/1/2",
        "device": {"name": "OLT-01"},
        "cable": None,
        "connected_endpoints": [],
    },
]


class ConnectionRoutePerformanceTests(unittest.TestCase):
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
        self.assertEqual(303, response.status_code)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch(
        "app.routers.connections.ConnectionService.list_recent_cables",
        new_callable=AsyncMock,
    )
    @patch(
        "app.routers.connections.ConnectionService.get_cable_choices",
        new_callable=AsyncMock,
    )
    @patch(
        "app.routers.connections.ConnectionService.list_sites",
        new_callable=AsyncMock,
    )
    def test_page_renders_without_waiting_for_netbox(
        self,
        list_sites,
        get_cable_choices,
        list_recent_cables,
    ):
        response = self.client.get("/connections")

        self.assertEqual(200, response.status_code)
        list_sites.assert_not_awaited()
        get_cable_choices.assert_not_awaited()
        list_recent_cables.assert_not_awaited()
        self.assertIn("Nuevas conexiones", response.text)
        self.assertIn("Agregar conexión", response.text)
        self.assertIn('id="connectionRows"', response.text)
        self.assertIn(
            "/api/connections/recent",
            Path("app/static/js/connections.js").read_text(
                encoding="utf-8",
            ),
        )

    @patch(
        "app.routers.connections.ConnectionService.get_cable_choices",
        new_callable=AsyncMock,
        return_value=CHOICES,
    )
    @patch(
        "app.routers.connections.ConnectionService.list_sites",
        new_callable=AsyncMock,
        return_value=SITES,
    )
    def test_bootstrap_loads_form_data_after_render(
        self,
        list_sites,
        get_cable_choices,
    ):
        response = self.client.get("/api/connections/bootstrap")

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["ok"])
        self.assertEqual("Samaná", response.json()["sites"][0]["name"])
        list_sites.assert_awaited_once()
        get_cable_choices.assert_awaited_once()

    @patch(
        "app.routers.connections.ConnectionService.list_recent_cables",
        new_callable=AsyncMock,
        return_value=[{"id": 90, "_a_label": "A", "_b_label": "B"}],
    )
    def test_recent_connections_use_a_lazy_endpoint(
        self,
        list_recent_cables,
    ):
        response = self.client.get("/api/connections/recent?limit=500")

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["count"])
        list_recent_cables.assert_awaited_once_with(50)

    def test_javascript_controls_rows_and_submits_the_batch(self):
        script = Path("app/static/js/connections.js").read_text(
            encoding="utf-8",
        )

        self.assertIn(
            'addRowButton.addEventListener("click", addConnectionRow)',
            script,
        )
        self.assertIn('form.addEventListener("submit", submitBatch)', script)
        self.assertIn('fetchJson("/api/connections/bulk"', script)
        self.assertIn("maximumRows = 50", script)
        self.assertNotIn('getElementById("interface_a")', script)


class ConnectionBatchRouteTests(unittest.TestCase):
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
        self.assertEqual(303, response.status_code)
        page = self.client.get("/connections")
        match = re.search(
            r'id="connectionCsrf"[^>]+value="([^"]+)"',
            page.text,
        )
        self.assertIsNotNone(match)
        self.csrf = match.group(1)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @staticmethod
    def payload(csrf: str) -> dict:
        return {
            "csrf": csrf,
            "connections": [
                {
                    "interface_a_id": 11,
                    "interface_b_id": 21,
                    "label": "FO-001",
                },
                {
                    "interface_a_id": 12,
                    "interface_b_id": 22,
                    "label": "FO-002",
                },
            ],
            "cable_type": "smf-os2",
            "status": "connected",
            "color": "#00c8d2",
            "length": "3",
            "length_unit": "m",
            "description": "Uplink óptico",
        }

    @patch(
        "app.routers.connections.ConnectionService.create_interface_cables",
        new_callable=AsyncMock,
        return_value=[{"id": 101}, {"id": 102}],
    )
    @patch(
        "app.routers.connections.ConnectionService.get_interface",
        new_callable=AsyncMock,
    )
    def test_batch_validates_then_creates_with_one_service_call(
        self,
        get_interface,
        create_interface_cables,
    ):
        get_interface.side_effect = INTERFACES

        with patch.object(
            connections_router.settings,
            "netbox_write_enabled",
            True,
        ):
            response = self.client.post(
                "/api/connections/bulk",
                json=self.payload(self.csrf),
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["created_count"])
        self.assertEqual([101, 102], response.json()["cable_ids"])
        self.assertEqual(4, get_interface.await_count)
        create_interface_cables.assert_awaited_once()
        call = create_interface_cables.await_args.kwargs
        self.assertEqual(2, len(call["connections"]))
        self.assertEqual(Decimal("3"), call["length"])

    @patch(
        "app.routers.connections.ConnectionService.get_interface",
        new_callable=AsyncMock,
    )
    def test_batch_rejects_a_repeated_interface_before_netbox(
        self,
        get_interface,
    ):
        payload = self.payload(self.csrf)
        payload["connections"][1]["interface_a_id"] = 11

        with patch.object(
            connections_router.settings,
            "netbox_write_enabled",
            True,
        ):
            response = self.client.post(
                "/api/connections/bulk",
                json=payload,
            )

        self.assertEqual(400, response.status_code)
        self.assertIn("no puede repetirse", response.json()["error"])
        get_interface.assert_not_awaited()

    def test_batch_requires_create_permission(self):
        self.assertEqual(
            "connections.create",
            PermissionMiddleware._required_permission(
                "/api/connections/bulk",
                "POST",
            ),
        )


class ConnectionServicePerformanceTests(
    unittest.IsolatedAsyncioTestCase,
):
    def test_bulk_validation_error_identifies_the_row(self):
        response = httpx.Response(
            400,
            json=[
                {},
                {"b_terminations": ["La interfaz ya está ocupada."]},
            ],
            request=httpx.Request("POST", "https://netbox.test/api/"),
        )

        message, details = ConnectionService._format_api_error(response)

        self.assertIn("Conexión 2", message)
        self.assertIn("ya está ocupada", message)
        self.assertIn("items", details)

    async def test_requests_share_one_http_client(self):
        response = httpx.Response(
            200,
            json={"results": [], "next": None},
            request=httpx.Request("GET", "https://netbox.test/api/"),
        )

        async with ConnectionService() as service:
            client = service._client
            assert client is not None

            with patch.object(
                client,
                "request",
                new_callable=AsyncMock,
                return_value=response,
            ) as request:
                await asyncio.gather(
                    service.list_sites(),
                    service.list_devices(10),
                )

            self.assertIs(client, service._client)
            self.assertEqual(2, request.await_count)

    async def test_recent_nested_terminations_need_no_extra_requests(self):
        cable = {
            "id": 90,
            "a_terminations": [{
                "object_type": "dcim.interface",
                "object_id": 11,
                "object": {
                    "device": {"name": "CORE-01"},
                    "name": "Ethernet1",
                },
            }],
            "b_terminations": [{
                "object_type": "dcim.interface",
                "object_id": 21,
                "object": {
                    "device": {"name": "OLT-01"},
                    "name": "xgei-1/1/1",
                },
            }],
            "type": {"value": "smf-os2", "label": "OS2"},
            "status": {"value": "connected", "label": "Connected"},
        }
        response = httpx.Response(
            200,
            json={"results": [cable], "next": None},
            request=httpx.Request("GET", "https://netbox.test/api/"),
        )

        async with ConnectionService() as service:
            client = service._client
            assert client is not None

            with patch.object(
                client,
                "request",
                new_callable=AsyncMock,
                return_value=response,
            ) as request:
                cables = await service.list_recent_cables()

        self.assertEqual(1, request.await_count)
        self.assertEqual("CORE-01 · Ethernet1", cables[0]["_a_label"])
        self.assertEqual("OLT-01 · xgei-1/1/1", cables[0]["_b_label"])

    async def test_bulk_creation_uses_one_netbox_post(self):
        response = httpx.Response(
            201,
            json=[{"id": 101}, {"id": 102}],
            request=httpx.Request("POST", "https://netbox.test/api/"),
        )

        async with ConnectionService() as service:
            client = service._client
            assert client is not None

            with patch.object(
                client,
                "request",
                new_callable=AsyncMock,
                return_value=response,
            ) as request:
                created = await service.create_interface_cables(
                    connections=[
                        {
                            "interface_a_id": 11,
                            "interface_b_id": 21,
                            "label": "FO-001",
                        },
                        {
                            "interface_a_id": 12,
                            "interface_b_id": 22,
                            "label": "FO-002",
                        },
                    ],
                    cable_type="smf-os2",
                    status="connected",
                    color="#00c8d2",
                    length=Decimal("3"),
                    length_unit="m",
                    description="Uplink óptico",
                    username="admin",
                )

        self.assertEqual([101, 102], [item["id"] for item in created])
        request.assert_awaited_once()
        submitted = request.await_args.kwargs["json"]
        self.assertEqual(2, len(submitted))
        self.assertEqual("00c8d2", submitted[0]["color"])


if __name__ == "__main__":
    unittest.main()
