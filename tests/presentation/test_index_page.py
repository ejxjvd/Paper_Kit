"""主頁（上傳）端到端回歸：真實 upload handler 路徑（2026-08-12 使用者實測 bug）。

使用者丟 CH4.pdf 上傳（UI 顯示 100%）但翻譯沒開始、頁面也沒有任何
可點按鍵——兩件事：
1. on_upload handler 拋 AttributeError（NiceGUI 3.15 的 UploadEventArguments
   沒有 name/content，改 e.file: FileUpload）被 handle_event 吞掉 → UI 靜默無反應。
2. 主頁沒有明顯的「開始翻譯」入口（原本只有上傳區）。

本測試經 user_simulation 開真實主頁、以 handle_uploads 模擬檔案上傳，
斷言任務卡片與完成下載連結出現——handler 拋任何例外都會紅。
"""

import pytest
from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload
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
    # user_simulation 的 root 在首個 request 才註冊路由——
    # 第一次 open 為暖身（404 骨架），第二次才是真實渲染。
    await user.open("/")
    await user.open("/")


@pytest.mark.asyncio
async def test_upload_starts_translation_and_shows_completed_card(
    tmp_path, monkeypatch, make_blank_pdf
):
    """上傳 CH4.pdf → 任務卡片出現 → FakeEngine 完成 → 下載連結出現。

    （resolve_engine 注入 FakeEngine：真實引擎會打 API；monkeypatch 只換
    引擎解析，其餘路徑——暫存寫檔、create_job、start、計價——全真實。）
    """
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        # 真空白 PDF（conftest make_blank_pdf）——壞檔會走 PdfStreamError 防衛
        # （ocr.py），非本測試目標；真檔才通過掃描件偵測路徑
        real_pdf = make_blank_pdf(tmp_path / "CH4.pdf")
        await upload_el.handle_uploads([
            SmallFileUpload(
                name="CH4.pdf",
                content_type="application/pdf",
                _data=real_pdf.read_bytes(),
            ),
        ])
        # 任務卡片由 1s timer 刷新出現——retries 放大（2s）
        await user.should_see("CH4.pdf", retries=20)
        # FakeEngine 立即完成 → 完成卡片的下載按鈕在下一輪刷新出現（5s 保守）
        await user.should_see("下載 mono", retries=50)
        await user.should_see("完成", retries=5)


@pytest.mark.asyncio
async def test_index_page_has_start_button(tmp_path):
    """2026-08-12 使用者回饋：主頁要有明顯可點的「開始翻譯」按鍵。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        await user.should_see("開始翻譯")
        await user.should_see("拖放 PDF 或點選選擇")
