"""RapidOcrAdapter：RapidOCR（onnxruntime 本機）實作 OcrPort。

紅線（票 12 設計）：本機執行——不碰雲端視覺 API，機密文件與 OCR 相容。
lazy import：模組在首次呼叫才載入，模型在 RapidOCR() 實例化時才下載/載入；
未安裝 → 友善 EngineError。

冒煙測試不在此單元測試內（真實 OCR 需下載模型）——屬 slow 整合冒煙。
"""

import logging
from pathlib import Path

import pymupdf  # 掃描頁 render 成點陣圖給 OCR

from paper_kit.application.ports import EngineError, OcrPort

logger = logging.getLogger("paper_kit.infrastructure.rapidocr_adapter")


class RapidOcrAdapter:
    """掃描 PDF → 每頁 render → RapidOCR → 每頁文字。engine 可注入（測試 fake）。"""

    def __init__(self, dpi: int = 200, engine=None):
        self._dpi = dpi
        self._engine = engine  # 測試注入：假 engine 驗證 render 管線，不載真實模型

    def extract_pages(self, pdf_path: str | Path) -> dict[int, str]:
        try:
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise EngineError(
                "掃描件 OCR 需要 rapidocr_onnxruntime（pip install rapidocr_onnxruntime）"
            ) from exc
        engine = self._engine or RapidOCR()
        doc = pymupdf.open(str(pdf_path))
        pages: dict[int, str] = {}
        try:
            for page_no, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=self._dpi)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )
                if img.shape[2] > 3:  # RGBA → RGB（RapidOCR 吃三通道）
                    img = img[:, :, :3]
                result, _elapsed = engine(img)
                # RapidOCR 回傳 [[box, text, score], ...]——取文字欄，依版面順序
                pages[page_no] = "\n".join(line[1] for line in (result or []))
        finally:
            doc.close()
        return pages
