"""2026-08-13 使用者 UI 驗收回報二件（夜間批次）：

1. **機密/掃描 toggle 連動**：使用者質疑「為何不勾選也能開始翻譯」——真意是
   toggle 與引擎卡的連動該**前置**：勾「🔒 機密文件」→ 引擎自動切 DeepSeek、
   視覺卡（siliconflow/babeldoc）禁用且點擊無效；已勾機密時點視覺卡不切換。
   舊行為＝勾了機密仍可點視覺卡，按「開始翻譯」才被 notify 拒絕（被動擋）。

2. **輸出目錄主頁就地設定**：輸出目錄只能到設定頁手動貼路徑——主頁翻譯面板
   加輸出目錄欄（與設定頁共用 SettingsService 後端，空白=預設）。
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
from paper_kit.presentation.app import _index_page

from test_ui_flow import FileWritingFakeEngine  # noqa: E402


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
    # user_simulation 的 root 在首個 request 才註冊路由——第一次 open 為暖身
    await user.open("/")
    await user.open("/")


def _engine_card(user, eid: str):
    """引擎卡 UserInteraction（marker 定位——Card 非 TextElement，content 查不到）。"""
    return user.find(kind=ui.card, marker=f"engine-card-{eid}")


def _sensitive_checkbox(user) -> ui.checkbox:
    return next(
        iter(
            c for c in user.find(ui.checkbox).elements
            if "機密" in (c.text or "")
        )
    )


def _output_dir_input(user) -> ui.input:
    return next(
        iter(
            i for i in user.find(ui.input).elements
            if "輸出目錄" in (i.label or "")
        )
    )


# ── 問題①：機密 toggle 與引擎卡連動 ─────────────────────────────


@pytest.mark.asyncio
async def test_checking_sensitive_switches_engine_to_deepseek(tmp_path):
    """勾「🔒 機密文件」→ 引擎卡自動切到 DeepSeek（DeepSeek 卡有選中態）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_engine("siliconflow")  # 預設視覺引擎

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        assert "ring-primary" in next(iter(_engine_card(user, "siliconflow").elements)).classes
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        classes = next(iter(_engine_card(user, "deepseek").elements)).classes
        assert "ring-primary" in classes, "勾機密後 DeepSeek 卡應有選中態"


@pytest.mark.asyncio
async def test_sensitive_disables_visual_engine_cards(tmp_path):
    """勾機密 → siliconflow/babeldoc 卡加禁用 class（灰化）；點擊不切換引擎。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        for eid in ("siliconflow", "babeldoc"):
            card = next(iter(_engine_card(user, eid).elements))
            assert "pk-engine-card--disabled" in card.classes, f"{eid} 卡應禁用"
        # 點擊視覺卡不切換（仍 DeepSeek）
        _engine_card(user, "siliconflow").click()
        classes = next(iter(_engine_card(user, "deepseek").elements)).classes
        assert "ring-primary" in classes, "點視覺卡不得切換引擎"


@pytest.mark.asyncio
async def test_sensitive_checked_blocks_visual_engine_selection(tmp_path):
    """已勾機密時點視覺卡 → 被拒（notify warning）＋引擎保持 DeepSeek。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        _engine_card(user, "babeldoc").click()
        await user.should_see("機密文件僅", retries=20)  # 拒絕提示
        classes = next(iter(_engine_card(user, "deepseek").elements)).classes
        assert "ring-primary" in classes, "機密下點視覺卡引擎仍 DeepSeek"


@pytest.mark.asyncio
async def test_unchecking_sensitive_restores_engine_cards(tmp_path):
    """取消勾機密 → 視覺卡解除禁用、可再選。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        _sensitive_checkbox(user).set_value(False)
        card = next(iter(_engine_card(user, "siliconflow").elements))
        assert "pk-engine-card--disabled" not in card.classes, "取消機密後視覺卡應解禁"


# ── 問題③：主頁輸出目錄就地設定 ───────────────────────────────


@pytest.mark.asyncio
async def test_index_page_shows_output_dir_input(tmp_path):
    """主頁翻譯面板有輸出目錄欄，顯示目前設定值。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_output_dir(str(tmp_path / "out"))

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        assert str(tmp_path / "out") == _output_dir_input(user).value


@pytest.mark.asyncio
async def test_output_dir_editable_from_index_persists(tmp_path):
    """主頁改輸出目錄 → 寫回 SettingsService（與設定頁共用後端，不需跳頁）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        new_dir = str(tmp_path / "custom-out")
        _output_dir_input(user).set_value(new_dir)
        user.find("套用輸出目錄").click()
        await user.should_see("輸出目錄已更新", retries=20)
        assert settings.output_dir() == new_dir, "主頁改輸出目錄應持久化到 settings"


@pytest.mark.asyncio
async def test_output_dir_blank_means_default(tmp_path):
    """主頁清空輸出目錄 → 存空字串（=預設 ~/.paper_kit/outputs，與設定頁一致）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_output_dir(str(tmp_path / "old"))

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _output_dir_input(user).set_value("   ")
        user.find("套用輸出目錄").click()
        await user.should_see("輸出目錄已更新", retries=20)
        assert settings.output_dir() == "", "清空應存空字串（預設）"
