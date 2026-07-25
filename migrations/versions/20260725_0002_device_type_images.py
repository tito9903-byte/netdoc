"""Guardar imágenes de modelos en la base local de NetDoc.

Revision ID: 20260725_0002
Revises: 20260724_0001
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260725_0002"
down_revision: Union[str, None] = "20260724_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_type_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_type_id", sa.Integer(), nullable=False),
        sa.Column("face", sa.String(length=10), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "face IN ('front', 'rear')",
            name="ck_device_type_images_face",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_type_id",
            "face",
            name="uq_device_type_images_device_type_face",
        ),
    )
    op.create_index(
        "ix_device_type_images_device_type_id",
        "device_type_images",
        ["device_type_id"],
    )
    op.create_index(
        "ix_device_type_images_sha256",
        "device_type_images",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_type_images_sha256",
        table_name="device_type_images",
    )
    op.drop_index(
        "ix_device_type_images_device_type_id",
        table_name="device_type_images",
    )
    op.drop_table("device_type_images")
