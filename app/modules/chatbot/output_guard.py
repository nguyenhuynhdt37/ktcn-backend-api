"""Kiểm tra/làm sạch câu trả lời của model trước khi trả cho người dùng."""
import re

from app.modules.chatbot.prompt import LEAK_MARKERS, NO_INFO_ANSWER, REFUSAL_ANSWER

MAX_ANSWER_CHARS = 2000
_BLOCKS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]*>")


def sanitize_answer(answer: str, canary: str, lang: str) -> str:
    lang = lang if lang in ("vi", "en") else "vi"
    text = answer or ""
    lowered = text.lower()

    if canary and canary in text:
        return REFUSAL_ANSWER[lang]
    if "<school_data" in lowered or "<articles" in lowered:
        return REFUSAL_ANSWER[lang]
    if sum(1 for marker in LEAK_MARKERS if marker in lowered) >= 2:
        return REFUSAL_ANSWER[lang]

    text = _TAGS.sub("", _BLOCKS.sub("", text)).strip()
    if not text:
        return NO_INFO_ANSWER[lang]
    return text[:MAX_ANSWER_CHARS]
