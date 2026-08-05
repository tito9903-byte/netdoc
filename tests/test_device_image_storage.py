from __future__ import annotations

import re
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import initialize_database, session_scope
from app.main import app
from app.models.device_media import DeviceTypeImage
from app.services.device_image_service import DeviceImageService
from app.services.device_type_service import DeviceTypeServiceError
from app.services.rack_service import RackService


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"netdoc-image"
SECOND_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"updated-image"
DEVICE_TYPE_ID = 987654


class DeviceImageStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    @staticmethod
    def _cleanup() -> None:
        with session_scope() as session:
            session.execute(
                delete(DeviceTypeImage).where(
                    DeviceTypeImage.device_type_id == DEVICE_TYPE_ID
                )
            )
        RackService._device_type_cache.pop(DEVICE_TYPE_ID, None)

    def test_save_read_decorate_and_replace_local_image(self):
        service = DeviceImageService()
        first = service.save_images(
            device_type_id=DEVICE_TYPE_ID,
            images={
                "front_image": (
                    "../front.png",
                    PNG_BYTES,
                    "image/png",
                )
            },
            username="tester",
        )

        self.assertEqual("front.png", first["front"]["filename"])
        self.assertEqual(
            (PNG_BYTES, "image/png", first["front"]["sha256"]),
            service.get_local_image(DEVICE_TYPE_ID, "front"),
        )

        decorated = service.decorate_device_type({
            "id": DEVICE_TYPE_ID,
            "model": "S148F",
            "front_image": None,
            "rear_image": None,
        })
        self.assertTrue(decorated["_local_front_image"])
        self.assertEqual("netdoc", decorated["_front_image_source"])
        self.assertEqual(
            f"/media/device-types/{DEVICE_TYPE_ID}/front",
            decorated["front_image"],
        )

        second = service.save_images(
            device_type_id=DEVICE_TYPE_ID,
            images={
                "front": (
                    "front-new.png",
                    SECOND_PNG_BYTES,
                    "image/png",
                )
            },
            username="tester2",
        )
        self.assertNotEqual(
            first["front"]["sha256"],
            second["front"]["sha256"],
        )
        stored = service.get_local_image(DEVICE_TYPE_ID, "front")
        self.assertIsNotNone(stored)
        self.assertEqual(SECOND_PNG_BYTES, stored[0])
        self.assertEqual(1, len(service.summary(DEVICE_TYPE_ID)))

    def test_rejects_file_whose_signature_is_not_an_image(self):
        with self.assertRaises(DeviceTypeServiceError):
            DeviceImageService().save_images(
                device_type_id=DEVICE_TYPE_ID,
                images={
                    "front": (
                        "not-an-image.png",
                        b"plain text",
                        "image/png",
                    )
                },
            )

    def test_rack_service_prefers_local_image_without_calling_netbox(self):
        DeviceImageService().save_images(
            device_type_id=DEVICE_TYPE_ID,
            images={
                "front": ("front.png", PNG_BYTES, "image/png")
            },
        )

        content, content_type, digest = __import__("asyncio").run(
            RackService().get_device_type_image(DEVICE_TYPE_ID, "front")
        )
        self.assertEqual(PNG_BYTES, content)
        self.assertEqual("image/png", content_type)
        self.assertEqual(64, len(digest))


class DeviceImageRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def setUp(self):
        with session_scope() as session:
            session.execute(
                delete(DeviceTypeImage).where(
                    DeviceTypeImage.device_type_id == DEVICE_TYPE_ID
                )
            )
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/device-types",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        with session_scope() as session:
            session.execute(
                delete(DeviceTypeImage).where(
                    DeviceTypeImage.device_type_id == DEVICE_TYPE_ID
                )
            )

    @staticmethod
    def _device_type() -> dict[str, object]:
        return {
            "id": DEVICE_TYPE_ID,
            "model": "FortiSwitch S148F",
            "display": "Fortinet FortiSwitch S148F",
            "manufacturer": {"id": 1, "name": "Fortinet"},
            "u_height": 1,
            "front_image": None,
            "rear_image": None,
        }

    @patch(
        "app.routers.device_images.DeviceTypeService.get_device_type",
        new_callable=AsyncMock,
    )
    def test_authenticated_upload_is_saved_locally_and_served(self, get_model):
        get_model.return_value = self._device_type()
        page = self.client.get(
            f"/device-types/{DEVICE_TYPE_ID}/images"
        )
        self.assertEqual(200, page.status_code)
        match = re.search(
            r'name="csrf" value="([^"]+)"',
            page.text,
        )
        self.assertIsNotNone(match)

        response = self.client.post(
            f"/device-types/{DEVICE_TYPE_ID}/images",
            data={"csrf": match.group(1)},
            files={
                "front_image": (
                    "fortiswitch.png",
                    PNG_BYTES,
                    "image/png",
                )
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)
        self.assertIn("notice=", response.headers["location"])

        image = self.client.get(
            f"/media/device-types/{DEVICE_TYPE_ID}/front"
        )
        self.assertEqual(200, image.status_code)
        self.assertEqual("image/png", image.headers["content-type"])
        self.assertEqual(PNG_BYTES, image.content)
        self.assertIn("etag", image.headers)


if __name__ == "__main__":
    unittest.main()
