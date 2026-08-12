"""Paper_Kit NiceGUI 介面（薄層：widget ↔ handlers ↔ JobService）。

widget 邏輯盡量薄——狀態對映在 handlers（純函式可測）、業務在 application。
NiceGUI 走 WebSocket 推送 → 事件驅動、無整頁重載（ui.timer 輪詢狀態）。

啟動：`uv run paper-kit` → http://localhost:8080（設定頁 /settings）
"""

import tempfile
import uuid
from pathlib import Path

from nicegui import app, ui

from paper_kit.application.cost_service import CostService
from paper_kit.application.errors import to_user_message
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.pages import parse_pages
from paper_kit.domain.translation_job import InvalidTransition
from paper_kit.application.ports import EngineError
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.cost_calculator import CostEstimate
from paper_kit.domain.glossary import GlossaryFormatError
from paper_kit.domain.translation_job import JobStatus
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS
from paper_kit.infrastructure.glossary_repo import GlossaryNameError, GlossaryRepository
from paper_kit.infrastructure.job_repo import SqliteJobRepository
from paper_kit.infrastructure.logging_setup import format_log_line, recent_log_entries, setup_logging
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.handlers import JobCardView, build_job_card
from paper_kit.presentation.theme import apply_theme

APP_DIR = Path.home() / ".paper_kit"
OUTPUTS_DIR = APP_DIR / "outputs"
GLOSSARIES_DIR = APP_DIR / "glossaries"
DB_PATH = APP_DIR / "paper_kit.db"
FILES_BASE = "/files"

BADGE_COLORS = {
    JobStatus.QUEUED: "blue-grey",
    JobStatus.TRANSLATING: "indigo",
    JobStatus.COMPLETED: "green",
    JobStatus.FAILED: "red",
    JobStatus.CANCELLED: "grey",
}


def _real_path(view_url: str) -> Path:
    """/files/<job_id>/<name> → 磁碟真實路徑（下載用）。"""
    return OUTPUTS_DIR / view_url.split(FILES_BASE + "/", 1)[1]


def _start_job(
    service: JobService,
    settings: SettingsService,
    cost: CostService,
    glossaries: GlossaryService,
    e,
    pages_text: str = "",
    sensitive: bool = False,
) -> None:
    # 票 07：頁面範圍輸入驗證（空白=全部）；非法格式不建任務（驗證先於寫暫存檔）
    try:
        pages = parse_pages(pages_text)
    except ValueError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    try:
        staging = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}-{e.name}"
        with open(staging, "wb") as f:
            f.write(e.content.read())
    except OSError as exc:  # 票 09：暫存寫入失敗也要有 toast，不吐 traceback
        ui.notify(to_user_message(exc), type="negative")
        return
    try:
        engine = settings.resolve_engine()
    except EngineError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    engine_id = settings.engine_id()
    # 票 10 紅線：機密文件＋視覺引擎 → 連任務都不建（UI 早攔，service.start 再兜底）。
    # .get()：未知引擎保守視為視覺（機密 fail-closed）
    spec = ENGINE_SPECS.get(engine_id)
    if sensitive and (spec is None or not spec.sensitive_ok):
        ui.notify("機密文件只可使用 DeepSeek 純文字引擎（先到設定切換引擎）", type="negative")
        return
    job = service.create_job(
        staging,
        target_lang=settings.target_lang(),
        pages=pages,
        output_dir=settings.output_dir(),
        sensitive=sensitive,
    )
    # 票 05：挑選的術語表組合＋自動提取開關隨任務記錄（之後改設定不影響舊任務）
    names = settings.selected_glossary_names(glossaries.list_glossaries())  # 預設全選
    job.glossary_files = glossaries.paths_for(names)
    job.auto_extract = settings.auto_extract()
    # 票 07：指定頁面範圍時估價按範圍縮放（規格書 story 4「只為需要的部分付費」）
    est = cost.estimate_for_pdf(engine_id, staging, pages=pages)
    if est is not None:
        job.estimated_cost = est.cost  # 存下前置估算：完成後比對的是「使用者看到的」數字
    _notify_estimate(cost, engine_id, est)
    ui.notify(f"任務已建立：{e.name}", type="positive")
    # 票 10：engine_allows_sensitive 由 UI 層查 ENGINE_SPECS 傳入（service 兜底防衛）
    service.start(
        job.job_id, engine, engine_id=engine_id,
        engine_allows_sensitive=spec.sensitive_ok if spec else False,
    )


def _notify_estimate(
    cost: CostService, engine_id: str, est: CostEstimate | None
) -> None:
    """票 06：上傳時顯示成本估算（頁數、引擎、單價明細）。不可估就靜默跳過。"""
    if est is None:
        return
    cfg = cost.pricing_for(engine_id)
    pages = est.total_tokens // cfg.per_page_tokens if cfg.per_page_tokens else 0
    if pages <= 0:
        return
    if cfg.input_per_1k == 0 and cfg.output_per_1k == 0:
        ui.notify(f"已估算：{pages} 頁 · {engine_id} 免費引擎無費用", type="info")
    else:
        ui.notify(
            f"已估算：{pages} 頁 · {engine_id}："
            f"in {est.input_tokens:,}×${cfg.input_per_1k}/1K + "
            f"out {est.output_tokens:,}×${cfg.output_per_1k}/1K ≈ ${est.cost}",
            type="info",
        )


def _retry_job(service: JobService, settings: SettingsService, job_id: str) -> None:
    """票 08：失敗任務重試（回 queued 再跑，不需重新上傳）。"""
    try:
        engine = settings.resolve_engine()
    except EngineError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    try:
        engine_id = settings.engine_id()
        # 票 10：機密任務重試也用目前的引擎判定（視覺引擎 → ValueError 拒絕）。
        # .get()：未知引擎保守視為視覺（機密 fail-closed）
        spec = ENGINE_SPECS.get(engine_id)
        service.retry(
            job_id, engine, engine_id=engine_id,
            engine_allows_sensitive=spec.sensitive_ok if spec else False,
        )
        ui.notify("已重新排隊", type="positive")
    except InvalidTransition as exc:
        ui.notify(to_user_message(exc), type="negative")
    except ValueError as exc:
        ui.notify(to_user_message(exc), type="negative")  # 票 10：機密＋視覺引擎（統一入口）
    except KeyError:
        ui.notify("找不到此任務", type="negative")  # KeyError 語境由呼叫端決定（票 09 review）


def _cancel_job(service: JobService, job_id: str) -> None:
    """票 08：進行中任務取消（狀態→cancelled、產出拋棄）。"""
    try:
        service.cancel(job_id)
        ui.notify("已取消", type="warning")
    except InvalidTransition as exc:
        ui.notify(to_user_message(exc), type="negative")
    except KeyError:
        ui.notify("找不到此任務", type="negative")  # KeyError 語境由呼叫端決定（票 09 review）


def _render_card(view: JobCardView, service: JobService, settings: SettingsService) -> None:
    with ui.card().classes("w-full pk-card"):  # 票 11：卡片主題 class（圓角/陰影/背景變數）
        with ui.row().classes("items-center justify-between w-full"):
            with ui.column().classes("gap-0"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(view.file_name).classes("text-lg font-semibold")
                    if view.sensitive:  # 票 10：機密標記顯示
                        ui.badge("🔒 機密").props("outline color=orange")
                # 票 08：歷史卡片顯示建立時間＋引擎
                meta = f"任務 {view.job_id[:8]} · {view.created_label}"
                if view.engine_label:
                    meta += f" · {view.engine_label}"
                ui.label(meta).classes("text-xs pk-meta")  # 票 11：muted 變數
            ui.badge(view.status_label).props(f"color={BADGE_COLORS[view.status]}")
        if view.is_running:
            # 票 11：進度條納入主題變數（深色下保持對比）
            ui.linear_progress(value=0.5).props("indeterminate").classes("w-full pk-progress")
        elif view.status is JobStatus.COMPLETED:
            ui.linear_progress(value=1.0).classes("w-full pk-progress")
        if view.error:
            ui.label(f"錯誤：{view.error}").classes("pk-error")  # 票 11：錯誤語意色走主題變數
        # 票 08 review：完成任務顯示「估算 vs 實際」，未完成顯示上傳時估價
        cost_label = view.usage_label or view.estimated_label
        if cost_label:
            ui.label(cost_label).classes("text-sm pk-cost")  # 票 11：成本排版變數
        with ui.row().classes("items-center"):
            if view.can_retry:
                ui.button(
                    "↻ 重試",
                    on_click=lambda: _retry_job(service, settings, view.job_id),
                ).props("outline")
            if view.can_cancel:
                ui.button(
                    "✕ 取消",
                    on_click=lambda: _cancel_job(service, view.job_id),
                ).props("outline negative")
            if view.mono_url:
                ui.button(
                    "下載 mono",
                    on_click=lambda: ui.download(str(_real_path(view.mono_url))),
                ).props("outline")
                ui.button(
                    "下載 dual",
                    on_click=lambda: ui.download(str(_real_path(view.dual_url))),
                ).props("outline")
                ui.button("瀏覽器內預覽", on_click=lambda: _preview(view.preview_url))


def _preview(url: str) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[90vw] h-[90vh]"):
        ui.pdf(url).classes("w-full h-full")
    dialog.open()


def _refresh(
    cards, service: JobService, cost: CostService, settings: SettingsService, memo: dict
) -> None:
    cards.clear()
    # spec review：引擎欄顯示 label（「DeepSeek（純文字…）」）不是 raw id
    engine_labels = {eid: spec.label for eid, spec in ENGINE_SPECS.items()}
    for job in service.list_jobs():
        # memo：完成任務只算一次成本標籤（1s 輪詢下避免每輪重讀 PDF 頁數）
        if job.status is JobStatus.COMPLETED and job.job_id not in memo:
            memo[job.job_id] = cost.usage_label(job)
        _render_card(
            build_job_card(
                job, usage_label=memo.get(job.job_id), engine_labels=engine_labels
            ),
            service,
            settings,
        )


def _save_engine(settings: SettingsService, engine_id: str, api_key: str) -> None:
    try:
        settings.set_engine(engine_id)
        if api_key:
            settings.set_api_key(engine_id, api_key)
        ui.notify("引擎設定已儲存", type="positive")
    except KeyError:
        ui.notify("未知引擎", type="negative")


def _settings_page(
    settings: SettingsService, cost: CostService, glossaries: GlossaryService
) -> None:
    @ui.page("/settings")
    def settings_page():
        ui.page_title("Paper_Kit 設定")
        _enter_theme(settings)  # 票 11：設定頁與 debug 頁同一主題
        with ui.header().classes("items-center"):
            ui.label("⚙️ Paper_Kit 設定").classes("text-2xl font-bold")
        with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
            with ui.card().classes("w-full"):
                ui.label("翻譯引擎").classes("font-bold")
                ui.select(
                    {eid: spec.label for eid, spec in ENGINE_SPECS.items()},
                    value=settings.engine_id(),
                    label="引擎",
                ).classes("w-full").bind_value_to(locals(), "engine_id")
                ui.input(
                    "API key（存本機 SQLite，不會進 log）",
                    value=settings.api_key(settings.engine_id()),
                    password=True,
                    password_toggle_button=True,
                ).classes("w-full").bind_value_to(locals(), "api_key")
                ui.button(
                    "儲存引擎設定",
                    on_click=lambda: _save_engine(settings, engine_id, api_key),
                ).props("outline")
            with ui.card().classes("w-full"):
                ui.label("預設值").classes("font-bold")
                ui.input(
                    "目標語言（如 zh-TW）",
                    value=settings.target_lang(),
                ).classes("w-full").bind_value_to(locals(), "target_lang")
                ui.input(
                    "輸出目錄（空白 = ~/.paper_kit/outputs）",
                    value=settings.output_dir(),
                ).classes("w-full").bind_value_to(locals(), "output_dir")
                ui.button(
                    "儲存預設",
                    on_click=lambda: _save_defaults(settings, target_lang, output_dir),
                ).props("outline")
            with ui.card().classes("w-full"):
                ui.label("引擎單價（USD / 1K tokens）").classes("font-bold")
                ui.label("票 06：DeepSeek 漲價只需改這裡（單價是設定不是寫死）").classes(
                    "text-xs text-grey-6"
                )
                base = cost.pricing_for(engine_id)
                ui.input(
                    "input 單價",
                    value=str(base.input_per_1k),
                ).classes("w-full").bind_value_to(locals(), "in_price")
                ui.input(
                    "output 單價",
                    value=str(base.output_per_1k),
                ).classes("w-full").bind_value_to(locals(), "out_price")
                ui.input(
                    "每頁 token 基準",
                    value=str(base.per_page_tokens),
                ).classes("w-full").bind_value_to(locals(), "per_page")
                ui.button(
                    "儲存單價（目前選定的引擎）",
                    on_click=lambda: _save_pricing(cost, engine_id, in_price, out_price, per_page),
                ).props("outline")
            with ui.card().classes("w-full"):
                ui.label("術語表庫").classes("font-bold")
                ui.label("票 05：多份術語表各自命名；翻譯前挑選套用哪些。CSV 標頭：source,target[,tgt_lng]").classes(
                    "text-xs text-grey-6"
                )
                glossary_select = ui.select(
                    glossaries.list_glossaries(),
                    value=settings.selected_glossary_names(glossaries.list_glossaries()),
                    multiple=True,
                    label="翻譯時套用的術語表（預設全選；勾選即生效）",
                ).classes("w-full")
                glossary_select.on_value_change(
                    lambda: settings.set_selected_glossaries(list(glossary_select.value))
                )
                ui.switch(
                    "自動術語提取（--term-siliconflow，Kimi 角色原生版）",
                    value=settings.auto_extract(),
                ).on_value_change(lambda e: settings.set_auto_extract(e.value))
                ui.upload(
                    label="匯入術語表 CSV（檔名＝術語表名）",
                    auto_upload=True,
                    on_upload=lambda e: _import_glossary(
                        glossaries, settings, glossary_select, edit_select, e
                    ),
                ).classes("w-full")
                new_name_input = ui.input("新術語表名稱").classes("w-full")
                ui.button(
                    "新增術語表",
                    on_click=lambda: _create_glossary(
                        glossaries, glossary_select, edit_select, new_name_input
                    ),
                ).props("outline")
                ui.separator()
                ui.label("編輯術語表").classes("font-bold")
                edit_select = ui.select(
                    glossaries.list_glossaries(),
                    value=None,
                    label="要編輯哪一份（顯示下面的列）",
                ).classes("w-full")
                edit_select.on_value_change(
                    lambda e: _render_entries(glossaries, entries_box, e.value)
                )
                rename_to_input = ui.input("改名為（選定後填入再按）").classes("w-full")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.button(
                        "改名",
                        on_click=lambda: _rename_glossary(
                            glossaries, settings, glossary_select, edit_select,
                            edit_select.value, rename_to_input, entries_box,
                        ),
                    ).props("outline")
                    ui.button(
                        "刪除選定術語表",
                        on_click=lambda: _delete_glossary(
                            glossaries, settings, glossary_select, edit_select,
                            edit_select.value, entries_box,
                        ),
                    ).props("outline flat color=red")
                entries_box = ui.column().classes("w-full gap-1")
                with ui.row().classes("w-full items-center gap-2"):
                    src_input = ui.input("source").props("dense").classes("flex-1")
                    tgt_input = ui.input("target").props("dense").classes("flex-1")
                    ui.button(
                        "新增術語列",
                        on_click=lambda: _add_entry(
                            glossaries, edit_select.value, src_input, tgt_input, entries_box
                        ),
                    ).props("outline")


def _save_defaults(settings: SettingsService, target_lang: str, output_dir: str) -> None:
    settings.set_target_lang(target_lang.strip() or "zh-TW")
    settings.set_output_dir(output_dir.strip())
    ui.notify("預設已儲存", type="positive")


# ── 票 05：術語表庫 UI ─────────────────────────────────────────


def _sync_glossary_pickers(
    glossaries: GlossaryService,
    glossary_select,
    edit_select,
    keep: list[str],
) -> None:
    """CRUD 後同步兩個選擇控件為最新術語表名（keep 之外的新名不自動選）。"""
    names = glossaries.list_glossaries()
    glossary_select.set_options(names, value=[n for n in keep if n in names])
    edit_select.set_options(names, value=edit_select.value if edit_select.value in names else None)


def _import_glossary(
    glossaries: GlossaryService,
    settings: SettingsService,
    glossary_select,
    edit_select,
    e,
) -> None:
    """CSV 上傳：檔名＝術語表名；缺 source/target 標頭顯示明確錯誤（不崩潰）。"""
    name = Path(e.name).stem.strip() or "匯入"
    raw = e.content.read()
    try:
        text = raw.decode("utf-8-sig")  # 吃 Excel 的 BOM
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp950")  # Big5 正體中文（本機環境常見）
        except UnicodeDecodeError:
            ui.notify("CSV 編碼無法識別（需 UTF-8 或 Big5）", type="negative")
            return
    try:
        count = glossaries.import_csv(name, text, target_lang=settings.target_lang())
    except (GlossaryFormatError, GlossaryNameError) as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    ui.notify(f"已匯入 {name}（{count} 條）", type="positive")
    _sync_glossary_pickers(
        glossaries, glossary_select, edit_select, list(glossary_select.value) + [name]
    )


def _create_glossary(
    glossaries: GlossaryService, glossary_select, edit_select, new_name_input
) -> None:
    name = new_name_input.value.strip()
    if not name:
        ui.notify("先填新術語表名稱", type="negative")
        return
    try:
        glossaries.create_glossary(name)
    except (GlossaryNameError, OSError) as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    ui.notify(f"已建立 {name}", type="positive")
    new_name_input.set_value("")
    _sync_glossary_pickers(
        glossaries, glossary_select, edit_select, list(glossary_select.value) + [name]
    )


def _delete_glossary(
    glossaries: GlossaryService,
    settings: SettingsService,
    glossary_select,
    edit_select,
    name,
    entries_box,
) -> None:
    if not name:
        ui.notify("先選要刪除的術語表", type="negative")
        return
    try:
        glossaries.delete_glossary(name)
    except KeyError:
        return
    ui.notify(f"已刪除 {name}", type="negative")
    keep = [n for n in glossary_select.value if n != name]
    stored = settings.selected_glossaries()  # stored 選擇同步：刪掉的名字不再引用
    if stored is not None:
        settings.set_selected_glossaries([n for n in stored if n != name])
    _sync_glossary_pickers(glossaries, glossary_select, edit_select, keep)
    _render_entries(glossaries, entries_box, None)


def _rename_glossary(
    glossaries: GlossaryService,
    settings: SettingsService,
    glossary_select,
    edit_select,
    name,
    rename_to_input,
    entries_box,
) -> None:
    if not name:
        ui.notify("先選要改名的術語表", type="negative")
        return
    new = rename_to_input.value.strip()
    try:
        glossaries.rename_glossary(name, new)
    except (GlossaryNameError, OSError) as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    except KeyError:
        ui.notify("找不到此術語表", type="negative")  # 語境由呼叫端決定（票 09 review）
        return
    ui.notify(f"已改名 {name} → {new}", type="positive")
    rename_to_input.set_value("")
    keep = [new if n == name else n for n in glossary_select.value]
    stored = settings.selected_glossaries()  # stored 選擇同步：舊名換新名
    if stored is not None:
        settings.set_selected_glossaries([new if n == name else n for n in stored])
    _sync_glossary_pickers(glossaries, glossary_select, edit_select, keep)
    _render_entries(glossaries, entries_box, new)


def _render_entries(glossaries: GlossaryService, entries_box, name) -> None:
    """編輯頁顯示術語列（每列 source → target＋刪除鈕）。"""
    entries_box.clear()
    if not name:
        return
    try:
        entries = glossaries.entries(name)
    except KeyError:
        return
    with entries_box:
        for i, (source, target) in enumerate(entries):
            with ui.row().classes("items-center w-full gap-2"):
                ui.label(f"{source} → {target}").classes("flex-1 text-sm")
                ui.button(
                    "✕",
                    on_click=lambda i=i: _delete_entry(glossaries, name, i, entries_box),
                ).props("dense flat color=red")
        if not entries:
            ui.label("（空白術語表）").classes("text-grey-6 text-sm")


def _delete_entry(
    glossaries: GlossaryService, name: str, index: int, entries_box
) -> None:
    glossaries.delete_entry(name, index)
    _render_entries(glossaries, entries_box, name)


def _add_entry(
    glossaries: GlossaryService,
    name: str,
    src_input,
    tgt_input,
    entries_box,
) -> None:
    if not name:
        ui.notify("先選要編輯的術語表", type="negative")
        return
    source = src_input.value.strip()
    target = tgt_input.value.strip()
    if not source or not target:
        ui.notify("source 與 target 都要填", type="negative")
        return
    glossaries.add_entry(name, source, target)
    src_input.set_value("")
    tgt_input.set_value("")
    _render_entries(glossaries, entries_box, name)


def _save_pricing(cost: CostService, engine_id: str, in_price: str, out_price: str, per_page: str) -> None:
    try:
        cost.set_pricing(engine_id, in_price, out_price, int(per_page))
        ui.notify(f"單價已儲存（{engine_id}）", type="positive")
    except (ValueError, TypeError):
        ui.notify("單價格式錯誤（需為數字）", type="negative")  # 表單驗證，固定訊息


def _enter_theme(settings: SettingsService) -> ui.dark_mode:
    """票 11：三頁共用入口——注入主題 CSS＋依偏好套深色，回傳控制器。"""
    dark = apply_theme()
    if settings.dark_mode():
        dark.enable()
    return dark


def _toggle_theme(settings: SettingsService, dark: ui.dark_mode, btn) -> None:
    """票 11：切換深色偏好並即時套用（不重載頁面），按鈕圖示同步更新。"""
    on = not settings.dark_mode()
    settings.set_dark_mode(on)
    if on:
        dark.enable()
    else:
        dark.disable()
    btn.set_text("☀️" if on else "🌙")


def _debug_page(log_path: Path, settings: SettingsService) -> None:
    """票 09：debug 檢視頁——最近任務的 log 可查（job_id 過濾）。"""

    @ui.page("/debug")
    def debug_page():
        ui.page_title("Paper_Kit Debug")
        _enter_theme(settings)  # 票 11：設定頁與 debug 頁同一主題
        with ui.header().classes("items-center"):
            ui.label("🔍 Paper_Kit Debug Log").classes("text-2xl font-bold")
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label(f"log 檔：{log_path}").classes("text-xs text-grey-6")
            job_filter = ui.input("過濾任務 id（空白 = 全部）").classes("w-full")
            box = ui.column().classes("w-full gap-1")

            def render():
                box.clear()
                entries = recent_log_entries(
                    log_path, n=200, job_id=(job_filter.value or "").strip() or None
                )
                with box:
                    if not entries:
                        ui.label("（無 log）").classes("text-grey-6 text-sm")
                    for entry in entries:
                        ui.label(format_log_line(entry)).classes("text-xs font-mono")

            job_filter.on_value_change(lambda: render())
            ui.button("重新整理", on_click=render).props("outline")
            render()


def main() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH = setup_logging(APP_DIR / "logs")  # 票 09：結構化 log 檔（debug 頁讀同一份）
    app.add_static_files(FILES_BASE, str(OUTPUTS_DIR))
    repo = SqliteSettingsRepository(DB_PATH)
    # 票 08：SQLite 任務歷史——重啟 app 後任務仍在（InMemory 只留給無頭執行）
    service = JobService(jobs=SqliteJobRepository(DB_PATH), outputs_dir=OUTPUTS_DIR)
    settings = SettingsService(repo)
    cost = CostService(repo)
    glossaries = GlossaryService(GlossaryRepository(GLOSSARIES_DIR))

    @ui.page("/")
    def index():
        ui.page_title("Paper_Kit")
        dark = _enter_theme(settings)  # 票 11：注入主題 CSS＋依偏好套深色（三頁共用入口）
        with ui.header().classes("items-center justify-between"):
            with ui.row().classes("items-center"):
                ui.label("📄 Paper_Kit 論文翻譯器").classes("text-2xl font-bold")
                ui.badge("自建 UI · 免除線上工具綁架").props("outline")
            with ui.row().classes("items-center gap-3"):
                # 票 11：主題切換按鈕——即時生效、不重載（偏好存 settings，圖示同步更新）
                theme_btn = ui.button(
                    "🌙" if settings.dark_mode() else "☀️",
                    on_click=lambda: _toggle_theme(settings, dark, theme_btn),
                ).props("flat round")
                ui.link("設定", "/settings").classes("text-white")
                ui.link("Debug", "/debug").classes("text-white text-grey-4")
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label("拖放 PDF 上傳，自動翻譯成繁體中文（mono＋dual 並排）").classes("text-grey-8")
            # 票 10：上傳即提示「檔案將送雲端」＋機密確認（R18／隱私紅線）
            ui.label(
                "⚠️ 上傳即代表同意：檔案內容將送雲端 API 翻譯。"
                "機密文件（R18／隱私）請勾選 🔒——僅 DeepSeek 純文字引擎可處理"
            ).classes("text-xs text-amber-7")
            sensitive_input = ui.checkbox("🔒 這是機密文件（只准純文字引擎，不上視覺模型）")
            memo: dict[str, str | None] = {}
            cards = ui.column().classes("w-full gap-4")
            # 票 07：頁面範圍（空白=全部；1-2／3-5／1-2,4-6 區間格式）
            pages_input = ui.input(
                "頁面範圍（空白=全部；如 1-2、3-5）"
            ).props("clearable").classes("w-full")
            ui.upload(
                label="拖放 PDF 或點選選擇",
                auto_upload=True,
                on_upload=lambda e: _start_job(
                    service, settings, cost, glossaries, e,
                    pages_text=pages_input.value, sensitive=sensitive_input.value,
                ),
            ).classes("w-full")
        ui.timer(1.0, lambda: _refresh(cards, service, cost, settings, memo))

    _settings_page(settings, cost, glossaries)
    _debug_page(LOG_PATH, settings)
    ui.run(title="Paper_Kit 論文翻譯器", reload=False)


if __name__ == "__main__":
    main()
