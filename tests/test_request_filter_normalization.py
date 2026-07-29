from __future__ import annotations

from urllib.parse import parse_qs
import unittest

from starlette.requests import Request

from app.core.auth import PermissionMiddleware


class DeviceFilterNormalizationTests(unittest.TestCase):
    @staticmethod
    def request(query: str) -> Request:
        return Request({
            "type": "http",
            "method": "GET",
            "path": "/devices",
            "raw_path": b"/devices",
            "query_string": query.encode("utf-8"),
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "app": object(),
        })

    def test_empty_site_and_role_are_removed_before_fastapi_validation(self):
        request = self.request(
            "q=S3910-48TS&site_id=&role_id=&status=active"
        )

        PermissionMiddleware._normalize_optional_device_filters(request)

        query = parse_qs(
            request.scope["query_string"].decode("utf-8"),
            keep_blank_values=True,
        )
        self.assertEqual(["S3910-48TS"], query["q"])
        self.assertEqual(["active"], query["status"])
        self.assertNotIn("site_id", query)
        self.assertNotIn("role_id", query)

    def test_valid_numeric_filters_are_preserved(self):
        request = self.request("site_id=12&role_id=8")

        PermissionMiddleware._normalize_optional_device_filters(request)

        query = parse_qs(
            request.scope["query_string"].decode("utf-8"),
        )
        self.assertEqual(["12"], query["site_id"])
        self.assertEqual(["8"], query["role_id"])


if __name__ == "__main__":
    unittest.main()
