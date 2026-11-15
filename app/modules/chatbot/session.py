"""Lịch sử hội thoại do server giữ trong Redis (không tin lịch sử từ trình duyệt)."""
import json
import re

from loguru import logger

_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def is_valid_session_id(value: str) -> bool:
    return bool(value) and bool(_SESSION_ID.match(value))


class ChatSessionStore:
    def __init__(self, redis, ttl_seconds: int, max_turns: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._max_turns = max_turns

    @staticmethod
    def _key(session_id: str) -> str:
        return f"chatbot:session:{session_id}"

    async def load(self, session_id: str) -> list[dict[str, str]]:
        try:
            raw = await self._redis.lrange(self._key(session_id), -2 * self._max_turns, -1)
            return [json.loads(item) for item in raw]
        except Exception as exc:  # Redis/JSON lỗi: trả lời không có lịch sử
            logger.warning(f"Chatbot session load failed (ignored): {exc}")
            return []

    async def append(self, session_id: str, user: str, assistant: str) -> None:
        key = self._key(session_id)
        try:
            await self._redis.rpush(
                key,
                json.dumps({"role": "user", "content": user}, ensure_ascii=False),
                json.dumps({"role": "assistant", "content": assistant}, ensure_ascii=False),
            )
            await self._redis.ltrim(key, -2 * self._max_turns, -1)
            await self._redis.expire(key, self._ttl)
        except Exception as exc:
            logger.warning(f"Chatbot session append failed (ignored): {exc}")
