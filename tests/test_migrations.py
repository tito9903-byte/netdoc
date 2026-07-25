from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from argon2 import PasswordHasher
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect


os.environ.setdefault("NETBOX_URL", "https://netbox.invalid")
os.environ.setdefault("NETBOX_TOKEN", "test-token")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    PasswordHasher().hash("AdminPassword123"),
)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.core.database import Base
from app.core.migrations import ACCESS_TABLES, ensure_database_schema
from app.models import access as _access_models
from app.models import device_media as _device_media_models


class MigrationTests(unittest.TestCase):
    def test_empty_database_is_migrated_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "netdoc.db"
            engine = create_engine(f"sqlite:///{database}")

            first = ensure_database_schema(engine)
            second = ensure_database_schema(engine)
            tables = set(inspect(engine).get_table_names())

            self.assertEqual("created", first)
            self.assertEqual("upgraded", second)
            self.assertTrue(ACCESS_TABLES.issubset(tables))
            self.assertIn("device_type_images", tables)
            self.assertIn("alembic_version", tables)
            engine.dispose()

    def test_existing_complete_schema_is_stamped_then_upgraded(self):
        _ = (_access_models, _device_media_models)
        engine = create_engine("sqlite:///:memory:")

        # Simula la base heredada: contiene las tablas originales de acceso,
        # pero todavía no registra una revisión Alembic ni la tabla de imágenes.
        for table in list(Base.metadata.sorted_tables):
            if table.name in ACCESS_TABLES:
                table.create(bind=engine)

        result = ensure_database_schema(engine)
        tables = set(inspect(engine).get_table_names())

        self.assertEqual("stamped", result)
        self.assertIn("device_type_images", tables)
        self.assertIn("alembic_version", tables)
        engine.dispose()

    def test_partial_schema_is_rejected(self):
        engine = create_engine("sqlite:///:memory:")
        metadata = MetaData()
        Table(
            "permissions",
            metadata,
            Column("id", Integer, primary_key=True),
        )
        metadata.create_all(bind=engine)

        with self.assertRaises(RuntimeError):
            ensure_database_schema(engine)

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
