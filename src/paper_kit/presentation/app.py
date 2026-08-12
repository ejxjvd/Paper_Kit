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
from paper_kit.application.job_service import JobService
from paper_kit.application.ports import EngineError
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.cost_calculator import CostEstimate
from paper_kit.domain.translation_job import JobStatus
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.handlers import JobCardView, build_job_card

APP_DIR = Path.home() / ".paper_kit"
OUTPUTS_DIR = APP_DIR / "outputs"
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
    service: JobService, settings: SettingsService, cost: CostService, e
) -> None:
    staging = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}-{e.name}"
    with open(staging, "wb") as f:
        f.write(e.content.read())
    job = service.create_job(staging, target_lang=settings.target_lang())
    try:
        engine = settings.resolve_engine()
    except EngineError as exc:
        ui.notify(str(exc), type="negative")
        return
    engine_id = settings.engine_id()
    est = cost.estimate_for_pdf(engine_id, staging)
    if est is not None:
        job.estimated_cost = est.cost  # 存下前置估算：完成後比對的是「使用者看到的」數字
    _notify_estimate(cost, engine_id, est)
    ui.notify(f"任務已建立：{e.name}", type="positive")
    service.start(job.job_id, engine, engine_id=engine_id)


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


def _render_card(view: JobCardView) -> None:
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center justify-between w-full"):
            with ui.column().classes("gap-0"):
                ui.label(view.file_name).classes("text-lg font-semibold")
                ui.label(f"任務 {view.job_id[:8]}").classes("text-xs text-grey-6")
            ui.badge(view.status_label).props(f"color={BADGE_COLORS[view.status]}")
        if view.is_running:
            ui.linear_progress(value=0.5).props("indeterminate").classes("w-full")
        elif view.status is JobStatus.COMPLETED:
            ui.linear_progress(value=1.0).classes("w-full")
        if view.error:
            ui.label(f"錯誤：{view.error}").classes("text-red-7")
        if view.usage_label:
            ui.label(view.usage_label).classes("text-grey-8 text-sm")
        if view.mono_url:
            with ui.row().classes("items-center"):
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


def _refresh(cards, service: JobService, cost: CostService, memo: dict) -> None:
    cards.clear()
    for job in service.list_jobs():
        # memo：完成任務只算一次成本標籤（1s 輪詢下避免每輪重讀 PDF 頁數）
        if job.status is JobStatus.COMPLETED and job.job_id not in memo:
            memo[job.job_id] = cost.usage_label(job)
        _render_card(build_job_card(job, usage_label=memo.get(job.job_id)))


def _save_engine(settings: SettingsService, engine_id: str, api_key: str) -> None:
    try:
        settings.set_engine(engine_id)
        if api_key:
            settings.set_api_key(engine_id, api_key)
        ui.notify("引擎設定已儲存", type="positive")
    except KeyError:
        ui.notify("未知引擎", type="negative")


def _settings_page(settings: SettingsService, cost: CostService) -> None:
    @ui.page("/settings")
    def settings_page():
        ui.page_title("Paper_Kit 設定")
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


def _save_defaults(settings: SettingsService, target_lang: str, output_dir: str) -> None:
    settings.set_target_lang(target_lang.strip() or "zh-TW")
    settings.set_output_dir(output_dir.strip())
    ui.notify("預設已儲存", type="positive")


def _save_pricing(cost: CostService, engine_id: str, in_price: str, out_price: str, per_page: str) -> None:
    try:
        cost.set_pricing(engine_id, in_price, out_price, int(per_page))
        ui.notify(f"單價已儲存（{engine_id}）", type="positive")
    except (ValueError, TypeError):
        ui.notify("單價格式錯誤（需為數字）", type="negative")


def main() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    app.add_static_files(FILES_BASE, str(OUTPUTS_DIR))
    repo = SqliteSettingsRepository(DB_PATH)
    service = JobService(jobs=InMemoryJobRepository(), outputs_dir=OUTPUTS_DIR)
    settings = SettingsService(repo)
    cost = CostService(repo)

    @ui.page("/")
    def index():
        ui.page_title("Paper_Kit")
        with ui.header().classes("items-center justify-between"):
            with ui.row().classes("items-center"):
                ui.label("📄 Paper_Kit 論文翻譯器").classes("text-2xl font-bold")
                ui.badge("自建 UI · 免除線上工具綁架").props("outline")
            ui.link("設定", "/settings").classes("text-white")
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label("拖放 PDF 上傳，自動翻譯成繁體中文（mono＋dual 並排）").classes("text-grey-8")
            memo: dict[str, str | None] = {}
            cards = ui.column().classes("w-full gap-4")
            ui.upload(
                label="拖放 PDF 或點選選擇",
                auto_upload=True,
                on_upload=lambda e: _start_job(service, settings, cost, e),
            ).classes("w-full")
        ui.timer(1.0, lambda: _refresh(cards, service, cost, memo))

    _settings_page(settings, cost)
    ui.run(title="Paper_Kit 論文翻譯器", reload=False)


if __name__ == "__main__":
    main()
