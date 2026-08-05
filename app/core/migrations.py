from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from app.core.config import get_settings


ACCESS_TABLES = {
    "permissions",
    "roles",
    "role_permissions",
    "users",
    "audit_events",
}
ACCESS_BASELINE_REVISION = "20260724_0001"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(connection) -> Config:
    settings = get_settings()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(PROJECT_ROOT / "migrations"),
    )
    config.set_main_option(
        "sqlalchemy.url",
        settings.database_url.replace("%", "%%"),
    )
    config.attributes["connection"] = connection
    return config


def ensure_database_schema(engine: Engine) -> str:
    """Create, baseline, or upgrade the local NetDoc schema.

    Returns one of: ``created``, ``stamped`` or ``upgraded``.
    A partially-created legacy schema is rejected to avoid hiding damage.
    """
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        config = _alembic_config(connection)

        if "alembic_version" in tables:
            command.upgrade(config, "head")
            return "upgraded"

        present = tables & ACCESS_TABLES

        if not present:
            command.upgrade(config, "head")
            return "created"

        if present == ACCESS_TABLES:
            # La base heredada corresponde al esquema original de acceso. Se
            # marca esa revisión exacta y luego se aplican migraciones nuevas;
            # marcar directamente ``head`` omitiría tablas posteriores.
            command.stamp(config, ACCESS_BASELINE_REVISION)
            command.upgrade(config, "head")
            return "stamped"

        missing = ", ".join(sorted(ACCESS_TABLES - present))
        raise RuntimeError(
            "La base local contiene un esquema parcial. "
            f"Faltan tablas: {missing}."
        )
