"""Offline security tests; never load the application's real .env or app.main.

Run with ``python -m pytest --confcutdir=tests/security tests/security`` so the
database-backed fixtures in tests/conftest.py are deliberately not imported.
"""

import ipaddress
import os
import socket
from unittest.mock import patch

from pydantic_settings.sources import DotEnvSettingsSource

# Install guards before importing any application modules during collection.
# dotenv loading is disabled even if a test constructs Settings independently.
DotEnvSettingsSource._read_env_files = lambda self: {}
os.environ.update(
    ENV="testing",
    DEBUG="false",
    POSTGRES_SERVER="127.0.0.1",
    POSTGRES_PORT="5432",
    POSTGRES_USER="security_test",
    POSTGRES_PASSWORD="offline-test-password",
    POSTGRES_DB="security_test",
    SQLALCHEMY_DATABASE_URI=(
        "postgresql+asyncpg://security_test:offline-test-password"
        "@127.0.0.1:5432/security_test"
    ),
    REDIS_URL="redis://127.0.0.1:6379/15",
    REDIS_HOST="127.0.0.1",
    REDIS_PASSWORD="",
    SECRET_KEY="offline-security-test-key-with-at-least-32-characters",
    MINIO_ENDPOINT="127.0.0.1:9000",
    MINIO_INTERNAL_ENDPOINT="127.0.0.1:9000",
    MINIO_ACCESS_KEY="offline-test-key",
    MINIO_SECRET_KEY="offline-test-secret",
    MINIO_BUCKET="security-test",
    AI_BASE_URL="http://127.0.0.1:8090",
    AI_API_KEY="offline-test-key",
    GEMINI_API_KEY="",
    VAPID_PRIVATE_KEY="",
    VAPID_PUBLIC_KEY="",
    COOKIE_SECURE="false",
    COOKIE_SAMESITE="lax",
    BACKEND_CORS_ORIGINS='["http://testserver"]',
    ALLOWED_HOSTS='["testserver", "localhost", "127.0.0.1"]',
)

_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex
_original_getaddrinfo = socket.getaddrinfo


def _require_loopback(host):
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise AssertionError("Outbound network is forbidden in security tests")


def _connect(sock, address):
    if isinstance(address, tuple):
        _require_loopback(address[0])
    return _original_connect(sock, address)


def _connect_ex(sock, address):
    if isinstance(address, tuple):
        _require_loopback(address[0])
    return _original_connect_ex(sock, address)


def _getaddrinfo(host, *args, **kwargs):
    _require_loopback(host)
    return _original_getaddrinfo(host, *args, **kwargs)


patch("socket.socket.connect", _connect).start()
patch("socket.socket.connect_ex", _connect_ex).start()
patch("socket.getaddrinfo", _getaddrinfo).start()
