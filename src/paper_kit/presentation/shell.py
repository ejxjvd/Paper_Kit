"""共用頁框、側欄導覽與主題切換（T-07 相位 4 自 app.py 抽出）。"""

import logging

from nicegui import ui

from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.translation_job import JobStatus
from paper_kit.presentation.composition import ENGINE_SPECS
from paper_kit.presentation.theme import apply_theme

logger = logging.getLogger("paper_kit.presentation.shell")


BADGE_COLORS = {
    JobStatus.QUEUED: "blue-grey",
    JobStatus.TRANSLATING: "indigo",
    JobStatus.COMPLETED: "green",
    JobStatus.FAILED: "red",
    JobStatus.CANCELLED: "grey",
}


# 票 16：統一頁框側欄導覽（label, path；active 由 _nav_active 依當前頁判定）
SIDEBAR_NAV = [
    ("翻譯", "/"),
    ("歷史", "/history"),
    ("設定", "/settings"),
]


def _nav_active(path: str, current: str) -> bool:
    """票 16：側欄項是否高亮（當前頁對應項）。"""
    return path == current


def _engine_label_map() -> dict[str, str]:
    """引擎顯示名對照（engine_id → label）。三頁共用（standards review：收攏重複對映）。"""
    return {eid: spec.label for eid, spec in ENGINE_SPECS.items()}


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


def app_frame(
    title: str,
    settings: SettingsService,
    nav: list[tuple[str, str, bool]],
    badge: str | None = None,
) -> None:
    """票 16：統一頁框——頂部標題＋左側導覽欄＋主題切換＋Debug 頁尾。

    各頁面建構時呼叫一次（header/drawer 為 client 層級元素，不包內容）；
    取代各頁自造的 ui.header——三頁從「三個獨立網站」變成一個工具。
    Debug 降級為側欄底部小字連結（票 16 決策）。
    """
    dark = _enter_theme(settings)
    with ui.header().classes("items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            ui.label(title).classes("text-2xl font-bold")
            if badge:
                ui.badge(badge).props("outline")
        with ui.row().classes("items-center gap-3"):
            theme_btn = ui.button(
                "🌙" if settings.dark_mode() else "☀️",
                on_click=lambda: _toggle_theme(settings, dark, theme_btn),
            ).props("flat round")
    with ui.left_drawer(value=True).classes("bg-grey-3"):
        with ui.column().classes("w-full gap-1 p-2"):
            for label, path, active in nav:
                # ui.link（真實 <a href>）：點擊即導航，不需手寫 on_click
                link = ui.link(label, path).classes("w-full px-3 py-2 rounded")
                if active:
                    link.classes("bg-primary text-white")
                else:
                    link.classes("hover:bg-grey-4")
        ui.link("Debug", "/debug").classes("text-xs text-grey-6 px-4")
