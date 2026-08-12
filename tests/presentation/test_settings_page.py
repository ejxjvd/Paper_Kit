"""/settings 頁渲染回歸測試（2026-08-12 使用者實測 500：NameError: engine_id）。

bug 根因：settings_page 依賴 bind_value_to(locals(), ...) 寫回變數，
但渲染當下（單價卡 `pricing_for(engine_id)`）與儲存 lambda 讀取時，
綁定事件從未觸發 → 變數不存在。本測試用 NiceGUI 官方
user_simulation 開真實 /settings 頁——渲染拋任何例外都會 500。
"""

import pytest
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _settings_page


@pytest.mark.asyncio
async def test_settings_page_renders_without_error(tmp_path):
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        # user_simulation 的 root 在首個 request 時才註冊路由——
        # 第一次 open 為暖身（404 骨架），第二次才是真實渲染。
        await user.open("/settings")
        client = await user.open("/settings")
        assert client is not None
        # 326 行（pricing_for(engine_id)）之後的元件必須渲染完成——
        # 若引擎卡例外中斷，術語表卡（343 行）不會出現。
        await user.should_see("術語表庫")
    # 隔離：user_simulation 退出殘留 Client.instances → 污染後續
    # sync 測試（slot stack is empty）。由 conftest.py 的
    # _nicegui_reset_between_tests（autouse）在每個測試進入前清理。


@pytest.mark.asyncio
async def test_settings_page_save_engine_without_touching_inputs(tmp_path):
    """使用者「不修改就按儲存」路徑：lambda 讀的變數必須已初始化。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")  # 暖身（見 test_settings_page_renders_without_error）
        await user.open("/settings")
        user.find("儲存引擎設定").click()
        await user.should_see("引擎設定已儲存")

