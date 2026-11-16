"""FAQ và câu xã giao có sẵn: trả lời không cần gọi model.

Chỉ khớp khi (gần như) cả câu là lời chào/cảm ơn...; câu còn thêm nội dung thật
thì trả `None` để đi tiếp luồng bình thường (và các bộ lọc phía sau).
"""
import re
from typing import Literal

from app.modules.chatbot.guard import fold

FaqIntent = Literal[
    "greeting", "how_are_you", "who_are_you", "help", "thanks",
    "bye", "ack", "unclear", "human", "abuse",
]

# Từ đệm được phép đứng kèm (đã fold).
_PAD = {"a", "ah", "nhe", "nha", "ban", "oi", "please", "pls", "ad", "admin", "bot", "em", "anh", "chi"}

_PHRASES: dict[str, set[str]] = {
    "greeting": {
        "chao", "xin chao", "hi", "hello", "hey", "alo", "hi there", "hello there",
        "good morning", "good afternoon", "good evening", "chao buoi sang",
        "chao buoi chieu", "chao buoi toi", "chao moi nguoi", "chao cac ban",
    },
    "how_are_you": {
        "khoe khong", "co khoe khong", "ban khoe khong", "ban co khoe khong",
        "how are you", "how are you doing", "ban the nao",
    },
    "who_are_you": {
        "ban la ai", "ban la bot", "ban la bot a", "ban la gi", "ban la robot",
        "who are you", "what are you", "are you a bot", "ten ban la gi", "ban ten gi",
    },
    "help": {
        "help", "giup", "giup duoc gi", "giup duoc gi khong", "ban giup duoc gi",
        "ban giup duoc gi khong", "lam duoc gi", "ban lam duoc gi", "ban co the lam gi",
        "huong dan", "huong dan su dung", "menu", "what can you do",
        "can you help me", "giup minh voi", "giup toi voi",
    },
    "thanks": {
        "cam on", "cam on nhieu", "cam on rat nhieu", "ok cam on", "da cam on",
        "thanks", "thank you", "thank you so much", "thanks a lot", "thx",
    },
    "bye": {
        "tam biet", "bye", "bye bye", "goodbye", "hen gap lai", "chao tam biet", "see you",
    },
    "ack": {
        "ok", "oke", "okay", "vang", "da", "u", "uh", "duoc roi", "ro roi",
        "hieu roi", "da hieu", "a ra the", "yes", "yeah", "sure", "dong y",
    },
}

_HUMAN_CUES = (
    "tu van vien", "nguoi that", "nhan vien", "gap nguoi", "lien he voi nguoi",
    "speak to a human", "talk to a human", "human agent", "real person", "customer service",
)
_ABUSE_TOKENS = {"dm", "dmm", "dcm", "vcl", "vkl", "cc", "fuck", "fck", "shit"}
_ABUSE_PHRASES = {"do ngu", "bot ngu", "ngu qua", "ngu vay", "stupid bot"}
_MASH = re.compile(r"^(asd|qwe|zxc|hjk|sdf|dfg|jkl)[a-z]*$")


def _squash(folded: str) -> str:
    # "hiiii" -> "hi": chữ lặp từ 3 lần trở lên gộp thành 1.
    return re.sub(r"(.)\1{2,}", r"\1", folded)


def detect_faq(text: str) -> FaqIntent | None:
    folded = _squash(fold(text))
    if not folded:
        return "unclear"  # chỉ có ký hiệu/emoji

    tokens = folded.split()
    stripped_tokens = [t for t in tokens if t not in _PAD]
    stripped = " ".join(stripped_tokens)
    candidates = {folded, stripped} - {""}

    if len(folded) <= 80 and any(cue in folded for cue in _HUMAN_CUES):
        return "human"

    if (len(tokens) <= 4 and (set(tokens) & _ABUSE_TOKENS)) or folded in _ABUSE_PHRASES:
        return "abuse"

    for intent, phrases in _PHRASES.items():
        if candidates & phrases:
            return intent  # type: ignore[return-value]

    if not stripped_tokens:  # chỉ có từ đệm: "bạn ơi", "ad ơi"
        return "greeting"

    if len(tokens) == 1 and _MASH.match(tokens[0]):
        return "unclear"
    return None


_TOPICS_VI = "khoa, chương trình đào tạo, cán bộ, tuyển sinh, liên hệ và tin tức của trường"
_TOPICS_EN = "faculties, study programs, staff, admissions, contact details and news"

FAQ_ANSWERS: dict[str, dict[str, str]] = {
    "vi": {
        "greeting": "Xin chào! Mình là trợ lý ảo của Trường Kỹ thuật và Công nghệ - Trường Đại học Vinh. "
                    f"Bạn có thể hỏi mình về {_TOPICS_VI}.",
        "how_are_you": "Mình ổn, cảm ơn bạn! Bạn muốn tìm hiểu thông tin gì về Trường Kỹ thuật và Công nghệ?",
        "who_are_you": "Mình là trợ lý ảo của Trường Kỹ thuật và Công nghệ - Trường Đại học Vinh. "
                       "Mình trả lời dựa trên thông tin có trên website của trường.",
        "help": f"Mình có thể giúp bạn tìm thông tin về {_TOPICS_VI}. Bạn thử hỏi một trong các gợi ý bên dưới nhé.",
        "thanks": "Không có gì ạ! Bạn còn cần mình hỗ trợ thêm điều gì không?",
        "bye": "Tạm biệt bạn! Chúc bạn một ngày tốt lành. Cần gì cứ quay lại hỏi mình nhé.",
        "ack": "Vâng ạ. Bạn còn cần mình hỗ trợ thêm gì không?",
        "unclear": "Mình chưa hiểu ý bạn. Bạn có thể nói rõ hơn không? "
                   f"Mình có thể trả lời về {_TOPICS_VI}.",
        "human": "Để được tư vấn trực tiếp, bạn vui lòng liên hệ: {contact}",
        "abuse": "Mình ở đây để hỗ trợ thông tin về Trường Kỹ thuật và Công nghệ. Bạn cần hỏi gì cứ nói nhé.",
    },
    "en": {
        "greeting": "Hello! I'm the virtual assistant of the College of Engineering and Technology - Vinh University. "
                    f"You can ask me about {_TOPICS_EN}.",
        "how_are_you": "I'm doing well, thank you! What would you like to know about the College?",
        "who_are_you": "I'm the virtual assistant of the College of Engineering and Technology - Vinh University. "
                       "I answer based on the information published on the College's website.",
        "help": f"I can help you find information about {_TOPICS_EN}. Try one of the suggestions below.",
        "thanks": "You're welcome! Is there anything else I can help you with?",
        "bye": "Goodbye! Have a great day. Come back any time you have a question.",
        "ack": "Sure. Is there anything else I can help with?",
        "unclear": "I didn't quite get that. Could you rephrase? "
                   f"I can answer questions about {_TOPICS_EN}.",
        "human": "For direct advice, please contact: {contact}",
        "abuse": "I'm here to help with information about the College of Engineering and Technology. Just ask.",
    },
}

_DEFAULT_CONTACT = {
    "vi": "vui lòng xem trang Tư vấn tuyển sinh của trường tại /vi/tu-van-tuyen-sinh hoặc gọi 0238 3855 452.",
    "en": "please see the College's Admissions Consultation page at /en/admissions-consultation or call 0238 3855 452.",
}


def faq_answer(intent: FaqIntent, lang: str, contact: str | None = None) -> str:
    lang = lang if lang in FAQ_ANSWERS else "vi"
    answer = FAQ_ANSWERS[lang][intent]
    if intent == "human":
        return answer.format(contact=contact or _DEFAULT_CONTACT[lang])
    return answer
