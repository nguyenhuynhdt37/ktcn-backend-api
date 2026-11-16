import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import TooManyRequestsException
from app.modules.chatbot.knowledge import (
    CoreKnowledgeCache,
    match_staff_for_question,
    search_articles,
)
from app.modules.chatbot.schemas import ChatRequest, ChatResponse
from app.modules.chatbot.service import ChatbotService
from app.modules.chatbot.session import ChatSessionStore
from app.shared.ai.service import AIService
from app.shared.client_ip import get_client_ip, is_internal_call
from app.shared.rate_limiter import check_rate_limit
from app.shared.redis import get_redis

portal_router = APIRouter()

_ai_service: AIService | None = None
_knowledge_cache: CoreKnowledgeCache | None = None


def format_contact(settings_obj) -> str | None:
    parts = []
    for label, value in (
        ("Điện thoại", getattr(settings_obj, "phone", None)),
        ("Email", getattr(settings_obj, "email", None)),
        ("Địa chỉ", getattr(settings_obj, "address_vi", None)),
        ("Tư vấn tuyển sinh", "/vi/tu-van-tuyen-sinh"),
    ):
        if value:
            parts.append(f"{label}: {value}")
    return "; ".join(parts) or None


async def _leadership_contact(db) -> str | None:
    from app.modules.setting.service import setting_service

    site_settings = await setting_service.get_site_settings(db)
    return format_contact(site_settings)


async def invalidate_knowledge_cache() -> None:
    """Xóa cache tri thức chatbot khi thông tin cấu hình website thay đổi."""
    if _knowledge_cache is not None:
        await _knowledge_cache.clear()


def get_chatbot_service(
    redis_client: aioredis.Redis = Depends(get_redis),
) -> ChatbotService:
    """Lắp dịch vụ cho mỗi request; AIService và cache tri thức dùng chung toàn tiến trình."""
    global _ai_service, _knowledge_cache
    if _ai_service is None:
        _ai_service = AIService()
    if _knowledge_cache is None:
        _knowledge_cache = CoreKnowledgeCache(settings.CHATBOT_KNOWLEDGE_TTL_SECONDS)
    store = ChatSessionStore(
        redis_client, settings.CHATBOT_SESSION_TTL_SECONDS, settings.CHATBOT_HISTORY_TURNS
    )
    return ChatbotService(
        _ai_service,
        store,
        _knowledge_cache,
        search_articles,
        _leadership_contact,
        match_staff_for_question,
    )


@portal_router.post("/messages", response_model=ChatResponse)
async def send_message(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
    service: ChatbotService = Depends(get_chatbot_service),
) -> ChatResponse:
    if not is_internal_call(request):
        allowed, _, retry_after = await check_rate_limit(
            redis_client,
            f"rate_limit:chatbot:{get_client_ip(request)}",
            max_attempts=settings.CHATBOT_RATE_LIMIT_PER_MIN,
            window_seconds=60,
        )
        if not allowed:
            raise TooManyRequestsException(
                message="Bạn gửi tin nhắn quá nhanh. Vui lòng thử lại sau ít phút.",
                details={"retry_after": retry_after},
            )
    reply = await service.answer(
        db, session_id=payload.session_id, message=payload.message, lang=payload.lang
    )
    return ChatResponse(answer=reply.answer, kind=reply.kind, sources=reply.sources)
