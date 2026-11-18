import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.modules.document.models import DocumentKind
from app.modules.setting.schemas import resolve_setting_media_url


def clean_object_key(value: Any) -> str:
    key = str(value or "").strip()
    if (
        not key
        or key.startswith("/")
        or "\\" in key
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in key)
        or any(seg in ("", ".", "..") for seg in key.split("/"))
        or key.lower().startswith(("http:", "https:", "data:", "javascript:"))
    ):
        raise ValueError("Khóa tệp không hợp lệ")
    return key


class DocumentBase(BaseModel):
    kind: DocumentKind
    title_vi: str = Field(..., min_length=1, max_length=255)
    title_en: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    file_object_key: str = Field(..., min_length=1, max_length=512)
    file_name: str = Field(..., min_length=1, max_length=255)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    file_size: Optional[int] = Field(default=None, ge=0)
    sort_order: int = Field(default=1, ge=0, le=100000)
    is_active: bool = True

    @field_validator("title_vi", "file_name", mode="before")
    @classmethod
    def strip_required(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("title_en", "description", "mime_type", mode="before")
    @classmethod
    def strip_optional(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("file_object_key", mode="before")
    @classmethod
    def validate_key(cls, v: Any) -> str:
        return clean_object_key(v)


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_url(self) -> Optional[str]:
        return resolve_setting_media_url(self.file_object_key)


class DocumentPagination(BaseModel):
    items: list[DocumentResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
