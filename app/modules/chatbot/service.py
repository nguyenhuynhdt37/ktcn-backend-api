"""Điều phối một lượt hỏi–đáp của chatbot."""
import secrets
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

from loguru import logger

from app.core.config import settings
from app.modules.chatbot.faq import detect_faq, faq_answer
from app.modules.chatbot.guard import check_message
from app.modules.chatbot.output_guard import sanitize_answer
from app.modules.chatbot.prompt import (
    ERROR_ANSWER,
    NO_INFO_ANSWER,
    REFUSAL_ANSWER,
    ArticleSnippet,
    build_system_instruction,
)

ReplyKind = Literal["faq", "refusal", "model", "error"]


@dataclass
class ChatReply:
    answer: str
    kind: ReplyKind
    sources: list[dict[str, str]] = field(default_factory=list)


class ChatbotService:
    def __init__(
        self,
        ai,
        session_store,
        knowledge_cache,
        article_search: Callable[..., Awaitable[list[ArticleSnippet]]],
        contact_provider: Callable[..., Awaitable[str | None]],
    ) -> None:
        self._ai = ai
        self._store = session_store
        self._knowledge = knowledge_cache
        self._article_search = article_search
        self._contact = contact_provider

    async def answer(self, db, *, session_id: str, message: str, lang: str) -> ChatReply:
        lang = lang if lang in ("vi", "en") else "vi"

        checked = check_message(message, settings.CHATBOT_MAX_MESSAGE_CHARS)
        if checked.reason == "empty":
            return ChatReply(faq_answer("unclear", lang), "faq")
        if not checked.ok:
            return ChatReply(REFUSAL_ANSWER[lang], "refusal")

        intent = detect_faq(checked.text)
        if intent:
            contact = await self._safe_contact(db) if intent == "human" else None
            return ChatReply(faq_answer(intent, lang, contact), "faq")

        canary = secrets.token_hex(8)
        try:
            core = await self._knowledge.get(db, lang)
            articles = await self._safe_articles(db, checked.text, lang)
            history = await self._store.load(session_id)
            system = build_system_instruction(lang, core, articles, canary)
            raw = await self._ai.generate_text(
                prompt=checked.text,
                system_instruction=system,
                history=history,
                temperature=0.2,
                max_tokens=settings.CHATBOT_MAX_OUTPUT_TOKENS,
                model=settings.CHATBOT_MODEL,
                db=db,
            )
        except Exception as exc:  # không lộ chi tiết lỗi cho người dùng
            logger.error(f"Chatbot call failed: {exc!r}")
            return ChatReply(ERROR_ANSWER[lang], "error")

        answer = sanitize_answer(raw, canary, lang)
        if answer == REFUSAL_ANSWER[lang]:
            return ChatReply(answer, "refusal")

        # Không lưu câu "chưa có thông tin" vào lịch sử: model sẽ bắt chước và từ chối cả những câu sau.
        if answer != NO_INFO_ANSWER[lang]:
            await self._store.append(session_id, checked.text, answer)
        sources = [{"title": a.title, "url": a.url} for a in articles if a.url in answer]
        return ChatReply(answer, "model", sources)

    async def _safe_articles(self, db, question: str, lang: str) -> list[ArticleSnippet]:
        try:
            return await self._article_search(db, question, lang)
        except Exception as exc:
            logger.warning(f"Chatbot article search failed (ignored): {exc!r}")
            return []

    async def _safe_contact(self, db) -> str | None:
        try:
            return await self._contact(db)
        except Exception as exc:
            logger.warning(f"Chatbot contact lookup failed (ignored): {exc!r}")
            return None
