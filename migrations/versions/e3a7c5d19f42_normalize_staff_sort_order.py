"""normalize staff sort_order within each department

Số thứ tự cán bộ đang bị trùng và nhảy cóc (0, 0, 0, 20...), nên con số trong trang
quản trị không khớp với vị trí thật. Đánh lại liên tục từ 0 trong từng đơn vị, giữ
nguyên thứ tự đang hiển thị (sort_order tăng dần, cùng số thì bản ghi mới hơn đứng trước).

Revision ID: e3a7c5d19f42
Revises: d2f9a61b4c8e
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e3a7c5d19f42"
down_revision: str | None = "d2f9a61b4c8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE staffs AS s
        SET sort_order = ranked.position
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY department_id
                       ORDER BY sort_order ASC, created_at DESC
                   ) - 1 AS position
            FROM staffs
            WHERE deleted_at IS NULL
        ) AS ranked
        WHERE s.id = ranked.id
          AND s.sort_order <> ranked.position
        """
    )


def downgrade() -> None:
    # Thứ tự hiển thị không đổi sau khi chuẩn hóa, nên không có gì để khôi phục.
    pass
