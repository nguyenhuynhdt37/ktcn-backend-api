import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.database import get_db
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.middleware.rate_limit import SLIDING_WINDOW_SCRIPT, RateLimitMiddleware
from app.core.security import create_access_token
from app.main import app
from app.modules.article.models import ArticleStatus
from app.modules.article.repositories.query_builder import (
    ArticleFilterParams,
    ArticleQueryBuilder,
)
from app.modules.article.schemas.admin import (
    ArticleSEOAnalyzeRequest,
    ArticleUpdateRequest,
)
from app.modules.article.seo_service import seo_service
from app.modules.article.service import article_service
from app.modules.article.tasks import _resolve_task_article_title
from app.modules.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
)
from app.modules.auth.models import LoginHistory
from app.modules.auth.schemas import UserLogin, UserResponse
from app.modules.auth.service import AuthService
from app.modules.consultation.models import (
    ConsultationRequestType,
    ConsultationStatus,
)
from app.modules.consultation.service import consultation_service
from app.modules.media.routers.portal import validate_media_object_key
from app.modules.media.service import (
    MediaService,
    check_svg_safety,
    sanitize_image_metadata,
    sanitize_media_filename,
)
from app.modules.menu.schemas.common import (
    MenuItemReorderItem,
    MenuItemReorderRequest,
)
from app.modules.menu.service import menu_service
from app.modules.menu.target_resolver import (
    _batch_resolve_articles,
    _resolve_article,
    _validate_article,
    _validate_category,
)
from app.modules.notification.routers import notification_stream
from app.modules.setting.schemas import FooterLinkItem, resolve_setting_media_url
from app.modules.statistics.service import statistics_service
from app.modules.translation.service import TranslationService
from app.shared.redis import get_redis


def _make_user_response(
    *, is_admin: bool = False, user_id: uuid.UUID | None = None
) -> UserResponse:
    uid = user_id or uuid.uuid4()
    return UserResponse(
        id=uid,
        username="admin" if is_admin else "editor1",
        email="admin@ktcn.edu.vn" if is_admin else "editor1@ktcn.edu.vn",
        full_name="Test User",
        avatar_url=None,
        roles=["admin"] if is_admin else ["member"],
        is_active=True,
        is_admin=is_admin,
    )


class _DummyScalarResult:
    def __init__(self, scalar=None, items=None, rows=None):
        self._scalar = scalar
        self._items = items or []
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def scalars(self):
        items = self._items

        class _Scalars:
            def all(self_inner):
                return items

            def first(self_inner):
                return items[0] if items else None

        return _Scalars()

    def all(self):
        return self._rows


def _make_mock_db(execute_side_effect=None):
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.expire = MagicMock()
    db.scalar = AsyncMock(return_value=0)
    db.execute = AsyncMock(
        side_effect=execute_side_effect
        if execute_side_effect is not None
        else (lambda *args, **kwargs: _DummyScalarResult())
    )
    return db


def _make_mock_redis():
    client = MagicMock()
    client.exists = AsyncMock(return_value=0)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.incr = AsyncMock(return_value=1)
    client.zadd = AsyncMock(return_value=1)
    client.zremrangebyscore = AsyncMock(return_value=0)
    client.zcard = AsyncMock(return_value=1)
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,url",
    [
        ("GET", "/api/v1/admin/categories"),
        ("GET", "/api/v1/admin/categories/tree"),
        ("GET", "/api/v1/admin/categories/check-slug?slug=tin-tuc"),
        ("GET", f"/api/v1/admin/categories/{uuid.uuid4()}"),
        ("GET", "/api/v1/admin/tags"),
        ("GET", "/api/v1/admin/tags/check-slug?slug=ai"),
        ("GET", "/api/v1/admin/articles/check-slug?slug=tuyen-sinh"),
    ],
)
async def test_previously_unauthenticated_admin_routes_require_auth(
    clean_overrides, method: str, url: str
):
    app.dependency_overrides[get_db] = lambda: _make_mock_db()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.request(method, url)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_seo_analyze_blocks_other_users_private_draft(clean_overrides):
    owner_id = uuid.uuid4()
    other_user = _make_user_response(is_admin=False, user_id=uuid.uuid4())
    draft_article = SimpleNamespace(
        id=uuid.uuid4(),
        author_id=owner_id,
        is_draft=True,
        thumbnail_object_key=None,
    )
    lang_row = uuid.uuid4()
    translation_row = SimpleNamespace(
        title="Secret draft",
        content="<p>Internal</p>",
        excerpt="",
        seo_title="",
        seo_description="",
        slug="secret-draft",
    )

    def _side_effect(*_args, **_kwargs):
        return _DummyScalarResult(scalar=draft_article)

    results = iter([
        _DummyScalarResult(scalar=draft_article),
        _DummyScalarResult(scalar=lang_row),
        _DummyScalarResult(scalar=translation_row),
    ])
    db = _make_mock_db(execute_side_effect=lambda *a, **kw: next(results))

    payload = ArticleSEOAnalyzeRequest(lang="vi")
    with pytest.raises(ForbiddenException):
        await seo_service.analyze_article(db, draft_article.id, payload, other_user)

    app.dependency_overrides[get_current_user] = lambda: other_user
    app.dependency_overrides[get_db] = lambda: _make_mock_db(
        execute_side_effect=_side_effect
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            f"/api/v1/admin/articles/{draft_article.id}/seo/analyze",
            json={"lang": "vi"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_global_search_runs_sequentially_and_hides_user_email_for_non_admin(
    clean_overrides,
):
    editor = _make_user_response(is_admin=False)
    in_flight = False
    captured_sql: list[str] = []

    class _SequentialDB:
        async def execute(self, stmt):
            nonlocal in_flight
            assert not in_flight, "AsyncSession.execute called concurrently!"
            in_flight = True
            try:
                sql = str(stmt)
                captured_sql.append(sql)
                if "FROM users" in sql:
                    return _DummyScalarResult(
                        rows=[
                            SimpleNamespace(
                                id=uuid.uuid4(),
                                full_name="Alice",
                                email="alice@ktcn.edu.vn",
                                username="alice",
                            )
                        ]
                    )
                return _DummyScalarResult(rows=[])
            finally:
                in_flight = False

    app.dependency_overrides[get_current_user] = lambda: editor
    app.dependency_overrides[get_db] = lambda: _SequentialDB()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/v1/admin/search?q=alice")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["users"]) == 1
    assert data["users"][0]["email"] is None
    user_queries = [s for s in captured_sql if "FROM users" in s]
    assert user_queries and "users.email" not in user_queries[0].split("WHERE")[1]
    article_queries = [s for s in captured_sql if "FROM articles" in s]
    assert article_queries and "is_draft" in article_queries[0]


@pytest.mark.asyncio
async def test_global_search_returns_email_for_admin(clean_overrides):
    admin = _make_user_response(is_admin=True)

    class _AdminDB:
        async def execute(self, stmt):
            if "FROM users" in str(stmt):
                return _DummyScalarResult(
                    rows=[
                        SimpleNamespace(
                            id=uuid.uuid4(),
                            full_name="Alice",
                            email="alice@ktcn.edu.vn",
                            username="alice",
                        )
                    ]
                )
            return _DummyScalarResult(rows=[])

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: _AdminDB()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/v1/admin/search?q=alice")

    assert resp.status_code == 200
    assert resp.json()["users"][0]["email"] == "alice@ktcn.edu.vn"


@pytest.mark.asyncio
async def test_ai_hub_playground_redacts_internal_errors(clean_overrides):
    admin = _make_user_response(is_admin=True)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: _make_mock_db()

    fake_ai = MagicMock()
    fake_ai.generate_text = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused to http://10.0.0.99:8090")
    )
    fake_ai.generate_embedding = AsyncMock(
        side_effect=RuntimeError("db password leak")
    )

    with patch("app.shared.ai.get_ai_service", return_value=fake_ai):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            r1 = await client.post(
                "/api/v1/ai-hub/playground",
                json={"prompt": "hello", "model": "gemini-flash"},
            )
            r2 = await client.post(
                "/api/v1/ai-hub/embedding-playground",
                json={"input": "hello", "model": "gemini-embedding-2"},
            )

    assert r1.status_code == 503
    assert "10.0.0.99" not in r1.text
    assert r2.status_code == 500
    assert "password" not in r2.text


@pytest.mark.asyncio
async def test_auth_failed_login_commits_history_and_unlock_rejects_deleted():
    service = AuthService()
    user_row = SimpleNamespace(
        id=uuid.uuid4(),
        username="u1",
        password_hash="not-matching",
        is_active=True,
        deleted_at=None,
        last_login=None,
    )
    db = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=user_row)
    )
    with patch("app.modules.auth.service.verify_password", return_value=False):
        with pytest.raises(UnauthorizedException):
            await service.authenticate(
                db, UserLogin(username="u1", password="wrong"), "1.2.3.4", "UA"
            )
    assert db.add.called
    assert isinstance(db.add.call_args[0][0], LoginHistory)
    assert db.commit.await_count == 1

    deleted_user = SimpleNamespace(
        id=uuid.uuid4(), deleted_at=datetime.now(UTC), is_active=False
    )
    db2 = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=deleted_user)
    )
    with pytest.raises(BadRequestException):
        await service.unlock_user(db2, deleted_user.id)

    db3 = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=deleted_user)
    )
    await service.delete_user(db3, deleted_user.id, _make_user_response(is_admin=True))
    assert db3.execute.await_count >= 2  # get_user_detail + update(RefreshToken)
    assert db3.commit.await_count == 1


@pytest.mark.asyncio
async def test_soft_deleted_user_rejected_in_dependencies():
    deleted_user = SimpleNamespace(
        id=uuid.uuid4(),
        username="ghost",
        email="ghost@ktcn.edu.vn",
        full_name="Ghost",
        avatar=None,
        avatar_url=None,
        is_active=True,
        is_admin=False,
        deleted_at=datetime.now(UTC),
        tokens_valid_after=None,
    )
    token = create_access_token(str(deleted_user.id))
    db = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=deleted_user)
    )
    opt_user = await get_current_user_optional(
        access_token=token, http_auth=None, db=db
    )
    assert opt_user is None
    with pytest.raises(UnauthorizedException):
        await get_current_user(access_token=token, http_auth=None, db=db)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/users?page=0&page_size=0",
        f"/api/v1/users/{uuid.uuid4()}/login-history?page_size=0",
        "/api/v1/admin/profile/login-history?page=0&page_size=0",
        "/api/v1/admin/profile/activity?limit=0",
        "/api/v1/admin/audit-logs?page_size=0",
    ],
)
async def test_pagination_bounds_reject_zero_and_negative(clean_overrides, url: str):
    admin = _make_user_response(is_admin=True)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: _make_mock_db()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get(url)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_logout_all_clears_both_cookies(clean_overrides):
    admin = _make_user_response(is_admin=True)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: _make_mock_db()

    with (
        patch("app.modules.auth.router.auth_service.logout_all", new=AsyncMock()),
        patch("app.modules.auth.router.log_action", new=AsyncMock()),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post("/api/v1/auth/logout-all")

    assert resp.status_code == 200
    set_cookies = resp.headers.get_list("set-cookie")
    assert any("access_token=" in c for c in set_cookies)
    assert any("refresh_token=" in c for c in set_cookies)


@pytest.mark.asyncio
async def test_notification_subscribe_uses_verified_optional_user(clean_overrides):
    user = _make_user_response(is_admin=False)
    app.dependency_overrides[get_current_user_optional] = lambda: user
    app.dependency_overrides[get_db] = lambda: _make_mock_db()

    with patch(
        "app.modules.notification.routers.notification_service.subscribe_device",
        new=AsyncMock(),
    ) as sub_mock:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                "/api/v1/portal/notifications/subscribe",
                json={
                    "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
                    "keys": {"p256dh": "k1", "auth": "k2"},
                },
            )
    assert resp.status_code == 200
    assert sub_mock.await_args.kwargs["user_id"] == user.id


@pytest.mark.asyncio
async def test_bulk_update_status_handles_translations_and_reverts_on_log_error():
    admin = _make_user_response(is_admin=True)
    art_ok = SimpleNamespace(
        id=uuid.uuid4(),
        author_id=admin.id,
        status=ArticleStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        last_edited_at=None,
        deleted_at=None,
        translations=[
            SimpleNamespace(language=SimpleNamespace(code="vi"), title="Bài viết 1")
        ],
    )
    art_fail = SimpleNamespace(
        id=uuid.uuid4(),
        author_id=admin.id,
        status=ArticleStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        last_edited_at=None,
        deleted_at=None,
        translations=[
            SimpleNamespace(language=SimpleNamespace(code="vi"), title="Bài viết 2")
        ],
    )
    db = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(
            items=[art_ok, art_fail]
        )
    )
    logged_titles: list[str] = []

    async def fake_log(_db, _user, _action, _type, target_id, details):
        if target_id == art_fail.id:
            raise RuntimeError("audit failure")
        logged_titles.append(details["title"])

    with patch("app.modules.audit.service.log_action", side_effect=fake_log):
        res = await article_service.bulk_update_status(
            db,
            article_ids=[art_ok.id, art_fail.id],
            action="archive",
            current_user=admin,
        )

    assert res.success_count == 1
    assert res.failed_count == 1
    assert logged_titles == ["Bài viết 1"]
    assert art_ok.status == ArticleStatus.ARCHIVED
    assert art_fail.status == ArticleStatus.PUBLISHED


def test_query_builder_correlates_tag_language():
    qb = ArticleQueryBuilder(db=_make_mock_db()).filter(
        ArticleFilterParams(tag_slug="ai")
    )
    sql = str(qb.query)
    assert "tag_translations.language_id" in sql or "languages.code" in sql
    assert "EXISTS" in sql.upper()


@pytest.mark.asyncio
async def test_target_resolver_handles_translated_category_and_article():
    cat = SimpleNamespace(
        id=uuid.uuid4(),
        status="INACTIVE",
        deleted_at=None,
        translations=[
            SimpleNamespace(
                language=SimpleNamespace(code="vi"),
                name="Tin tức",
                slug="tin-tuc",
                description=None,
                seo_title=None,
                seo_description=None,
            )
        ],
    )
    db_cat = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=cat)
    )
    with pytest.raises(BadRequestException) as exc:
        await _validate_category(db_cat, cat.id)
    assert "Tin tức" in exc.value.message

    art = SimpleNamespace(
        id=uuid.uuid4(),
        status=ArticleStatus.PUBLISHED,
        deleted_at=None,
        translations=[
            SimpleNamespace(
                language=SimpleNamespace(code="vi"),
                title="Chào tân sinh viên",
                slug="chao-tan-sinh-vien",
                excerpt=None,
                content="",
                seo_title=None,
                seo_description=None,
                canonical_url=None,
                robots=None,
                og_title=None,
                og_description=None,
                og_image=None,
            )
        ],
    )
    db_art = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=art)
    )
    await _validate_article(db_art, art.id)
    info = await _resolve_article(db_art, art.id, lang="vi")
    assert info.name == "Chào tân sinh viên"
    assert info.slug == "chao-tan-sinh-vien"

    db_batch = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(items=[art])
    )
    batch = await _batch_resolve_articles(db_batch, [art.id], lang="vi")
    assert batch[art.id].name == "Chào tân sinh viên"


@pytest.mark.asyncio
async def test_menu_reorder_rejects_unknown_parent_id():
    item_id = uuid.uuid4()
    missing_parent = uuid.uuid4()
    fake_menu = SimpleNamespace(id=uuid.uuid4())
    existing_item = SimpleNamespace(id=item_id, parent_id=None, sort_order=0, depth=1)

    with (
        patch.object(menu_service, "get_menu_by_id", AsyncMock(return_value=fake_menu)),
        pytest.raises(NotFoundException),
    ):
        db = _make_mock_db(
            execute_side_effect=lambda *a, **kw: _DummyScalarResult(
                items=[existing_item]
            )
        )
        req = MenuItemReorderRequest(
            items=[
                MenuItemReorderItem(
                    id=item_id, parent_id=missing_parent, sort_order=1
                )
            ]
        )
        await menu_service.reorder_items(db, fake_menu.id, req)


@pytest.mark.asyncio
async def test_consultation_csv_export_neutralizes_formula_injection(clean_overrides):
    admin = _make_user_response(is_admin=True)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db] = lambda: _make_mock_db()

    row = SimpleNamespace(
        reference_code="KTCN-01",
        full_name="=CMD|'/C calc'!A0",
        phone="+84901234567",
        email="a@b.vn",
        interested_major="-1+1",
        request_type=ConsultationRequestType.ADMISSION_CONSULTING,
        status=ConsultationStatus.NEW,
        created_at=datetime.now(UTC),
        message=" @SUM(1,2)",
        admin_notes="\tHYPERLINK(\"http://evil\")",
    )
    with patch.object(
        consultation_service, "list_admin", AsyncMock(return_value=([row], 1))
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/v1/admin/consultations/export")

    assert resp.status_code == 200
    body = resp.text
    assert "'=CMD" in body
    assert "'+84901234567" in body
    assert "'-1+1" in body
    assert "' @SUM(1,2)" in body
    assert "'\tHYPERLINK" in body


@pytest.mark.asyncio
async def test_translation_does_not_cache_on_ai_failure():
    svc = TranslationService()
    svc.ai_service = MagicMock()
    svc.ai_service.generate_text = AsyncMock(side_effect=RuntimeError("AI down"))
    svc._get_cache = AsyncMock(return_value=None)
    svc._set_cache = AsyncMock()

    res_text = await svc.translate_text("Xin chào bạn", ["vi", "en"])
    assert res_text["en"] == "Xin chào bạn"
    assert svc._set_cache.await_count == 0

    res_batch = await svc.translate_batch(["Xin chào bạn"], ["en"])
    assert res_batch[0]["en"] == "Xin chào bạn"
    assert svc._set_cache.await_count == 0

    res_html = await svc.translate_html("<p>Xin chào</p>", ["en"])
    assert res_html["en"] == "<p>Xin chào</p>"
    assert svc._set_cache.await_count == 0


def test_setting_url_and_media_sanitizer():
    with pytest.raises(ValidationError):
        FooterLinkItem(label_vi="X", label_en="X", href="java\tscript:alert(1)")
    with pytest.raises(ValidationError):
        FooterLinkItem(label_vi="X", label_en="X", href="file:///etc/passwd")
    assert resolve_setting_media_url("data:text/html,<script>") is None
    assert resolve_setting_media_url("data:image/svg+xml,<svg/>") is None
    data_png = "data:image/png;base64,abc"
    assert resolve_setting_media_url(data_png) == data_png


@pytest.mark.asyncio
async def test_health_endpoint_redacts_internal_errors(clean_overrides):
    class _BrokenDB:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError(
                "password authentication failed for user postgres@10.0.0.2"
            )

    class _BrokenRedis:
        async def ping(self):
            raise ConnectionError("Error connecting to 127.0.0.1:6379 secret")

    app.dependency_overrides[get_db] = lambda: _BrokenDB()
    app.dependency_overrides[get_redis] = lambda: _BrokenRedis()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "unhealthy"
    assert payload["details"]["postgres"] == "unhealthy"
    assert payload["details"]["redis"] == "unhealthy"


@pytest.mark.asyncio
async def test_rate_limiter_guards_and_lua_uniqueness():
    mw = RateLimitMiddleware(app=MagicMock())
    assert ":seq" in SLIDING_WINDOW_SCRIPT
    assert mw._get_limit_for_path("/api/v1/auth/refresh")[2] == "auth"
    assert mw._get_limit_for_path("/api/v1/admin/profile/password")[2] == "auth"

    no_sub_token = create_access_token(subject="user-1")
    req = SimpleNamespace(cookies={"access_token": no_sub_token}, headers={})
    with patch(
        "app.core.middleware.rate_limit.decode_access_token",
        return_value={"sub": None},
    ):
        assert mw._get_user_id_from_token(req) is None


@pytest.mark.asyncio
async def test_portal_article_rejects_malicious_guest_uuid_cookie(clean_overrides):
    art = SimpleNamespace(
        id=uuid.uuid4(),
        view_count=5,
        status=ArticleStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        is_pinned=False,
        is_featured=False,
        reading_time_minutes=1,
        thumbnail_object_key=None,
        category=None,
        author=None,
        tags=[],
        translations=[],
        title="Test",
        slug="test",
        excerpt=None,
        content="Body",
        seo_title=None,
        seo_description=None,
        canonical_url=None,
        robots=None,
        og_title=None,
        og_description=None,
        og_image=None,
    )
    app.dependency_overrides[get_db] = lambda: _make_mock_db()
    fake_redis = _make_mock_redis()
    app.dependency_overrides[get_redis] = lambda: fake_redis

    captured_kwargs = {}

    async def fake_get_article(db, **kwargs):
        captured_kwargs.update(kwargs)
        return art

    with patch(
        "app.modules.article.routers.portal.article_service.get_article_by_slug_portal",
        side_effect=fake_get_article,
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/portal/articles/test",
                cookies={"guest_uuid": "bad-value:injected"},
            )

    assert resp.status_code == 200
    parsed = str(uuid.UUID(captured_kwargs["guest_uuid"]))
    assert parsed == captured_kwargs["guest_uuid"]
    assert any("guest_uuid=" in c for c in resp.headers.get_list("set-cookie"))


@pytest.mark.asyncio
async def test_statistics_record_visit_uses_atomic_nx():
    fake_redis = _make_mock_redis()
    fake_redis.set = AsyncMock(side_effect=[True, False])  # ip already claimed
    db = _make_mock_db()
    await statistics_service.record_visit(
        guest_uuid=str(uuid.uuid4()),
        client_ip="1.2.3.4",
        redis_client=fake_redis,
        db=db,
    )
    assert fake_redis.incr.await_count == 0
    assert db.commit.await_count == 0


def test_media_traversal_svg_entity_filename_and_bomb_guards():
    assert check_svg_safety(b"<svg><circle /></svg>") is True
    assert check_svg_safety(
        b'<svg><a href="&#106;avascript:alert(1)">x</a></svg>'
    ) is False
    assert check_svg_safety(
        b'<svg><a href="java&#x09;script:alert(1)">x</a></svg>'
    ) is False
    assert check_svg_safety(b'<?xml-stylesheet href="evil.xsl"?><svg/>') is False
    assert check_svg_safety(
        b'<svg><image href="data:image/svg+xml;base64,PHN2Zz4="/></svg>'
    ) is False

    assert validate_media_object_key("files/abc123") == "files/abc123"
    bad_keys = (
        "../secret",
        "files/../secret",
        "/etc/passwd",
        "files\\evil",
        "files/a\x00b",
    )
    for bad_key in bad_keys:
        with pytest.raises(HTTPException):
            validate_media_object_key(bad_key)

    assert sanitize_media_filename("../../evil\r\n.png") == "evil.png"
    long_name = sanitize_media_filename("a" * 300 + ".jpg")
    assert len(long_name) <= 255 and long_name.endswith(".jpg")

    fake_img = SimpleNamespace(width=10000, height=10000)
    with patch("app.modules.media.service.Image.open", return_value=fake_img):
        with pytest.raises(ValueError):
            sanitize_image_metadata(b"fake")


@pytest.mark.asyncio
async def test_media_folder_descendant_cycle_guard():
    svc = MediaService.__new__(MediaService)
    f1, f2 = uuid.uuid4(), uuid.uuid4()
    target = uuid.uuid4()
    parents = iter([f2, f1])
    db = _make_mock_db(
        execute_side_effect=lambda *a, **kw: _DummyScalarResult(scalar=next(parents))
    )
    assert await svc._is_folder_descendant_of(db, f1, target) is False


@pytest.mark.asyncio
async def test_article_update_commits_audit_and_dedupes_tag_ids():
    admin = _make_user_response(is_admin=True)
    dup_tag_id = uuid.uuid4()
    tag_obj = SimpleNamespace(id=dup_tag_id, usage_count=0)
    article_obj = SimpleNamespace(
        id=uuid.uuid4(),
        author_id=admin.id,
        category_id=None,
        status=ArticleStatus.PUBLISHED,
        is_draft=True,
        is_pinned=False,
        thumbnail_object_key=None,
        cover_object_key=None,
        department_id=None,
        program_id=None,
        article_type=None,
        published_at=None,
        publish_at=None,
        expire_at=None,
        last_edited_at=None,
        tags=[],
        translations=[
            SimpleNamespace(language=SimpleNamespace(code="vi"), title="Draft title")
        ],
    )
    results = iter([
        _DummyScalarResult(items=[article_obj]),  # find existing article
        _DummyScalarResult(items=[tag_obj]),  # Tag query with deduped IN
        _DummyScalarResult(items=[article_obj]),  # stmt_reload
    ])
    db = _make_mock_db(execute_side_effect=lambda *a, **kw: next(results))

    payload = ArticleUpdateRequest(is_draft=True, tag_ids=[dup_tag_id, dup_tag_id])
    with patch("app.modules.audit.service.log_action", new=AsyncMock()) as mock_log:
        reloaded = await article_service.update_article(
            db, article_id=article_obj.id, payload=payload, current_user=admin
        )

    assert reloaded is article_obj
    assert mock_log.await_count == 1
    assert db.commit.await_count == 2  # article update + audit log commit
    assert tag_obj.usage_count == 1


@pytest.mark.asyncio
async def test_portal_article_service_filters_drafts_and_tolerates_redis_failure():
    art = SimpleNamespace(
        id=uuid.uuid4(),
        view_count=2,
        category=None,
        tags=[],
        translations=[
            SimpleNamespace(
                language=SimpleNamespace(code="vi"),
                title="Public News",
                slug="public-news",
                excerpt=None,
                content="Body",
                seo_title=None,
                seo_description=None,
                canonical_url=None,
                robots=None,
                og_title=None,
                og_description=None,
                og_image=None,
            )
        ],
    )
    captured_sql: list[str] = []

    async def fake_execute(stmt):
        sql = str(stmt)
        captured_sql.append(sql)
        if "FROM languages" in sql:
            return _DummyScalarResult(scalar=uuid.uuid4())
        return _DummyScalarResult(items=[art])

    db = _make_mock_db(execute_side_effect=fake_execute)
    broken_redis = _make_mock_redis()
    broken_redis.exists = AsyncMock(side_effect=ConnectionError("Redis down"))
    broken_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))

    result = await article_service.get_article_by_slug_portal(
        db,
        slug="public-news",
        lang="vi",
        guest_uuid="not-a-valid-uuid",
        client_ip="127.0.0.1",
        redis_client=broken_redis,
    )

    assert result.view_count == 3
    article_sql = [s for s in captured_sql if "FROM articles" in s]
    assert article_sql and "is_draft IS false" in article_sql[0]


def test_task_article_title_resolution():
    art = SimpleNamespace(
        id=uuid.uuid4(),
        translations=[
            SimpleNamespace(language=SimpleNamespace(code="en"), title="English"),
            SimpleNamespace(language=SimpleNamespace(code="vi"), title="Tiếng Việt"),
        ],
    )
    assert _resolve_task_article_title(art) == "Tiếng Việt"
    assert _resolve_task_article_title(SimpleNamespace(translations=[])) == "Chưa dịch"


@pytest.mark.asyncio
async def test_notification_stream_closes_pubsub_on_subscribe_error():
    user = _make_user_response()
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock(side_effect=RuntimeError("Redis pubsub error"))
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    redis_client = MagicMock()
    redis_client.pubsub = MagicMock(return_value=pubsub)

    resp = await notification_stream(current_user=user, redis_client=redis_client)
    with pytest.raises(RuntimeError):
        await anext(resp.body_iterator)
    assert pubsub.close.await_count == 1


@pytest.mark.asyncio
async def test_media_upload_cleans_up_s3_if_db_commit_fails():
    svc = MediaService.__new__(MediaService)
    deleted_keys: list[str] = []

    def fake_put_object(**_kwargs):
        return {}

    def fake_delete_object(**kwargs):
        deleted_keys.append(kwargs["Key"])
        return {}

    svc.s3_client = MagicMock()
    svc.s3_client.put_object = fake_put_object
    svc.s3_client.delete_object = fake_delete_object

    db = _make_mock_db()
    db.commit = AsyncMock(side_effect=RuntimeError("DB insert failed"))

    valid_pdf = b"%PDF-1.4\n%test"
    with pytest.raises(RuntimeError):
        await svc.upload_file(db, valid_pdf, "../../bad\r\n.pdf", "application/pdf")

    assert db.rollback.await_count == 1
    assert len(deleted_keys) == 1
    assert deleted_keys[0].startswith("files/")


@pytest.mark.asyncio
async def test_visitor_counter_middleware_replaces_invalid_guest_cookie():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    import app.shared.redis as redis_shared
    from app.core.middleware.visitor_counter import VisitorCounterMiddleware

    inner = Starlette(
        routes=[
            Route("/api/v1/portal/statistics", lambda _req: JSONResponse({"ok": True}))
        ]
    )
    inner.add_middleware(VisitorCounterMiddleware)
    fake_redis = _make_mock_redis()

    with (
        patch.object(redis_shared, "redis_pool", object()),
        patch(
            "app.core.middleware.visitor_counter.aioredis.Redis",
            return_value=fake_redis,
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=inner),
            base_url="http://testserver",
        ) as client:
            resp = await client.get(
                "/api/v1/portal/statistics",
                headers={"User-Agent": "Mozilla/5.0"},
                cookies={"guest_uuid": "bad-cookie\r\ninjected"},
            )

    assert resp.status_code == 200
    assert fake_redis.zadd.await_count == 1
    member_key = next(iter(fake_redis.zadd.await_args.args[1].keys()))
    assert str(uuid.UUID(member_key)) == member_key
    assert any("guest_uuid=" in c for c in resp.headers.get_list("set-cookie"))


def test_media_service_uses_lazy_minio_init():
    with patch("app.modules.media.service.boto3.client") as mock_boto:
        svc = MediaService()
        assert mock_boto.call_count == 0
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        assert svc.s3_client is mock_client
        assert mock_boto.call_count == 1
        assert svc.s3_client is mock_client
        assert mock_boto.call_count == 1


@pytest.mark.asyncio
async def test_save_log_to_db_does_not_commit_caller_session():
    from app.shared.ai.providers.omniroute import save_log_to_db

    caller_db = _make_mock_db()
    indep_session = _make_mock_db()
    indep_cm = MagicMock()
    indep_cm.__aenter__ = AsyncMock(return_value=indep_session)
    indep_cm.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.shared.ai.providers.omniroute.SessionLocal", return_value=indep_cm
    ):
        await save_log_to_db(
            model="gemini-2.5-flash",
            prompt="hello",
            response="world",
            db_session=caller_db,
        )

    assert caller_db.commit.await_count == 0
    assert caller_db.add.call_count == 0
    assert indep_session.add.call_count == 1
    assert indep_session.commit.await_count == 1


@pytest.mark.asyncio
async def test_rate_limit_middleware_falls_back_to_memory_when_redis_fails():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    import app.shared.redis as redis_shared

    inner = Starlette(
        routes=[
            Route(
                "/api/v1/auth/login",
                lambda _req: JSONResponse({"ok": True}),
                methods=["POST"],
            )
        ]
    )
    inner.add_middleware(RateLimitMiddleware)

    broken_redis = _make_mock_redis()
    broken_redis.register_script = MagicMock(
        return_value=AsyncMock(side_effect=ConnectionError("Redis unreachable"))
    )

    with (
        patch.object(redis_shared, "redis_pool", object()),
        patch(
            "app.core.middleware.rate_limit.aioredis.Redis",
            return_value=broken_redis,
        ),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=inner),
            base_url="http://testserver",
        ) as client:
            statuses = []
            for _ in range(6):
                r = await client.post("/api/v1/auth/login")
                statuses.append(r.status_code)

    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert statuses[5] == 429


@pytest.mark.asyncio
async def test_shared_check_rate_limit_falls_back_to_memory_when_redis_fails():
    from app.shared.rate_limiter import check_rate_limit, clear_memory_rate_limit

    broken_redis = MagicMock()
    broken_redis.incr = AsyncMock(side_effect=ConnectionError("Redis down"))
    key = f"rate_limit:login:test-{uuid.uuid4()}"
    try:
        for _ in range(3):
            allowed, _, _ = await check_rate_limit(
                broken_redis, key, max_attempts=3, window_seconds=60
            )
            assert allowed is True
        allowed_4th, remaining, retry_after = await check_rate_limit(
            broken_redis, key, max_attempts=3, window_seconds=60
        )
        assert allowed_4th is False
        assert remaining == 0
        assert retry_after >= 1
    finally:
        clear_memory_rate_limit(key)


def test_settings_production_safe_defaults_and_dev_compatibility(monkeypatch):
    from app.core.config import Settings

    for var in (
        "ENV",
        "DEBUG",
        "COOKIE_SECURE",
        "ALLOWED_HOSTS",
        "SECRET_KEY",
        "POSTGRES_PASSWORD",
        "MINIO_SECRET_KEY",
        "AI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    prod_default = Settings(_env_file=None)
    assert prod_default.ENV == "production"
    assert prod_default.DEBUG is False
    assert prod_default.COOKIE_SECURE is True
    # Not configured explicitly -> backward compatible wildcard.
    assert prod_default.ALLOWED_HOSTS == ["*"]
    # Configured explicitly -> restricted exactly as configured.
    restricted = Settings(
        _env_file=None, ALLOWED_HOSTS='["api.example.com"]', SECRET_KEY="x" * 40
    )
    assert restricted.ALLOWED_HOSTS == ["api.example.com"]
    assert prod_default.POSTGRES_PASSWORD == ""
    assert prod_default.MINIO_SECRET_KEY == ""
    assert prod_default.AI_API_KEY == ""
    assert len(prod_default.SECRET_KEY) >= 32

    with pytest.raises(ValidationError):
        Settings(_env_file=None, ENV="production", SECRET_KEY="")

    dev_cfg = Settings(_env_file=None, ENV="development")
    assert dev_cfg.ENV == "development"
    assert dev_cfg.COOKIE_SECURE is False
