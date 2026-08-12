"""PptVisionAdapter（票 14）：PPT 視覺路徑——拆圖 → gemma 逐頁翻譯 → 注記 PDF。

管線（Ports & Adapters，converter/translator 可注入）：
  1. PptToImagePort（LibreOfficeConverter）：.pptx → 每頁 PNG（設計 100% 保留）
  2. VisionTranslatorPort（SiliconFlowVisionTranslator）：每頁圖 → 譯文＋tokens
  3. 組裝：新 PDF——原圖（設計原樣）＋下方譯文注記（雙語注記）
產出 JobResult：mono = 注記版 PDF、dual = None；tokens 累加 → 既有
CostService 記錄入歷史（AC3，UI 零改動）。

敏感紅線：視覺翻譯 = 圖片上雲端 → registry spec sensitive_ok=False，
機密任務在 UI/service 兩層都被攔截。
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from paper_kit.application.ports import (
    EngineError,
    MISSING_API_KEY_MESSAGE,
    PptToImagePort,
    VisionTranslatorPort,
)
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.ppt_converter import LibreOfficeConverter
from paper_kit.infrastructure.siliconflow_vision import (
    DEFAULT_VISION_BASE_URL,
    DEFAULT_VISION_MODEL,
    SiliconFlowVisionTranslator,
)

logger = logging.getLogger("paper_kit.infrastructure.ppt_vision_adapter")

_NOTE_HEIGHT = 400  # 譯文注記區高度（px）
_NOTE_FONT_SIZE = 18  # 注記固定字號（可讀性優先）——放不下就分頁，不縮字
_CONT_TITLE = "（譯文續）"  # 續頁標題（長譯文分頁時標註）


def _note_capacity(rect: pymupdf.Rect, reserve_lines: int = 0) -> int:
    """注記區可容納字數（CJK 全寬：每字寬 ≈ 字號；保守向下取整）。

    reserve_lines：續頁扣掉標題行數。實測 18px 臨界 ~850 字，估算一致。
    """
    chars_per_line = max(1, int(rect.width / _NOTE_FONT_SIZE))
    lines = max(1, int(rect.height / (_NOTE_FONT_SIZE * 1.4)) - reserve_lines)
    return chars_per_line * lines


def _split_note(text: str, main_capacity: int, cont_capacity: int) -> list[str]:
    """依容量切段：首段 = 圖頁注記區，其餘 = 續頁（每頁含標題空間）。"""
    if len(text) <= main_capacity:
        return [text]
    chunks = [text[:main_capacity]]
    rest = text[main_capacity:]
    while rest:
        chunks.append(rest[:cont_capacity])
        rest = rest[cont_capacity:]
    return chunks


def build_notes_pdf(images: list[Path], texts: list[str], out_path: Path) -> Path:
    """每頁：原圖（全幅、設計原樣）＋下方譯文注記（CJK 內建字體嵌入）。

    頁面尺寸依圖比例動態計算（原圖不拉伸變形）；譯文用 fontname="china-t"
    （pymupdf 內建 CJK 子集字體——Helvetica 中文會變 '?'，票 12 教訓）。

    票 14 spec review：長譯文（>一頁注記區容量）自動開「（譯文續）」頁——
    insert_textbox 溢位回負值時整段文字不渲染、任務仍 COMPLETED（靜默空白）。
    """
    doc = pymupdf.open()
    try:
        for image, text in zip(images, texts):
            pix = pymupdf.Pixmap(str(image))
            ratio = pix.width / pix.height
            page_w = 1200
            img_h = int(page_w / ratio)
            page = doc.new_page(width=page_w, height=img_h + _NOTE_HEIGHT)
            page.insert_image(
                pymupdf.Rect(0, 0, page_w, img_h), filename=str(image)
            )
            notes_rect = pymupdf.Rect(40, img_h + 20, page_w - 40, img_h + _NOTE_HEIGHT - 20)
            chunks = _split_note(
                text, _note_capacity(notes_rect), _note_capacity(notes_rect, reserve_lines=2)
            )
            page.insert_textbox(
                notes_rect,
                chunks[0],
                fontsize=_NOTE_FONT_SIZE,
                fontname="china-t",
                lineheight=1.4,
            )
            for chunk in chunks[1:]:
                cont = doc.new_page(width=page_w, height=_NOTE_HEIGHT)  # 續頁＝純注記
                cont.insert_textbox(
                    pymupdf.Rect(40, 20, page_w - 40, _NOTE_HEIGHT - 20),
                    f"{_CONT_TITLE}\n{chunk}",
                    fontsize=_NOTE_FONT_SIZE,
                    fontname="china-t",
                    lineheight=1.4,
                )
        doc.save(str(out_path), garbage=3, deflate=True)
    finally:
        doc.close()
    return out_path


@dataclass(frozen=True)
class PptVisionConfig:
    api_key: str = ""
    model: str = DEFAULT_VISION_MODEL
    base_url: str = DEFAULT_VISION_BASE_URL


class PptVisionAdapter:
    """實作 TranslationEnginePort：PPT 視覺路徑（第三支引擎插頭）。"""

    def __init__(
        self,
        config: PptVisionConfig,
        converter: PptToImagePort | None = None,
        translator: VisionTranslatorPort | None = None,
    ):
        self._config = config
        self._converter = converter or LibreOfficeConverter()
        self._translator = translator or SiliconFlowVisionTranslator(
            config.api_key, model=config.model, base_url=config.base_url
        )
        self._cancelled = False

    def cancel(self) -> None:
        """票 08 契約：取消——逐頁迴圈檢查旗標，之後的 translate 一律拒絕。"""
        self._cancelled = True

    def translate(self, job: TranslationJob) -> JobResult:
        if self._cancelled:
            raise EngineError("已取消")
        if not self._config.api_key:
            # 早期檢查（同 CliAdapterBase）：缺 key 先於拆圖失敗（不白跑 soffice）
            raise EngineError(MISSING_API_KEY_MESSAGE)
        if not job.source_path:
            raise EngineError("缺少簡報檔路徑")
        source = Path(job.source_path)
        work = source.parent / "ppt"
        # 缺 LibreOffice / 缺 key 都會在此或逐頁翻譯時以友善錯誤失敗
        images = self._converter.convert_to_images(source, work)
        if self._cancelled:
            raise EngineError("已取消")
        texts: list[str] = []
        total_in = 0
        total_out = 0
        for image in images:
            if self._cancelled:
                raise EngineError("已取消")
            translation = self._translator.translate_image(image, job.target_lang)
            texts.append(translation.text)
            total_in += translation.input_tokens
            total_out += translation.output_tokens
        out_pdf = build_notes_pdf(images, texts, source.parent / "notes.pdf")
        logger.info(
            "PPT 視覺翻譯完成",
            extra={
                "job_id": job.job_id,
                "pages": len(images),
                "input_tokens": total_in,
                "output_tokens": total_out,
            },
        )
        return JobResult(
            mono_path=str(out_pdf),
            dual_path=None,  # 視覺路徑單一產出（注記版）
            input_tokens=total_in,
            output_tokens=total_out,
        )
