"""Báo cho các site frontend làm mới cache ngay khi quản trị viên thay đổi nội dung.

Frontend (Next.js) lưu đệm dữ liệu API vài phút. Sau mỗi thay đổi thành công từ khu vực
admin, backend gọi `POST <url>` kèm header `x-revalidation-token` tới từng frontend đã cấu hình
để chúng xóa cache. Lỗi mạng chỉ được ghi log, không bao giờ ảnh hưởng tới request của admin.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.core.config import settings

# Các đường dẫn admin không làm thay đổi nội dung công khai.
SKIP_PREFIXES = (
    "/api/v1/admin/audit",
    "/api/v1/admin/ai-hub",
)
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
ADMIN_PREFIX = "/api/v1/admin/"
DEBOUNCE_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class RevalidateTarget:
    url: str
    token: str


def parse_targets(raw: str) -> list[RevalidateTarget]:
    """Đọc JSON dạng [{"url": "...", "token": "..."}]; bỏ qua mục không hợp lệ."""
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("FRONTEND_REVALIDATE_TARGETS không phải JSON hợp lệ, bỏ qua")
        return []
    if not isinstance(data, list):
        logger.warning("FRONTEND_REVALIDATE_TARGETS phải là một danh sách, bỏ qua")
        return []

    targets: list[RevalidateTarget] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        token = str(item.get("token") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or not token:
            logger.warning("Bỏ qua mục revalidate không hợp lệ: {}", url or "(trống)")
            continue
        targets.append(RevalidateTarget(url=url, token=token))
    return targets


def should_notify(method: str, path: str, status_code: int) -> bool:
    if method.upper() not in MUTATING_METHODS or status_code >= 400:
        return False
    if not path.startswith(ADMIN_PREFIX):
        return False
    return not path.startswith(SKIP_PREFIXES)


class RevalidationService:
    def __init__(
        self,
        targets: Callable[[], list[RevalidateTarget]] | None = None,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        debounce: float = DEBOUNCE_SECONDS,
    ) -> None:
        self._targets = targets or (
            lambda: parse_targets(settings.FRONTEND_REVALIDATE_TARGETS)
        )
        self._client_factory = client_factory or (
            lambda: httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
        )
        self._debounce = debounce
        self._pending: asyncio.Task[None] | None = None

    def schedule(self) -> None:
        """Gộp nhiều thay đổi liên tiếp thành một lần gọi."""
        if self._pending is not None and not self._pending.done():
            return
        if not self._targets():
            return
        self._pending = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            await asyncio.sleep(self._debounce)
            await self.notify_all()
        except Exception as exc:  # noqa: BLE001 - không để lỗi lan sang request khác
            logger.warning("Revalidate frontend thất bại: {}", exc)

    async def notify_all(self) -> list[bool]:
        targets = self._targets()
        if not targets:
            return []
        async with self._client_factory() as client:
            results = await asyncio.gather(
                *(self._notify(client, target) for target in targets)
            )
        return list(results)

    @staticmethod
    async def _notify(client: httpx.AsyncClient, target: RevalidateTarget) -> bool:
        try:
            response = await client.post(
                target.url, headers={"x-revalidation-token": target.token}
            )
        except httpx.HTTPError as exc:
            logger.warning("Revalidate {} lỗi mạng: {}", target.url, exc)
            return False
        if response.status_code != 200:
            logger.warning(
                "Revalidate {} trả về HTTP {}", target.url, response.status_code
            )
            return False
        return True


revalidation_service = RevalidationService()
