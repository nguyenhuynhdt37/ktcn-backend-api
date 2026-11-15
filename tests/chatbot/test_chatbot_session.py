import pytest

from app.modules.chatbot.session import ChatSessionStore, is_valid_session_id

SID = "a" * 24


class FakeRedis:
    def __init__(self):
        self.lists: dict[str, list[str]] = {}
        self.expires: dict[str, int] = {}

    async def rpush(self, key, *values):
        self.lists.setdefault(key, []).extend(values)

    async def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        end = None if end == -1 else end + 1
        return items[start:end]

    async def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        self.lists[key] = items[start:] if end == -1 else items[start : end + 1]

    async def expire(self, key, seconds):
        self.expires[key] = seconds


class BrokenRedis:
    async def rpush(self, *a, **k):
        raise ConnectionError("down")

    lrange = ltrim = expire = rpush


async def test_append_then_load_roundtrip():
    store = ChatSessionStore(FakeRedis(), ttl_seconds=1800, max_turns=10)
    await store.append(SID, "hỏi 1", "đáp 1")
    assert await store.load(SID) == [
        {"role": "user", "content": "hỏi 1"},
        {"role": "assistant", "content": "đáp 1"},
    ]


async def test_load_unknown_session_is_empty():
    store = ChatSessionStore(FakeRedis(), 1800, 10)
    assert await store.load(SID) == []


async def test_history_trimmed_to_max_turns():
    store = ChatSessionStore(FakeRedis(), 1800, 10)
    for i in range(12):
        await store.append(SID, f"q{i}", f"a{i}")
    history = await store.load(SID)
    assert len(history) == 20
    assert history[0] == {"role": "user", "content": "q2"}
    assert history[-1] == {"role": "assistant", "content": "a11"}


async def test_ttl_set_on_append():
    redis = FakeRedis()
    store = ChatSessionStore(redis, 1800, 10)
    await store.append(SID, "q", "a")
    assert redis.expires[f"chatbot:session:{SID}"] == 1800


async def test_broken_redis_does_not_raise():
    store = ChatSessionStore(BrokenRedis(), 1800, 10)
    assert await store.load(SID) == []
    await store.append(SID, "q", "a")


@pytest.mark.parametrize(
    "value,ok",
    [("a" * 15, False), ("x" * 16, True), ("a" * 64, True), ("a" * 65, False),
     ("abc def ghi jkl mno", False), ("../../etc/passwd-xx", False), ("ok_ok-ok_ok-ok_ok", True)],
)
def test_session_id_validation(value, ok):
    assert is_valid_session_id(value) is ok
