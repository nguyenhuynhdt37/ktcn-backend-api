import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.modules.chatbot.knowledge import (
    build_staff_match_context,
    extract_keywords,
    format_core_knowledge,
)
from app.modules.chatbot.output_guard import sanitize_answer
from app.modules.setting.models import Setting
from app.modules.setting.service import SITE_APPEARANCE_KEY


def _make_dept(dept_id: str, name: str, slug: str, phone: str | None = None, email: str | None = None):
    return SimpleNamespace(
        id=dept_id,
        name=name,
        slug=slug,
        office="Tầng 1",
        phone=phone,
        email=email,
        short_description=None,
        description=None,
    )


def _make_staff(
    staff_id: str,
    full_name: str,
    slug: str,
    position_name: str,
    dept,
    title: str | None = None,
    degree: str | None = "Tiến sĩ",
):
    return SimpleNamespace(
        id=staff_id,
        full_name=full_name,
        english_name=None,
        slug=slug,
        department_id=dept.id,
        department=dept,
        position=SimpleNamespace(name=position_name),
        position_name=position_name,
        academic_title_resolved=title,
        degree_resolved=degree,
        research_interests=None,
    )


def test_build_staff_match_context_handles_given_name_middle_name_and_false_positives():
    dept_khmt = _make_dept("d1", "Khoa Khoa học máy tính và Trí tuệ nhân tạo", "khoa-khoa-hoc-may-tinh-va-tri-tue-nhan-tao")
    dept_tdh = _make_dept("d2", "Khoa Tự động hóa", "khoa-tu-dong-hoa")
    dept_cntt = _make_dept("d3", "Khoa Công nghệ thông tin", "khoa-cong-nghe-thong-tin")
    dept_bld = _make_dept("d0", "Ban lãnh đạo Trường", "ban-lanh-dao-vien")

    staffs = [
        _make_staff("s0", "Hoàng Hữu Việt", "hoang-huu-viet", "Phó Hiệu trưởng, phụ trách Trường", dept_bld, title="Phó giáo sư"),
        _make_staff("s1", "Võ Đức Quang", "vo-duc-quang", "Giảng viên", dept_khmt),
        _make_staff("s2", "Hoàng Hữu Tính", "hoang-huu-tinh", "Giảng viên", dept_khmt),
        _make_staff("s3", "Lê Văn Chương", "le-van-chuong", "Phó trưởng khoa", dept_tdh),
        _make_staff("s4", "Nguyễn Quang Ninh", "nguyen-quang-ninh", "Giảng viên chính", dept_cntt, degree="Thạc sĩ"),
        _make_staff("s5", "Mai Thế Anh", "mai-the-anh", "Trưởng khoa", dept_tdh),
    ]
    depts = [dept_bld, dept_khmt, dept_tdh, dept_cntt]

    # 1. Hỏi tên Quang -> chỉ khớp Võ Đức Quang (tên chính) và ghi chú Nguyễn Quang Ninh (tên đệm), không dính Lê Văn Chương
    ctx_quang = build_staff_match_context("có thầy nào tên quang", staffs, depts, "vi")
    assert "Võ Đức Quang" in ctx_quang
    assert "Nguyễn Quang Ninh" in ctx_quang
    assert "Lê Văn Chương" not in ctx_quang
    assert "TÊN GỌI CHÍNH" in ctx_quang

    # 2. Hỏi tên Anh -> tìm được Mai Thế Anh
    ctx_anh = build_staff_match_context("cho mình hỏi có thầy nào tên anh không", staffs, depts, "vi")
    assert "Mai Thế Anh" in ctx_anh

    # 3. Hỏi tên không tồn tại -> báo rõ không tìm thấy
    ctx_bao = build_staff_match_context("có thầy nào tên bảo không", staffs, depts, "vi")
    assert "Không tìm thấy cán bộ/giảng viên nào" in ctx_bao

    # 4. Hỏi "Chương trình đào tạo ngành khoa học máy tính" -> không khớp nhầm Hoàng Hữu Tính
    ctx_prog = build_staff_match_context("Chương trình đào tạo ngành khoa học máy tính", staffs, depts, "vi")
    assert "Hoàng Hữu Tính" not in ctx_prog

    # 5. Hỏi giảng viên của Khoa Tự động hóa (có dấu và không dấu) -> liệt kê đúng người của khoa
    ctx_tdh = build_staff_match_context("Khoa Tự động hóa có những giảng viên nào?", staffs, depts, "vi")
    assert "Mai Thế Anh" in ctx_tdh
    assert "Lê Văn Chương" in ctx_tdh
    assert "Võ Đức Quang" not in ctx_tdh

    ctx_tdh_unaccented = build_staff_match_context("khoa tu dong hoa co nhung giang vien nao", staffs, depts, "vi")
    assert "Mai Thế Anh" in ctx_tdh_unaccented
    assert "Lê Văn Chương" in ctx_tdh_unaccented

    # 6. Hỏi Hiệu trưởng -> trả thông tin Phó Hiệu trưởng phụ trách Trường
    ctx_rector = build_staff_match_context("Hiệu trưởng của trường là ai?", staffs, depts, "vi")
    assert "Hoàng Hữu Việt" in ctx_rector


def test_format_core_knowledge_filters_test_departments_and_placeholder_contacts():
    fake_dept = _make_dept("df", "Dept A", "dept-a-b078")
    bld_dept = _make_dept("db", "Ban lãnh đạo Trường", "ban-lanh-dao-vien")
    real_dept = _make_dept(
        "d1",
        "Khoa Công nghệ thông tin",
        "khoa-cong-nghe-thong-tin",
        phone="+84 (24) 3754 7891",
        email="fit@university.edu.vn",
    )
    staff = _make_staff("s1", "Cao Thanh Sơn", "cao-thanh-son", "Trưởng khoa", real_dept)
    prog = SimpleNamespace(
        name="Công nghệ thông tin",
        slug="cong-nghe-thong-tin",
        code="7480201",
        degree_level="bachelor",
        duration_years=5.0,
        short_description="Đào tạo kỹ sư CNTT",
    )

    text = format_core_knowledge([fake_dept, bld_dept, real_dept], [prog], [staff], "vi")
    assert "Dept A" not in text
    assert "/vi/bo-mon/ban-lanh-dao-vien" not in text
    assert "/vi/gioi-thieu/cac-khoa-dao-tao" in text
    assert "/vi/khoa/khoa-cong-nghe-thong-tin" in text
    assert "+84 (24) 3754 7891" not in text
    assert "fit@university.edu.vn" not in text
    assert "[Tên gọi: Sơn]" in text
    assert "Đại học / Kỹ sư" in text
    assert "## Trưởng / Phó khoa các đơn vị" in text


def test_extract_keywords_ignores_staff_question_fillers():
    kws = extract_keywords("có thầy nào tên quang")
    assert kws == ["quang"]


def test_sanitize_answer_strips_redundant_no_info_tail():
    raw = (
        "- Địa chỉ tư vấn tuyển sinh: Tầng 2, Nhà A0, 182 Lê Duẩn, TP. Vinh.\n"
        "- Biểu mẫu đăng ký tư vấn: /vi/tu-van-tuyen-sinh\n"
        "- Chi tiết các khoa xem tại /vi/bo-mon/ban-lanh-dao-vien và /vi/bo-mon/khoa-cong-nghe-thong-tin\n"
        "- Mình chưa có thông tin này trên website của trường. Bạn vui lòng xem trang Liên hệ (/lien-he) hoặc hỏi cách khác để mình hỗ trợ nhé."
    )
    cleaned = sanitize_answer(raw, "secret-canary", "vi")
    assert "/vi/tu-van-tuyen-sinh" in cleaned
    assert "/vi/gioi-thieu/cac-khoa-dao-tao" in cleaned
    assert "/vi/khoa/khoa-cong-nghe-thong-tin" in cleaned
    assert "/vi/bo-mon/ban-lanh-dao-vien" not in cleaned
    assert "Mình chưa có thông tin này" not in cleaned


@pytest.mark.asyncio
async def test_site_settings_portal_and_admin_endpoints(
    client: AsyncClient, admin_headers: dict, db_session
):
    # Lưu lại trạng thái ban đầu (nếu có) để khôi phục sau test
    initial_res = await client.get("/api/v1/portal/settings")
    assert initial_res.status_code == 200
    initial_data = initial_res.json()
    assert initial_data["phone"]
    assert initial_data["email"]

    try:
        marker_phone = f"0238-{uuid.uuid4().hex[:6]}"
        payload = {
            "header_logo_object_key": "files/test-header-logo.png",
            "footer_logo_object_key": "files/test-footer-logo.png",
            "fanpage_image_object_key": None,
            "logo_alt_vi": "Logo KTCN Test",
            "logo_alt_en": "SET Logo Test",
            "college_name_vi": "Trường Kỹ thuật và Công nghệ - Trường Đại học Vinh",
            "college_name_en": "College of Engineering and Technology - Vinh University",
            "address_vi": "182 Lê Duẩn, Thành phố Vinh, Nghệ An",
            "address_en": "182 Le Duan, Vinh City, Nghe An",
            "phone": marker_phone,
            "email": "cet@vinhuni.edu.vn",
            "website": "ktcn.itup.io.vn",
            "responsible_officer_vi": "PGS. TS. Hoàng Hữu Việt - Hiệu phó",
            "responsible_officer_en": "Assoc. Prof. Dr. Hoang Huu Viet - Vice Rector",
            "facebook_url": "https://www.facebook.com/Vienktcn",
            "messenger_url": "#",
            "copyright_vi": "© {year} Bản quyền thuộc về Trường Kỹ thuật và Công nghệ.",
            "copyright_en": "© {year} College of Engineering and Technology.",
            "developer_name": "CLB ITUP",
            "developer_url": "https://www.facebook.com/itup.binhdanhocvuso.dhv/",
            "quick_links": [
                {
                    "label_vi": "Liên hệ",
                    "label_en": "Contact",
                    "href": "/tu-van-tuyen-sinh",
                    "open_in_new_tab": False,
                }
            ],
            "external_links": [
                {
                    "label_vi": "Đại học Vinh",
                    "label_en": "Vinh University",
                    "href": "https://vinhuni.edu.vn",
                    "open_in_new_tab": True,
                }
            ],
        }

        # Admin GET
        admin_get = await client.get("/api/v1/admin/settings", headers=admin_headers)
        assert admin_get.status_code == 200

        # Admin PUT without auth -> 401 (xóa cookie login từ admin_headers trước khi gửi request không xác thực)
        saved_cookies = dict(client.cookies)
        client.cookies.clear()
        try:
            unauth_put = await client.put("/api/v1/admin/settings", json=payload)
            assert unauth_put.status_code == 401
        finally:
            client.cookies.update(saved_cookies)

        # Admin PUT with auth -> 200
        admin_put = await client.put("/api/v1/admin/settings", json=payload, headers=admin_headers)
        assert admin_put.status_code == 200
        updated = admin_put.json()
        assert updated["phone"] == marker_phone
        assert updated["header_logo_url"] == "/api/v1/portal/media/file/files/test-header-logo.png"
        assert updated["footer_logo_url"] == "/api/v1/portal/media/file/files/test-footer-logo.png"

        # Portal GET reflects update
        portal_get = await client.get("/api/v1/portal/settings")
        assert portal_get.status_code == 200
        assert portal_get.json()["phone"] == marker_phone
        assert len(portal_get.json()["quick_links"]) == 1
    finally:
        # Dọn dẹp: xóa bản ghi settings test hoặc khôi phục lại như trước
        await db_session.execute(delete(Setting).where(Setting.key == SITE_APPEARANCE_KEY))
        await db_session.commit()
