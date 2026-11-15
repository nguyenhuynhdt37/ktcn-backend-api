from types import SimpleNamespace as NS

from app.modules.chatbot.knowledge import (
    CoreKnowledgeCache,
    extract_keywords,
    format_core_knowledge,
    page_url,
)


def test_extract_keywords_drops_stopwords_and_keeps_longest():
    kws = extract_keywords("Cho mình hỏi học phí ngành công nghệ thông tin")
    # Từ khóa giữ nguyên dấu để tìm được trong DB tiếng Việt.
    assert kws and "cho" not in kws and "hỏi" not in kws and "mình" not in kws
    assert "ngành" in kws and "thông" in kws
    assert len(kws) <= 3


def test_extract_keywords_empty_for_only_stopwords():
    assert extract_keywords("cho mình hỏi với nhé") == []
    assert extract_keywords("") == []


def test_page_url_matches_frontend_routes_per_locale():
    assert page_url("department", "khoa-a", "vi") == "/vi/bo-mon/khoa-a"
    assert page_url("department", "khoa-a", "en") == "/en/departments/khoa-a"
    assert page_url("postgraduate", "p", "vi") == "/vi/dao-tao/sau-dai-hoc/p"
    assert page_url("undergraduate", "p", "en") == "/en/academics/undergraduate/p"
    assert page_url("staff", "s", "en") == "/en/staffs/s"
    assert page_url("article", "tin", "vi") == "/vi/tin"


def _data():
    dept = NS(name="Khoa Tự động hóa", slug="khoa-tu-dong-hoa", unit_type="faculty",
              description="<p>Đào tạo robot</p>", short_description=None,
              office="Tầng 4", phone="0123", email="fa@x.vn")
    prog = NS(name="Thạc sĩ CNTT", slug="ths-cntt", code="8480201", degree_level="master",
              duration_years=2, short_description="Chương trình thạc sĩ")
    staff = NS(full_name="Lê Văn Minh", slug="le-van-minh", academic_title_resolved=None,
               degree_resolved="Tiến sĩ", position=NS(name="Phó Hiệu trưởng"),
               department=NS(name="Khoa CNTT"))
    return [dept], [prog], [staff]


def test_format_core_knowledge_has_links_and_only_given_items():
    depts, progs, staffs = _data()
    text = format_core_knowledge(depts, progs, staffs, "vi")
    assert "/vi/bo-mon/khoa-tu-dong-hoa" in text
    assert "/vi/dao-tao/sau-dai-hoc/ths-cntt" in text
    assert "/vi/nhan-su/le-van-minh" in text
    assert "Phó Hiệu trưởng" in text and "0123" in text and "fa@x.vn" in text
    assert "<p>" not in text
    assert "Nguyễn" not in text


def test_format_truncates_long_descriptions():
    depts, progs, staffs = _data()
    depts[0].description = "x" * 1000
    text = format_core_knowledge(depts, progs, staffs, "vi")
    assert "x" * 400 not in text


async def test_cache_reuses_value_within_ttl_and_rebuilds_at_zero_ttl():
    calls = []

    async def builder(db, lang):
        calls.append(lang)
        return f"core-{lang}"

    cache = CoreKnowledgeCache(300, builder=builder)
    assert await cache.get(None, "vi") == "core-vi"
    assert await cache.get(None, "vi") == "core-vi"
    assert await cache.get(None, "en") == "core-en"
    assert calls == ["vi", "en"]

    calls.clear()
    fresh = CoreKnowledgeCache(0, builder=builder)
    await fresh.get(None, "vi")
    await fresh.get(None, "vi")
    assert calls == ["vi", "vi"]
