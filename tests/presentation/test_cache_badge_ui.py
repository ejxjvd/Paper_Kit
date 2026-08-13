"""票 26：命中快取 UI 標記——主頁任務卡顯示「⚡ 快取」badge。

票 24 快取命中→ JobResult(from_cache=True)；本測試鎖 UI 契約：快取命中的
完成任務卡片顯示「⚡ 快取」badge、一般翻譯任務不顯示（badge 是唯一分界，
使用者要能一眼看出「這筆沒花引擎錢」）。
"""

import pytest
from nicegui import ui
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _index_page


def _build(tmp_path) -> tuple[JobService, SettingsService, CostService, GlossaryService]:
    repo = InMemoryJobRepository()
    # 快取命中任務（from_cache=True——引擎未呼叫）
    repo.add(
        TranslationJob(
            job_id="seed-cached",
            source_path="cached.pdf",
            status=JobStatus.COMPLETED,
            engine_id="deepseek",
            result=JobResult(
                mono_path="cached.zh.mono.pdf",
                dual_path="cached.zh.dual.pdf",
                from_cache=True,  # 票 24：快取命中（引擎未呼叫）
            ),
        )
    )
    # 一般翻譯任務（from_cache 預設 False）
    repo.add(
        TranslationJob(
            job_id="seed-regular",
            source_path="regular.pdf",
            status=JobStatus.COMPLETED,
            engine_id="siliconflow",
            result=JobResult(mono_path="regular.zh.mono.pdf", dual_path="regular.zh.dual.pdf"),
        )
    )
    service = JobService(jobs=repo, outputs_dir=tmp_path / "outputs")
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    return service, settings, cost, glossaries


def _cache_badges(user) -> list:
    return [b for b in user.find(ui.badge).elements if b.text == "⚡ 快取"]


@pytest.mark.asyncio
async def test_cache_hit_card_shows_cache_badge(tmp_path):
    """快取命中的完成任務卡顯示「⚡ 快取」badge（引擎未呼叫的視覺證據）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        await user.should_see("cached.pdf")
        assert len(_cache_badges(user)) == 1, "快取命中的任務應顯示「⚡ 快取」badge"


@pytest.mark.asyncio
async def test_regular_job_card_has_no_cache_badge(tmp_path):
    """一般翻譯（引擎呼叫）的完成任務卡不顯示快取 badge——seed 只有 1 筆命中。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        await user.should_see("regular.pdf")
        assert len(_cache_badges(user)) == 1, "僅快取命中的任務有 badge（一般任務不得誤標）"
