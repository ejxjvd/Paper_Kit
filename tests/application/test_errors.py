"""票 09 切片 A：統一錯誤→使用者訊息對映（不吐原始 traceback）。

規格書 story 15「清楚的錯誤訊息」：領域錯誤→使用者看得懂的訊息；
未預期例外→一句話帶過，不透傳 traceback 明細。
"""

import pytest

from paper_kit.application.errors import to_user_message
from paper_kit.application.ports import EngineError
from paper_kit.domain.glossary import GlossaryFormatError
from paper_kit.domain.translation_job import InvalidTransition


def test_engine_error_passes_friendly_message_through():
    """adapter 已把引擎錯誤轉成友善中文 → 對映原樣通過。"""
    msg = "API key 無效或已過期（檢查 key 與端點：國際站用 .com）"
    assert to_user_message(EngineError(msg)) == msg


def test_invalid_transition_maps_to_chinese_instruction():
    """領域狀態機錯誤（英文）→ 使用者看得懂的中文。"""
    assert to_user_message(InvalidTransition("Illegal transition")) == "此任務狀態無法執行該操作"


def test_glossary_format_error_passes_message_through():
    msg = "術語表 CSV 格式錯誤：標頭列必須含 source,target"
    assert to_user_message(GlossaryFormatError(msg)) == msg


def test_unexpected_exception_hides_internals():
    """未預期例外 → 一句話帶過（不吐 traceback）。"""
    msg = to_user_message(RuntimeError("boom"))
    assert "發生未預期錯誤：boom" in msg
    assert "Traceback" not in msg


def test_value_error_from_pages_keeps_chinese_validation_message():
    """頁面範圍驗證（票 07）錯誤訊息本身已是中文 → 原樣。"""
    msg = "頁面範圍格式錯誤：'abc'（如 1-2、3-5、1-2,4-6）"
    assert to_user_message(ValueError(msg)) == msg
