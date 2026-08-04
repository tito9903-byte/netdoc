from __future__ import annotations

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


class DeviceSearchFilterTests(unittest.TestCase):
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
        "app.main.NetBoxClient.list_device_roles",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_sites",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_devices",
        new_callable=AsyncMock,
        return_value={"count": 0, "results": []},
    )
    def test_empty_filters_are_treated_as_not_selected(
        self,
        list_devices,
        _list_sites,
        _list_roles,
    ):
        response = self.client.get(
            "/devices?q=heade&site_id=&role_id=&status=",
        )

        self.assertEqual(200, response.status_code)
        self.assertIn("Inventario de dispositivos", response.text)
        self.assertIn("js/devices.js", response.text)
        list_devices.assert_awaited_once_with(
            page=1,
            page_size=25,
            query="heade",
            site_id=None,
            status="",
            role_id=None,
        )

    @patch(
        "app.main.NetBoxClient.list_device_roles",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_sites",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_devices",
        new_callable=AsyncMock,
        return_value={"count": 0, "results": []},
    )
    def test_valid_filter_ids_are_forwarded_as_integers(
        self,
        list_devices,
        _list_sites,
        _list_roles,
    ):
        response = self.client.get(
            "/devices",
            params={
                "q": "  header  ",
                "site_id": "4",
                "role_id": "7",
                "status": "active",
                "page": "2",
            },
        )

        self.assertEqual(200, response.status_code)
        list_devices.assert_awaited_once_with(
            page=2,
            page_size=25,
            query="header",
            site_id=4,
            status="active",
            role_id=7,
        )

    @patch(
        "app.main.NetBoxClient.list_device_roles",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_sites",
        new_callable=AsyncMock,
        return_value=[],
    )
    @patch(
        "app.main.NetBoxClient.list_devices",
        new_callable=AsyncMock,
        return_value={"count": 0, "results": []},
    )
    def test_malformed_filters_fall_back_without_validation_json(
        self,
        list_devices,
        _list_sites,
        _list_roles,
    ):
        response = self.client.get(
            "/devices?site_id=invalid&role_id=-5&page=invalid",
        )

        self.assertEqual(200, response.status_code)
        self.assertIn("text/html", response.headers["content-type"])
        list_devices.assert_awaited_once_with(
            page=1,
            page_size=25,
            query="",
            site_id=None,
            status="",
            role_id=None,
        )

    def test_filter_script_omits_empty_controls_before_submit(self):
        script = Path("app/static/js/devices.js").read_text(
            encoding="utf-8",
        )

        self.assertIn('form.addEventListener("submit"', script)
        self.assertIn('field.value.trim() === ""', script)
        self.assertIn("field.disabled = true", script)


if __name__ == "__main__":
    unittest.main()
