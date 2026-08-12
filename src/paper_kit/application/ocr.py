"""OcrService（application）：掃描件預處理——把無文字層 PDF 變成有文字層。

垂直切片設計（票 12）：OCR 的產出是「有文字層的 PDF」——既有翻譯管線
（pdf2zh）零改動接手。文字層只要存在且順序正確即可，排版交給 pdf2zh
的版面分析（ocrmypdf 同款做法的簡化版，不需精確 bbox 對位）。

紅線：OCR 走本機 onnxruntime（RapidOCR）——不碰雲端視覺 API，
機密文件反而相容（本機直接看圖）。
"""

from collections.abc import Callable
from pathlib import Path

import pypdf

from paper_kit.application.ports import EngineError, OcrPort
from paper_kit.infrastructure.pdf_overlay import overlay_text_layer

# overlay 可注入（測試換 fake，不碰 pymupdf）；正式 = 隱形文字層內嵌
OverlayFn = Callable[[Path, dict[int, str], Path], Path]


def is_pdf_path(path: str | Path) -> bool:
    """PDF 副檔名判定（票 14 收攏：偵測與 UI 共用同一 predicate）。"""
    return Path(path).suffix.lower() == ".pdf"


def has_text_layer(pdf_path: str | Path) -> bool:
    """掃描件偵測（AC1）：任一頁有非空白文字 → 有文字層（回 True）。

    票 14：非 PDF 副檔名（.pptx 等）直接回 False——pypdf 對非 PDF 檔會
    拋警告/例外，PPT 上傳走同一偵測路徑時不該炸 UI。
    """
    if not is_pdf_path(pdf_path):
        return False
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except pypdf.errors.PdfStreamError:
        # 2026-08-12：損壞/非標準 PDF 拋 PdfStreamError（非 OSError）——
        # 偵測路徑永不炸 UI（同票 14 精神）；壞檔由翻譯引擎在任務層報錯。
        # 無法判定 → 視為無文字層（提示可能掃描件，輕度誤導可接受）。
        return False
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            return True
    return False


class OcrService:
    """OCR 服務：偵測 → OCR → 內嵌文字層 → 回傳 OCR 版 PDF（或 None＝有文字層）。"""

    def __init__(self, ocr: OcrPort, overlay: OverlayFn = overlay_text_layer):
        self._ocr = ocr
        self._overlay = overlay

    def ensure_text_layer(self, pdf_path: str | Path) -> Path | None:
        """確保 PDF 有文字層；無則 OCR 並回傳 OCR 版路徑（原檔不動）。

        票 14 spec review：非 PDF（.pptx 等）安全跳過回 None——pypdf 對非
        PDF 檔拋 FileDataError，而視覺路徑根本不需要文字層。
        """
        src = Path(pdf_path)
        if not is_pdf_path(src):
            return None
        if has_text_layer(src):
            return None
        pages = self._ocr.extract_pages(src)
        if not any(pages.values()):  # spec review：空 OCR → 拒絕產出空白文字層
            raise EngineError("掃描件 OCR 無結果——可能不是可辨識的掃描件")
        out = src.with_name(f"ocr-{src.name}")
        return self._overlay(src, pages, out)
