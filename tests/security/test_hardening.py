"""Offline regression tests for the media, session, proxy and ownership hardening."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI, Request
from starlette.responses import Response

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenException, setup_exception_handlers
from app.core.middleware.rate_limit import RateLimitMiddleware
from app.modules.article.service import ArticleService
from app.modules.auth import router as auth_module
from app.modules.auth.dependencies import get_current_user, is_token_stale
from app.modules.auth.schemas import UserResponse, UserUpdate
from app.modules.auth.service import AuthService
from app.modules.media.service import (
    build_content_disposition,
    build_public_media_headers,
    check_svg_safety,
    is_active_content_type,
    validate_magic_bytes,
)
from app.shared.client_ip import get_client_ip, is_internal_call

# Importing ArticleService registers the Article mapper; SQLAlchemy can only
# configure it once every model it references is imported too (as app.main does).
import app.modules.academic_title.models  # noqa: E402,F401
import app.modules.ai_hub.models  # noqa: E402,F401
import app.modules.audit.models  # noqa: E402,F401
import app.modules.auth.models  # noqa: E402,F401
import app.modules.banner.models  # noqa: E402,F401
import app.modules.category.models  # noqa: E402,F401
import app.modules.consultation.models  # noqa: E402,F401
import app.modules.degree.models  # noqa: E402,F401
import app.modules.department.models  # noqa: E402,F401
import app.modules.gallery.models  # noqa: E402,F401
import app.modules.language.models  # noqa: E402,F401
import app.modules.media.models  # noqa: E402,F401
import app.modules.menu.models  # noqa: E402,F401
import app.modules.notification.models  # noqa: E402,F401
import app.modules.position.models  # noqa: E402,F401
import app.modules.program.models  # noqa: E402,F401
import app.modules.staff.models  # noqa: E402,F401
import app.modules.statistics.models  # noqa: E402,F401
import app.modules.tag.models  # noqa: E402,F401

MEMBER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")


def http_request(peer="203.0.113.5", headers=None, scheme="http", path="/"):
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": scheme, "path": path, "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (peer, 1234), "server": ("testserver", 80),
    })


# ── Client address / rate limiting ───────────────────────────────────────────

@pytest.mark.parametrize("header", ["CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"])
def test_direct_clients_cannot_spoof_their_address(header):
    request = http_request(peer="203.0.113.5", headers={header: "192.0.2.9"})
    assert get_client_ip(request) == "203.0.113.5"
    assert is_internal_call(request) is False


def test_trusted_proxy_headers_are_honoured():
    assert get_client_ip(http_request("172.18.0.1", {"CF-Connecting-IP": "192.0.2.9"})) == "192.0.2.9"
    assert get_client_ip(http_request("127.0.0.1", {"X-Real-IP": "192.0.2.10"})) == "192.0.2.10"


def test_forwarded_for_uses_the_hop_added_by_our_proxy():
    # "6.6.6.6" was typed by the client; the real address is the one our proxy appended.
    request = http_request("10.0.0.2", {"X-Forwarded-For": "6.6.6.6, 198.51.100.8, 10.0.0.9"})
    assert get_client_ip(request) == "198.51.100.8"


def test_private_calls_without_forwarding_headers_are_internal():
    assert is_internal_call(http_request("172.18.0.5")) is True
    assert is_internal_call(http_request("172.18.0.5", {"X-Real-IP": "192.0.2.9"})) is False


def test_rate_limit_bucket_ignores_slugs_and_ids():
    bucket = RateLimitMiddleware._bucket_for_path
    assert bucket("/api/v1/portal/articles/a") == bucket("/api/v1/portal/articles/b")
    assert bucket(f"/api/v1/users/{MEMBER_ID}") == bucket(f"/api/v1/users/{OTHER_ID}")
    assert bucket("/api/v1/portal/articles/a") != bucket("/api/v1/portal/departments/a")


@pytest.mark.asyncio
async def test_rate_limit_key_is_not_derived_from_spoofed_headers(monkeypatch):
    from app.shared import redis as redis_module

    monkeypatch.setattr(redis_module, "redis_pool", object())
    seen = []

    class FakeRedis:
        def __init__(self, connection_pool):
            pass

        def register_script(self, _script):
            async def run(keys, args):
                seen.extend(keys)
                return 1
            return run

        async def close(self):
            return None

    monkeypatch.setattr("app.core.middleware.rate_limit.aioredis.Redis", FakeRedis)
    middleware = RateLimitMiddleware(None)

    async def call_next(_request):
        return Response("ok")

    for slug, fake_ip in (("a", "1.1.1.1"), ("b", "2.2.2.2")):
        await middleware.dispatch(
            http_request(path=f"/api/v1/portal/articles/{slug}", headers={"X-Forwarded-For": fake_ip}),
            call_next,
        )
    assert len(seen) == 2 and seen[0] == seen[1]
    assert "203.0.113.5" in seen[0]


# ── Media ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("content_type", [
    "text/html", "TEXT/HTML; charset=utf-8", "application/xhtml+xml",
    "application/javascript", "text/xml", "application/atom+xml",
])
def test_active_document_types_are_rejected(content_type):
    assert is_active_content_type(content_type) is True


@pytest.mark.parametrize("content_type", [
    "image/png", "image/svg+xml", "application/pdf", "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
])
def test_ordinary_file_types_are_still_accepted(content_type):
    assert is_active_content_type(content_type) is False


@pytest.mark.parametrize("payload", [
    b'<svg><animate onbegin="bad()" attributeName="x"/></svg>',
    b'<svg><foreignObject><body xmlns="http://www.w3.org/1999/xhtml"></body></foreignObject></svg>',
    b'<svg><a href="JavaScript:bad()">x</a></svg>',
    b'<svg><set onend = "bad()"/></svg>',
    b'<svg>< script>bad()</script></svg>',
    b'<!DOCTYPE svg [<!ENTITY x "bad">]><svg>&x;</svg>',
    "<svg><script>bad()</script></svg>".encode("utf-16"),
])
def test_svg_scanner_blocks_known_bypasses(payload):
    assert check_svg_safety(payload) is False


def test_plain_svg_is_still_allowed():
    assert check_svg_safety(b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1z" fill="#fff"/></svg>') is True


def test_webp_signature_is_checked():
    assert validate_magic_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp") is True
    assert validate_magic_bytes(b"<html>", "image/webp") is False


@pytest.mark.parametrize("stored_type", ["text/html", "application/javascript", "", None, "application/zip"])
def test_non_passive_objects_are_forced_to_download(stored_type):
    media_type, headers = build_public_media_headers(stored_type)
    assert media_type == "application/octet-stream"
    assert headers["Content-Disposition"] == "attachment"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in headers["Content-Security-Policy"]


def test_images_stay_inline_and_svg_is_sandboxed():
    media_type, headers = build_public_media_headers("image/png")
    assert media_type == "image/png" and "Content-Disposition" not in headers
    media_type, headers = build_public_media_headers("image/svg+xml")
    assert media_type == "image/svg+xml"
    assert "sandbox" in headers["Content-Security-Policy"]


def test_vietnamese_file_names_produce_a_valid_download_header():
    value = build_content_disposition('Kế hoạch "tuyển sinh" 2026.pdf')
    Response(b"x", headers={"Content-Disposition": value})  # must be latin-1 encodable
    assert value.startswith("attachment; filename=")
    assert "filename*=UTF-8''K%E1%BA%BF%20ho%E1%BA%A1ch" in value
    assert "\n" not in build_content_disposition("a\r\nSet-Cookie: x=1.pdf")


# ── Sessions ─────────────────────────────────────────────────────────────────

def test_access_tokens_are_short_lived_by_default():
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 60


def test_tokens_issued_before_a_password_change_are_stale():
    changed = datetime.now(UTC)
    user = SimpleNamespace(password_changed_at=changed)
    assert is_token_stale(user, int((changed - timedelta(minutes=5)).timestamp())) is True
    assert is_token_stale(user, int((changed + timedelta(seconds=2)).timestamp())) is False
    assert is_token_stale(user, None) is True
    assert is_token_stale(SimpleNamespace(password_changed_at=None), 1) is False


def test_https_does_not_downgrade_cookies_to_samesite_none(monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_SAMESITE", "lax")
    response = Response()
    auth_module.set_auth_cookies(response, "access", "refresh", http_request(scheme="https"))
    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    for cookie in cookies:
        lowered = cookie.lower()
        assert "samesite=lax" in lowered
        assert "secure" in lowered and "httponly" in lowered
        assert f"max-age={settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400}" in lowered


@pytest.mark.asyncio
async def test_member_cannot_reset_own_password_without_the_current_one():
    user = SimpleNamespace(id=MEMBER_ID, password_hash="old-hash", password_changed_at=None)
    db = AsyncMock()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=user))
    member = SimpleNamespace(id=MEMBER_ID, is_admin=False)
    with pytest.raises(ForbiddenException):
        await AuthService().update_user(db, MEMBER_ID, UserUpdate(password="new-secret"), member)
    assert user.password_hash == "old-hash"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_password_reset_invalidates_existing_tokens():
    user = SimpleNamespace(id=OTHER_ID, password_hash="old-hash", password_changed_at=None)
    db = AsyncMock()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=user))
    admin = SimpleNamespace(id=MEMBER_ID, is_admin=True)
    issued_before = int(datetime.now(UTC).timestamp()) - 60
    await AuthService().update_user(db, OTHER_ID, UserUpdate(password="new-secret"), admin)
    assert user.password_hash != "old-hash"
    assert is_token_stale(user, issued_before) is True


# ── User directory ───────────────────────────────────────────────────────────

@pytest.fixture
def users_api(monkeypatch):
    now = datetime.now(UTC)
    rows = [
        SimpleNamespace(id=uid, username=name, email=f"{name}@example.test", phone="0900000000",
                        full_name=name, avatar=None, avatar_url=None, is_active=True,
                        is_admin=False, last_login=None, created_at=now)
        for uid, name in ((MEMBER_ID, "me"), (OTHER_ID, "other"))
    ]
    service = SimpleNamespace(get_users_page=AsyncMock(return_value=(rows, 2, 1)))
    monkeypatch.setattr(auth_module, "auth_service", service)
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(auth_module.users_router, prefix="/api/v1")

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    return app, service


@pytest.mark.asyncio
@pytest.mark.parametrize("admin", [False, True])
async def test_only_admins_see_other_users_contact_details(users_api, admin):
    app, service = users_api
    app.dependency_overrides[get_current_user] = lambda: UserResponse(
        id=MEMBER_ID, username="me", email="me@example.test", full_name="me",
        is_admin=admin, roles=["admin"] if admin else ["member"],
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/users?search=example")
    assert response.status_code == 200
    items = {item["username"]: item for item in response.json()["items"]}
    assert items["me"]["email"] == "me@example.test"
    assert service.get_users_page.await_args.kwargs["search_contact"] is admin
    if admin:
        assert items["other"]["email"] == "other@example.test"
        assert items["other"]["phone"] == "0900000000"
    else:
        assert items["other"]["email"] == ""
        assert items["other"]["phone"] is None


# ── Article ownership ────────────────────────────────────────────────────────

def test_only_the_author_or_an_admin_may_change_an_article():
    article = SimpleNamespace(author_id=OTHER_ID)
    guard = ArticleService._ensure_owner_or_admin
    with pytest.raises(ForbiddenException):
        guard(article, SimpleNamespace(id=MEMBER_ID, is_admin=False, roles=["member"]))
    guard(article, SimpleNamespace(id=OTHER_ID, is_admin=False, roles=["member"]))
    guard(article, SimpleNamespace(id=MEMBER_ID, is_admin=True, roles=["admin"]))


@pytest.mark.asyncio
@pytest.mark.parametrize("method,kwargs", [
    ("archive_article", {}),
    ("publish_article", {}),
    ("restore_article", {}),
    ("update_article_attributes", {"payload": SimpleNamespace(is_pinned=True)}),
])
async def test_members_cannot_change_state_of_someone_elses_article(method, kwargs):
    article = SimpleNamespace(
        id=uuid.uuid4(), author_id=OTHER_ID, status=None, is_pinned=False,
        deleted_at=datetime.now(UTC), translations=[],
    )
    db = AsyncMock()
    db.add = Mock()
    db.execute.return_value = Mock(scalars=Mock(return_value=Mock(first=Mock(return_value=article))))
    member = SimpleNamespace(id=MEMBER_ID, username="me", is_admin=False, roles=["member"])
    with pytest.raises(ForbiddenException):
        await getattr(ArticleService(), method)(db, article_id=article.id, current_user=member, **kwargs)
    assert article.is_pinned is False and article.deleted_at is not None
    db.commit.assert_not_awaited()
