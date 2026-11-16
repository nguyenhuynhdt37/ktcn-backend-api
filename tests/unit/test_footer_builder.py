import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from app.modules.setting.schemas import SiteSettingsPayload
from app.modules.setting.service import SettingService


def layout():
    return {
        "version": 1,
        "enabled": True,
        "rows": [{"id": "row-1", "columns": [
            {"id": "col-1", "width": 2, "blocks": [
                {"id": "block-1", "type": "text", "text_vi": "Xin chào", "text_en": "Hello"}
            ]},
            {"id": "col-2", "width": 1, "blocks": []},
        ]}],
    }


class FooterBuilderTests(unittest.TestCase):
    def test_legacy_settings_remain_opt_in(self):
        self.assertIsNone(SiteSettingsPayload().footer_builder)

    def test_round_trip_preserves_layout_languages_and_empty_columns(self):
        payload = SiteSettingsPayload(footer_builder=layout())
        restored = SiteSettingsPayload.model_validate_json(payload.model_dump_json())
        self.assertEqual(restored.footer_builder.rows[0].columns[0].blocks[0].text_en, "Hello")
        self.assertEqual(restored.footer_builder.rows[0].columns[1].blocks, [])
        self.assertEqual(restored.footer_builder.rows[0].columns[0].width, 2)

    def test_rejects_duplicate_identifiers_across_the_entire_tree(self):
        value = layout()
        value["rows"][0]["columns"][1]["id"] = "block-1"
        with self.assertRaises(ValidationError):
            SiteSettingsPayload(footer_builder=value)

    def test_rejects_invalid_versions_colors_and_unbounded_dimensions(self):
        for change in [{"version": 2}, {"background": "url(https://example.com)"}, {"gap": -1}]:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                SiteSettingsPayload(footer_builder={**layout(), **change})
        with self.assertRaises(ValidationError):
            SiteSettingsPayload(header_logo_width=99999)

    def test_rejects_executable_links_and_media(self):
        for field in ["href", "image_object_key"]:
            for url in ["javascript:alert(1)", "java\nscript:alert(1)", "data:text/html,hello"]:
                value = layout()
                value["rows"][0]["columns"][0]["blocks"][0][field] = url
                with self.subTest(field=field, url=url), self.assertRaises(ValidationError):
                    SiteSettingsPayload(footer_builder=value)

    def test_rejects_empty_rows_and_excessive_columns(self):
        value = layout()
        value["rows"][0]["columns"] = []
        with self.assertRaises(ValidationError):
            SiteSettingsPayload(footer_builder=value)


class MemorySession:
    def __init__(self, value=None):
        self.setting = SimpleNamespace(value=value, group_name="appearance") if value is not None else None

    async def execute(self, _statement):
        return SimpleNamespace(scalar_one_or_none=lambda: self.setting)

    def add(self, setting):
        self.setting = setting

    async def flush(self):
        pass


class FooterSettingsPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_saves_and_reads_builder_and_logo_dimensions(self):
        session = MemorySession()
        service = SettingService()
        payload = SiteSettingsPayload(footer_builder=layout(), header_logo_width=240, header_logo_height=64)
        updated = await service.update_site_settings(session, payload)
        loaded = await service.get_site_settings(session)
        self.assertEqual(updated.footer_builder, loaded.footer_builder)
        self.assertEqual(loaded.header_logo_width, 240)
        self.assertEqual(session.setting.value["footer_builder"]["rows"][0]["columns"][1]["blocks"], [])

    async def test_service_merges_legacy_settings_without_enabling_builder(self):
        loaded = await SettingService().get_site_settings(MemorySession({"phone": "0238 123 456"}))
        self.assertEqual(loaded.phone, "0238 123 456")
        self.assertIsNone(loaded.footer_builder)


if __name__ == "__main__":
    unittest.main()
