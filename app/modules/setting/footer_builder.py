"""Versioned, bounded layout data. Never accepts executable markup or CSS."""
import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")]


def safe_builder_url(value: str | None) -> str:
    cleaned = (value or "").strip()
    # Browsers ignore ASCII control characters inside URL schemes.
    normalized = re.sub(r"[\x00-\x20\x7f]", "", cleaned)
    scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", normalized)
    if scheme and scheme.group(1).lower() not in {"http", "https", "mailto", "tel"}:
        raise ValueError("Chỉ cho phép liên kết HTTP, HTTPS, email, điện thoại hoặc đường dẫn nội bộ")
    return cleaned


class BuilderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuilderLink(BuilderModel):
    label_vi: str = Field(max_length=150)
    label_en: str = Field(max_length=150)
    href: str = Field(max_length=500)
    open_in_new_tab: bool = False
    _safe_href = field_validator("href")(safe_builder_url)


class FooterBlock(BuilderModel):
    id: Identifier
    type: Literal["logo", "heading", "text", "links", "contact", "social", "image", "button", "divider", "spacer", "copyright"]
    title_vi: str = Field(default="", max_length=255)
    title_en: str = Field(default="", max_length=255)
    text_vi: str = Field(default="", max_length=5000)
    text_en: str = Field(default="", max_length=5000)
    href: str = Field(default="", max_length=500)
    open_in_new_tab: bool = False
    image_object_key: str | None = Field(default=None, max_length=512)
    image_alt_vi: str = Field(default="", max_length=255)
    image_alt_en: str = Field(default="", max_length=255)
    source: Literal[
        "custom",
        "quick_links",
        "external_links",
        "navigation",
        "departments",
        "categories",
        "latest_articles",
    ] = "custom"
    unit_type: Literal["faculty", "department", "office", "center", "lab"] = "faculty"
    item_limit: int = Field(default=8, ge=1, le=20)
    menu_index: int = Field(default=0, ge=0, le=20)
    links: list[BuilderLink] = Field(default_factory=list, max_length=50)
    align: Literal["left", "center", "right"] = "left"
    color: Color | None = None
    background: Color | None = None
    font_size: int = Field(default=14, ge=8, le=96)
    padding: int = Field(default=0, ge=0, le=120)
    width: int = Field(default=224, ge=32, le=1200)
    height: int = Field(default=56, ge=0, le=600)
    hidden_desktop: bool = False
    hidden_mobile: bool = False

    _safe_urls = field_validator("href", "image_object_key")(safe_builder_url)


class FooterColumn(BuilderModel):
    id: Identifier
    width: int = Field(default=1, ge=1, le=12)
    blocks: list[FooterBlock] = Field(default_factory=list, max_length=30)


class FooterRow(BuilderModel):
    id: Identifier
    columns: list[FooterColumn] = Field(min_length=1, max_length=6)
    background: Color | None = None
    color: Color | None = None
    padding: int = Field(default=32, ge=0, le=120)
    gap: int = Field(default=24, ge=0, le=96)


class FooterBuilder(BuilderModel):
    version: Literal[1] = 1
    enabled: bool = False
    background: Color = "#f8fafc"
    color: Color = "#334155"
    link_color: Color = "#1e40af"
    max_width: int = Field(default=1280, ge=320, le=1920)
    gap: int = Field(default=20, ge=0, le=96)
    show_statistics: bool = True
    rows: list[FooterRow] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        identifiers = []
        for row in self.rows:
            identifiers.append(row.id)
            for column in row.columns:
                identifiers.append(column.id)
                identifiers.extend(block.id for block in column.blocks)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Mỗi hàng, cột và khối phải có mã riêng")
        return self
