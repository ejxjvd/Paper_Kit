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
"""

import pytest
from nicegui.testing.general import nicegui_reset_globals


@pytest.fixture(autouse=True)
def _nicegui_reset_between_tests():
    with nicegui_reset_globals():
        yield
