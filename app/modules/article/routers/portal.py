import uuid
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.modules.article.schemas import (
    PortalArticleListResponse,
    PortalArticlePaginationResponse,
    PortalArticleResponse,
)
from app.modules.article.service import article_service
from app.shared.redis import get_redis

router = APIRouter()


@router.get("", response_model=PortalArticlePaginationResponse)
async def list_all_articles_portal(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None),
    category_slug: str | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    program_id: uuid.UUID | None = Query(default=None),
    article_type: str | None = Query(default=None),
    category_slugs: list[str] | None = Query(default=None, alias="category_slugs"),
    category_slugs_arr: list[str] | None = Query(default=None, alias="category_slugs[]"),
    exclude_category_slugs: list[str] | None = Query(default=None, alias="exclude_category_slugs"),
    exclude_category_slugs_arr: list[str] | None = Query(default=None, alias="exclude_category_slugs[]"),
    tag_slug: str | None = Query(default=None),
    author_username: str | None = Query(default=None),
    is_pinned: bool | None = Query(default=None),
    has_thumbnail: bool | None = Query(default=None),
    published_from: datetime | None = Query(default=None),
    published_to: datetime | None = Query(default=None),
    sort_by: str = Query(default="publish_at"),
    sort_dir: str = Query(default="desc"),
    lang: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PortalArticlePaginationResponse:
    allowed_sort_fields = {
        "title", "slug", "created_at", "updated_at",
        "publish_at", "published_at", "view_count",
        "sort_order", "is_pinned"
    }
    if sort_by not in allowed_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Trường sắp xếp 'sort_by' không hợp lệ. Cho phép: {', '.join(allowed_sort_fields)}"
        )

    if sort_dir.lower() not in {"asc", "desc"}:
        raise HTTPException(
            status_code=400,
            detail="Hướng sắp xếp 'sort_dir' chỉ được phép là 'asc' hoặc 'desc'"
        )

    parsed_category_slugs = []
    raw_slugs = []
    if category_slugs:
        raw_slugs.extend(category_slugs)
    if category_slugs_arr:
        raw_slugs.extend(category_slugs_arr)

    for item in raw_slugs:
        if "," in item:
            for sub_item in item.split(","):
                sub_item = sub_item.strip()
                if sub_item:
                    parsed_category_slugs.append(sub_item)
        else:
            item = item.strip()
            if item:
                parsed_category_slugs.append(item)

    parsed_exclude_category_slugs = []
    raw_exclude_slugs = []
    if exclude_category_slugs:
        raw_exclude_slugs.extend(exclude_category_slugs)
    if exclude_category_slugs_arr:
        raw_exclude_slugs.extend(exclude_category_slugs_arr)

    for item in raw_exclude_slugs:
        if "," in item:
            for sub_item in item.split(","):
                sub_item = sub_item.strip()
                if sub_item:
                    parsed_exclude_category_slugs.append(sub_item)
        else:
            item = item.strip()
            if item:
                parsed_exclude_category_slugs.append(item)

    from app.core.language import get_locale_from_request
    resolved_lang = get_locale_from_request(request, lang)

    items, total = await article_service.list_all_articles_portal(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        category_slug=category_slug,
        department_id=department_id,
        program_id=program_id,
        article_type=article_type,
        category_slugs=parsed_category_slugs if parsed_category_slugs else None,
        exclude_category_slugs=parsed_exclude_category_slugs if parsed_exclude_category_slugs else None,
        tag_slug=tag_slug,
        author_username=author_username,
        is_pinned=is_pinned,
        has_thumbnail=has_thumbnail,
        published_from=published_from,
        published_to=published_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
        lang=resolved_lang,
    )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    has_next = page < total_pages
    has_previous = page > 1

    return PortalArticlePaginationResponse(
        items=[PortalArticleListResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


@router.get("/{slug}", response_model=PortalArticleResponse)
async def get_article_detail_portal(
    slug: str,
    request: Request,
    response: Response,
    lang: str | None = Query(default=None),
    guest_uuid: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> PortalArticleResponse:
    # 1. Lấy hoặc sinh mới guest_uuid hợp lệ (bỏ qua cookie sai định dạng)
    is_new_guest = False
    try:
        resolved_guest_uuid = str(uuid.UUID(guest_uuid)) if guest_uuid else ""
    except (ValueError, TypeError, AttributeError):
        resolved_guest_uuid = ""

    if not resolved_guest_uuid:
        resolved_guest_uuid = str(uuid.uuid4())
        is_new_guest = True
    guest_uuid = resolved_guest_uuid

    # 2. Lấy IP khách hàng làm fallback
    from app.shared.client_ip import get_client_ip
    client_ip = get_client_ip(request)

    from app.core.language import get_locale_from_request
    resolved_lang = get_locale_from_request(request, lang)

    # 3. Lấy chi tiết bài viết và tăng view (có kiểm tra trùng lặp qua Redis)
    article = await article_service.get_article_by_slug_portal(
        db,
        slug=slug,
        lang=resolved_lang,
        guest_uuid=guest_uuid,
        client_ip=client_ip,
        redis_client=redis_client
    )

    # 4. Lưu guest_uuid vào cookie nếu sinh mới
    if is_new_guest:
        response.set_cookie(
            key="guest_uuid",
            value=guest_uuid,
            httponly=True,
            secure=settings.ENV == "production",
            samesite="lax",
            max_age=365 * 24 * 60 * 60,  # 1 năm
            path="/"
        )

    return PortalArticleResponse.model_validate(article)
