from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.setting.footer_builder import FooterBuilder, safe_builder_url


def _validate_safe_url(value: str | None, *, allow_empty: bool = False) -> str:
    cleaned = safe_builder_url(value)
    if not cleaned:
        return "" if allow_empty else "#"
    return cleaned


def resolve_setting_media_url(object_key: str | None) -> str | None:
    if not object_key:
        return None
    val = object_key.strip()
    if not val:
        return None
    lowered = val.lower()
    if lowered.startswith(("http://", "https://", "/")):
        return val
    if (
        lowered.startswith("data:image/")
        and not lowered.startswith("data:image/svg+xml")
    ):
        return val
    if lowered.startswith("data:"):
        return None
    return f"/api/v1/portal/media/file/{val.lstrip('/')}"


def default_quick_links() -> list["FooterLinkItem"]:
    return [
        FooterLinkItem(label_vi="Liên hệ", label_en="Contact", href="/tu-van-tuyen-sinh", open_in_new_tab=False),
        FooterLinkItem(label_vi="Thư viện", label_en="Library", href="/thu-vien", open_in_new_tab=False),
        FooterLinkItem(label_vi="Sơ đồ trang", label_en="Sitemap", href="/so-do-trang", open_in_new_tab=False),
        FooterLinkItem(label_vi="Sơ đồ trường", label_en="Campus Map", href="/so-do-truong", open_in_new_tab=False),
        FooterLinkItem(
            label_vi="Tham quan, trải nghiệm",
            label_en="Campus Tour",
            href="/tham-quan-trai-nghiem",
            open_in_new_tab=False,
        ),
    ]


def default_external_links() -> list["FooterLinkItem"]:
    return [
        FooterLinkItem(
            label_vi="Bộ GD&ĐT",
            label_en="Ministry of Education & Training",
            href="https://moet.gov.vn",
            open_in_new_tab=True,
        ),
        FooterLinkItem(
            label_vi="Trường Đại học Vinh",
            label_en="Vinh University",
            href="https://vinhuni.edu.vn",
            open_in_new_tab=True,
        ),
        FooterLinkItem(
            label_vi="Chương trình ETEP",
            label_en="ETEP Program",
            href="http://etep.edu.vn",
            open_in_new_tab=True,
        ),
        FooterLinkItem(
            label_vi="Đề án ngoại ngữ QG",
            label_en="National Foreign Languages Project",
            href="http://deanngoai-ngu.edu.vn",
            open_in_new_tab=True,
        ),
        FooterLinkItem(
            label_vi="Quỹ Nafosted",
            label_en="Nafosted Foundation",
            href="https://nafosted.gov.vn",
            open_in_new_tab=True,
        ),
    ]


class FooterLinkItem(BaseModel):
    label_vi: str = Field(..., min_length=1, max_length=150)
    label_en: str = Field(..., min_length=1, max_length=150)
    href: str = Field(..., min_length=1, max_length=500)
    open_in_new_tab: bool = False

    @field_validator("label_vi", "label_en", mode="before")
    @classmethod
    def strip_labels(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("href", mode="before")
    @classmethod
    def validate_href(cls, v: Any) -> str:
        return _validate_safe_url(str(v or ""), allow_empty=False)


HOME_SHORTCUT_ICONS = (
    "calendar",
    "mail",
    "file-text",
    "book-open",
    "briefcase",
    "message-circle",
    "link",
    "download",
    "graduation-cap",
    "users",
)


class HomeShortcutItem(BaseModel):
    """Lối tắt ở thanh biểu tượng trang chủ (cấu hình động trong admin)."""

    label_vi: str = Field(..., min_length=1, max_length=150)
    label_en: str = Field(..., min_length=1, max_length=150)
    href: str = Field(..., min_length=1, max_length=500)
    icon: str = Field(default="link", max_length=40)
    open_in_new_tab: bool = False

    @field_validator("label_vi", "label_en", mode="before")
    @classmethod
    def strip_labels(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("href", mode="before")
    @classmethod
    def validate_href(cls, v: Any) -> str:
        return _validate_safe_url(str(v or ""), allow_empty=False)

    @field_validator("icon", mode="before")
    @classmethod
    def validate_icon(cls, v: Any) -> str:
        icon = str(v or "link").strip().lower()
        return icon if icon in HOME_SHORTCUT_ICONS else "link"


def default_home_shortcuts() -> list[HomeShortcutItem]:
    return [
        HomeShortcutItem(label_vi="Lịch tuần", label_en="Weekly calendar", href="/lich-tuan", icon="calendar"),
        HomeShortcutItem(
            label_vi="Thư điện tử", label_en="Webmail", href="https://outlook.office.com/",
            icon="mail", open_in_new_tab=True,
        ),
        HomeShortcutItem(
            label_vi="Văn bản – Biểu mẫu", label_en="Documents & forms",
            href="/tai-lieu/van-ban-bieu-mau", icon="file-text",
        ),
        HomeShortcutItem(
            label_vi="Bài giảng – Giáo trình", label_en="Lectures & textbooks",
            href="/tai-lieu/bai-giang-giao-trinh", icon="book-open",
        ),
        HomeShortcutItem(
            label_vi="Thông tin việc làm", label_en="Career opportunities",
            href="/tin-tuc?category_slug=tuyen-dung", icon="briefcase",
        ),
        HomeShortcutItem(
            label_vi="Hỏi đáp", label_en="Questions & answers",
            href="/tu-van-tuyen-sinh", icon="message-circle",
        ),
    ]


class SiteSettingsPayload(BaseModel):
    footer_builder: FooterBuilder | None = None
    header_logo_width: int = Field(default=320, ge=80, le=600)
    header_logo_height: int = Field(default=56, ge=24, le=120)
    header_logo_object_key: str | None = Field(default=None, max_length=512)
    footer_logo_object_key: str | None = Field(default=None, max_length=512)
    fanpage_image_object_key: str | None = Field(default=None, max_length=512)

    logo_alt_vi: str = Field(
        default="Trường Kỹ thuật và Công nghệ - Trường Đại học Vinh",
        min_length=1,
        max_length=255,
    )
    logo_alt_en: str = Field(
        default="College of Engineering and Technology - Vinh University",
        min_length=1,
        max_length=255,
    )
    college_name_vi: str = Field(
        default="Trường Kỹ thuật và Công nghệ - Trường Đại học Vinh",
        min_length=1,
        max_length=255,
    )
    college_name_en: str = Field(
        default="College of Engineering and Technology - Vinh University",
        min_length=1,
        max_length=255,
    )

    address_vi: str = Field(default="182 Lê Duẩn, Thành phố Vinh, Nghệ An", min_length=1, max_length=500)
    address_en: str = Field(default="182 Le Duan, Vinh City, Nghe An", min_length=1, max_length=500)
    phone: str = Field(default="0238 3855 452", max_length=100)
    email: str = Field(default="vienktcn@vinhuni.edu.vn", max_length=255)
    website: str = Field(default="ktcn.itup.io.vn", max_length=255)

    responsible_officer_vi: str = Field(
        default="PGS. TS. Hoàng Hữu Việt - Hiệu phó",
        max_length=255,
    )
    responsible_officer_en: str = Field(
        default="Assoc. Prof. Dr. Hoang Huu Viet - Vice Rector",
        max_length=255,
    )

    facebook_url: str = Field(default="https://www.facebook.com/Vienktcn", max_length=500)
    messenger_url: str = Field(default="#", max_length=500)

    copyright_vi: str = Field(
        default="© {year} Bản quyền thuộc về Trường Kỹ thuật và Công nghệ, Trường Đại học Vinh.",
        max_length=500,
    )
    copyright_en: str = Field(
        default="© {year} Copyright belongs to the College of Engineering and Technology, Vinh University.",
        max_length=500,
    )
    developer_name: str = Field(default="CLB ITUP", max_length=150)
    developer_url: str = Field(default="https://www.facebook.com/itup.binhdanhocvuso.dhv/", max_length=500)

    quick_links: list[FooterLinkItem] = Field(default_factory=default_quick_links)
    external_links: list[FooterLinkItem] = Field(default_factory=default_external_links)
    home_shortcuts: list[HomeShortcutItem] = Field(
        default_factory=default_home_shortcuts, max_length=12
    )

    @field_validator(
        "header_logo_object_key",
        "footer_logo_object_key",
        "fanpage_image_object_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_key(cls, v: Any) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned or None

    @field_validator("facebook_url", "messenger_url", "developer_url", mode="before")
    @classmethod
    def validate_urls(cls, v: Any) -> str:
        return _validate_safe_url(str(v or ""), allow_empty=False)

    @field_validator(
        "logo_alt_vi",
        "logo_alt_en",
        "college_name_vi",
        "college_name_en",
        "address_vi",
        "address_en",
        "phone",
        "email",
        "website",
        "responsible_officer_vi",
        "responsible_officer_en",
        "copyright_vi",
        "copyright_en",
        "developer_name",
        mode="before",
    )
    @classmethod
    def strip_text(cls, v: Any) -> str:
        return str(v or "").strip()


class SiteSettingsResponse(SiteSettingsPayload):
    header_logo_url: str | None = None
    footer_logo_url: str | None = None
    fanpage_image_url: str | None = None
