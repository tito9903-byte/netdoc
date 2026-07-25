from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceTypeImage(Base):
    """Imagen frontal o trasera asociada a un tipo de dispositivo de NetBox."""

    __tablename__ = "device_type_images"
    __table_args__ = (
        UniqueConstraint(
            "device_type_id",
            "face",
            name="uq_device_type_images_device_type_face",
        ),
        CheckConstraint(
            "face IN ('front', 'rear')",
            name="ck_device_type_images_face",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_type_id: Mapped[int] = mapped_column(Integer, index=True)
    face: Mapped[str] = mapped_column(String(10))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
