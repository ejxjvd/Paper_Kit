"""presentation 層測試隔離（2026-08-12 bug 修復）。

NiceGUI 的 pytest plugin（pytest-nicegui）會為每個測試執行
nicegui_reset_globals 重置全域（清路由、Client.instances、core 變數等）；
本 repo 未安裝該 plugin、手動使用 user_simulation（test_settings_page.py），
而 user_simulation 只在「進入時」清 Client.instances、退出時不清——
殘留的 page client 會讓後續 sync 測試（test_theme 的 apply_theme）在
context.slot 找不到 pseudo client → RuntimeError: slot stack is empty
（nicegui/context.py:20 的守門員是 `if not Client.instances`）。

本 fixture 是官方 general_fixtures.py 的 nicegui_reset_globals
fixture 等價物，autouse 掛在 presentation 層（user_simulation 僅用於此層）。

2026-10-17（T-07 相位 4）補：`nicegui_reset_globals` 的 finally 會把已註冊
頁面路由模組**連同所有父套件**從 `sys.modules` 移除（nicegui/testing/
general.py）。本 repo 的頁面建構器是普通函式（路由在呼叫時才註冊），pop
沒有必要，卻留下「子模組還在、父套件不見」的破碎狀態——之後任何
`import paper_kit.presentation.X as Y`（含延遲 import 測試模組）都會炸
`ImportError: cannot import name 'presentation' from 'paper_kit'`。
修法：每個測試結束後把被 pop 的 `paper_kit` 模組**原物件**放回 sys.modules，
保持模組身分不變（monkeypatch 目標與 closure 查的是同一份）。
"""

import sys

import pytest
from nicegui.testing.general import nicegui_reset_globals

_PAPER_KIT_MODULES: dict[str, object] = {}


@pytest.fixture(autouse=True, scope="session")
def _snapshot_paper_kit_modules():
    """收集期結束後（第一次測試前）快照 paper_kit 全模組，供還原使用。"""
    _PAPER_KIT_MODULES.update(
        {
            name: module
            for name, module in sys.modules.items()
            if name == "paper_kit" or name.startswith("paper_kit.")
        }
    )
    yield


def _restore_paper_kit_modules() -> None:
    for name, module in _PAPER_KIT_MODULES.items():
        if name not in sys.modules:
            sys.modules[name] = module


@pytest.fixture(autouse=True)
def _nicegui_reset_between_tests(_snapshot_paper_kit_modules):
    with nicegui_reset_globals():
        yield
    # reset_globals 的 finally 已經跑完（pop 已發生）——此時補回原物件。
    _restore_paper_kit_modules()
