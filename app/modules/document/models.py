import enum
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models.base import BaseModel


class DocumentKind(str, enum.Enum):
    """Nhóm tài liệu hiển thị ở trang chủ."""

    VAN_BAN = "VAN_BAN"  # Văn bản - Biểu mẫu
    BAI_GIANG = "BAI_GIANG"  # Bài giảng - Giáo trình


class Document(BaseModel):
    """Tài liệu có tệp đính kèm (tệp được tải lên kho media/MinIO)."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_kind_sort", "kind", "sort_order"),
        Index("idx_documents_active", "is_active"),
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title_vi: Mapped[str] = mapped_column(String(255), nullable=False)
    title_en: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    file_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
