from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.audit.service import log_action
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserResponse
from app.modules.setting.schemas import SiteSettingsPayload, SiteSettingsResponse
from app.modules.setting.service import setting_service

admin_router = APIRouter()
portal_router = APIRouter()


@portal_router.get("", response_model=SiteSettingsResponse)
async def get_site_settings_portal(
    db: AsyncSession = Depends(get_db),
) -> SiteSettingsResponse:
    """
    [Portal Website] Lấy cấu hình giao diện công khai (Logo, Footer, thông tin liên hệ).
    """
    return await setting_service.get_site_settings(db)


@admin_router.get("", response_model=SiteSettingsResponse)
async def get_site_settings_admin(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SiteSettingsResponse:
    """
    [Admin CMS] Lấy cấu hình giao diện (Logo, Footer, thông tin liên hệ).
    """
    return await setting_service.get_site_settings(db)


@admin_router.put("", response_model=SiteSettingsResponse)
async def update_site_settings_admin(
    request: Request,
    payload: SiteSettingsPayload,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SiteSettingsResponse:
    """
    [Admin CMS] Cập nhật cấu hình giao diện (Logo, Footer, thông tin liên hệ).
    """
    updated = await setting_service.update_site_settings(db, payload)
    await log_action(
        db,
        current_user,
        "SETTING_UPDATED",
        "setting",
        None,
        payload.model_dump(),
        request,
    )
    await db.commit()

    # Làm mới cache tri thức chatbot để đồng bộ thông tin liên hệ ngay lập tức
    try:
        from app.modules.chatbot.routers import invalidate_knowledge_cache

        await invalidate_knowledge_cache()
    except Exception:
        pass

    return updated
