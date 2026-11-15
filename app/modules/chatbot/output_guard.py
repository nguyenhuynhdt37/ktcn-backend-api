"""Kiểm tra/làm sạch câu trả lời của model trước khi trả cho người dùng."""
import re

from app.modules.chatbot.prompt import LEAK_MARKERS, NO_INFO_ANSWER, REFUSAL_ANSWER

MAX_ANSWER_CHARS = 2000
_BLOCKS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]*>")
_MD_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BRACKET_PATH = re.compile(r"\[((?:https?://|/)[^\]\s]+)\]")
_MD_EMPHASIS = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)
_MD_HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)


def _plain_text(text: str) -> str:
    """Model hay trả Markdown; widget hiển thị văn bản thuần nên chuyển về dạng đọc được."""
    text = _MD_LINK.sub(r"\1 (\2)", text)
    text = _BRACKET_PATH.sub(r"\1", text)
    text = _MD_EMPHASIS.sub(r"\2", text)
    text = _MD_HEADING.sub("", text)
    return text.replace("`", "")


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

    text = _plain_text(_TAGS.sub("", _BLOCKS.sub("", text))).strip()
    if not text:
        return NO_INFO_ANSWER[lang]
    return text[:MAX_ANSWER_CHARS]
