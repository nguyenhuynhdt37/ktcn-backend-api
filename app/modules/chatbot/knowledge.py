"""Nguồn tri thức cho chatbot: khối lõi (luôn gửi), đối khớp cán bộ theo câu hỏi và tìm bài viết (top-k)."""
import asyncio
import re
import time
from typing import Any, Awaitable, Callable

from loguru import logger

from app.modules.chatbot.guard import fold, normalize_text
from app.modules.chatbot.prompt import ArticleSnippet
from app.modules.chatbot.static_knowledge import STATIC_ABOUT, build_contact_knowledge

_PAGES = {
    "faculty": {"vi": "/khoa/{slug}", "en": "/faculties/{slug}"},
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
    """cho minh toi hoi voi nhe nha a oi ban la cua va the nao gi nao o dau khong co ko khum uh
    ve cac nhung mot nay do duoc can muon xin vui long thi se da dang bi tai trong tu
    den hay hoac nhu sao bao nhieu may nao ai tim biet cho biet tin
    thay ten giang vien can bo giao su tien si thac truong khoa nganh hoc dao tao chuong trinh
    em anh chi ad admin bot
    the a an of to is are was were be do does did can could would should please tell me
    about what which who whom whose where when how why for in on at and or with my your i you
    lecturer lecturers staff teacher teachers professor faculty faculties program programs
    department departments school college named name""".split()
)

_STAFF_QUERY_STOPWORDS = _STOPWORDS | set(
    """pgs ts ths gs ks cn cu nhan ky su pho hieu truong bo mon don vi chuc vu
    phong van email sdt so dien thoai lien he gioi thieu thong tin ho nguoi dung dau phu trach
    gom danh sach tat ca nghien cuu linh vuc day lam viec thuoc
    bao nhieu tong luong trinh hoc ham day
    rector vice dean head office contact phone research work works unit list all any there whose
    assoc prof dr""".split()
)

_STAFF_CUES_RE = re.compile(
    r"\b(?:thay|co|giang vien|can bo|tien si|thac si|pho giao su|giao su|"
    r"pgs|ts|ths|gs|ten|named|called|lecturer|lecturers|staff|teacher|teachers|professor|faculty member)\b"
)
_EXPLICIT_CUE_PREFIX_RE = re.compile(
    r"\b(?:ten la|ten|named|called|thay giao|co giao|thay|co|tien si|thac si|pho giao su|giao su|pgs|ts|ths|gs|dr|prof)\b"
)
_DEPT_STAFF_CUE_RE = re.compile(
    r"\b(?:giang vien|can bo|nhan su|thay|co|truong khoa|pho khoa|pho truong khoa|lanh dao|ai|lecturer|lecturers|staff|dean|head|who)\b"
)
_LEADERSHIP_CUE_RE = re.compile(
    r"\b(?:ban lanh dao|ban giam hieu|hieu truong|pho hieu truong|rector|vice rector|leadership|board of management)\b"
)
_DEPT_ALIASES = (
    ("khoa cntt", "khoa-cong-nghe-thong-tin"),
    ("cntt", "khoa-cong-nghe-thong-tin"),
    ("cong nghe thong tin", "khoa-cong-nghe-thong-tin"),
    ("khoa khmt", "khoa-khoa-hoc-may-tinh-va-tri-tue-nhan-tao"),
    ("khmt", "khoa-khoa-hoc-may-tinh-va-tri-tue-nhan-tao"),
    ("khoa hoc may tinh", "khoa-khoa-hoc-may-tinh-va-tri-tue-nhan-tao"),
    ("tri tue nhan tao", "khoa-khoa-hoc-may-tinh-va-tri-tue-nhan-tao"),
    ("tu dong hoa", "khoa-tu-dong-hoa"),
    ("dien tu", "khoa-dien-tu-va-cong-nghe-ban-dan"),
    ("ban dan", "khoa-dien-tu-va-cong-nghe-ban-dan"),
    ("ky thuat dien", "khoa-cong-nghe-ky-thuat-dien"),
    ("o to", "khoa-cong-nghe-ky-thuat-o-to"),
    ("van phong truong", "van-phong-truong"),
)

_TRAILING_FILLERS = {
    "khong", "ko", "khum", "a", "ah", "vay", "nhe", "nha", "oi", "la", "ai", "o",
    "dau", "nao", "gi", "day", "lam", "viec", "khoa", "thuoc", "don", "vi", "cua", "truong",
    "in", "at", "of", "the", "is", "are", "who", "where", "which", "work", "works", "teach",
}
_NON_NAME_CUE_ARGS = _TRAILING_FILLERS | {
    "nhung", "cac", "moi", "tat", "ca", "giang", "vien", "can", "bo", "nhan", "su",
    "pho", "giao", "thay", "co", "nhieu", "may", "ten", "hoc", "mon", "nganh",
    "duoc", "phai", "the", "trong", "ve", "cho", "hoi", "de", "biet", "van", "phong",
    "chuong", "trinh", "dao", "tao", "ma", "hay", "hoac", "va", "thi", "all", "any",
    "from", "does", "do", "lecturer", "lecturers", "staff", "teacher", "teachers",
}
_EXPLICIT_NAME_BREAK_TOKENS = _NON_NAME_CUE_ARGS | {"chu"}
_STRICT_NAME_CUE_BREAK_TOKENS = {
    "khong", "ko", "khum", "a", "ah", "vay", "nhe", "nha", "oi", "la", "ai", "o", "dau", "nao",
    "gi", "day", "cua", "thuoc", "don", "vi", "thay", "co", "ong", "ba", "nguoi", "ay", "do", "nay",
    "ma", "hay", "hoac", "va", "thi", "cho", "hoi", "de", "biet", "chu", "is", "are", "who", "in", "at", "of",
}

_ROLE_PHRASES_TO_STRIP = (
    "ban lanh dao truong",
    "ban lanh dao",
    "ban giam hieu",
    "pho hieu truong phu trach truong",
    "pho hieu truong",
    "hieu truong",
    "pho truong khoa",
    "truong khoa",
    "pho truong bo mon",
    "truong bo mon",
    "van phong truong",
    "chuong trinh dao tao",
    "giang vien chinh",
    "giang vien cao cap",
    "giang vien",
    "can bo",
    "pho giao su",
    "giao su",
    "tien si",
    "thac si",
    "cu nhan",
    "ky su",
    "bao nhieu",
    "nhung ai",
    "may tinh",
    "vien thong",
    "dieu khien",
    "cong nghe",
    "ky thuat",
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


# Chuyên mục tin tức của website (các chuyên mục khác chứa trang tĩnh, lịch tuần...).
NEWS_CATEGORY_SLUG = "tin-tuc-va-su-kien"
_LATEST = re.compile(r"moi nhat|gan day|moi dang|latest|recent|newest")


def extract_phrases(question: str, limit: int = 3) -> list[str]:
    """Các cặp từ liền nhau (không bị stopword ngắt), vd 'tuyển dụng' — để tìm nguyên cụm."""
    runs: list[list[str]] = [[]]
    for token in re.findall(r"\w+", normalize_text(question).lower()):
        folded = fold(token)
        if len(folded) >= 2 and folded not in _STOPWORDS:
            runs[-1].append(token)
        else:
            runs.append([])
    phrases: list[str] = []
    for run in runs:
        for first, second in zip(run, run[1:]):
            phrase = f"{first} {second}"
            if phrase not in phrases:
                phrases.append(phrase)
    return phrases[:limit]


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


def _given_name(full_name: str) -> str:
    parts = (full_name or "").strip().split()
    return parts[-1] if parts else ""


def _is_test_department(dept) -> bool:
    slug = (getattr(dept, "slug", None) or "").strip().lower()
    name_folded = fold(_name(dept))
    if slug.startswith("dept-"):
        return True
    return bool(re.fullmatch(r"dept [a-z0-9]+", name_folded))


def _is_leadership_department(dept) -> bool:
    slug = (getattr(dept, "slug", None) or "").strip().lower()
    name_folded = fold(_name(dept))
    return (
        slug in ("ban-lanh-dao-vien", "institute-board-of-management")
        or "ban lanh dao" in name_folded
        or "board of management" in name_folded
    )


def _is_faculty_department(dept) -> bool:
    unit_type = (getattr(dept, "unit_type", None) or "").strip().lower()
    slug = (getattr(dept, "slug", None) or "").strip().lower()
    name_folded = fold(_name(dept))
    return (
        unit_type == "faculty"
        or slug.startswith(("khoa-", "faculty-"))
        or name_folded.startswith(("khoa ", "faculty "))
    )


def department_url(dept, lang: str) -> str:
    vi = lang != "en"
    if _is_leadership_department(dept):
        return "/vi/gioi-thieu/can-bo" if vi else "/en/about/staff"
    if _is_faculty_department(dept):
        return page_url("faculty", dept.slug, lang)
    unit_type = (getattr(dept, "unit_type", None) or "").strip().lower()
    slug = (getattr(dept, "slug", None) or "").strip().lower()
    if unit_type == "office" or slug.startswith("van-phong"):
        return "/vi/gioi-thieu" if vi else "/en/about"
    return page_url("department", dept.slug, lang)


def _is_placeholder_phone(phone: str | None) -> bool:
    cleaned = (phone or "").strip()
    return not cleaned or "+84 (24) 3754" in cleaned


def _is_placeholder_email(email: str | None) -> bool:
    cleaned = (email or "").strip().lower()
    return not cleaned or cleaned.endswith("@university.edu.vn")


def _format_staff_line(staff, lang: str, *, include_given_tag: bool = True, note: str | None = None) -> str:
    vi = lang != "en"
    position = _position_of(staff)
    unit = _name(getattr(staff, "department", None))
    given = _given_name(getattr(staff, "full_name", ""))
    prefix = f"[{'Tên gọi' if vi else 'Given name'}: {given}] " if include_given_tag and given else ""
    parts = [f"- {prefix}{_who(staff)} — {page_url('staff', staff.slug, lang)}"]
    if position:
        parts.append(f"{'Chức vụ' if vi else 'Position'}: {position}")
    if unit:
        parts.append(f"{'Đơn vị' if vi else 'Unit'}: {unit}")
    if note:
        parts.append(note)
    research = _plain(getattr(staff, "research_interests", None), limit=160)
    if research:
        parts.append(f"{'Nghiên cứu' if vi else 'Research'}: {research}")
    return "; ".join(parts)


def _format_degree_level(level: str | None, vi: bool) -> str:
    mapping = {
        "bachelor": "Đại học / Kỹ sư" if vi else "Bachelor / Engineer",
        "master": "Thạc sĩ" if vi else "Master",
        "phd": "Tiến sĩ" if vi else "PhD",
    }
    raw = (level or "").strip().lower()
    return mapping.get(raw, level or "")


def format_core_knowledge(departments, programs, staffs, lang: str) -> str:
    vi = lang != "en"
    lines: list[str] = []

    real_departments = [d for d in departments if not _is_test_department(d)]
    faculties = [d for d in real_departments if _is_faculty_department(d)]
    other_units = [
        d for d in real_departments if not _is_faculty_department(d) and not _is_leadership_department(d)
    ]

    lines.append(
        "## Các khoa đào tạo (Trang tổng hợp danh sách khoa: /vi/gioi-thieu/cac-khoa-dao-tao)"
        if vi
        else "## Academic Faculties (Faculties overview page: /en/about/faculties)"
    )
    for d in faculties:
        parts = [f"- {d.name} — {department_url(d, lang)}"]
        if getattr(d, "office", None):
            parts.append(f"{'Văn phòng' if vi else 'Office'}: {d.office}")
        if not _is_placeholder_phone(getattr(d, "phone", None)):
            parts.append(f"{'Điện thoại' if vi else 'Phone'}: {d.phone}")
        if not _is_placeholder_email(getattr(d, "email", None)):
            parts.append(f"Email: {d.email}")
        desc = _plain(getattr(d, "short_description", None) or getattr(d, "description", None))
        if desc:
            parts.append(desc)
        lines.append("; ".join(parts))

    if other_units:
        lines.append("## Văn phòng / Đơn vị hành chính" if vi else "## Administrative Offices")
        for d in other_units:
            parts = [f"- {d.name} — {department_url(d, lang)}"]
            if getattr(d, "office", None):
                parts.append(f"{'Văn phòng' if vi else 'Office'}: {d.office}")
            if not _is_placeholder_phone(getattr(d, "phone", None)):
                parts.append(f"{'Điện thoại' if vi else 'Phone'}: {d.phone}")
            if not _is_placeholder_email(getattr(d, "email", None)):
                parts.append(f"Email: {d.email}")
            desc = _plain(getattr(d, "short_description", None) or getattr(d, "description", None))
            if desc:
                parts.append(desc)
            lines.append("; ".join(parts))

    leaders = [s for s in staffs if "hieu truong" in fold(_position_of(s)) or "rector" in fold(_position_of(s))]
    lines.append(
        "## Ban lãnh đạo Trường (/vi/gioi-thieu/can-bo)"
        if vi
        else "## School leadership (/en/about/staff)"
    )
    for s in leaders:
        pos = _position_of(s)
        pos_folded = fold(pos)
        extra = ""
        if "phu trach" in pos_folded or "acting" in pos_folded or "in charge" in pos_folded:
            extra = (
                " (Người đứng đầu phụ trách điều hành Trường hiện nay; hiện chưa có Hiệu trưởng riêng, Phó Hiệu trưởng Hoàng Hữu Việt đang phụ trách Trường)"
                if vi
                else " (Acting head currently in charge of the College)"
            )
        lines.append(f"- {_who(s)} — {pos}{extra} — {page_url('staff', s.slug, lang)}")

    deans = [s for s in staffs if "truong khoa" in fold(_position_of(s)) or "dean" in fold(_position_of(s))]
    if deans:
        lines.append("## Trưởng / Phó khoa các đơn vị" if vi else "## Faculty Deans & Vice Deans")
        for s in deans:
            unit = _name(getattr(s, "department", None))
            unit_part = f" — {unit}" if unit else ""
            lines.append(f"- {_who(s)} — {_position_of(s)}{unit_part} — {page_url('staff', s.slug, lang)}")

    lines.append("## Chương trình đào tạo" if vi else "## Study programs")
    for p in programs:
        kind = "postgraduate" if getattr(p, "degree_level", None) == "master" else "undergraduate"
        parts = [f"- {p.name} — {page_url(kind, p.slug, lang)}"]
        if getattr(p, "code", None):
            parts.append(f"{'Mã' if vi else 'Code'}: {p.code}")
        parts.append(f"{'Bậc' if vi else 'Level'}: {_format_degree_level(getattr(p, 'degree_level', ''), vi)}")
        if getattr(p, "duration_years", None):
            parts.append(f"{'Thời gian' if vi else 'Duration'}: {p.duration_years} {'năm' if vi else 'years'}")
        desc = _plain(getattr(p, "short_description", None))
        if desc:
            parts.append(desc)
        lines.append("; ".join(parts))
    lines.append(
        "- Lưu ý: Trang tổng hợp chương trình đào tạo là /vi/dao-tao. Trường có Khoa Khoa học máy tính và Trí tuệ nhân tạo (/vi/khoa/khoa-khoa-hoc-may-tinh-va-tri-tue-nhan-tao) và Khoa Công nghệ thông tin (/vi/khoa/khoa-cong-nghe-thong-tin); toàn bộ chương trình đào tạo đã công bố được liệt kê ở trên."
        if vi
        else "- Note: Full programs overview is at /en/academics. The College includes the Faculty of Computer Science and Artificial Intelligence (/en/faculties/faculty-of-computer-science-and-artificial-intelligence) and the Faculty of Information Technology (/en/faculties/faculty-of-information-technology); all published programs are listed above."
    )

    lines.append("## Cán bộ" if vi else "## Staff")
    for s in staffs:
        lines.append(_format_staff_line(s, lang))

    return "\n".join(lines)


def _match_departments_in_question(folded_q: str, departments: list[Any]) -> list[Any]:
    real = [d for d in departments if not _is_test_department(d)]
    matched: list[Any] = []
    seen_ids: set[Any] = set()

    for d in real:
        d_folded = fold(_name(d))
        if d_folded and re.search(rf"\b{re.escape(d_folded)}\b", folded_q):
            matched.append(d)
            seen_ids.add(getattr(d, "id", d_folded))

    for alias, slug in _DEPT_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", folded_q):
            for d in real:
                if getattr(d, "slug", None) == slug and getattr(d, "id", slug) not in seen_ids:
                    matched.append(d)
                    seen_ids.add(getattr(d, "id", slug))

    return matched


def _extract_person_name_tokens(question: str, matched_depts: list[Any]) -> tuple[list[str], bool, bool]:
    # Loại bỏ từ có dấu mang nghĩa động từ/trợ từ ("có", "những", "nhỉ") trước khi bỏ dấu để không nhầm với tên riêng.
    norm_lower = normalize_text(question).lower()
    cue_source = re.sub(r"\b(?:có|những|nhỉ)\b", " ", norm_lower)
    folded_cue_source = fold(cue_source)

    for d in matched_depts:
        d_folded = fold(_name(d))
        if d_folded:
            folded_cue_source = re.sub(rf"\b{re.escape(d_folded)}\b", " ", folded_cue_source)
    for alias, _ in _DEPT_ALIASES:
        folded_cue_source = re.sub(rf"\b{re.escape(alias)}\b", " ", folded_cue_source)
    for phrase in _ROLE_PHRASES_TO_STRIP:
        folded_cue_source = re.sub(rf"\b{re.escape(phrase)}\b", " ", folded_cue_source)

    has_staff_cue = bool(_STAFF_CUES_RE.search(folded_cue_source))

    # 1. Nếu có mẫu rõ ràng như "tên Quang", "thầy Minh", ưu tiên trích xuất cụm tên ngay sau cue
    explicit_tokens: list[str] = []
    for match in _EXPLICIT_CUE_PREFIX_RE.finditer(folded_cue_source):
        cue_word = match.group(0)
        break_tokens = (
            _STRICT_NAME_CUE_BREAK_TOKENS
            if cue_word in {"ten", "ten la", "named", "called"}
            else _EXPLICIT_NAME_BREAK_TOKENS
        )
        rest_words = re.findall(r"[a-z0-9]+", folded_cue_source[match.end() :])[:4]
        if not rest_words or rest_words[0] in break_tokens:
            continue
        for tok in rest_words:
            if tok in break_tokens:
                break
            if len(tok) >= 2 and not tok.isdigit() and tok not in explicit_tokens:
                explicit_tokens.append(tok)

    if explicit_tokens:
        return explicit_tokens, True, True

    # 2.Fallback khi không có cue rõ ràng: lấy các token không phải stopword / tên khoa / chức vụ
    tokens = [
        tok
        for tok in folded_cue_source.split()
        if len(tok) >= 2 and tok not in _STAFF_QUERY_STOPWORDS and not tok.isdigit()
    ]
    return tokens, has_staff_cue, False


def build_staff_match_context(
    question: str,
    staffs: list[Any],
    departments: list[Any],
    lang: str = "vi",
) -> str:
    """Đối khớp cán bộ định hướng theo tên, đơn vị hoặc ban lãnh đạo để tránh LLM bịa sai."""
    vi = lang != "en"
    folded_q = fold(question)
    if not folded_q:
        return ""

    # 1. Khớp họ tên đầy đủ trực tiếp trong câu hỏi (vd "Võ Đức Quang", "Hoàng Hữu Việt")
    full_name_matches = []
    for s in staffs:
        full_folded = fold(getattr(s, "full_name", "") or "")
        en_folded = fold(getattr(s, "english_name", "") or "")
        if full_folded and re.search(rf"\b{re.escape(full_folded)}\b", folded_q):
            full_name_matches.append(s)
        elif en_folded and re.search(rf"\b{re.escape(en_folded)}\b", folded_q):
            full_name_matches.append(s)

    if full_name_matches:
        header = (
            "## Kết quả tra cứu cán bộ theo câu hỏi (ƯU TIÊN TUYỆT ĐỐI)"
            if vi
            else "## Matched staff for this question (STRICT PRIORITY)"
        )
        lines = [header]
        for s in full_name_matches:
            lines.append(_format_staff_line(s, lang, include_given_tag=False))
        lines.append(
            "Lưu ý: Chỉ trả lời về đúng các cán bộ nêu trên; không thêm tên cán bộ khác."
            if vi
            else "Note: Answer only with the staff listed above; do not add other staff members."
        )
        return "\n".join(lines)

    matched_depts = _match_departments_in_question(folded_q, departments)
    name_tokens, has_staff_cue, has_explicit_name = _extract_person_name_tokens(question, matched_depts)

    # 2. Khớp theo token tên (phân biệt rõ tên gọi chính ở cuối với họ/tên đệm)
    # Chỉ đối khớp theo từ đơn khi câu hỏi thực sự có ngữ cảnh hỏi về cán bộ/tên người (tránh nhầm "máy tính" -> "Tính").
    if name_tokens and (has_staff_cue or len(name_tokens) >= 2):
        raw_folded_pairs = [
            (normalize_text(tok).lower(), fold(tok))
            for tok in re.findall(r"\w+", question)
            if fold(tok) in name_tokens
        ]
        raw_by_fold = {folded_tok: raw_tok for raw_tok, folded_tok in raw_folded_pairs}

        multi_matches: list[Any] = []
        given_matches: list[Any] = []
        partial_matches: list[Any] = []
        seen_ids: set[Any] = set()

        if len(name_tokens) >= 2:
            token_set = set(name_tokens)
            for s in staffs:
                s_words = fold(getattr(s, "full_name", "") or "").split()
                if token_set.issubset(set(s_words)):
                    multi_matches.append(s)
                    seen_ids.add(getattr(s, "id", s.full_name))

        for s in staffs:
            sid = getattr(s, "id", s.full_name)
            if sid in seen_ids:
                continue
            raw_words = [w.lower() for w in (getattr(s, "full_name", "") or "").strip().split()]
            folded_words = [fold(w) for w in raw_words]
            if not folded_words:
                continue
            given_word = folded_words[-1]
            other_words = folded_words[:-1]

            if any(tok == given_word for tok in name_tokens):
                given_matches.append(s)
                seen_ids.add(sid)
            elif any(tok in other_words for tok in name_tokens):
                partial_matches.append(s)
                seen_ids.add(sid)

        # Nếu người hỏi gõ có dấu (vd "Hòa" khác "Hoa"), ưu tiên người khớp đúng dấu lên đầu
        def _accent_score(staff_obj: Any) -> int:
            last_raw = (getattr(staff_obj, "full_name", "") or "").strip().split()[-1].lower()
            last_fold = fold(last_raw)
            asked_raw = raw_by_fold.get(last_fold)
            if asked_raw and asked_raw != last_fold:
                return 0 if asked_raw == last_raw else 1
            return 0

        given_matches.sort(key=_accent_score)

        has_any_match = bool(multi_matches or given_matches or partial_matches)
        if (has_staff_cue and (has_any_match or has_explicit_name)) or multi_matches:
            query_label = " ".join(name_tokens)
            header = (
                "## Kết quả tra cứu cán bộ theo câu hỏi (ƯU TIÊN TUYỆT ĐỐI)"
                if vi
                else "## Matched staff for this question (STRICT PRIORITY)"
            )
            lines = [header, f"{'Từ khóa tên tra cứu' if vi else 'Searched name keyword'}: \"{query_label}\""]

            if multi_matches:
                lines.append(
                    f"- Cán bộ khớp các từ tên ({len(multi_matches)} người):"
                    if vi
                    else f"- Staff matching name terms ({len(multi_matches)}):"
                )
                for s in multi_matches:
                    lines.append("  " + _format_staff_line(s, lang, include_given_tag=False))

            if given_matches:
                lines.append(
                    f"- Cán bộ có TÊN GỌI CHÍNH khớp \"{query_label}\" ({len(given_matches)} người):"
                    if vi
                    else f"- Staff whose GIVEN NAME matches \"{query_label}\" ({len(given_matches)}):"
                )
                for s in given_matches:
                    lines.append("  " + _format_staff_line(s, lang, include_given_tag=False))

            if partial_matches:
                lines.append(
                    f"- Cán bộ chỉ có HỌ hoặc TÊN ĐỆM chứa \"{query_label}\" (KHÔNG phải tên gọi chính; {len(partial_matches)} người):"
                    if vi
                    else f"- Staff whose SURNAME/MIDDLE NAME contains \"{query_label}\" (NOT given name; {len(partial_matches)}):"
                )
                for s in partial_matches:
                    given = _given_name(getattr(s, "full_name", ""))
                    note = (
                        f"Chỉ trùng họ/tên đệm; tên gọi chính là {given}"
                        if vi
                        else f"Surname/middle name match only; given name is {given}"
                    )
                    lines.append("  " + _format_staff_line(s, lang, include_given_tag=False, note=note))

            if not has_any_match:
                lines.append(
                    "- Không tìm thấy cán bộ/giảng viên nào trong danh sách chính thức của Trường có tên khớp với từ khóa này."
                    if vi
                    else "- No faculty or staff member in the College's official directory matches this name."
                )

            lines.append(
                "Lưu ý bắt buộc: Chỉ được liệt kê đúng các cán bộ ở mục này; tuyệt đối không tự thêm bất kỳ tên cán bộ nào khác từ danh sách chung."
                if vi
                else "Mandatory note: List ONLY the staff shown in this section; never pull other names from the general directory."
            )
            return "\n".join(lines)

    # 3. Hỏi danh sách giảng viên / trưởng khoa của một Khoa/Đơn vị cụ thể
    if matched_depts and _DEPT_STAFF_CUE_RE.search(folded_q):
        dept_ids = {getattr(d, "id", None) for d in matched_depts}
        dept_staffs = [s for s in staffs if getattr(s, "department_id", None) in dept_ids]
        if dept_staffs:
            dept_names = ", ".join(_name(d) for d in matched_depts)
            header = (
                f"## Kết quả tra cứu cán bộ thuộc đơn vị {dept_names} (ƯU TIÊN TUYỆT ĐỐI)"
                if vi
                else f"## Staff in {dept_names} (STRICT PRIORITY)"
            )
            lines = [header]
            for s in dept_staffs:
                lines.append(_format_staff_line(s, lang, include_given_tag=False))
            return "\n".join(lines)

    # 4. Hỏi về Hiệu trưởng / Ban lãnh đạo Trường
    if _LEADERSHIP_CUE_RE.search(folded_q):
        leaders = [
            s for s in staffs if "hieu truong" in fold(_position_of(s)) or "rector" in fold(_position_of(s))
        ]
        if leaders:
            header = (
                "## Kết quả tra cứu Ban lãnh đạo Trường (ƯU TIÊN TUYỆT ĐỐI)"
                if vi
                else "## School leadership lookup (STRICT PRIORITY)"
            )
            lines = [header]
            for s in leaders:
                pos = _position_of(s)
                note = (
                    "Hiện Trường chưa có Hiệu trưởng riêng; PGS. TS. Hoàng Hữu Việt là Phó Hiệu trưởng, phụ trách Trường (người đứng đầu điều hành hiện nay)."
                    if ("phu trach" in fold(pos) or "acting" in fold(pos)) and vi
                    else None
                )
                lines.append(_format_staff_line(s, lang, include_given_tag=False, note=note))
            return "\n".join(lines)

    return ""


async def _load_roster(db, lang: str) -> tuple[list[Any], list[Any]]:
    from app.modules.department.service import department_service
    from app.modules.staff.service import staff_service

    departments, _ = await department_service.list_departments(
        db=db, is_active=True, page=1, page_size=1000, lang=lang
    )
    staffs, _ = await staff_service.list_staffs(
        db=db, is_active=True, is_visible=True, page=1, page_size=1000, lang=lang
    )
    return departments, staffs


async def match_staff_for_question(
    db,
    question: str,
    lang: str = "vi",
    *,
    staffs: list[Any] | None = None,
    departments: list[Any] | None = None,
) -> str:
    if staffs is None or departments is None:
        departments, staffs = await _load_roster(db, lang)
    return build_staff_match_context(question, staffs, departments, lang)


async def _build_core(db, lang: str) -> str:
    from app.modules.program.service import program_service
    from app.modules.setting.service import setting_service

    departments, staffs = await _load_roster(db, lang)
    programs, _ = await program_service.list(db, published_only=True, page_size=200, lang=lang)
    try:
        site_settings = await setting_service.get_site_settings(db)
    except Exception:
        site_settings = None

    about = STATIC_ABOUT.get(lang) or STATIC_ABOUT["vi"]
    contact = build_contact_knowledge(site_settings, lang)
    return about + "\n\n" + contact + "\n\n" + format_core_knowledge(departments, programs, staffs, lang)


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

    async def clear(self) -> None:
        async with self._lock:
            self._values.clear()


async def search_articles(db, question: str, lang: str, limit: int = 4) -> list[ArticleSnippet]:
    from app.modules.article.schemas.portal import PortalArticleListResponse
    from app.modules.article.service import article_service

    keywords = extract_keywords(question)
    phrases = extract_phrases(question)
    wants_latest = bool(_LATEST.search(fold(question)))

    found: dict[str, ArticleSnippet] = {}

    async def collect(search: str | None, **filters) -> None:
        try:
            articles, _ = await article_service.list_all_articles_portal(
                db, search=search, page=1, page_size=limit * 2, lang=lang, **filters
            )
        except Exception as exc:  # tìm bài lỗi không được làm hỏng câu trả lời
            logger.warning(f"Chatbot article search failed for {search!r}: {exc}")
            return
        for article in articles:
            item = PortalArticleListResponse.model_validate(article)
            key = str(item.id)
            if key not in found and item.slug:
                found[key] = ArticleSnippet(
                    title=item.title, url=page_url("article", item.slug, lang),
                    excerpt=_plain(item.excerpt) or item.title,
                    published=(item.published_at or item.publish_at).strftime("%d/%m/%Y")
                    if (item.published_at or item.publish_at) else "",
                )

    if wants_latest:
        # "tin mới nhất": bài tin mới đăng (bỏ trang tĩnh), không cần từ khóa
        await collect(None, category_slug=NEWS_CATEGORY_SLUG, sort_by="published_at", sort_dir="desc")
        latest = list(found.values())[:limit]
        return latest

    # Cụm từ liền nhau trước ("tuyển dụng"), rồi từ lẻ; sau đó xếp hạng theo số từ khớp.
    for term in [*phrases, *keywords]:
        await collect(term)

    def score(snippet: ArticleSnippet) -> int:
        text = fold(f"{snippet.title} {snippet.excerpt}")
        return 2 * sum(fold(p) in text for p in phrases) + sum(fold(k) in text for k in keywords)

    ranked = sorted(found.values(), key=score, reverse=True)  # sort ổn định: giữ thứ tự gặp trước khi hòa
    return ranked[:limit]
