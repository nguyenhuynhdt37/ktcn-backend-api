from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import BaseModel


class Setting(BaseModel):
    """
    Model lưu trữ cấu hình hệ thống dạng key-value (JSONB).
    Tương ứng bảng `settings` trong schema hệ thống.
    """

    __tablename__ = "settings"
    __table_args__ = (Index("idx_settings_group", "group_name"),)

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    group_name: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
