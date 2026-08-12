"""Ports（埠）：application 依賴的介面，實作在 infrastructure/presentation。

Ports & Adapters 架構保證：換引擎＝換插頭，UI 與業務邏輯零改動。
"""

from pathlib import Path
from typing import Protocol

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.domain.vision_translation import VisionTranslation


class EngineError(Exception):
    """引擎失敗（adapter 包裝真實錯誤後丟出）。"""


MISSING_API_KEY_MESSAGE = "尚未設定 API key（設定頁填入後再翻譯）"


class TranslationEnginePort(Protocol):
    """翻譯引擎埠：translate(job) → JobResult。實作：Pdf2zhNextAdapter 等。"""

    def translate(self, job: TranslationJob) -> JobResult:
        """翻譯任務；失敗丟 EngineError（job 狀態由 application 處理）。"""
        ...

    def cancel(self) -> None:
        """票 08：中止進行中的翻譯（殺子程序；之後的 translate 應拋 EngineError）。"""
        ...


class JobRepository(Protocol):
    """任務儲存埠。實作：InMemoryJobRepository（測試）、SQLite repository（正式）。"""

    def add(self, job: TranslationJob) -> None: ...

    def get(self, job_id: str) -> TranslationJob | None: ...

    def save(self, job: TranslationJob) -> None: ...

    def list(self) -> list[TranslationJob]:
        """票 08：全部任務（建立順序）——重啟後 JobService 由此載入歷史。"""
        ...


class OcrPort(Protocol):
    """票 12：OCR 埠——掃描 PDF 每頁 → 文字（本機執行，不上雲端視覺 API）。

    實作：RapidOcrAdapter（onnxruntime）。機密文件與 OCR 相容——本機直接看圖。
    """

    def extract_pages(self, pdf_path: str | Path) -> dict[int, str]:
        """把無文字層 PDF 每頁 OCR 成文字；失敗丟 EngineError。"""
        ...


class PptToImagePort(Protocol):
    """票 14：PPT→圖埠——簡報拆成每頁一張圖（送視覺翻譯用）。

    實作：LibreOfficeConverter（soffice headless→PDF→pymupdf 逐頁 render）。
    需要系統 LibreOffice；soffice 不存在時丟 EngineError（友善訊息）。
    """

    def convert_to_images(self, pptx_path: str | Path, out_dir: str | Path) -> list[Path]:
        """把 .pptx 每頁轉成一張 PNG；回傳依頁序的路徑清單。"""
        ...


class VisionTranslatorPort(Protocol):
    """票 14：視覺翻譯埠——單頁圖 → 繁中譯文＋tokens（成本記錄入歷史）。

    實作：SiliconFlowVisionTranslator（gemma 眼睛模型鏈，上雲端視覺 API——
    機密文件不可用，由引擎 spec sensitive_ok=False 攔截）。
    """

    def translate_image(
        self, image_path: str | Path, target_lang: str = "zh-TW"
    ) -> VisionTranslation:
        """把幻燈片圖翻譯成目標語言文字；失敗丟 EngineError。"""
        ...


class TeXCompilePort(Protocol):
    """票 15：LaTeX 編譯埠——.tex 源碼 → 產物 PDF 路徑（xeCJK 中文關鍵）。

    實作：TeXCompiler（xelatex headless；MiKTeX --enable-installer 自動裝缺套件）。
    需要系統 xelatex；不存在時丟 EngineError（友善訊息含安裝指引）。
    """

    def compile(self, tex_path: str | Path, out_dir: str | Path) -> Path:
        """編譯 .tex → PDF；回傳產物路徑。"""
        ...
