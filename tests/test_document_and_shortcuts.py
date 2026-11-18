"""Kiểm tra schema tài liệu và lối tắt trang chủ (không chạm vào DB)."""

import pytest
from pydantic import ValidationError

from app.modules.document.schemas import DocumentCreate, DocumentResponse
from app.modules.setting.schemas import (
    HomeShortcutItem,
    SiteSettingsPayload,
    default_home_shortcuts,
)


def _doc(**over):
    base = {
        "kind": "VAN_BAN",
        "title_vi": "  Mẫu đơn  ",
        "file_object_key": "files/abc.pdf",
        "file_name": "mau-don.pdf",
    }
    base.update(over)
    return base


def test_document_create_strips_and_defaults():
    doc = DocumentCreate(**_doc())
    assert doc.title_vi == "Mẫu đơn"
    assert doc.is_active is True
    assert doc.sort_order == 1


@pytest.mark.parametrize(
    "key",
    ["", "../etc/passwd", "/abs/path", "a/../b", "a\\b", "https://evil.example/x", "javascript:alert(1)"],
)
def test_document_rejects_unsafe_object_key(key):
    with pytest.raises(ValidationError):
        DocumentCreate(**_doc(file_object_key=key))


def test_document_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        DocumentCreate(**_doc(kind="OTHER"))


def test_document_response_exposes_download_url():
    from datetime import UTC, datetime
    import uuid

    now = datetime.now(UTC)
    resp = DocumentResponse(**_doc(), id=uuid.uuid4(), created_at=now, updated_at=now)
    assert resp.file_url == "/api/v1/portal/media/file/files/abc.pdf"


def test_default_shortcuts_include_configurable_webmail():
    shortcuts = default_home_shortcuts()
    assert len(shortcuts) == 6
    mail = next(s for s in shortcuts if s.icon == "mail")
    assert mail.href.startswith("https://")
    assert SiteSettingsPayload().home_shortcuts == shortcuts


def test_shortcut_rejects_dangerous_href():
    with pytest.raises(ValidationError):
        HomeShortcutItem(label_vi="A", label_en="A", href="javascript:alert(1)")


def test_shortcut_unknown_icon_falls_back_to_link():
    item = HomeShortcutItem(label_vi="A", label_en="A", href="/x", icon="nope")
    assert item.icon == "link"


def test_shortcut_limit():
    items = [{"label_vi": "A", "label_en": "A", "href": "/x"}] * 13
    with pytest.raises(ValidationError):
        SiteSettingsPayload(home_shortcuts=items)
