"""相位 6 共用 UI 元件：空狀態、載入骨架、行內錯誤（T-07）。

設計原則（來自 v0.3 作戰計畫 Phase 6 的影響力排序）：
- **狀態要看得見**：空狀態與載入骨架原本各 0 處——使用者看到的是空白，
  分不出「沒有資料」與「還在載入」。
- **錯誤留在原地**：任務成敗類訊息改在卡片內呈現（可展開詳情），toast 只留
  操作確認。錯誤 toast 一閃即逝，使用者回頭找不到原因。
- 所有樣式走 `theme.py` 的 token（`.pk-empty-state`／`.pk-skeleton`／
  `.pk-inline-error`），深色模式與 reduced-motion 由主題統一處理。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from nicegui import ui


@contextmanager
def empty_state(icon: str = "inbox") -> Iterator[None]:
    """空狀態容器（虛線框＋圖示＋置中）——內容由呼叫端填入。

    用法：
        with empty_state():
            ui.label("尚無翻譯任務").classes("pk-text-xl")
            ui.link("翻譯新文件", "/").classes("pk-link")
    """
    with ui.column().mark("empty-state").classes(
        "pk-empty-state items-center justify-center w-full py-10 pk-gap-2"
    ):
        ui.icon(icon).classes("pk-empty-icon")
        yield


def skeleton_rows(count: int = 3) -> None:
    """載入骨架列（脈動動畫；reduced-motion 下由主題歸零）。"""
    for _ in range(count):
        with ui.row().mark("skeleton-row").classes(
            "pk-skeleton-row w-full items-center pk-gap-3"
        ):
            ui.element("div").classes("pk-skeleton pk-skeleton-title")
            ui.element("div").classes("pk-skeleton pk-skeleton-meta")


def inline_error(message: str, detail: str | None = None) -> None:
    """行內錯誤區（卡片內就地呈現；可展開技術詳情）。

    文字固定以「錯誤：」開頭——既有測試與使用者心智模型都靠這個前綴定位。
    """
    with ui.column().mark("inline-error").classes("pk-inline-error w-full pk-gap-1"):
        ui.label(f"錯誤：{message}").classes("pk-error pk-text-sm")
        if detail:
            with ui.expansion("詳情", icon="expand_more").classes("w-full"):
                ui.label(detail).classes("pk-text-xs pk-muted whitespace-pre-wrap")
