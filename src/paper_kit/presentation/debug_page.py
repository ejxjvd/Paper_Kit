"""Debug log 檢視頁（T-07 相位 4 自 app.py 抽出）。"""

import logging
from pathlib import Path

from nicegui import ui

from paper_kit.application.settings_service import SettingsService
from paper_kit.presentation.composition import format_log_line, recent_log_entries
from paper_kit.presentation.shell import SIDEBAR_NAV, _nav_active, app_frame

logger = logging.getLogger("paper_kit.presentation.debug_page")


def _debug_page(log_path: Path, settings: SettingsService) -> None:
    """票 09：debug 檢視頁——最近任務的 log 可查（job_id 過濾）。"""

    @ui.page("/debug")
    def debug_page():
        ui.page_title("Paper_Kit Debug")
        # 票 16：統一頁框——側欄導覽；Debug 頁也進框架
        nav = [(l, p, _nav_active(p, "/debug")) for l, p in SIDEBAR_NAV]
        app_frame("🔍 Paper_Kit Debug Log", settings, nav)
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label(f"log 檔：{log_path}").classes("pk-text-xs pk-muted")
            job_filter = ui.input("過濾任務 id（空白 = 全部）").classes("w-full")
            box = ui.column().classes("w-full gap-1")

            def render():
                box.clear()
                entries = recent_log_entries(
                    log_path, n=200, job_id=(job_filter.value or "").strip() or None
                )
                with box:
                    if not entries:
                        ui.label("（無 log）").classes("pk-muted pk-text-sm")
                    for entry in entries:
                        ui.label(format_log_line(entry)).classes("pk-text-xs font-mono")

            job_filter.on_value_change(lambda: render())
            ui.button("重新整理", on_click=render).props("outline")
            render()
