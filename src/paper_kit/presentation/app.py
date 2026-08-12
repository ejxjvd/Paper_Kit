"""Paper_Kit NiceGUI 介面（薄層：widget ↔ handlers ↔ JobService）。

widget 邏輯盡量薄——狀態對映在 handlers（純函式可測）、業務在 application。
NiceGUI 走 WebSocket 推送 → 事件驅動、無整頁重載（ui.timer 輪詢狀態）。

啟動：`uv run paper-kit` → http://localhost:8080
"""

import os
import tempfile
import uuid
from pathlib import Path

from nicegui import app, ui

from paper_kit.application.job_service import JobService
from paper_kit.domain.translation_job import JobStatus
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.pdf2zh_next_adapter import EngineConfig, Pdf2zhNextAdapter
from paper_kit.presentation.handlers import JobCardView, build_job_card

OUTPUTS_DIR = Path.home() / ".paper_kit" / "outputs"
FILES_BASE = "/files"

BADGE_COLORS = {
    JobStatus.QUEUED: "blue-grey",
    JobStatus.TRANSLATING: "indigo",
    JobStatus.COMPLETED: "green",
    JobStatus.FAILED: "red",
    JobStatus.CANCELLED: "grey",
}


def resolve_engine_config() -> EngineConfig:
    """票 03 預設引擎：DeepSeek（有 DEEPSEEK_API_KEY 才用）；否則 SiliconFlow .com。"""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        return EngineConfig(provider="deepseek", api_key=deepseek_key)
    return EngineConfig(api_key=os.environ.get("SILICONFLOW_API_KEY", "").strip())


def _real_path(view_url: str) -> Path:
    """/files/<job_id>/<name> → 磁碟真實路徑（下載用）。"""
    return OUTPUTS_DIR / view_url.split(FILES_BASE + "/", 1)[1]


def _start_job(service: JobService, e) -> None:
    staging = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}-{e.name}"
    with open(staging, "wb") as f:
        f.write(e.content.read())
    job = service.create_job(staging)
    ui.notify(f"任務已建立：{e.name}", type="positive")
    service.start(job.job_id, Pdf2zhNextAdapter(resolve_engine_config()))


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


def _refresh(cards, service: JobService) -> None:
    cards.clear()
    for job in service.list_jobs():
        _render_card(build_job_card(job))


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    app.add_static_files(FILES_BASE, str(OUTPUTS_DIR))
    service = JobService(jobs=InMemoryJobRepository(), outputs_dir=OUTPUTS_DIR)

    @ui.page("/")
    def index():
        ui.page_title("Paper_Kit")
        with ui.header().classes("items-center"):
            ui.label("📄 Paper_Kit 論文翻譯器").classes("text-2xl font-bold")
            ui.badge("自建 UI · 免除線上工具綁架").props("outline")
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label("拖放 PDF 上傳，自動翻譯成繁體中文（mono＋dual 並排）").classes("text-grey-8")
            cards = ui.column().classes("w-full gap-4")
            ui.upload(
                label="拖放 PDF 或點選選擇",
                auto_upload=True,
                on_upload=lambda e: _start_job(service, e),
            ).classes("w-full")
        ui.timer(1.0, lambda: _refresh(cards, service))

    ui.run(title="Paper_Kit 論文翻譯器", reload=False)


if __name__ == "__main__":
    main()
