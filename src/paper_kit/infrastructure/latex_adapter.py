"""LatexAdapter（票 15）：LaTeX 源碼翻譯主管線——翻 .tex → xelatex 編譯。

管線（Ports & Adapters，translator/compiler 可注入）：
  1. 讀 .tex（UTF-8）→ split_tex_segments 分段（equation/figure 等整段 keep）
  2. 每段可譯文字：行內公式/引用 \\PKP{n} 佔位 → LLM 翻譯（模型鏈）
     → 還原佔位（AC2 公式 100% 原樣）→ 組裝回源碼
  3. TeXCompiler（xelatex）：xeCJK 中文編譯 → PDF
產出 JobResult：mono = 編譯 PDF、dual = None；tokens 累加 → 既有
CostService 記錄入歷史（UI 零改動）。

機密紅線：純文字引擎——registry spec sensitive_ok=True（LaTeX 源碼
不上圖、不上第三方；DeepSeek 直連需 key 但內容是文字）。
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from paper_kit.application.ports import (
    EngineError,
    MISSING_API_KEY_MESSAGE,
)
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.text_translation import TextTranslation
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.latex_parser import (
    protect_tex_inline,
    restore_tex_inline,
    split_item_command,
    split_tex_segments,
    split_title_command,
)
from paper_kit.infrastructure.latex_translator import (
    DEFAULT_LATEX_BASE_URL,
    DEFAULT_LATEX_MODEL,
    LatexTranslator,
)
from paper_kit.infrastructure.tex_compiler import TeXCompiler

logger = logging.getLogger("paper_kit.infrastructure.latex_adapter")


@dataclass(frozen=True)
class LatexConfig:
    api_key: str = ""
    model: str = DEFAULT_LATEX_MODEL
    base_url: str = DEFAULT_LATEX_BASE_URL


class LatexAdapter:
    """實作 TranslationEnginePort：LaTeX 源碼 → 翻譯後編譯 PDF。"""

    def __init__(
        self,
        config: LatexConfig,
        translator=None,
        compiler=None,
    ):
        self._config = config
        self._translator = translator or LatexTranslator(
            config.api_key, model=config.model, base_url=config.base_url
        )
        self._compiler = compiler or TeXCompiler()
        self._cancelled = False

    def cancel(self) -> None:
        """票 08 契約：取消——分段迴圈檢查旗標，之後的翻譯一律拒絕。"""
        self._cancelled = True

    def translate(self, job: TranslationJob) -> JobResult:
        if self._cancelled:
            raise EngineError("已取消")
        if not self._config.api_key:
            # 早期檢查（同 PptVisionAdapter）：缺 key 先於讀檔/翻譯
            raise EngineError(MISSING_API_KEY_MESSAGE)
        if not job.source_path:
            raise EngineError("缺少 LaTeX 源碼路徑")
        source = Path(job.source_path)
        if not source.exists():
            raise EngineError(f"找不到 LaTeX 源碼：{source.name}")
        try:
            src_text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise EngineError(
                f"無法讀取 {source.name}——需要 UTF-8 編碼（xeCJK 中文源碼）"
            ) from None

        segments = split_tex_segments(src_text)
        out_parts: list[str] = []
        total_in = 0
        total_out = 0
        for segment in segments:
            if self._cancelled:
                raise EngineError("已取消")
            if segment.kind == "keep":
                out_parts.append(segment.content)
                continue
            translation = self._translate_chunk(segment.content, job.target_lang)
            out_parts.append(translation.text)
            total_in += translation.input_tokens
            total_out += translation.output_tokens

        work = source.parent / "latex"
        work.mkdir(parents=True, exist_ok=True)
        out_tex = work / f"{source.stem}-{job.target_lang}.tex"
        out_tex.write_text("".join(out_parts), encoding="utf-8")
        pdf = self._compiler.compile(out_tex, work)
        logger.info(
            "LaTeX 翻譯完成",
            extra={
                "job_id": job.job_id,
                "input_tokens": total_in,
                "output_tokens": total_out,
            },
        )
        return JobResult(
            mono_path=str(pdf),
            dual_path=None,  # LaTeX 路線單一產出（編譯 PDF）
            input_tokens=total_in,
            output_tokens=total_out,
        )

    def _translate_chunk(self, chunk: str, target_lang: str) -> TextTranslation:
        """一段可譯文字：標題/item 指令只翻其後內文；其餘整段翻。"""
        for splitter in (split_title_command, split_item_command):
            parts = splitter(chunk)
            if parts:
                prefix, content, suffix = parts
                inner = self._translate_core(content, target_lang)
                return TextTranslation(
                    text=prefix + inner.text + suffix,
                    input_tokens=inner.input_tokens,
                    output_tokens=inner.output_tokens,
                )
        return self._translate_core(chunk, target_lang)

    def _translate_core(self, text: str, target_lang: str) -> TextTranslation:
        """保護行內公式/引用 → 翻譯 → 還原佔位（AC2 公式 100% 原樣）。"""
        protected, placeholders = protect_tex_inline(text)
        translation = self._translator.translate_chunk(protected, target_lang)
        return TextTranslation(
            text=restore_tex_inline(translation.text, placeholders),
            input_tokens=translation.input_tokens,
            output_tokens=translation.output_tokens,
        )
