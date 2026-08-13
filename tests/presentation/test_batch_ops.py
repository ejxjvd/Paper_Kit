"""票 18：歷史批量操作——勾選＋全選、批量刪除（二次確認＋執行中拒絕）、
批量下載 mono／dual（zip 路由）。

對照沉浸式翻譯記錄頁的批量工具列。雙語下載是使用者明定「最不可或缺」——
mono／dual 兩鍵獨立、都要有（AC 逐條鎖）。
"""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from nicegui import app, ui
from nicegui.testing import user_simulation
from starlette.testclient import TestClient

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _history_page, register_batch_download_route


def _build(tmp_path) -> tuple[JobService, SettingsService]:
    service = JobService(
        jobs=InMemoryJobRepository(),
        outputs_dir=tmp_path / "outputs",
    )
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    return service, settings


def _seed_completed(service: JobService, tmp_path, n: int) -> list[str]:
    """建 n 筆完成任務（有 mono/dual 產出），回傳 job_ids。"""
    ids = []
    for i in range(n):
        pdf = tmp_path / f"paper{i}.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        job = service.create_job(pdf, target_lang="zh-TW", pages=None, output_dir=tmp_path / "outputs")
        job.status = JobStatus.COMPLETED
        out = tmp_path / "outputs" / job.job_id
        out.mkdir(parents=True, exist_ok=True)
        (out / f"paper{i}.zh.mono.pdf").write_bytes(b"mono")
        (out / f"paper{i}.zh.dual.pdf").write_bytes(b"dual")
        job.result = JobResult(
            mono_path=str(out / f"paper{i}.zh.mono.pdf"),
            dual_path=str(out / f"paper{i}.zh.dual.pdf"),
            input_tokens=0,
            output_tokens=0,
        )
        ids.append(job.job_id)
    return ids


async def _open_history(user, service, settings) -> ui.table:
    await user.open("/history")
    await user.open("/history")
    return list(user.find(ui.table).elements)[0]


# ── 勾選與批量工具列 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_table_supports_multiple_selection(tmp_path):
    """AC1：表格可勾選多筆＋全選（Quasar selection='multiple'，勾選欄＋全選內建）。"""
    service, settings = _build(tmp_path)
    _seed_completed(service, tmp_path, 3)

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        table = await _open_history(user, service, settings)
        assert table.selection == "multiple", "歷史表格應啟用多選勾選"
        assert table.row_key == "job_id"
        # 勾選兩筆（公開 property；前端勾選事件會走到同一 setter）
        table.selected = [table.rows[0], table.rows[1]]
        assert len(table.selected) == 2


@pytest.mark.asyncio
async def test_batch_toolbar_has_all_five_batch_buttons(tmp_path):
    """AC4/5/6：刪除＋重試＋取消＋「批量下載 mono」＋「批量下載 dual」五鍵齊備
    （dual 不可退化；重試／取消是票 17 review 裁決——issue #21——併入批量操作列）。"""
    service, settings = _build(tmp_path)
    _seed_completed(service, tmp_path, 2)

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        await _open_history(user, service, settings)
        labels = {b.text for b in user.find(ui.button).elements}
        for expected in ("批量刪除", "↻ 批量重試", "✕ 批量取消", "批量下載 mono", "批量下載 dual"):
            assert expected in labels, f"缺批量按鈕 {expected}：{labels}"


# ── 批量刪除（二次確認＋執行中拒絕） ───────────────────────────────


@pytest.mark.asyncio
async def test_batch_delete_confirms_then_removes_jobs(tmp_path):
    """AC2：勾選→批量刪除→二次確認 dialog→確認後任務消失＋輸出目錄移除。"""
    service, settings = _build(tmp_path)
    ids = _seed_completed(service, tmp_path, 2)
    out_dirs = [tmp_path / "outputs" / jid for jid in ids]

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        table = await _open_history(user, service, settings)
        table.selected = table.rows[:]
        user.find(kind=ui.button, content="批量刪除").click()
        # 二次確認 dialog
        await user.should_see("確定刪除 2 筆任務")
        user.find(kind=ui.button, content="確認刪除").click()
        await user.should_see("已刪除 2 筆任務", retries=20)
        assert table.rows == [], "刪除後表格應無列"
        assert all(not d.exists() for d in out_dirs), "刪除應移除輸出目錄"


@pytest.mark.asyncio
async def test_batch_delete_keeps_running_jobs_with_notice(tmp_path):
    """AC3：勾選含翻譯中任務 → 刪除時提示、執行中任務保留。"""
    service, settings = _build(tmp_path)
    ids = _seed_completed(service, tmp_path, 1)
    running_pdf = tmp_path / "running.pdf"
    running_pdf.write_bytes(b"%PDF-1.4")
    running = service.create_job(
        running_pdf, target_lang="zh-TW", pages=None, output_dir=tmp_path / "outputs"
    )
    running.status = JobStatus.TRANSLATING

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        table = await _open_history(user, service, settings)
        table.selected = table.rows[:]  # 全勾（含執行中）
        user.find(kind=ui.button, content="批量刪除").click()
        await user.should_see("確定刪除")
        user.find(kind=ui.button, content="確認刪除").click()
        await user.should_see("執行中的任務無法刪除", retries=20)
        # 執行中任務保留、完成任務已刪
        remaining = [r["file_name"] for r in table.rows]
        assert remaining == ["running.pdf"], f"執行中任務應保留，實際 {remaining}"


# ── 批量重試／取消（票 17 review 裁決：issue #21 承諾） ─────────────


@pytest.mark.asyncio
async def test_batch_retry_requeues_failed_jobs(tmp_path, monkeypatch):
    """票 18 review：勾選失敗任務 → 批量重試 → 回 queued 再跑（不需重新上傳）。"""
    from test_ui_flow import FileWritingFakeEngine  # 同 test_index_page 模式（避免打真 API）

    service, settings = _build(tmp_path)
    pdf = tmp_path / "failed.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = service.create_job(pdf, target_lang="zh-TW", pages=None, output_dir=tmp_path / "outputs")
    job.status = JobStatus.FAILED
    job.error = "測試失敗"
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        table = await _open_history(user, service, settings)
        table.selected = table.rows[:]
        user.find(kind=ui.button, content="↻ 批量重試").click()
        await user.should_see("已重新排隊", retries=20)
        # 任務仍在表格（回 queued 重跑，不是被刪除）
        assert [r["file_name"] for r in table.rows] == ["failed.pdf"]


@pytest.mark.asyncio
async def test_batch_cancel_cancels_running_jobs(tmp_path):
    """票 18 review：勾選翻譯中任務 → 批量取消 → 狀態變已取消（引擎中止走同一路徑）。"""
    service, settings = _build(tmp_path)
    pdf = tmp_path / "running2.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = service.create_job(pdf, target_lang="zh-TW", pages=None, output_dir=tmp_path / "outputs")
    job.status = JobStatus.TRANSLATING

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        table = await _open_history(user, service, settings)
        table.selected = table.rows[:]
        user.find(kind=ui.button, content="✕ 批量取消").click()
        await user.should_see("已取消", retries=20)
        statuses = [r["status_label"] for r in table.rows]
        assert statuses == ["已取消"], f"批量取消後狀態應為已取消，實際 {statuses}"


# ── 批量下載 zip 路由 ─────────────────────────────────────────────


def _seed_for_route(tmp_path) -> JobService:
    service = JobService(
        jobs=InMemoryJobRepository(),
        outputs_dir=tmp_path / "outputs",
    )
    _seed_completed(service, tmp_path, 2)
    return service


def test_batch_download_route_serves_mono_zip(tmp_path):
    """AC4：/download-batch?kind=mono 回傳 zip，內含勾選任務的 mono 檔。"""
    service = _seed_for_route(tmp_path)
    ids = [j.job_id for j in service.list_jobs()]
    register_batch_download_route(service)

    resp = TestClient(app).get(
        "/download-batch", params={"ids": ",".join(ids), "kind": "mono"}
    )

    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert len(names) == 2
        assert all(n.endswith(".zh.mono.pdf") for n in names)
        assert zf.read(names[0]) == b"mono"


def test_batch_download_route_serves_dual_zip(tmp_path):
    """AC5：kind=dual 回傳 zip 內含 dual 檔（兩鍵獨立、都要有——dual 不可退化）。"""
    service = _seed_for_route(tmp_path)
    ids = [j.job_id for j in service.list_jobs()]
    register_batch_download_route(service)

    resp = TestClient(app).get(
        "/download-batch", params={"ids": ",".join(ids), "kind": "dual"}
    )

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert all(n.endswith(".zh.dual.pdf") for n in zf.namelist())


def test_batch_download_route_404_when_nothing_to_zip(tmp_path):
    """勾選任務皆無產出 → 404（UI 已提示，路由兜底）。"""
    service = _build(tmp_path)[0]
    pdf = tmp_path / "queued.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    service.create_job(pdf, target_lang="zh-TW", pages=None, output_dir=tmp_path / "outputs")
    register_batch_download_route(service)

    resp = TestClient(app).get(
        "/download-batch",
        params={"ids": ",".join(j.job_id for j in service.list_jobs()), "kind": "mono"},
    )

    assert resp.status_code == 404


def test_batch_download_zip_tempfile_removed_after_send(tmp_path):
    """AC6：zip 送完暫存刪除（不堆積 tempdir）。"""
    service = _seed_for_route(tmp_path)
    ids = [j.job_id for j in service.list_jobs()]
    register_batch_download_route(service)

    resp = TestClient(app).get(
        "/download-batch", params={"ids": ",".join(ids), "kind": "mono"}
    )
    assert resp.status_code == 200

    leftovers = list(Path(tempfile.gettempdir()).glob("paper-kit-mono-*.zip"))
    assert leftovers == [], f"送完應刪暫存 zip，殘留 {leftovers}"


# ── #24/#26：寬度填滿＋tokens 用量／金額欄 ──────────────────────────


def _seed_with_usage(service: JobService, tmp_path) -> str:
    """建 1 筆完成任務（siliconflow 引擎、有 token 用量），回傳 job_id。"""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    job = service.create_job(
        pdf, target_lang="zh-TW", pages="29,30", output_dir=tmp_path / "outputs"
    )
    job.engine_id = "siliconflow"
    job.total_pages = 2
    job.pdf_pages = 58
    job.status = JobStatus.COMPLETED
    job.result = JobResult(
        mono_path="/x/mono.pdf",
        dual_path="/x/dual.pdf",
        input_tokens=5682,
        output_tokens=1751,
    )
    return job.job_id


@pytest.mark.asyncio
async def test_history_columns_include_tokens_and_cost(tmp_path):
    """#26：歷史表格有「tokens 用量」＋「金額」兩欄（使用者要求新增）。"""
    service, settings = _build(tmp_path)
    _seed_completed(service, tmp_path, 1)

    async with user_simulation(
        root=lambda: _history_page(service, settings, CostService(SqliteSettingsRepository(tmp_path / "pk.db")))
    ) as user:
        table = await _open_history(user, service, settings)
        names = [c["name"] for c in table.columns]
        assert "tokens" in names and "cost" in names
        assert any(c["name"] == "tokens" and c["label"] == "tokens 用量" for c in table.columns)
        assert any(c["name"] == "cost" and c["label"] == "金額" for c in table.columns)


@pytest.mark.asyncio
async def test_history_row_shows_tokens_and_cost(tmp_path):
    """#26：完成任務列顯示 in/out 用量＋實際金額（siliconflow 單價 ×32 匯率）。

    siliconflow in/out 皆 $0.0012/1K：5682×0.0012 + 1751×0.0012 = US$0.00892
    × 32 = NT$0.285 → 顯示 NT$0.29（2 位小數）。
    """
    service, settings = _build(tmp_path)
    _seed_with_usage(service, tmp_path)
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))

    async with user_simulation(
        root=lambda: _history_page(service, settings, cost)
    ) as user:
        table = await _open_history(user, service, settings)
        row = table.rows[0]
        assert row["tokens_label"] == "in 5,682 / out 1,751"
        assert row["cost_label"] == "NT$0.29"


@pytest.mark.asyncio
async def test_history_tokens_empty_when_no_usage(tmp_path):
    """#26：無用量（未完成／0 token）→ 兩欄顯示 "—"，不誤導為免費。"""
    service, settings = _build(tmp_path)
    _seed_completed(service, tmp_path, 1)  # _seed_completed 的 result tokens 都是 0

    async with user_simulation(
        root=lambda: _history_page(service, settings, CostService(SqliteSettingsRepository(tmp_path / "pk.db")))
    ) as user:
        table = await _open_history(user, service, settings)
        assert table.rows[0]["tokens_label"] == "—"
        assert table.rows[0]["cost_label"] == "—"


@pytest.mark.asyncio
async def test_history_container_spans_full_width(tmp_path):
    """#24：歷史頁容器不再被 max-w-5xl 限寬（使用者明定「填滿左右」）。"""
    service, settings = _build(tmp_path)
    _seed_completed(service, tmp_path, 1)

    async with user_simulation(
        root=lambda: _history_page(service, settings)
    ) as user:
        await _open_history(user, service, settings)
        columns = [el for el in user.find(ui.column).elements]
        assert any(
            "w-full" in el._classes and not any(c.startswith("max-w") for c in el._classes)
            for el in columns
        ), "歷史頁應有無 max-w 限制的 w-full 容器"
