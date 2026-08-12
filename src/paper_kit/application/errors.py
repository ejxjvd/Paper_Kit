"""票 09：統一錯誤→使用者訊息對映（UI 所有 notify 單一入口）。

規律：已知領域錯誤（訊息已是中文）→ 原樣通過；英文領域錯誤（狀態機）
→ 固定中文對映；未預期例外 → 一句話帶過，不透傳 traceback／內部路徑。
UI 不再各自拼錯誤字串（不吐原始 traceback）。
"""

from paper_kit.application.ports import EngineError
from paper_kit.domain.glossary import GlossaryFormatError
from paper_kit.domain.translation_job import InvalidTransition

# 固定對映：領域錯誤的訊息是英文／機械語 → 使用者看得懂的中文
# （KeyError 語境太多——「任務不存在」vs「未知引擎」——由呼叫端決定，不在此泛對映）
_FIXED_MESSAGES: dict[type, str] = {
    InvalidTransition: "此任務狀態無法執行該操作",
}

# 原樣通過：adapter／領域驗證已產出中文使用者訊息
_PASSTHROUGH = (EngineError, GlossaryFormatError, ValueError)  # GlossaryNameError 繼承 ValueError


def to_user_message(exc: Exception) -> str:
    """例外 → 給使用者看的訊息（全站 notify 唯一入口，票 09）。"""
    for exc_type, message in _FIXED_MESSAGES.items():
        if isinstance(exc, exc_type):
            return message
    if isinstance(exc, _PASSTHROUGH):
        return str(exc)
    return f"發生未預期錯誤：{exc}"
