"""HTTP regression tests for account ownership and administrative permissions."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI

from app.core.database import get_db
from app.core.exceptions import setup_exception_handlers
from app.modules.auth import router as auth_module
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserResponse

MEMBER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OTHER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
SESSION_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")

ACCOUNT_CASES = [
    ("GET", "", "get_user_detail"),
    ("GET", "/sessions", "get_user_sessions"),
    ("GET", "/login-history", "get_login_history"),
    ("GET", "/anomalies", "get_anomaly_report"),
    ("POST", f"/sessions/{SESSION_ID}/revoke", "revoke_user_session"),
    ("POST", "/sessions/revoke-all", "revoke_all_user_sessions"),
    ("POST", "/lock", "lock_user"),
    ("POST", "/unlock", "unlock_user"),
]


def account_detail(user_id):
    return {
        "id": user_id,
        "username": "test-member",
        "email": "member@example.test",
        "phone": None,
        "full_name": "Test Member",
        "bio": None,
        "title": None,
        "avatar_id": None,
        "avatar": None,
        "avatar_url": None,
        "is_active": True,
        "is_admin": False,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


@pytest.fixture
def account_api(monkeypatch):
    db = AsyncMock()
    service = SimpleNamespace(
        get_user_detail=AsyncMock(return_value=account_detail(OTHER_ID)),
        get_user_sessions=AsyncMock(return_value=[]),
        get_login_history=AsyncMock(
            return_value={"items": [], "total": 0, "page": 1,
                          "page_size": 20, "total_pages": 0}
        ),
        get_anomaly_report=AsyncMock(
            return_value={"user_id": OTHER_ID, "risk_level": "SAFE",
                          "anomalies": [], "active_session_count": 0,
                          "failed_login_count_24h": 0,
                          "generated_at": datetime.now(UTC)}
        ),
        revoke_user_session=AsyncMock(),
        revoke_all_user_sessions=AsyncMock(return_value=1),
        lock_user=AsyncMock(
            return_value={"success": True, "message": "locked",
                          "user_id": OTHER_ID, "is_active": False}
        ),
        unlock_user=AsyncMock(
            return_value={"success": True, "message": "unlocked",
                          "user_id": OTHER_ID, "is_active": True}
        ),
    )
    monkeypatch.setattr(auth_module, "auth_service", service)
    monkeypatch.setattr(auth_module, "log_action", AsyncMock())
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(auth_module.router, prefix="/api/v1")
    app.include_router(auth_module.users_router, prefix="/api/v1")

    async def fake_db():
        yield db

    app.dependency_overrides[get_db] = fake_db
    return app, service


def authenticate(app, *, admin=False):
    user = UserResponse(
        id=MEMBER_ID, username="test-member", email="member@example.test",
        full_name="Test Member", is_admin=admin,
        roles=["admin"] if admin else ["member"],
    )
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.mark.parametrize("method,suffix,service_method", ACCOUNT_CASES)
async def test_member_cannot_access_another_accounts_private_operations(
    account_api, method, suffix, service_method
):
    app, service = account_api
    authenticate(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, f"/api/v1/users/{OTHER_ID}{suffix}")
    assert response.status_code == 403
    getattr(service, service_method).assert_not_awaited()


@pytest.mark.parametrize("method,suffix,service_method", ACCOUNT_CASES[:6])
async def test_member_can_access_own_account_and_revoke_own_sessions(
    account_api, method, suffix, service_method
):
    app, service = account_api
    authenticate(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, f"/api/v1/users/{MEMBER_ID}{suffix}")
    assert response.status_code == 200
    assert getattr(service, service_method).await_args.args[1] == MEMBER_ID


@pytest.mark.parametrize("method,suffix,service_method", ACCOUNT_CASES)
async def test_admin_can_manage_other_accounts(
    account_api, method, suffix, service_method
):
    app, service = account_api
    authenticate(app, admin=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, f"/api/v1/users/{OTHER_ID}{suffix}")
    assert response.status_code == 200
    assert getattr(service, service_method).await_args.args[1] == OTHER_ID


@pytest.mark.parametrize("method,suffix,service_method", ACCOUNT_CASES)
async def test_unauthenticated_account_requests_are_rejected(
    account_api, method, suffix, service_method
):
    app, service = account_api
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, f"/api/v1/users/{OTHER_ID}{suffix}")
    assert response.status_code == 401
    getattr(service, service_method).assert_not_awaited()


@pytest.mark.parametrize("suffix", ["/lock", "/unlock"])
async def test_member_cannot_lock_or_unlock_even_own_account(account_api, suffix):
    app, service = account_api
    authenticate(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(f"/api/v1/users/{MEMBER_ID}{suffix}")
    assert response.status_code == 403
    service.lock_user.assert_not_awaited()
    service.unlock_user.assert_not_awaited()


@pytest.fixture
def ai_api(monkeypatch):
    from app.modules.ai_hub.routers import admin as ai_module
    from app.modules.translation.routers import admin as translation_module
    from app.shared.ai import get_ai_service

    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(ai_module.ai_hub_router, prefix="/api/v1/ai-hub")
    app.include_router(translation_module.translation_router,
                       prefix="/api/v1/translation")
    writes = Mock()
    monkeypatch.setattr(ai_module, "save_active_model", writes)
    monkeypatch.setattr(ai_module, "save_active_embedding_model", writes)
    monkeypatch.setattr(translation_module, "save_active_model", writes)
    monkeypatch.setattr(translation_module, "get_active_model", lambda: "test-model")
    logs = AsyncMock(return_value=(0, []))
    spend = AsyncMock(return_value=([], []))
    monkeypatch.setattr(ai_module.ai_hub_service, "get_logs", logs)
    monkeypatch.setattr(ai_module.ai_hub_service, "get_spend_statistics", spend)
    translate = AsyncMock(return_value={"en": "Hello"})
    monkeypatch.setattr(translation_module.translation_service,
                        "translate_text", translate)

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_ai_service] = lambda: SimpleNamespace(
        list_models=AsyncMock(return_value=[{"id": "test-model"}])
    )
    return app, writes, logs, spend


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/v1/ai-hub/settings", {"active_model": "test-model"}),
    ("POST", "/api/v1/translation/ai/settings", {"active_model": "test-model"}),
    ("GET", "/api/v1/ai-hub/logs", None),
    ("GET", "/api/v1/ai-hub/spend", None),
])
async def test_member_cannot_change_global_ai_settings_or_read_others_usage(
    ai_api, method, path, body
):
    app, writes, logs, spend = ai_api
    authenticate(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, path, json=body)
    assert response.status_code == 403
    writes.assert_not_called()
    logs.assert_not_awaited()
    spend.assert_not_awaited()


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/v1/ai-hub/settings", {"active_model": "test-model"}),
    ("POST", "/api/v1/translation/ai/settings", {"active_model": "test-model"}),
    ("GET", "/api/v1/ai-hub/logs", None),
    ("GET", "/api/v1/ai-hub/spend", None),
])
async def test_admin_retains_global_ai_administration(ai_api, method, path, body):
    app, _, _, _ = ai_api
    authenticate(app, admin=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(method, path, json=body)
    assert response.status_code == 200


async def test_member_retains_translation_and_model_selection(ai_api):
    app, _, _, _ = ai_api
    authenticate(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        models = await client.get("/api/v1/translation/ai/models")
        translation = await client.post(
            "/api/v1/translation", json={"text": "Xin chào", "target_languages": ["en"]}
        )
    assert models.status_code == 200
    assert models.json()["models"] == [{"id": "test-model"}]
    assert translation.status_code == 200
    assert translation.json() == {"en": "Hello"}
