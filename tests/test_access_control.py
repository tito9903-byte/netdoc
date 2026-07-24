import os
import unittest
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher


os.environ.setdefault("NETBOX_URL", "https://netbox.invalid")
os.environ.setdefault("NETBOX_TOKEN", "test-token")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("AdminPassword123"),
)

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.access import AuditEvent, Permission, Role
from app.services.access_service import (
    AccessServiceError,
    authenticate_user,
    create_role,
    create_user,
    list_permissions,
    login_throttle_status,
    record_audit,
    seed_access_control,
)


class AccessControlTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.session = self.session_factory()
        seed_access_control(self.session)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_seed_creates_system_roles_and_permissions(self):
        roles = {
            role.code: role
            for role in self.session.scalars(select(Role)).all()
        }
        permissions = list(
            self.session.scalars(select(Permission)).all()
        )

        self.assertEqual(
            {"administrador", "operador", "consulta"},
            set(roles),
        )
        self.assertEqual(11, len(permissions))
        self.assertEqual(11, len(roles["administrador"].permissions))

    def test_seed_preserves_custom_system_role_permissions(self):
        operator = self.session.scalar(
            select(Role).where(Role.code == "operador")
        )
        operator.permissions = [
            permission
            for permission in operator.permissions
            if permission.code != "devices.create"
        ]
        self.session.commit()

        seed_access_control(self.session)
        self.session.commit()
        self.session.refresh(operator)

        self.assertNotIn(
            "devices.create",
            {permission.code for permission in operator.permissions},
        )

    def test_create_and_authenticate_user(self):
        role = self.session.scalar(
            select(Role).where(Role.code == "consulta")
        )
        user = create_user(
            self.session,
            username="Operador.Uno",
            full_name="Operador Uno",
            email="operador@example.com",
            password="Password123",
            role_id=role.id,
        )
        self.session.commit()

        identity = authenticate_user(
            self.session,
            "operador.uno",
            "Password123",
        )

        self.assertIsNotNone(identity)
        self.assertEqual(user.id, identity.id)
        self.assertIn("devices.view", identity.permissions)
        self.assertNotIn("devices.create", identity.permissions)

    def test_rejects_weak_password(self):
        role = self.session.scalar(
            select(Role).where(Role.code == "consulta")
        )

        with self.assertRaises(AccessServiceError):
            create_user(
                self.session,
                username="consulta",
                full_name="Consulta",
                email=None,
                password="debil",
                role_id=role.id,
            )

    def test_login_throttle_blocks_recent_failures(self):
        now = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

        for index in range(5):
            self.session.add(AuditEvent(
                created_at=now - timedelta(minutes=4, seconds=index),
                username="bloqueado",
                action="LOGIN_FAILED",
                resource="session",
                success=False,
                ip_address="192.0.2.10",
            ))
        self.session.commit()

        status = login_throttle_status(
            self.session,
            username="Bloqueado",
            ip_address="192.0.2.10",
            max_attempts=5,
            window_seconds=900,
            now=now,
        )

        self.assertTrue(status.blocked)
        self.assertEqual(5, status.attempts)
        self.assertGreater(status.retry_after_seconds, 0)

    def test_login_throttle_is_scoped_by_ip_and_window(self):
        now = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

        for index in range(5):
            self.session.add(AuditEvent(
                created_at=now - timedelta(hours=1, seconds=index),
                username="consulta",
                action="LOGIN_FAILED",
                resource="session",
                success=False,
                ip_address="192.0.2.11",
            ))
        self.session.commit()

        expired = login_throttle_status(
            self.session,
            username="consulta",
            ip_address="192.0.2.11",
            max_attempts=5,
            window_seconds=900,
            now=now,
        )
        other_ip = login_throttle_status(
            self.session,
            username="consulta",
            ip_address="192.0.2.12",
            max_attempts=5,
            window_seconds=900,
            now=now,
        )

        self.assertFalse(expired.blocked)
        self.assertFalse(other_ip.blocked)

    def test_custom_role_and_audit_event(self):
        permissions = list_permissions(self.session)
        selected = [
            permission.code
            for permission in permissions
            if permission.code in {
                "dashboard.view",
                "devices.view",
            }
        ]

        role = create_role(
            self.session,
            name="Inventario",
            code="inventario",
            description="Consulta de inventario.",
            permission_codes_value=selected,
        )

        event = record_audit(
            self.session,
            action="ROLE_CREATE",
            resource="role",
            resource_id=role.id,
            username="admin",
            detail="Rol de prueba.",
        )
        self.session.commit()

        stored = self.session.get(AuditEvent, event.id)
        self.assertTrue(stored.success)
        self.assertEqual("ROLE_CREATE", stored.action)


if __name__ == "__main__":
    unittest.main()
