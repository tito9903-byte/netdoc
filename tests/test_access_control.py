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
        self.assertEqual(9, len(permissions))
        self.assertEqual(9, len(roles["administrador"].permissions))

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
