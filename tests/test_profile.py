import os
import unittest

from argon2 import PasswordHasher


os.environ.setdefault("NETBOX_URL", "https://netbox.invalid")
os.environ.setdefault("NETBOX_TOKEN", "test-token")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("AdminPassword123"),
)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

from app.core.database import session_scope
from app.core.security import verify_password
from app.main import app
from app.models.access import User


class ProfileRouteTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(
            "/login",
            data={
                "username": "admin",
                "password": "AdminPassword123",
                "next_url": "/profile",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @staticmethod
    def _csrf(page: str, field_name: str, occurrence: int = 0) -> str:
        marker = f'name="{field_name}" value="'
        start = 0
        for _ in range(occurrence + 1):
            start = page.index(marker, start) + len(marker)
        return page[start:page.index('"', start)]

    def test_profile_page_is_available(self):
        response = self.client.get("/profile")
        self.assertEqual(200, response.status_code)
        self.assertIn("Mi perfil", response.text)
        self.assertIn("Administrador", response.text)

    def test_profile_details_can_be_updated(self):
        page = self.client.get("/profile")
        csrf = self._csrf(page.text, "csrf", 0)

        response = self.client.post(
            "/profile",
            data={
                "csrf": csrf,
                "full_name": "Administrador NetDoc",
                "email": "admin.netdoc@example.com",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)

        with session_scope() as session:
            user = session.get(User, 1)
            self.assertEqual("Administrador NetDoc", user.full_name)
            self.assertEqual("admin.netdoc@example.com", user.email)

    def test_password_change_requires_current_password(self):
        page = self.client.get("/profile")
        csrf = self._csrf(page.text, "csrf", 1)

        rejected = self.client.post(
            "/profile/password",
            data={
                "csrf": csrf,
                "current_password": "incorrect",
                "new_password": "UpdatedPassword123",
                "confirm_password": "UpdatedPassword123",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, rejected.status_code)

        with session_scope() as session:
            user = session.get(User, 1)
            self.assertFalse(
                verify_password(user.password_hash, "UpdatedPassword123")
            )

    def test_password_can_be_changed_and_restored(self):
        page = self.client.get("/profile")
        csrf = self._csrf(page.text, "csrf", 1)

        response = self.client.post(
            "/profile/password",
            data={
                "csrf": csrf,
                "current_password": "AdminPassword123",
                "new_password": "UpdatedPassword123",
                "confirm_password": "UpdatedPassword123",
            },
            follow_redirects=False,
        )
        self.assertEqual(303, response.status_code)

        with session_scope() as session:
            user = session.get(User, 1)
            self.assertTrue(
                verify_password(user.password_hash, "UpdatedPassword123")
            )

            user.password_hash = PasswordHasher().hash("AdminPassword123")


if __name__ == "__main__":
    unittest.main()
