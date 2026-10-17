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
    # 相位 6 圖示系統：狀態語意 emoji 換成 Material 圖示（UI 內建圖示集，
    # 不引入外部資源）。圖示反映「目前模式」——深色時顯示月亮。
    btn.props(f"icon={'light_mode' if on else 'dark_mode'}")


def app_frame(
    title: str,
    settings: SettingsService,
    nav: list[tuple[str, str, bool]],
    badge: str | None = None,
    icon: str | None = None,
) -> None:
    """票 16：統一頁框——頂部標題＋左側導覽欄＋主題切換＋Debug 頁尾。

    各頁面建構時呼叫一次（header/drawer 為 client 層級元素，不包內容）；
    取代各頁自造的 ui.header——三頁從「三個獨立網站」變成一個工具。
    Debug 降級為側欄底部小字連結（票 16 決策）。
    """
    dark = _enter_theme(settings)
    with ui.header().classes("items-center justify-between"):
        with ui.row().classes("items-center pk-gap-3"):
            if icon:
                # 相位 6 圖示系統：裝飾性 emoji 換成 Material 圖示（UI 內建集）
                ui.icon(icon).classes("pk-text-2xl pk-muted")
            ui.label(title).classes("pk-text-2xl font-bold")
            if badge:
                ui.badge(badge).props("outline")
        with ui.row().classes("items-center pk-gap-3"):
            theme_btn = ui.button(
                icon="dark_mode" if settings.dark_mode() else "light_mode",
                on_click=lambda: _toggle_theme(settings, dark, theme_btn),
            ).props("flat round").mark("theme-toggle")
    with ui.left_drawer(value=True).classes("pk-sidebar"):
        with ui.column().classes("w-full pk-gap-1 p-2"):
            for label, path, active in nav:
                # ui.link（真實 <a href>）：點擊即導航，不需手寫 on_click
                link = ui.link(label, path).classes("w-full px-3 py-2 rounded")
                if active:
                    link.classes("pk-nav-active")
                else:
                    link.classes("pk-nav-link")
        ui.link("Debug", "/debug").classes("pk-text-xs pk-muted px-4")
