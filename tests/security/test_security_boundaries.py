import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.exceptions import validation_exception_handler
from app.core.middleware.security import RequestSizeLimiterMiddleware
from app.modules.audit.service import log_action
from app.modules.notification.schemas import PushSubscriptionCreate


@pytest.mark.asyncio
async def test_passwords_and_tokens_are_not_written_to_audit_logs():
    db = SimpleNamespace(add=lambda item: entries.append(item), flush=AsyncMock())
    entries = []
    actor = SimpleNamespace(id=None, username="test-user")
    await log_action(db, actor, "USER_UPDATED", "user", changes={
        "password": "fake-password", "full_name": "Example",
        "nested": [{"refresh_token": "fake-token"}],
    })
    serialized = json.dumps(entries[0].changes)
    assert "fake-password" not in serialized
    assert "fake-token" not in serialized
    assert entries[0].changes["full_name"] == "Example"


@pytest.mark.asyncio
async def test_validation_errors_do_not_log_request_body(monkeypatch):
    messages = []
    monkeypatch.setattr("app.core.exceptions.logger.error", lambda msg: messages.append(msg))
    error = RequestValidationError([
        {"loc": ("body", "password"), "msg": "Field required", "type": "missing"},
    ], body={"password": "fake-sensitive-value"})
    await validation_exception_handler(Request({"type": "http"}), error)
    assert "fake-sensitive-value" not in " ".join(messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
async def test_streamed_oversized_body_is_rejected_before_handler(monkeypatch, headers):
    monkeypatch.setattr(settings, "MAX_CONTENT_LENGTH", 4)
    handler = AsyncMock()
    messages = iter([
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"def", "more_body": False},
    ])
    sent = []

    async def receive():
        return next(messages, {"type": "http.disconnect"})

    async def send(message):
        sent.append(message)

    middleware = RequestSizeLimiterMiddleware(handler)
    await middleware({"type": "http", "method": "POST", "path": "/upload", "headers": headers}, receive, send)
    assert any(m.get("status") == 413 for m in sent)
    handler.assert_not_awaited()


@pytest.mark.parametrize("endpoint", [
    "http://127.0.0.1/push", "https://127.0.0.1/push",
    "https://example.org/push", "https://fcm.googleapis.com.evil.example/push",
    "https://user:pass@fcm.googleapis.com/push", "https://fcm.googleapis.com:8443/push",
])
def test_push_subscriptions_cannot_target_arbitrary_servers(endpoint):
    with pytest.raises(ValueError):
        PushSubscriptionCreate(endpoint=endpoint, keys={"p256dh": "fake", "auth": "fake"})


def test_legitimate_browser_push_endpoint_is_accepted():
    subscription = PushSubscriptionCreate(
        endpoint="https://fcm.googleapis.com/fcm/send/fake-test-device",
        keys={"p256dh": "fake", "auth": "fake"},
    )
    assert subscription.endpoint.startswith("https://fcm.googleapis.com/")
