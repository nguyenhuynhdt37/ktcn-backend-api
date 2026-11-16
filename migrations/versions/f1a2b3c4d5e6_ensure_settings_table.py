"""ensure settings table exists

Revision ID: f1a2b3c4d5e6
Revises: e3a7c5d19f42
Create Date: 2026-11-16 15:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e3a7c5d19f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key VARCHAR(100) NOT NULL UNIQUE,
            value JSONB NOT NULL,
            group_name VARCHAR(50) NOT NULL DEFAULT 'general',
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_settings_group ON settings(group_name)")


def downgrade() -> None:
    # Bảng settings có thể đã tồn tại từ schema khởi tạo ban đầu.
    pass
