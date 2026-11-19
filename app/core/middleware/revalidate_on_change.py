from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core import revalidation


class RevalidateOnChangeMiddleware(BaseHTTPMiddleware):
    """Sau mỗi thay đổi thành công từ khu vực admin, yêu cầu frontend làm mới cache."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if revalidation.should_notify(
            request.method, request.url.path, response.status_code
        ):
            revalidation.revalidation_service.schedule()
        return response
