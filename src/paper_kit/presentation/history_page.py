"""任務歷史頁與批量下載路由（T-07 相位 4 自 app.py 抽出）。"""

import logging
import tempfile

from fastapi.responses import FileResponse, JSONResponse  # 票 18：批量下載 zip 路由
from nicegui import app, ui
from starlette.background import BackgroundTask  # 票 18：zip 送完即刪

from paper_kit.application.cost_service import CostService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.presentation.handlers import JobCardView, build_batch_zip, build_job_card
from paper_kit.presentation.job_actions import (
    _batch_cancel,
    _batch_retry,
    _delete_jobs,
)
from paper_kit.presentation.runtime import FILES_BASE
from paper_kit.presentation.shell import (
    BADGE_COLORS,
    SIDEBAR_NAV,
    _engine_label_map,
    _nav_active,
    app_frame,
)

logger = logging.getLogger("paper_kit.presentation.history_page")


def _history_page(
    service: JobService,
    settings: SettingsService,
    cost: CostService | None = None,  # #26：金額欄（實際成本）；None → 顯示 "—"
    engine_labels: dict[str, str] | None = None,
) -> None:
    """票 17：任務歷史表格頁——表格化＋分頁（每頁 10）＋引擎欄＋空狀態。

    對照沉浸式翻譯「記錄頁」：欄位（文件名／創建時間／頁數／引擎／狀態／操作）。
    批量操作（勾選／刪除／zip 下載）是票 18；本頁先立表格骨架。
    ui.table 的列資料直接送前端渲染（Vue），必須 JSON-safe——
    enum 不序列化，故列資料用挑選過的 dict（非 vars(view)）。
    slot 模板的 scope 變數是 props（`props.row`）且 body-cell slot 需自包
    <q-td>（spec review：裸 row.xxx 模板在前端渲染失敗）。
    """

    @ui.page("/history")
    def history_page():
        ui.page_title("Paper_Kit 歷史")
        # 票 16：統一頁框——側欄（歷史 active）
        nav = [(l, p, _nav_active(p, "/history")) for l, p in SIDEBAR_NAV]
        app_frame("📚 翻譯歷史", settings, nav)
        # #24：歷史頁寬度填滿左右（使用者明定「歷史頁的文件才應該填滿左右，
        # 而不是用左右橫向條」）——max-w-5xl 造成 1920 螢幕左右大留白、表格被擠
        with ui.column().classes("w-full p-6 gap-4"):
            jobs = service.list_jobs()
            if not jobs:
                # 票 17 AC：空歷史提示＋「翻譯新文件」快捷入口（→ 主頁）
                ui.label("尚無翻譯任務").classes("text-xl text-grey-8")
                ui.link("翻譯新文件", "/").classes("text-primary")
                return
            engine_map = engine_labels or _engine_label_map()
            columns = [
                {"name": "file_name", "label": "文件名", "field": "file_name", "align": "left"},
                {"name": "created", "label": "創建時間", "field": "created_label", "align": "left"},
                {"name": "pages", "label": "頁數", "field": "pages_label", "align": "left"},
                {"name": "engine", "label": "引擎", "field": "engine_label", "align": "left"},
                # #26：tokens 用量（in/out 兩種）＋金額花費欄（使用者要求；
                # 多引擎如 BabelDOC 顯示 in/out 兩種用量）
                {"name": "tokens", "label": "tokens 用量", "field": "tokens_label", "align": "left"},
                {"name": "cost", "label": "金額", "field": "cost_label", "align": "left"},
                {"name": "cache", "label": "來源", "field": "cache_label", "align": "left"},
                {"name": "status", "label": "狀態", "field": "status_label", "align": "left"},
                {"name": "actions", "label": "操作", "field": "actions", "align": "left"},
            ]
            rows = _history_rows(service, engine_map, cost)
            # 票 18：selection='multiple' → Quasar 內建勾選欄＋全選；
            # row_key 指向 job_id（row dict 由 _history_row 提供）
            table = ui.table(
                columns=columns, rows=rows, row_key="job_id",
                selection="multiple", pagination={"rowsPerPage": 10},
            ).classes("w-full")
            # 狀態彩色標籤（q-badge；scope=props、需自包 <q-td>）
            table.add_slot(
                "body-cell-status",
                "<q-td><q-badge :color='props.row.status_color' :label='props.row.status_label' /></q-td>",
            )
            # #27：頁數欄顯示「N/M 頁」（翻譯頁數/PDF 總頁數）；hover 顯示原始選取頁碼
            table.add_slot(
                "body-cell-pages",
                "<q-td :title=\"props.row.pages_raw ? '選取頁碼：' + props.row.pages_raw : ''\">"
                "{{ props.row.pages_label }}</q-td>",
            )
            # 操作列：mono／dual 下載（dual 不可退化——使用者明定）；
            # download attr＝附件下載（與主頁 ui.download 行為一致）。
            # 重試／取消：Vue slot 無法綁 Python handler，票 17 review 裁決——
            # 單列重試／取消併入票 18 批量操作列（批量按鈕在表格下方，Python handler 可直綁）。
            table.add_slot(
                "body-cell-actions",
                """<q-td><div class="flex gap-1">
                <q-btn v-if="props.row.mono_url" size="sm" flat color="primary" type="a"
                       :href="props.row.mono_url" download label="下載 mono" />
                <q-btn v-if="props.row.dual_url" size="sm" flat color="teal" type="a"
                       :href="props.row.dual_url" download label="下載 dual" />
                </div></q-td>""",
            )

            # ── 票 18：批量操作工具列（勾選後操作；刪除二次確認） ──

            def _refresh_rows() -> None:
                """批量操作後重繪表格（選取清空）。#26：重繪必須帶 cost——否則
                操作後金額欄回退 "—"，與初次渲染不一致。"""
                table.rows = _history_rows(service, engine_map, cost)
                table.selected = []

            def _require_selection() -> list[str] | None:
                """勾選檢查——空選回 None（已提示），否則回 job_id 清單。"""
                ids = [r["job_id"] for r in table.selected]
                if not ids:
                    ui.notify("請先勾選要操作的任務", type="warning")
                    return None
                return ids

            def _batch_delete() -> None:
                ids = _require_selection()
                if ids is None:
                    return
                # 二次確認 dialog（破壞性操作——規格書 Further Notes 必做）
                with ui.dialog() as dialog, ui.card().classes("p-4 gap-2"):
                    ui.label(f"確定刪除 {len(ids)} 筆任務（含輸出檔）？").classes("text-lg")
                    ui.label("此操作無法復原").classes("text-xs text-grey-6")
                    with ui.row().classes("gap-2"):
                        ui.button("取消", on_click=dialog.close).props("outline")
                        ui.button(
                            "確認刪除",
                            on_click=lambda: (_confirm_delete(ids), dialog.close()),
                        ).props("color=negative")
                dialog.open()

            def _confirm_delete(ids: list[str]) -> None:
                deleted, blocked = _delete_jobs(service, ids)
                if blocked:
                    ui.notify(f"{blocked} 筆執行中的任務無法刪除", type="warning")
                if deleted:
                    ui.notify(f"已刪除 {deleted} 筆任務", type="positive")
                _refresh_rows()

            def _batch_action(action: str) -> None:
                """票 18：批量重試／取消（票 17 review 裁決的承諾——Python handler 直綁）。"""
                ids = _require_selection()
                if ids is None:
                    return
                if action == "retry":
                    n = _batch_retry(service, settings, ids)
                    if n == 0:
                        ui.notify("沒有可重試的任務（僅失敗／已取消可重試）", type="warning")
                else:
                    n = _batch_cancel(service, ids)
                    if n == 0:
                        ui.notify("沒有執行中的任務可取消", type="warning")
                _refresh_rows()

            def _batch_download(kind: str) -> None:
                ids = _require_selection()
                if ids is None:
                    return
                # 跳到 /download-batch 路由：伺服端 zip 打包、附件回傳（送完刪暫存）
                ui.navigate.to(f"/download-batch?ids={','.join(ids)}&kind={kind}")

            with ui.row().classes("items-center gap-2"):
                ui.button("批量刪除", on_click=_batch_delete).props("outline color=negative")
                ui.button(
                    "↻ 批量重試", on_click=lambda: _batch_action("retry")
                ).props("outline")
                ui.button(
                    "✕ 批量取消", on_click=lambda: _batch_action("cancel")
                ).props("outline")
                ui.button(
                    "批量下載 mono", on_click=lambda: _batch_download("mono")
                ).props("outline")
                ui.button(
                    "批量下載 dual", on_click=lambda: _batch_download("dual")
                ).props("outline color=teal")
                ui.label("勾選表格列後操作；執行中任務無法刪除").classes("text-xs text-grey-6")


def register_batch_download_route(service: JobService) -> None:
    """票 18：/download-batch?ids=...&kind=mono|dual —— 批量 zip 附件下載。

    伺服端打包（build_batch_zip 純函式）、zip 暫存 tempdir、送完即刪
    （FastAPI BackgroundTask）。無可打包任務 → 404（UI 已先提示）；
    kind 只接受 mono/dual（review 修正：未知 kind 不靜默走 dual）。
    """
    @app.get("/download-batch")
    def download_batch(ids: str = "", kind: str = "mono"):
        if kind not in ("mono", "dual"):
            return JSONResponse({"error": "bad kind"}, status_code=400)
        job_ids = [i for i in ids.split(",") if i]
        jobs = [j for j in service.list_jobs() if j.job_id in job_ids]
        zip_path = build_batch_zip(jobs, kind, tempfile.gettempdir())
        if zip_path is None:
            return JSONResponse({"error": "no files"}, status_code=404)
        return FileResponse(
            zip_path,
            filename=zip_path.name,
            media_type="application/zip",
            background=BackgroundTask(zip_path.unlink, missing_ok=True),
        )


def _history_rows(
    service: JobService, engine_map: dict[str, str], cost: CostService | None = None
) -> list[dict]:
    """票 18：歷史表格列資料一處建構（initial 與 _refresh_rows 共用，免重複）。"""
    return [
        _history_row(
            build_job_card(job, files_base=FILES_BASE, engine_labels=engine_map),
            job,
            cost,
        )
        for job in service.list_jobs()
    ]


def _tokens_label(job: TranslationJob) -> str:
    """#26：歷史表 tokens 用量欄——「in 5,682 / out 1,751」（千分位）。

    使用者要求「額度 tokens 用量（若是多個模型如 BabelDOC 則要顯示 2 種）」——
    輸入/輸出兩種用量。未完成／無用量 → "—"。
    """
    result = job.result
    if not result or not (result.input_tokens or result.output_tokens):
        return "—"
    return f"in {result.input_tokens:,} / out {result.output_tokens:,}"


def _cost_label(job: TranslationJob, cost: CostService | None) -> str:
    """#26：歷史表金額欄——實際成本 NT$（actual 為準，與卡片 usage_label 同源）。

    不可算（無 cost service／無用量／引擎未知／估算例外）→ "—"，不誤導為免費。
    """
    result = job.result
    if cost is None or not result or not (result.input_tokens or result.output_tokens):
        return "—"
    if not job.engine_id:
        return "—"
    try:
        actual = cost.actual(job, job.engine_id)
    except Exception:
        return "—"
    return f"NT${cost.twd(actual.cost):.2f}"


def _history_row(view: JobCardView, job: TranslationJob, cost: CostService | None = None) -> dict:
    """歷史表格列資料——只挑 JSON-safe 欄位（票 17；enum 不序列化）。"""
    return {
        "job_id": view.job_id,  # 票 18：row_key（勾選回傳可對映回任務）
        "file_name": view.file_name,
        "created_label": view.created_label,
        "pages_label": view.pages_label,
        "pages_raw": view.pages_raw,  # #27：原始選取頁碼（hover title）
        "engine_label": view.engine_label or "",
        "tokens_label": _tokens_label(job),  # #26：in/out 用量
        "cost_label": _cost_label(job, cost),  # #26：實際金額
        "cache_label": "⚡ 快取" if view.from_cache else "—",  # 票 26：來源欄
        "status_label": view.status_label,
        "status_color": BADGE_COLORS[view.status],
        "mono_url": view.mono_url,
        "dual_url": view.dual_url,
    }
