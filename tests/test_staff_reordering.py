"""Thứ tự hiển thị cán bộ trong một đơn vị.

Dữ liệu thật có sort_order trùng nhau và nhảy cóc (0, 0, 0, 20), nên con số trong
form không khớp với vị trí thật trên danh sách. Các test này dùng một đơn vị tạm,
không đụng tới thứ tự của dữ liệu đang có.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.modules.department.models import Department
from app.modules.position.models import Position
from app.modules.staff.models import Staff
from app.modules.staff.schemas import StaffUpdate
from app.modules.staff.service import staff_service


async def _displayed(db, department_id) -> list[tuple[str, int]]:
    """Tên và sort_order theo đúng thứ tự mà trang danh sách đang dùng."""
    rows = await db.execute(
        select(Staff.full_name, Staff.sort_order)
        .where(Staff.department_id == department_id, Staff.deleted_at.is_(None))
        .order_by(Staff.sort_order.asc(), Staff.created_at.desc())
    )
    return [(name, sort) for name, sort in rows.all()]


@pytest.fixture
async def messy_department(db_session):
    """Đơn vị tạm có 4 cán bộ hiển thị theo thứ tự A, B, C, D với sort_order 0, 0, 0, 20."""
    dept = Department(is_active=True, sort_order=9999)
    pos = Position(is_active=True, sort_order=9999)
    db_session.add_all([dept, pos])
    await db_session.flush()

    now = datetime.now(UTC)
    staffs = {}
    # Cùng sort_order thì bản ghi tạo sau hiển thị trước.
    for offset, (name, sort) in enumerate([("C", 0), ("B", 0), ("A", 0), ("D", 20)]):
        staff = Staff(
            department_id=dept.id,
            position_id=pos.id,
            full_name=name,
            slug=f"reorder-test-{uuid.uuid4().hex}",
            sort_order=sort,
            created_at=now + timedelta(seconds=offset),
        )
        db_session.add(staff)
        staffs[name] = staff
    dept_id, pos_id = dept.id, pos.id
    await db_session.commit()

    try:
        yield dept, staffs
    finally:
        await db_session.rollback()
        await db_session.execute(delete(Staff).where(Staff.department_id == dept_id))
        await db_session.execute(delete(Department).where(Department.id == dept_id))
        await db_session.execute(delete(Position).where(Position.id == pos_id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_saving_without_touching_order_keeps_order_and_repairs_numbers(db_session, messy_department):
    dept, staffs = messy_department
    assert [name for name, _ in await _displayed(db_session, dept.id)] == ["A", "B", "C", "D"]

    # Người dùng mở form của D (đang ghi 20), sửa số điện thoại rồi lưu.
    await staff_service.update_staff(db_session, staffs["D"].id, StaffUpdate(phone="0123", sort_order=20))
    await db_session.commit()

    assert await _displayed(db_session, dept.id) == [("A", 0), ("B", 1), ("C", 2), ("D", 3)]


@pytest.mark.asyncio
async def test_moving_a_staff_to_the_top_among_duplicates(db_session, messy_department):
    dept, staffs = messy_department

    # Đưa D (đang cuối) lên đầu danh sách.
    await staff_service.update_staff(db_session, staffs["D"].id, StaffUpdate(sort_order=0))
    await db_session.commit()

    assert await _displayed(db_session, dept.id) == [("D", 0), ("A", 1), ("B", 2), ("C", 3)]


@pytest.mark.asyncio
async def test_move_up_swaps_with_the_person_shown_above(db_session, messy_department):
    dept, staffs = messy_department

    # C đang hiển thị thứ 3 nhưng sort_order vẫn là 0 như A và B.
    await staff_service.move_staff(db_session, staffs["C"].id, "up")
    await db_session.commit()
    assert await _displayed(db_session, dept.id) == [("A", 0), ("C", 1), ("B", 2), ("D", 3)]

    await staff_service.move_staff(db_session, staffs["C"].id, "top")
    await db_session.commit()
    assert await _displayed(db_session, dept.id) == [("C", 0), ("A", 1), ("B", 2), ("D", 3)]

    # Đã ở đầu thì "lên" không làm gì.
    await staff_service.move_staff(db_session, staffs["C"].id, "up")
    await staff_service.move_staff(db_session, staffs["C"].id, "down")
    await db_session.commit()
    assert await _displayed(db_session, dept.id) == [("A", 0), ("C", 1), ("B", 2), ("D", 3)]
