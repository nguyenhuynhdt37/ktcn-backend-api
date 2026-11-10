"""Resolve the real client address without trusting spoofable headers.

Forwarding headers (CF-Connecting-IP, X-Real-IP, X-Forwarded-For) are only
honoured when the TCP peer is one of ``settings.TRUSTED_PROXIES``. A client
that connects directly can therefore not choose its own rate-limit identity.
"""

import ipaddress
from functools import lru_cache

from starlette.requests import HTTPConnection

from app.core.config import settings

_DEFAULT_HEADERS = ("cf-connecting-ip", "x-real-ip", "x-forwarded-for")
_MAX_LEN = 64


@lru_cache(maxsize=8)
def _networks(raw: tuple[str, ...]) -> tuple:
    networks = []
    for item in raw:
        try:
            networks.append(ipaddress.ip_network(item.strip(), strict=False))
        except ValueError:
            continue
    return tuple(networks)


def is_trusted_proxy(host: str | None) -> bool:
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return any(
        address.version == network.version and address in network
        for network in _networks(tuple(settings.TRUSTED_PROXIES))
    )


def _forwarded_client(request: HTTPConnection) -> str | None:
    configured = settings.CLIENT_IP_HEADER.strip().lower()
    headers = (configured,) if configured else _DEFAULT_HEADERS
    for header in headers:
        value = request.headers.get(header, "").strip()
        if not value:
            continue
        if header != "x-forwarded-for":
            return value[:_MAX_LEN]
        hops = [hop.strip() for hop in value.split(",") if hop.strip()]
        # Walk from the nearest proxy outwards: the first hop that is not one
        # of our own proxies is the real client; anything left of it is
        # attacker-controlled.
        for hop in reversed(hops):
            if not is_trusted_proxy(hop):
                return hop[:_MAX_LEN]
        if hops:
            return hops[0][:_MAX_LEN]
    return None


def get_client_ip(request: HTTPConnection, default: str = "unknown") -> str:
    peer = request.client.host if request.client else None
    if is_trusted_proxy(peer):
        return _forwarded_client(request) or peer or default
    return peer or default


def is_internal_call(request: HTTPConnection) -> bool:
    """True for server-to-server calls (e.g. Next.js SSR) inside the private network."""
    peer = request.client.host if request.client else None
    return is_trusted_proxy(peer) and _forwarded_client(request) is None
