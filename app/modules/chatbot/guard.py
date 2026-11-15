"""Chuẩn hóa và kiểm tra câu hỏi người dùng trước khi vào chatbot."""
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

GuardReason = Literal["empty", "too_long", "injection"]


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: GuardReason | None
    text: str


def normalize_text(raw: str) -> str:
    """NFKC, bỏ ký tự điều khiển/zero-width, gộp khoảng trắng."""
    text = unicodedata.normalize("NFKC", raw or "")
    out: list[str] = []
    for ch in text:
        if ch.isspace():
            out.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf"):
            continue
        else:
            out.append(ch)
    return re.sub(r" +", " ", "".join(out)).strip()


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu (kể cả đ), ký tự không phải chữ/số thành khoảng trắng."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    stripped = stripped.replace("đ", "d")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", stripped)).strip()


# Mẫu trên văn bản đã fold (không dấu). Mỗi mẫu đòi một cụm (động từ + đối tượng)
# để câu hỏi bình thường như "hướng dẫn đăng ký" không bị chặn.
_FOLDED_PATTERNS = [
    r"\b(ignore|disregard|override|bypass)\b.{0,40}\b(instructions?|prompts?|rules?|guidelines?|system|previous|prior|above)\b",
    r"\bforget\b.{0,30}\b(everything|all|instructions?|previous|your)\b",
    r"\b(bo qua|phot lo|vuot qua|quen het)\b.{0,40}\b(huong dan|chi dan|chi thi|quy tac|truoc do|truoc day|tat ca)\b",
    r"\b(system|developer)\s+(prompt|message|instructions?)\b",
    r"\b(prompt|chi dan|huong dan)\s+he thong\b",
    r"\byou are now\b",
    r"\bact as\b",
    r"\bpretend (to be|you)\b",
    r"\bfrom now on (you|act)\b",
    r"\btu gio (ban|em|may)\b",
    r"\b(dong vai|gia vo)\b",
    r"\b(jailbreak|developer mode|do anything now)\b",
    r"\b(reveal|print|show|display|repeat|leak|output|tiet lo|in ra|hien thi|lap lai|cho xem)\b.{0,40}\b(prompt|api key|secret key|secret|mat khau|system prompt|your (rules|instructions)|instructions? (above|you were given)|chi dan cua ban|huong dan cua ban|luat cua ban|chi dan ban dau)\b",
]
# Mẫu trên văn bản gốc (chữ thường) — thẻ vai trò / định dạng chat.
_RAW_PATTERNS = [
    r"^\s*(system|assistant|developer)\s*:",
    r"<\|im_(start|end)\|>",
    r"###\s*(instruction|system)",
    r"\[(system|inst)\]",
]

INJECTION_PATTERNS = [re.compile(p) for p in _FOLDED_PATTERNS]
_RAW_INJECTION_PATTERNS = [re.compile(p) for p in _RAW_PATTERNS]


def _looks_like_injection(text: str) -> bool:
    folded = fold(text)
    if any(p.search(folded) for p in INJECTION_PATTERNS):
        return True
    lowered = text.lower()
    return any(p.search(lowered) for p in _RAW_INJECTION_PATTERNS)


def check_message(raw: str, max_chars: int) -> GuardResult:
    text = normalize_text(raw)
    if not text:
        return GuardResult(False, "empty", text)
    if len(text) > max_chars:
        return GuardResult(False, "too_long", text)
    if _looks_like_injection(text):
        return GuardResult(False, "injection", text)
    return GuardResult(True, None, text)


_EN_WORDS = {
    "the", "what", "which", "where", "who", "how", "when", "why", "is", "are", "do", "does", "can", "could",
    "school", "college", "faculty", "faculties", "program", "programs", "university", "tuition", "admission",
    "admissions", "contact", "staff", "lecturer", "lecturers", "about", "offer", "offers", "have", "has", "me",
}


def detect_lang(text: str, default: str = "vi") -> str:
    """Ngôn ngữ của câu hỏi: có dấu tiếng Việt -> vi; toàn ASCII và có từ tiếng Anh phổ biến -> en; còn lại giữ mặc định."""
    if re.search(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", text.lower()):
        return "vi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    return "en" if words & _EN_WORDS else default
