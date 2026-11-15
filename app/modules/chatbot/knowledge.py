"""Nguồn tri thức cho chatbot: khối lõi (luôn gửi) và tìm bài viết (top-k)."""
import asyncio
import re
import time
from typing import Awaitable, Callable

from loguru import logger

from app.modules.chatbot.guard import fold, normalize_text
from app.modules.chatbot.prompt import ArticleSnippet

_PAGES = {
    "department": {"vi": "/bo-mon/{slug}", "en": "/departments/{slug}"},
    "undergraduate": {"vi": "/dao-tao/dai-hoc/{slug}", "en": "/academics/undergraduate/{slug}"},
    "postgraduate": {"vi": "/dao-tao/sau-dai-hoc/{slug}", "en": "/academics/postgraduate/{slug}"},
    "staff": {"vi": "/nhan-su/{slug}", "en": "/staffs/{slug}"},
    "article": {"vi": "/{slug}", "en": "/{slug}"},
}


def page_url(kind: str, slug: str, lang: str) -> str:
    lang = lang if lang in ("vi", "en") else "vi"
    return f"/{lang}" + _PAGES[kind][lang].format(slug=slug)


_STOPWORDS = set(
    """cho minh toi hoi voi nhe nha a oi ban la cua va the nao gi nao o dau khong co
    ve cac nhung mot nay do duoc can muon xin vui long thi se da dang bi tai trong tu
    den hay hoac nhu sao bao nhieu may nao ai tim biet cho biet
    the a an of to is are was were be do does did can could would should please tell me
    about what which who whom whose where when how why for in on at and or with my your i you""".split()
)

_TAGS = re.compile(r"<[^>]*>")


def extract_keywords(question: str, limit: int = 3) -> list[str]:
    """Từ khóa (giữ nguyên dấu) để tìm bài viết: bỏ stopword, ưu tiên từ dài."""
    seen: list[str] = []
    for token in re.findall(r"\w+", normalize_text(question).lower()):
        if len(fold(token)) < 3 or fold(token) in _STOPWORDS or token in seen:
            continue
        seen.append(token)
    return sorted(seen, key=len, reverse=True)[:limit]


def _plain(text: str | None, limit: int = 300) -> str:
    cleaned = re.sub(r"\s+", " ", _TAGS.sub(" ", text or "")).strip()
    return cleaned[:limit]


def _name(obj) -> str:
    return getattr(obj, "name", None) or ""


def _position_of(staff) -> str:
    return _name(getattr(staff, "position", None)) or getattr(staff, "position_name", None) or ""


def _who(staff) -> str:
    title = " ".join(
        x for x in (getattr(staff, "academic_title_resolved", None), getattr(staff, "degree_resolved", None)) if x
    )
    return f"{title} {staff.full_name}".strip()


def format_core_knowledge(departments, programs, staffs, lang: str) -> str:
    vi = lang != "en"
    lines: list[str] = []

    lines.append("## Đơn vị" if vi else "## Units")
    for d in departments:
        parts = [f"- {d.name} — {page_url('department', d.slug, lang)}"]
        for label, value in (
            ("Văn phòng" if vi else "Office", getattr(d, "office", None)),
            ("Điện thoại" if vi else "Phone", getattr(d, "phone", None)),
            ("Email", getattr(d, "email", None)),
        ):
            if value:
                parts.append(f"{label}: {value}")
        desc = _plain(getattr(d, "short_description", None) or getattr(d, "description", None))
        if desc:
            parts.append(desc)
        lines.append("; ".join(parts))

    leaders = [s for s in staffs if "hieu truong" in fold(_position_of(s)) or "rector" in fold(_position_of(s))]
    lines.append("## Ban lãnh đạo Trường" if vi else "## School leadership")
    for s in leaders:
        lines.append(f"- {_who(s)} — {_position_of(s)} — {page_url('staff', s.slug, lang)}")

    lines.append("## Chương trình đào tạo" if vi else "## Study programs")
    for p in programs:
        kind = "postgraduate" if getattr(p, "degree_level", None) == "master" else "undergraduate"
        parts = [f"- {p.name} — {page_url(kind, p.slug, lang)}"]
        if getattr(p, "code", None):
            parts.append(f"{'Mã' if vi else 'Code'}: {p.code}")
        parts.append(f"{'Bậc' if vi else 'Level'}: {getattr(p, 'degree_level', '')}")
        if getattr(p, "duration_years", None):
            parts.append(f"{'Thời gian' if vi else 'Duration'}: {p.duration_years} {'năm' if vi else 'years'}")
        desc = _plain(getattr(p, "short_description", None))
        if desc:
            parts.append(desc)
        lines.append("; ".join(parts))

    lines.append("## Cán bộ" if vi else "## Staff")
    for s in staffs:
        position = _position_of(s)
        unit = _name(getattr(s, "department", None))
        parts = [f"- {_who(s)} — {page_url('staff', s.slug, lang)}"]
        if position:
            parts.append(f"{'Chức vụ' if vi else 'Position'}: {position}")
        if unit:
            parts.append(f"{'Đơn vị' if vi else 'Unit'}: {unit}")
        lines.append("; ".join(parts))

    return "\n".join(lines)


async def _build_core(db, lang: str) -> str:
    from app.modules.department.service import department_service
    from app.modules.program.service import program_service
    from app.modules.staff.service import staff_service

    departments, _ = await department_service.list_departments(
        db=db, is_active=True, page=1, page_size=1000, lang=lang
    )
    programs, _ = await program_service.list(db, published_only=True, page_size=200, lang=lang)
    staffs, _ = await staff_service.list_staffs(
        db=db, is_active=True, is_visible=True, page=1, page_size=1000, lang=lang
    )
    return format_core_knowledge(departments, programs, staffs, lang)


class CoreKnowledgeCache:
    def __init__(self, ttl_seconds: int, builder: Callable[..., Awaitable[str]] | None = None) -> None:
        self._ttl = ttl_seconds
        self._builder = builder or _build_core
        self._values: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, db, lang: str) -> str:
        async with self._lock:
            cached = self._values.get(lang)
            now = time.monotonic()
            if cached and now - cached[0] < self._ttl:
                return cached[1]
            value = await self._builder(db, lang)
            self._values[lang] = (now, value)
            return value


async def search_articles(db, question: str, lang: str, limit: int = 4) -> list[ArticleSnippet]:
    from app.modules.article.schemas.portal import PortalArticleListResponse
    from app.modules.article.service import article_service

    found: dict[str, ArticleSnippet] = {}
    for keyword in extract_keywords(question):
        try:
            articles, _ = await article_service.list_all_articles_portal(
                db, search=keyword, page=1, page_size=limit, lang=lang
            )
        except Exception as exc:  # tìm bài lỗi không được làm hỏng câu trả lời
            logger.warning(f"Chatbot article search failed for {keyword!r}: {exc}")
            continue
        for article in articles:
            item = PortalArticleListResponse.model_validate(article)
            key = str(item.id)
            if key not in found and item.slug:
                found[key] = ArticleSnippet(
                    title=item.title, url=page_url("article", item.slug, lang),
                    excerpt=_plain(item.excerpt) or item.title,
                )
    return list(found.values())[:limit]
