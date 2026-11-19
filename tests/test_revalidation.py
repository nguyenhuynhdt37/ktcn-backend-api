"""Kiểm tra cơ chế báo frontend làm mới cache (không chạm vào DB)."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import revalidation
from app.core.middleware.revalidate_on_change import RevalidateOnChangeMiddleware
from app.core.revalidation import (
    RevalidateTarget,
    RevalidationService,
    parse_targets,
    should_notify,
)


def test_parse_targets_accepts_valid_and_skips_invalid():
    raw = (
        '[{"url": "http://fe-a:3000/api/revalidate", "token": "a"},'
        ' {"url": "ftp://bad", "token": "x"},'
        ' {"url": "https://fe-b/api/revalidate", "token": ""},'
        ' "not-an-object"]'
    )
    assert parse_targets(raw) == [
        RevalidateTarget("http://fe-a:3000/api/revalidate", "a")
    ]


@pytest.mark.parametrize("raw", ["", "   ", "not json", "{}", '"x"'])
def test_parse_targets_tolerates_bad_config(raw):
    assert parse_targets(raw) == []


@pytest.mark.parametrize(
    "method,path,status,expected",
    [
        ("POST", "/api/v1/admin/articles", 201, True),
        ("PUT", "/api/v1/admin/settings", 200, True),
        ("DELETE", "/api/v1/admin/documents/abc", 204, True),
        ("GET", "/api/v1/admin/articles", 200, False),
        ("POST", "/api/v1/admin/articles", 422, False),
        ("POST", "/api/v1/admin/articles", 500, False),
        ("POST", "/api/v1/portal/consultations", 201, False),
        ("POST", "/api/v1/auth/login", 200, False),
        ("POST", "/api/v1/admin/audit/export", 200, False),
        ("POST", "/api/v1/admin/ai-hub/playground", 200, False),
    ],
)
def test_should_notify(method, path, status, expected):
    assert should_notify(method, path, status) is expected


def _service(calls, status=200, debounce=0.01):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((str(request.url), request.headers.get("x-revalidation-token")))
        return httpx.Response(status)

    targets = [
        RevalidateTarget("http://fe-a/api/revalidate", "token-a"),
        RevalidateTarget("http://fe-b/api/revalidate", "token-b"),
    ]
    return RevalidationService(
        targets=lambda: targets,
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        debounce=debounce,
    )


def test_notify_all_sends_each_target_its_own_token():
    calls: list = []
    service = _service(calls)
    assert asyncio.run(service.notify_all()) == [True, True]
    assert sorted(calls) == [
        ("http://fe-a/api/revalidate", "token-a"),
        ("http://fe-b/api/revalidate", "token-b"),
    ]


def test_notify_reports_failure_without_raising():
    calls: list = []
    service = _service(calls, status=401)
    assert asyncio.run(service.notify_all()) == [False, False]


def test_notify_survives_network_error():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    service = RevalidationService(
        targets=lambda: [RevalidateTarget("http://fe/api/revalidate", "t")],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(boom)),
    )
    assert asyncio.run(service.notify_all()) == [False]


def test_schedule_coalesces_bursts_into_one_round():
    calls: list = []
    service = _service(calls)

    async def burst():
        for _ in range(5):
            service.schedule()
        await asyncio.sleep(0.2)

    asyncio.run(burst())
    assert len(calls) == 2  # one request per target, not per change


def test_schedule_is_noop_without_targets():
    service = RevalidationService(targets=lambda: [])

    async def run():
        service.schedule()
        return service._pending

    assert asyncio.run(run()) is None


def test_middleware_schedules_only_for_successful_admin_changes(monkeypatch):
    scheduled: list[int] = []

    class Recorder:
        def schedule(self) -> None:
            scheduled.append(1)

    monkeypatch.setattr(revalidation, "revalidation_service", Recorder())

    app = FastAPI()
    app.add_middleware(RevalidateOnChangeMiddleware)

    @app.post("/api/v1/admin/things")
    def create():
        return {"ok": True}

    @app.post("/api/v1/admin/fail", status_code=400)
    def fail():
        return {"ok": False}

    @app.get("/api/v1/admin/things")
    def read():
        return {"ok": True}

    client = TestClient(app)
    client.get("/api/v1/admin/things")
    client.post("/api/v1/admin/fail")
    assert scheduled == []
    client.post("/api/v1/admin/things")
    assert scheduled == [1]
