"""create_documents_table

Revision ID: a7c1d2e3f4b5
Revises: f1a2b3c4d5e6
Create Date: 2026-11-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c1d2e3f4b5"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title_vi", sa.String(255), nullable=False),
        sa.Column("title_en", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_object_key", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('VAN_BAN', 'BAI_GIANG')", name="chk_documents_kind"),
    )
    op.create_index("idx_documents_kind_sort", "documents", ["kind", "sort_order"])
    op.create_index("idx_documents_active", "documents", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_documents_active", table_name="documents")
    op.drop_index("idx_documents_kind_sort", table_name="documents")
    op.drop_table("documents")
