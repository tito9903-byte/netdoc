from __future__ import annotations

import asyncio
from base64 import b64encode
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import func, select

from app.core.database import session_scope
from app.main import app
from app.models.access import User
from app.services.netbox_client import NetBoxClient


DEVICE = {
    "id": 300,
    "name": "3NT01-PP02",
    "device_type": {
        "id": 49255,
        "model": "49255-H24",
        "display": "49255-H24",
        "manufacturer": {
            "id": 7,
            "name": "Leviton",
            "display": "Leviton",
        },
    },
    "rack": {
        "id": 31,
        "name": "3NTI01",
        "display": "3NTI01",
    },
    "site": {"id": 4, "name": "Telenord SFM"},
    "status": {"value": "active", "label": "Active"},
    "position": 4.0,
    "face": {"value": "front", "label": "Front"},
}

INTERFACES = [
    {
        "id": 910,
        "name": "MGMT",
        "type": {"value": "virtual", "label": "Virtual"},
        "enabled": True,
    },
    {
        "id": 911,
        "name": "port1",
        "type": {"value": "1000base-t", "label": "1000BASE-T"},
        "enabled": True,
    },
]

INTERFACE_IP_ADDRESSES = [
    {
        "id": 1001,
        "address": "192.0.2.10/24",
        "display": "192.0.2.10/24",
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": 910,
    },
    {
        "id": 1002,
        "address": "2001:db8::10/64",
        "display": "2001:db8::10/64",
        "assigned_object_type": "dcim.interface",
        "assigned_object": {"id": 910, "name": "MGMT"},
    },
    {
        "id": 1003,
        "address": "198.51.100.40/24",
        "display": "198.51.100.40/24",
        "assigned_object_type": "virtualization.vminterface",
        "assigned_object_id": 910,
    },
]


class DeviceDetailNavigationTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        with session_scope() as session:
            admin_id = session.scalar(
                select(User.id).where(
                    func.lower(User.username) == "admin",
                )
            )
        self.assertIsInstance(admin_id, int)
        payload = b64encode(
            json.dumps(
                {
                    "authenticated": True,
                    "user_id": admin_id,
                    "username": "admin",
                }
            ).encode("utf-8")
        )
        signed_session = TimestampSigner(
            os.environ["SESSION_SECRET"],
        ).sign(payload)
        self.client.cookies.set(
            os.environ["SESSION_COOKIE_NAME"],
            signed_session.decode("utf-8"),
        )

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @patch(
        "app.main.NetBoxClient.get_device_interface_ip_addresses",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.get_device_interfaces",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.get_device",
        new_callable=AsyncMock,
        return_value=DEVICE,
    )
    def test_model_and_rack_open_their_internal_details(
        self,
        get_device,
        get_interfaces,
        get_ip_addresses,
    ):
        response = self.client.get("/devices/300")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.text.count('href="/device-types/49255"'),
            2,
        )
        self.assertEqual(
            response.text.count('href="/racks/31"'),
            1,
        )
        self.assertIn(
            'aria-label="Abrir ficha del modelo 49255-H24"',
            response.text,
        )
        self.assertIn(
            'aria-label="Abrir rack 3NTI01"',
            response.text,
        )
        self.assertIn(
            "css/devices.css?v=20260804-interface-ips-1",
            response.text,
        )
        get_device.assert_awaited_once_with(300)
        get_interfaces.assert_awaited_once_with(300)
        get_ip_addresses.assert_awaited_once_with(300)

    @patch(
        "app.main.NetBoxClient.get_device_interface_ip_addresses",
        new_callable=AsyncMock,
        return_value=INTERFACE_IP_ADDRESSES,
    )
    @patch(
        "app.main.NetBoxClient.get_device_interfaces",
        new_callable=AsyncMock,
        return_value=INTERFACES,
    )
    @patch(
        "app.main.NetBoxClient.get_device",
        new_callable=AsyncMock,
        return_value=DEVICE,
    )
    def test_interface_ip_addresses_are_grouped_and_rendered(
        self,
        _get_device,
        _get_interfaces,
        get_ip_addresses,
    ):
        response = self.client.get("/devices/300")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Direcciones IP", response.text)
        self.assertIn("192.0.2.10/24", response.text)
        self.assertIn("2001:db8::10/64", response.text)
        self.assertNotIn("198.51.100.40/24", response.text)
        self.assertEqual(
            response.text.count('class="interface-ip-list"'),
            1,
        )
        self.assertIn('class="interface-ip-empty">—</span>', response.text)
        get_ip_addresses.assert_awaited_once_with(300)

    def test_device_ip_query_is_limited_to_the_selected_device(self):
        client = NetBoxClient()
        client.get_all = AsyncMock(return_value=INTERFACE_IP_ADDRESSES)

        result = asyncio.run(
            client.get_device_interface_ip_addresses(300)
        )

        self.assertEqual(result, INTERFACE_IP_ADDRESSES)
        client.get_all.assert_awaited_once_with(
            "/api/ipam/ip-addresses/",
            params={
                "device_id": 300,
                "ordering": "address",
            },
            page_limit=200,
        )

    def test_model_and_rack_links_are_visually_identifiable(self):
        stylesheet = Path("app/static/css/devices.css").read_text(
            encoding="utf-8",
        )
        link_rule = stylesheet.split(
            ".device-reference-link {",
            maxsplit=1,
        )[1].split("}", maxsplit=1)[0]
        header_link_rule = stylesheet.split(
            ".device-header-reference-link {",
            maxsplit=1,
        )[1].split("}", maxsplit=1)[0]

        self.assertIn("color: var(--accent);", link_rule)
        self.assertIn("text-decoration: underline;", link_rule)
        self.assertIn("color: var(--accent);", header_link_rule)
        self.assertIn('content: "→";', stylesheet)
        self.assertIn(
            ".device-reference-link:focus-visible",
            stylesheet,
        )


if __name__ == "__main__":
    unittest.main()
