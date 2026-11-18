"""
Global Search API — Tìm kiếm nhanh đa nguồn dữ liệu.
Endpoint: GET /api/v1/admin/search?q=keyword&limit=5
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

# Models
from app.modules.article.models import Article, ArticleTranslation
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import UserResponse
from app.modules.category.models import Category
from app.modules.staff.models import Staff
from app.modules.tag.models import Tag, TagTranslation

router = APIRouter()


async def _search_articles(
    db: AsyncSession, keyword: str, limit: int, current_user: UserResponse
) -> list[dict]:
    """Tìm bài viết theo title trong ArticleTranslation (DISTINCT ON article_id)."""
    from app.modules.category.models import CategoryTranslation

    stmt = (
        select(
            Article.id,
            ArticleTranslation.title,
            ArticleTranslation.slug,
            Article.status,
            Article.published_at,
            CategoryTranslation.name.label("category_name"),
        )
        .join(ArticleTranslation, ArticleTranslation.article_id == Article.id)
        .outerjoin(Category, Category.id == Article.category_id)
        .outerjoin(
            CategoryTranslation,
            (CategoryTranslation.category_id == Category.id),
        )
        .where(
            Article.deleted_at.is_(None),
            ArticleTranslation.title.ilike(f"%{keyword}%"),
        )
    )
    if not current_user.is_admin:
        stmt = stmt.where(
            Article.is_draft.is_(False) | (Article.author_id == current_user.id)
        )
    stmt = (
        stmt.distinct(Article.id)
        .order_by(Article.id, Article.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "slug": r.slug,
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "category_name": r.category_name,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in result.all()
    ]


async def _search_users(
    db: AsyncSession, keyword: str, limit: int, include_email: bool
) -> list[dict]:
    """Tìm user theo full_name, username (và email nếu là admin)."""
    keyword_filter = User.full_name.ilike(f"%{keyword}%") | User.username.ilike(
        f"%{keyword}%"
    )
    if include_email:
        keyword_filter = keyword_filter | User.email.ilike(f"%{keyword}%")

    stmt = (
        select(User.id, User.full_name, User.email, User.username)
        .where(
            User.deleted_at.is_(None),
            keyword_filter,
        )
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": str(r.id),
            "full_name": r.full_name,
            "email": r.email if include_email else None,
            "username": r.username,
        }
        for r in result.all()
    ]


async def _search_categories(db: AsyncSession, keyword: str, limit: int) -> list[dict]:
    """Tìm danh mục qua CategoryTranslation. DISTINCT ON category_id."""
    from app.modules.category.models import CategoryTranslation

    stmt = (
        select(Category.id, CategoryTranslation.name, CategoryTranslation.slug)
        .join(CategoryTranslation, CategoryTranslation.category_id == Category.id)
        .where(
            Category.deleted_at.is_(None),
            CategoryTranslation.name.ilike(f"%{keyword}%"),
        )
        .distinct(Category.id)
        .order_by(Category.id, Category.sort_order)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {"id": str(r.id), "name": r.name, "slug": r.slug}
        for r in result.all()
    ]


async def _search_tags(db: AsyncSession, keyword: str, limit: int) -> list[dict]:
    """Tìm tag qua TagTranslation. DISTINCT ON tag_id."""
    stmt = (
        select(Tag.id, TagTranslation.name, TagTranslation.slug)
        .join(TagTranslation, TagTranslation.tag_id == Tag.id)
        .where(
            Tag.deleted_at.is_(None),
            TagTranslation.name.ilike(f"%{keyword}%"),
        )
        .distinct(Tag.id)
        .order_by(Tag.id, Tag.sort_order)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {"id": str(r.id), "name": r.name, "slug": r.slug}
        for r in result.all()
    ]


async def _search_staff(db: AsyncSession, keyword: str, limit: int) -> list[dict]:
    """Tìm nhân sự theo full_name, email."""
    stmt = (
        select(Staff.id, Staff.full_name, Staff.email, Staff.slug)
        .where(
            Staff.deleted_at.is_(None),
            (
                Staff.full_name.ilike(f"%{keyword}%")
                | Staff.email.ilike(f"%{keyword}%")
            ),
        )
        .order_by(Staff.sort_order)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {"id": str(r.id), "full_name": r.full_name, "email": r.email, "slug": r.slug}
        for r in result.all()
    ]


@router.get("")
async def global_search(
    q: str = Query(..., min_length=1, max_length=100, description="Từ khóa tìm kiếm"),
    limit: int = Query(default=5, ge=1, le=20, description="Số kết quả mỗi nhóm"),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Tìm kiếm nhanh đa nguồn: bài viết, thành viên, danh mục, tags, nhân sự.
    """
    keyword = q.strip()
    if not keyword:
        return {"articles": [], "users": [], "categories": [], "tags": [], "staff": []}

    # SQLAlchemy AsyncSession không hỗ trợ chạy query song song trên 1 connection
    articles = await _search_articles(db, keyword, limit, current_user)
    users = await _search_users(
        db, keyword, limit, include_email=bool(current_user.is_admin)
    )
    categories = await _search_categories(db, keyword, limit)
    tags = await _search_tags(db, keyword, limit)
    staff = await _search_staff(db, keyword, limit)

    return {
        "articles": articles,
        "users": users,
        "categories": categories,
        "tags": tags,
        "staff": staff,
    }
