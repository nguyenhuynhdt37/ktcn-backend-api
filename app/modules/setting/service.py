from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.setting.models import Setting
from app.modules.setting.schemas import (
    SiteSettingsPayload,
    SiteSettingsResponse,
    resolve_setting_media_url,
)

SITE_APPEARANCE_KEY = "site_appearance"
SITE_APPEARANCE_GROUP = "appearance"


class SettingService:
    @staticmethod
    def _to_response(payload: SiteSettingsPayload) -> SiteSettingsResponse:
        return SiteSettingsResponse(
            **payload.model_dump(),
            header_logo_url=resolve_setting_media_url(payload.header_logo_object_key),
            footer_logo_url=resolve_setting_media_url(payload.footer_logo_object_key),
            fanpage_image_url=resolve_setting_media_url(payload.fanpage_image_object_key),
        )

    async def get_site_settings(self, db: AsyncSession) -> SiteSettingsResponse:
        stmt = select(Setting).where(Setting.key == SITE_APPEARANCE_KEY)
        setting = (await db.execute(stmt)).scalar_one_or_none()
        if not setting or not isinstance(setting.value, dict):
            return self._to_response(SiteSettingsPayload())

        defaults = SiteSettingsPayload().model_dump()
        merged = {**defaults}
        for field_name, val in setting.value.items():
            if field_name in merged and val is not None:
                merged[field_name] = val

        payload = SiteSettingsPayload.model_validate(merged)
        return self._to_response(payload)

    async def update_site_settings(
        self, db: AsyncSession, payload: SiteSettingsPayload
    ) -> SiteSettingsResponse:
        stmt = select(Setting).where(Setting.key == SITE_APPEARANCE_KEY)
        setting = (await db.execute(stmt)).scalar_one_or_none()
        data_dict = payload.model_dump()

        if setting:
            setting.value = data_dict
            setting.group_name = SITE_APPEARANCE_GROUP
        else:
            setting = Setting(
                key=SITE_APPEARANCE_KEY,
                value=data_dict,
                group_name=SITE_APPEARANCE_GROUP,
                description="Cấu hình giao diện website (Logo, Footer, thông tin liên hệ)",
            )
            db.add(setting)

        await db.flush()
        return self._to_response(payload)


setting_service = SettingService()
