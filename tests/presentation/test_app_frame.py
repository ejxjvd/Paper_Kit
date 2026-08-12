"""統一頁框（票 16）：所有頁面共用左側欄導覽。

使用者「對比沉浸式翻譯差太多」回饋的資訊架構修復第一步——
三頁（主頁／設定頁／歷史頁）不再是三個獨立網站，共用
側欄（翻譯／歷史／設定）＋頂部標題。
"""

import pytest
from nicegui import ui
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _debug_page, _index_page, _settings_page


def _build(tmp_path) -> tuple[JobService, SettingsService, CostService, GlossaryService]:
    service = JobService(
        jobs=InMemoryJobRepository(),
        outputs_dir=tmp_path / "outputs",
    )
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    return service, settings, cost, glossaries


async def _open_twice(user) -> None:
    # user_simulation 的 root 在首個 request 才註冊路由——
    # 第一次 open 為暖身（404 骨架），第二次才是真實渲染。
    await user.open("/")
    await user.open("/")


@pytest.mark.asyncio
async def test_index_page_has_sidebar_with_three_nav_items(tmp_path):
    """主頁出現左側欄，含「翻譯」「歷史」「設定」三個導覽項（翻譯為當前頁高亮）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        drawers = user.find(ui.left_drawer).elements
        assert drawers, "主頁應有 ui.left_drawer 側欄"
        await user.should_see("翻譯")
        await user.should_see("歷史")
        await user.should_see("設定")
        # 票 16：當前頁導覽項高亮（bg-primary class）——高亮是純視覺 CSS，
        # 無公開行為可斷言，讀 _classes 屬已知脆弱點（standards review 記錄）
        nav_links = [l for l in user.find(ui.link).elements if l.text in {"翻譯", "歷史", "設定"}]
        assert len(nav_links) == 3, f"側欄應有 3 個導覽連結，實際 {len(nav_links)}"
        active = next(l for l in nav_links if l.text == "翻譯")
        assert "bg-primary" in active._classes, "當前頁導覽項應有 bg-primary 高亮"
        inactive = [l for l in nav_links if l.text != "翻譯"]
        assert all("bg-primary" not in l._classes for l in inactive)


@pytest.mark.asyncio
async def test_clicking_sidebar_item_navigates(tmp_path):
    """點側欄「設定」→ 真的切到設定頁（測試環境的 navigate 會開新頁面）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    # root 需註冊兩頁（導航目標也要有路由；user_simulation 不會自動註冊）
    def root():
        _index_page(service, settings, cost, glossaries)
        _settings_page(settings, cost, glossaries)

    async with user_simulation(root=root) as user:
        await _open_twice(user)
        user.find(kind=ui.link, content="設定").click()
        # 設定頁特有元素（儲存引擎設定按鈕）出現 = 導航成功
        await user.should_see("儲存引擎設定", retries=20)


@pytest.mark.asyncio
async def test_debug_reachable_from_settings_sidebar(tmp_path):
    """AC3：從設定頁側欄的 Debug 連結可達 /debug（票 09 除錯頁仍在框架內）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    log_path = tmp_path / "logs"

    def root():
        _settings_page(settings, cost, glossaries)
        _debug_page(log_path, settings)

    async with user_simulation(root=root) as user:
        await user.open("/settings")
        await user.open("/settings")
        user.find(kind=ui.link, content="Debug").click()
        # debug 頁特有元素（log 檔路徑標籤）出現 = 導航成功
        await user.should_see("log 檔", retries=20)


@pytest.mark.asyncio
async def test_settings_page_has_sidebar_with_three_nav_items(tmp_path):
    """設定頁也出現同一組側欄導覽（不只主頁）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        drawers = user.find(ui.left_drawer).elements
        assert drawers, "設定頁應有 ui.left_drawer 側欄"
        await user.should_see("翻譯")
        await user.should_see("歷史")
        await user.should_see("設定")
