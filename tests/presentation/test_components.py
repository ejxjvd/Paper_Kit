"""T-07 相位 6：狀態承載與錯誤呈現的元件契約。

背景：相位 6 的影響力排序第一條是「狀態要看得見」——空狀態與載入骨架原本
各 0 處；第二條是「錯誤留在原地」——任務失敗只閃一則 toast，使用者回頭找不到。

守門重點：
1. 三個共用元件真的渲染出語意 class（不是只有函式存在）。
2. 歷史頁的空狀態用同一個容器（避免又長回各頁自製版本）。
3. 任務卡的錯誤走行內錯誤區（文字仍以「錯誤：」開頭）。
"""

import pytest
from nicegui import ui
from nicegui.testing import user_simulation

from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.components import empty_state, inline_error, skeleton_rows
from paper_kit.presentation.history_page import _history_page
from paper_kit.presentation.handlers import build_job_card
from paper_kit.presentation.index_page import _render_card
from paper_kit.domain.translation_job import JobStatus, TranslationJob


def _classes_of(element) -> list[str]:
    return list(getattr(element, "_classes", []))


async def _open_twice(user) -> None:
    await user.open("/")
    await user.open("/")


@pytest.mark.asyncio
async def test_empty_state_renders_semantic_container():
    def page():
        @ui.page("/")
        def _():
            with empty_state():
                ui.label("尚無翻譯任務").classes("pk-text-xl")

    async with user_simulation(root=page) as user:
        await _open_twice(user)
        containers = user.find(marker="empty-state").elements
        assert containers, "空狀態必須使用 .pk-empty-state 容器"
        assert "pk-empty-state" in _classes_of(next(iter(containers)))
        await user.should_see("尚無翻譯任務")


@pytest.mark.asyncio
async def test_skeleton_rows_render_placeholders():
    def page():
        @ui.page("/")
        def _():
            skeleton_rows(3)

    async with user_simulation(root=page) as user:
        await _open_twice(user)
        rows = user.find(marker="skeleton-row").elements
        assert len(rows) == 3
        bars = [e for e in user.find(ui.element).elements if "pk-skeleton" in _classes_of(e)]
        assert len(bars) == 6, "每列兩個骨架塊（標題＋meta）"


@pytest.mark.asyncio
async def test_inline_error_shows_message_and_expandable_detail():
    def page():
        @ui.page("/")
        def _():
            inline_error("API key 無效", detail="HTTP 401 token expired")

    async with user_simulation(root=page) as user:
        await _open_twice(user)
        await user.should_see("錯誤：API key 無效")
        await user.should_see("詳情")
        await user.should_see("HTTP 401 token expired")


@pytest.mark.asyncio
async def test_history_empty_state_uses_shared_container(tmp_path):
    service = JobService(
        jobs=InMemoryJobRepository(), outputs_dir=tmp_path / "outputs"
    )
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        await user.open("/history")
        await user.open("/history")
        containers = user.find(marker="empty-state").elements
        assert containers, "歷史頁空狀態應使用共用容器（.pk-empty-state）"
        assert "pk-empty-state" in _classes_of(next(iter(containers)))
        await user.should_see("尚無翻譯任務")
        await user.should_see("翻譯新文件")


@pytest.mark.asyncio
async def test_failed_job_card_uses_inline_error(tmp_path):
    service = JobService(
        jobs=InMemoryJobRepository(), outputs_dir=tmp_path / "outputs"
    )
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    upload = tmp_path / "bad.pdf"
    upload.write_bytes(b"%PDF-1.4")
    job = TranslationJob(
        job_id="job-bad", status=JobStatus.FAILED, source_path=str(upload),
        error="上游 500",
    )
    view = build_job_card(job)

    def page():
        @ui.page("/")
        def _():
            _render_card(view, service, settings)

    async with user_simulation(root=page) as user:
        await _open_twice(user)
        containers = user.find(marker="inline-error").elements
        assert containers, "任務失敗應以行內錯誤區呈現（.pk-inline-error）"
        assert "pk-inline-error" in _classes_of(next(iter(containers)))
        await user.should_see("錯誤：上游 500")
