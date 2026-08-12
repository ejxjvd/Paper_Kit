"""歷史表格頁（票 17）：/history 表格化＋分頁＋引擎欄＋空狀態。

使用者對照沉浸式翻譯「翻譯記錄表格」的批 0 計畫——卡片流 → 表格
（勾選/文件名/創建時間/頁數/引擎/狀態/操作），每頁 10 筆分頁。
批量操作（勾選/刪除/下載 zip）是票 18，本頁先立表格骨架。
"""

import pytest
from nicegui import ui
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _history_page, _index_page

ENGINE_LABELS = {"siliconflow": "SiliconFlow（GLM）", "deepseek": "DeepSeek（純文字）"}


def _build(tmp_path) -> tuple[JobService, SettingsService, CostService, GlossaryService]:
    service = JobService(
        jobs=InMemoryJobRepository(),
        outputs_dir=tmp_path / "outputs",
    )
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    return service, settings, cost, glossaries


def _seed(service: JobService, n: int, dirpath, make_blank_pdf) -> None:
    """建 n 筆任務（真實 create_job 路徑；未 start，手動填 engine_id 供表格顯示）。"""
    out = dirpath / "outputs"
    for i in range(n):
        pdf = make_blank_pdf(dirpath / f"paper{i:02d}.pdf")
        job = service.create_job(pdf, target_lang="zh-TW", pages=None, output_dir=out)
        job.engine_id = "deepseek" if i % 2 == 0 else "siliconflow"


@pytest.mark.asyncio
async def test_history_page_renders_table_with_all_columns(tmp_path, make_blank_pdf):
    """/history 渲染表格：欄位定義＋任務列資料出現（引擎欄顯示名稱非 raw id）。

    表格儲存格是 Vue 前端渲染（非 NiceGUI 元素，should_see 不可見），
    斷言落在公開屬性 columns/rows（資料契約層）。
    """
    service, settings, cost, glossaries = _build(tmp_path)
    _seed(service, 3, tmp_path, make_blank_pdf)

    async with user_simulation(
        root=lambda: _history_page(service, settings, engine_labels=ENGINE_LABELS)
    ) as user:
        await user.open("/history")
        await user.open("/history")
        table = list(user.find(ui.table).elements)[0]  # .elements 是 set（元素容器）
        labels = {c["label"] for c in table.columns}
        assert {"文件名", "創建時間", "頁數", "引擎", "狀態", "操作"} <= labels, labels
        files = [r["file_name"] for r in table.rows]
        assert "paper00.pdf" in files and "paper02.pdf" in files
        # 引擎欄顯示對照名（deepseek → 「DeepSeek（純文字）」）
        engines = {r["engine_label"] for r in table.rows}
        assert "DeepSeek（純文字）" in engines


@pytest.mark.asyncio
async def test_history_page_pagination_default_10(tmp_path, make_blank_pdf):
    """20 筆任務 → 表格分頁每頁 10 筆（與沉浸式翻譯記錄頁一致）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    _seed(service, 20, tmp_path, make_blank_pdf)

    async with user_simulation(
        root=lambda: _history_page(service, settings, engine_labels=ENGINE_LABELS)
    ) as user:
        await user.open("/history")
        await user.open("/history")
        tables = list(user.find(ui.table).elements)
        assert tables, "歷史頁應有 ui.table"
        table = tables[0]
        assert len(table.rows) == 20, "20 筆任務全部在表格資料中"
        pagination = table.pagination
        assert pagination is not None, "表格應有分頁設定"
        assert pagination.get("rowsPerPage") == 10, f"每頁應 10 筆，實際 {pagination}"


@pytest.mark.asyncio
async def test_history_page_empty_state(tmp_path):
    """空歷史：引導提示＋「翻譯新文件」連結（→ /）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _history_page(service, settings, engine_labels=ENGINE_LABELS)
    ) as user:
        await user.open("/history")
        await user.open("/history")
        await user.should_see("尚無翻譯任務")
        new_link = next(
            l for l in user.find(ui.link).elements if l.text == "翻譯新文件"
        )
        assert new_link.props.get("href") == "/"


@pytest.mark.asyncio
async def test_history_page_completed_job_has_download_links(tmp_path, make_blank_pdf):
    """完成任務（有 result）的操作列提供 mono／dual 下載連結（dual 不可退化——使用者明定）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    pdf = make_blank_pdf(tmp_path / "done.pdf")
    job = service.create_job(
        pdf, target_lang="zh-TW", pages=None, output_dir=tmp_path / "outputs"
    )
    job.status = JobStatus.COMPLETED
    out = tmp_path / "outputs" / job.job_id
    out.mkdir(parents=True, exist_ok=True)  # create_job 已建過目錄（存在即用）
    (out / "done-mono.pdf").write_bytes(b"mono")
    (out / "done-dual.pdf").write_bytes(b"dual")
    job.result = JobResult(
        mono_path=str(out / "done-mono.pdf"),
        dual_path=str(out / "done-dual.pdf"),
        input_tokens=0,
        output_tokens=0,
    )

    async with user_simulation(
        root=lambda: _history_page(service, settings, engine_labels=ENGINE_LABELS)
    ) as user:
        await user.open("/history")
        await user.open("/history")
        table = list(user.find(ui.table).elements)[0]  # .elements 是 set（元素容器）
        row = next(r for r in table.rows if r["file_name"] == "done.pdf")
        # row 資料帶下載路徑（mono＋dual——使用者明定雙語不可退化）
        assert row["mono_url"].endswith("done-mono.pdf")
        assert row["dual_url"].endswith("done-dual.pdf")
        # 操作列 slot 模板含 mono／dual 下載連結（Vue 模板，前端渲染；
        # slots 值是 Slot 物件，模板字串在其 .template）。
        # spec review 教訓：scope 必須是 props.row 且自包 <q-td>（裸 row 渲染失敗）——
        # 模板斷言同時鎖這兩個契約，防止該 bug 重現。
        actions_slot = table.slots.get("body-cell-actions")
        assert actions_slot is not None, "表格應有 actions 列 slot"
        template = actions_slot.template
        assert template.startswith("<q-td>"), "body-cell slot 需自包 <q-td>"
        assert "props.row.mono_url" in template and "props.row.dual_url" in template
        assert "下載 mono" in template and "下載 dual" in template
        assert "download" in template, "下載按鈕需附件下載（與主頁 ui.download 一致）"
        status_slot = table.slots.get("body-cell-status")
        assert status_slot is not None
        assert "props.row.status_color" in status_slot.template
