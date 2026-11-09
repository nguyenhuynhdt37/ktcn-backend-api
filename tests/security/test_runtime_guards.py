"""Offline checks for response headers, upload guards, and rate limiting."""

import io

import pytest
from fastapi import Request
from PIL import Image
from starlette.responses import Response
from unittest.mock import AsyncMock

from app.core.config import settings
from app.core.middleware.rate_limit import RateLimitMiddleware, parse_rate_limit_string
from app.core.middleware.security import RequestSizeLimiterMiddleware, SecurityHeadersMiddleware
from app.modules.media.service import check_svg_safety, sanitize_image_metadata
from app.shared import redis as redis_module


def http_request(path="/", scheme="http", headers=None):
    raw_headers = [
        (key.lower().encode(), value.encode())
        for key, value in (headers or {}).items()
    ]
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("203.0.113.5", 1234),
        "server": ("testserver", 80),
    })


@pytest.mark.asyncio
async def test_security_headers_and_hsts(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "production")

    async def call_next(_request):
        return Response("ok")

    response = await SecurityHeadersMiddleware(None).dispatch(http_request(), call_next)
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=63072000")


@pytest.mark.asyncio
async def test_hsts_is_absent_on_plain_http_outside_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "testing")

    async def call_next(_request):
        return Response("ok")

    response = await SecurityHeadersMiddleware(None).dispatch(http_request(), call_next)
    assert "Strict-Transport-Security" not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("length", [b"-1", b"nope"])
async def test_invalid_content_length_is_rejected(length):
    handler = AsyncMock()
    sent = []

    async def send(message):
        sent.append(message)

    middleware = RequestSizeLimiterMiddleware(handler)
    await middleware(
        {"type": "http", "headers": [(b"content-length", length)]},
        AsyncMock(),
        send,
    )
    assert any(message.get("status") == 400 for message in sent)
    handler.assert_not_awaited()


def test_svg_script_and_event_handlers_are_rejected():
    assert check_svg_safety(b'<svg><rect width="1" height="1"/></svg>') is True
    assert check_svg_safety(b'<svg><script>bad()</script></svg>') is False
    assert check_svg_safety(b'<svg onload="bad()"></svg>') is False


def test_image_metadata_rewrite_keeps_pixel_size():
    source = io.BytesIO()
    Image.new("RGB", (2, 3), "red").save(source, format="PNG")
    cleaned, width, height = sanitize_image_metadata(source.getvalue())
    assert cleaned.startswith(b"\x89PNG")
    assert (width, height) == (2, 3)


def test_rate_limit_categories():
    assert parse_rate_limit_string("5/minute") == (5, 60000)
    middleware = RateLimitMiddleware(None)
    assert middleware._get_limit_for_path("/api/v1/auth/login")[2] == "auth"
    assert middleware._get_limit_for_path("/api/v1/ai-hub/rewrite")[2] == "ai"
    assert middleware._get_limit_for_path("/api/v1/articles")[2] == "global"
    request = http_request(headers={"X-Forwarded-For": "198.51.100.8, 203.0.113.5", "CF-Connecting-IP": "192.0.2.9"})
    assert middleware._extract_client_ip(request) == "192.0.2.9"


@pytest.mark.asyncio
async def test_rate_limit_returns_429_when_the_window_is_full(monkeypatch):
    monkeypatch.setattr(redis_module, "redis_pool", object())

    class FakeRedis:
        def __init__(self, connection_pool):
            self.connection_pool = connection_pool

        def register_script(self, _script):
            async def run(keys, args):
                assert keys and args
                return 0

            return run

        async def close(self):
            return None

    monkeypatch.setattr("app.core.middleware.rate_limit.aioredis.Redis", FakeRedis)
    middleware = RateLimitMiddleware(None)
    called = False

    async def call_next(_request):
        nonlocal called
        called = True
        return Response("ok")

    response = await middleware.dispatch(http_request("/api/v1/auth/login"), call_next)
    assert response.status_code == 429
    assert response.headers["retry-after"]
    assert called is False


@pytest.mark.asyncio
async def test_health_check_skips_rate_limit(monkeypatch):
    monkeypatch.setattr(redis_module, "redis_pool", object())
    middleware = RateLimitMiddleware(None)

    async def call_next(_request):
        return Response("ok")

    response = await middleware.dispatch(http_request("/health"), call_next)
    assert response.status_code == 200
