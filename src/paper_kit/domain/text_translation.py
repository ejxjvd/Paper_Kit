"""TextTranslation 值物件：單段純文字的 LLM 翻譯結果（純值，無行為）。

票 15：LaTeX 源碼翻譯的領域交換值（與 VisionTranslation 平行）——
譯文＋token 用量（成本記錄入歷史）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextTranslation:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
