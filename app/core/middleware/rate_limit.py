import time
from collections import deque
from typing import Any

import jwt
import redis.asyncio as aioredis
from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_access_token
from app.shared import redis
from app.shared.client_ip import get_client_ip, is_internal_call

# Redis Lua Script for Sliding Window Rate Limiting (Atomic Operation)
SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window
local ttl = math.max(1, math.ceil(window / 1000))

redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)
local count = redis.call('ZCARD', key)

if count < limit then
    local seq = redis.call('INCR', key .. ':seq')
    redis.call('EXPIRE', key .. ':seq', ttl)
    redis.call('ZADD', key, now, tostring(now) .. ':' .. tostring(seq))
    redis.call('EXPIRE', key, ttl)
    return 1
else
    return 0
end
"""


def parse_rate_limit_string(limit_str: str) -> tuple[int, int]:
    """
    Parses limit strings like '100/minute', '5/second' into (limit_count, window_ms).
    """
    try:
        parts = limit_str.split("/")
        limit = int(parts[0])
        unit = parts[1].strip().lower()
        if unit == "second":
            return limit, 1000
        elif unit == "minute":
            return limit, 60000
        elif unit == "hour":
            return limit, 3600000
        elif unit == "day":
            return limit, 86400000
        return limit, 60000
    except Exception as e:
        logger.error(
            f"Error parsing rate limit string '{limit_str}': {e}. "
            "Using default 100/minute."
        )
        return 100, 60000


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-based Sliding Window Rate Limiting Middleware with in-memory fallback.
    Distinguishes limits by endpoint types (Auth, AI/Translation, Global)
    and uses User ID (if authenticated) or Client IP.
    """

    _MAX_MEMORY_KEYS = 10000

    def __init__(self, app: Any):
        super().__init__(app)
        self.lua_script = None
        self._memory_windows: dict[str, deque[int]] = {}

    def _check_memory_limit(
        self, key: str, now_ms: int, window_ms: int, limit: int
    ) -> bool:
        """
        In-memory sliding-window fallback when Redis is unavailable.
        """
        cutoff = now_ms - window_ms
        bucket = self._memory_windows.get(key)
        if bucket is None:
            if len(self._memory_windows) >= self._MAX_MEMORY_KEYS:
                oldest_key = next(iter(self._memory_windows))
                self._memory_windows.pop(oldest_key, None)
            bucket = deque()
            self._memory_windows[key] = bucket

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) < limit:
            bucket.append(now_ms)
            return True
        return False

    def _get_limit_for_path(self, path: str) -> tuple[int, int, str]:
        """
        Returns (limit, window_ms, limit_category) based on request path.
        """
        # Public media proxy: one page legitimately loads many files
        if path.startswith(f"{settings.API_V1_STR}/portal/media/"):
            limit, window = parse_rate_limit_string(settings.RATE_LIMIT_MEDIA)
            return limit, window, "media"

        # Auth endpoints
        if (
            "/auth/login" in path
            or "/auth/register" in path
            or "/auth/refresh" in path
            or "/profile/password" in path
        ):
            limit, window = parse_rate_limit_string(settings.RATE_LIMIT_AUTH)
            return limit, window, "auth"

        # AI & Translation endpoints (expensive)
        if "/translation" in path or "/ai-hub" in path or "/seo/" in path:
            limit, window = parse_rate_limit_string(settings.RATE_LIMIT_AI)
            return limit, window, "ai"

        # Default global endpoints
        limit, window = parse_rate_limit_string(settings.RATE_LIMIT_GLOBAL)
        return limit, window, "global"

    def _extract_client_ip(self, request: Request) -> str:
        """
        Extracts client IP. Proxy headers are honoured only when the request
        really comes from a trusted proxy (see app.shared.client_ip).
        """
        return get_client_ip(request)

    @staticmethod
    def _bucket_for_path(path: str) -> str:
        """
        Collapses a URL to its module (e.g. /api/v1/portal/articles) so that
        distinct slugs / ids do not each get a fresh counter.
        """
        parts = [part for part in path.split("/") if part]
        depth = 4 if len(parts) > 2 and parts[2] in ("admin", "portal") else 3
        return "/".join(parts[:depth])

    def _get_user_id_from_token(self, request: Request) -> str | None:
        """
        Extracts User ID (sub) from access_token cookie or Authorization JWT if valid.
        """
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return None

        try:
            payload = decode_access_token(token)
            sub = payload.get("sub")
            return str(sub) if sub is not None else None
        except (jwt.PyJWTError, Exception):
            # If token is invalid/expired, we fall back to IP-based rate limiting
            return None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for docs, redoc, health checks, or uninitialized Redis pool
        path = request.url.path
        if (
            path == "/health"
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path == "/openapi.json"
            or redis.redis_pool is None
        ):
            return await call_next(request)

        # 1. Determine rate limit values
        limit, window_ms, category = self._get_limit_for_path(path)

        # 2. Determine Identifier (User ID if logged in, otherwise Client IP)
        # Key theo module (không theo full path) để không thể né bằng cách đổi slug/id.
        bucket = self._bucket_for_path(path)
        user_id = self._get_user_id_from_token(request)
        if user_id:
            identifier_key = f"ratelimit:{category}:user:{user_id}:{bucket}"
        else:
            # Server-side rendering calls from inside the private network carry no
            # end-user address; throttling them would throttle the whole site.
            if category in ("global", "media") and is_internal_call(request):
                return await call_next(request)
            client_ip = self._extract_client_ip(request)
            identifier_key = f"ratelimit:{category}:ip:{client_ip}:{bucket}"

        # 3. Apply Sliding Window Limit using Redis Script (with in-memory fallback)
        logger.debug(
            f"RateLimit Check | Path: {path} | Category: {category} | Limit: {limit}"
            f" | Key: {identifier_key} | User ID: {user_id}"
        )
        now_ms = int(time.time() * 1000)
        allowed = True
        redis_client = None
        try:
            # Create redis client using global pool
            redis_client = aioredis.Redis(connection_pool=redis.redis_pool)

            script = self.lua_script or redis_client.register_script(
                SLIDING_WINDOW_SCRIPT
            )

            # Execute Script
            allowed = bool(
                await script(
                    keys=[identifier_key],
                    args=[now_ms, window_ms, limit],
                )
            )
        except Exception as e:
            logger.warning(
                f"Redis rate limiting failed for {identifier_key} on {path}: {e}. "
                "Using in-memory rate limit fallback."
            )
            allowed = self._check_memory_limit(
                identifier_key, now_ms, window_ms, limit
            )
        finally:
            if redis_client is not None:
                close_fn = getattr(redis_client, "aclose", None) or redis_client.close
                await close_fn()

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for key {identifier_key} on path {path}"
            )
            retry_after_seconds = max(1, int(window_ms / 1000))
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "TOO_MANY_REQUESTS",
                        "message": "Too many requests. Please try again later.",
                        "retry_after_seconds": retry_after_seconds,
                    }
                },
                headers={"Retry-After": str(retry_after_seconds)},
            )

        return await call_next(request)
