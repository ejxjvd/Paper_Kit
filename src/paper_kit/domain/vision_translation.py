"""VisionTranslation 值物件：單頁圖的視覺翻譯結果（純值，無行為）。

票 14：PPT 視覺路徑的領域交換值——譯文＋token 用量（成本記錄入歷史）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionTranslation:
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
