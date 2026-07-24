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
from sqlalchemy import select

from app.core.database import session_scope
from app.main import app
from app.models.access import Role, User
from app.services.access_service import (
    create_user,
    set_user_password,
)


class AdminRouteTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def login(self, username: str, password: str):
        return self.client.post(
            "/login",
            data={
                "username": username,
                "password": password,
                "next_url": "/",
            },
            follow_redirects=False,
        )

    @staticmethod
    def ensure_user(
        username: str,
        role_code: str,
    ) -> int:
        with session_scope() as session:
            role = session.scalar(
                select(Role).where(Role.code == role_code)
            )
            user = session.scalar(
                select(User).where(User.username == username)
            )

            if user is None:
                user = create_user(
                    session,
                    username=username,
                    full_name=username.replace(".", " ").title(),
                    email=f"{username}@example.com",
                    password="Password123",
                    role_id=role.id,
                )
            else:
                user.role = role
                user.is_active = True
                set_user_password(session, user, "Password123")

            return user.id

    def test_admin_can_open_access_control_pages(self):
        response = self.login("admin", "AdminPassword123")
        self.assertEqual(303, response.status_code)

        for path in (
            "/admin/users",
            "/admin/roles",
            "/admin/audit",
        ):
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(200, page.status_code)

    def test_read_only_user_is_denied_admin_pages(self):
        self.ensure_user("consulta.test", "consulta")

        response = self.login("consulta.test", "Password123")
        self.assertEqual(303, response.status_code)

        denied = self.client.get(
            "/admin/users",
            follow_redirects=False,
        )
        self.assertEqual(303, denied.status_code)
        self.assertEqual("/forbidden", denied.headers["location"])

    def test_invalid_login_is_audited(self):
        response = self.login("admin", "incorrect-password")
        self.assertEqual(401, response.status_code)

        self.login("admin", "AdminPassword123")
        audit_page = self.client.get("/admin/audit")
        self.assertEqual(200, audit_page.status_code)
        self.assertIn("LOGIN_FAILED", audit_page.text)

    def test_account_deactivation_invalidates_existing_session(self):
        user_id = self.ensure_user("revocado.test", "consulta")
        response = self.login("revocado.test", "Password123")
        self.assertEqual(303, response.status_code)

        allowed = self.client.get("/forbidden")
        self.assertEqual(403, allowed.status_code)

        with session_scope() as session:
            user = session.get(User, user_id)
            user.is_active = False

        revoked = self.client.get(
            "/forbidden",
            follow_redirects=False,
        )
        self.assertEqual(303, revoked.status_code)
        self.assertTrue(revoked.headers["location"].startswith("/login?next="))

        with session_scope() as session:
            user = session.get(User, user_id)
            user.is_active = True

    def test_role_change_refreshes_permissions_on_next_request(self):
        user_id = self.ensure_user("promovido.test", "consulta")
        response = self.login("promovido.test", "Password123")
        self.assertEqual(303, response.status_code)

        denied = self.client.get(
            "/admin/users",
            follow_redirects=False,
        )
        self.assertEqual(303, denied.status_code)

        with session_scope() as session:
            user = session.get(User, user_id)
            admin_role = session.scalar(
                select(Role).where(Role.code == "administrador")
            )
            user.role = admin_role

        allowed = self.client.get("/admin/users")
        self.assertEqual(200, allowed.status_code)

        with session_scope() as session:
            user = session.get(User, user_id)
            consultation_role = session.scalar(
                select(Role).where(Role.code == "consulta")
            )
            user.role = consultation_role


if __name__ == "__main__":
    unittest.main()
