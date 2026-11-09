from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject critical security headers into every HTTP response.
    Protects against clickjacking, MIME-sniffing, and cross-site scripting (XSS).
    """
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        
        # Prevent Clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME-Sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS protection in older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Control Referrer information disclosure
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Force HTTPS in production (HSTS)
        if settings.ENV == "production" or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
            
        return response


class RequestSizeLimiterMiddleware:
    """Bound actual received bytes before parsers or business handlers run."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = dict(scope["headers"]).get(b"content-length")
        try:
            declared = int(length) if length is not None else 0
            if declared < 0:
                raise ValueError
        except ValueError:
            await JSONResponse({"error": {"code": "BAD_REQUEST"}}, status_code=400)(scope, receive, send)
            return

        chunks = []
        size = 0
        if declared <= settings.MAX_CONTENT_LENGTH:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > settings.MAX_CONTENT_LENGTH:
                    break
                chunks.append(message)
                if not message.get("more_body", False):
                    iterator = iter(chunks)

                    async def replay() -> dict:
                        return next(iterator, None) or await receive()

                    await self.app(scope, replay, send)
                    return

        await JSONResponse(
            {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Request body exceeds the configured limit"}},
            status_code=413,
        )(scope, receive, send)
