import time
from collections import deque

import redis.asyncio as aioredis
from loguru import logger

_FALLBACK_MAX_KEYS = 10000
_fallback_windows: dict[str, deque[float]] = {}


def _check_memory_rate_limit(
    key: str, max_attempts: int, window_seconds: int
) -> tuple[bool, int, int]:
    now = time.monotonic()
    cutoff = now - window_seconds
    bucket = _fallback_windows.get(key)
    if bucket is None:
        if len(_fallback_windows) >= _FALLBACK_MAX_KEYS:
            oldest_key = next(iter(_fallback_windows))
            _fallback_windows.pop(oldest_key, None)
        bucket = deque()
        _fallback_windows[key] = bucket

    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    bucket.append(now)
    current = len(bucket)
    remaining = max(0, max_attempts - current)
    allowed = current <= max_attempts
    retry_after = 0
    if not allowed and bucket:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
    return allowed, remaining, retry_after


def clear_memory_rate_limit(key: str) -> None:
    _fallback_windows.pop(key, None)


async def check_rate_limit(
    redis_client: aioredis.Redis,
    key: str,
    max_attempts: int = 5,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    """
    Checks if the given key has exceeded the rate limit.

    Returns:
        (allowed, remaining, retry_after_seconds)
        - allowed: True if the request is within the limit.
        - remaining: Number of attempts left in the current window.
        - retry_after: Seconds until the window resets (0 if allowed).
    """
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds)

        ttl = await redis_client.ttl(key)
        if ttl < 0:
            ttl = window_seconds

        remaining = max(0, max_attempts - current)
        allowed = current <= max_attempts

        return allowed, remaining, 0 if allowed else ttl
    except Exception as e:
        logger.warning(
            f"Rate limiter Redis error for {key}: {e}. "
            "Falling back to in-memory rate limiter."
        )
        return _check_memory_rate_limit(key, max_attempts, window_seconds)
