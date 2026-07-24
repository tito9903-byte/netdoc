from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()


def _prepare_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    database_path = database_url.removeprefix(prefix)
    if database_path == ":memory:":
        return

    path = Path(database_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    path.parent.mkdir(parents=True, exist_ok=True)


_prepare_sqlite_directory(settings.database_url)

connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database() -> None:
    from app.core.migrations import ensure_database_schema
    from app.models.access import AuditEvent, Permission, Role, User
    from app.services.access_service import seed_access_control

    _ = (AuditEvent, Permission, Role, User)
    ensure_database_schema(engine)

    with session_scope() as session:
        seed_access_control(session)
