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

_REDUNDANT_NO_INFO_SIGNATURES = (
    "mình chưa có thông tin này trên website của trường",
    "i don't have this information on the college's website",
)


def _normalize_internal_paths(text: str, lang: str) -> str:
    """Chuẩn hóa các đường dẫn nội bộ của Khoa / Ban lãnh đạo nếu model viết nhầm sang /bo-mon/."""
    text = re.sub(r"/vi/bo-mon/(khoa-[A-Za-z0-9_-]+)", r"/vi/khoa/\1", text)
    text = re.sub(r"/en/departments/((?:faculty|khoa)-[A-Za-z0-9_-]+)", r"/en/faculties/\1", text)
    fallback_vi = "/vi/gioi-thieu/cac-khoa-dao-tao" if "khoa" in text.lower() else "/vi/gioi-thieu/can-bo"
    fallback_en = "/en/about/faculties" if "facult" in text.lower() else "/en/about/staff"
    text = text.replace("/vi/bo-mon/ban-lanh-dao-vien", fallback_vi)
    text = text.replace("/en/departments/ban-lanh-dao-vien", fallback_en)
    text = text.replace("/en/departments/institute-board-of-management", fallback_en)
    text = text.replace("/vi/bo-mon/van-phong-truong", "/vi/gioi-thieu")
    text = text.replace("/en/departments/van-phong-truong", "/en/about")
    return text


def _plain_text(text: str, lang: str = "vi") -> str:
    """Model hay trả Markdown; widget hiển thị văn bản thuần nên chuyển về dạng đọc được."""
    text = _MD_LINK.sub(r"\1 (\2)", text)
    text = _BRACKET_PATH.sub(r"\1", text)
    text = _MD_EMPHASIS.sub(r"\2", text)
    text = _MD_HEADING.sub("", text)
    text = _normalize_internal_paths(text, lang)
    return text.replace("`", "")


def _strip_redundant_no_info_lines(text: str) -> str:
    """Nếu câu trả lời đã có thông tin hợp lệ nhưng model lại ghép thêm câu NO_INFO ở cuối, loại bỏ dòng thừa đó."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        return text

    kept = [
        line
        for line in lines
        if not any(sig in line.lower() for sig in _REDUNDANT_NO_INFO_SIGNATURES)
    ]
    if kept:
        return "\n".join(kept)
    return text


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

    text = _plain_text(_TAGS.sub("", _BLOCKS.sub("", text)), lang).strip()
    if not text:
        return NO_INFO_ANSWER[lang]
    text = _strip_redundant_no_info_lines(text).strip()
    if not text:
        return NO_INFO_ANSWER[lang]
    return text[:MAX_ANSWER_CHARS]
