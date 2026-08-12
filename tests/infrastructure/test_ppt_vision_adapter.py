"""票 14：PptVisionAdapter——拆圖 → gemma 逐頁翻譯 → 注記 PDF（版面保留）。

測試以 FakeConverter/FakeTranslator 注入（不碰真實 soffice 與視覺 API）；
build_notes_pdf 為純函式直接驗證組裝（原圖＋譯文注記，CJK 字體可提取）。
"""

from pathlib import Path

import pymupdf
import pytest

from paper_kit.application.ports import EngineError
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.domain.vision_translation import VisionTranslation
from paper_kit.infrastructure.ppt_vision_adapter import (
    PptVisionAdapter,
    PptVisionConfig,
    build_notes_pdf,
)


def make_png(path: Path, w: int = 64, h: int = 36) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h))
    pix.save(str(path))
    return path


class FakeConverter:
    def __init__(self, images: list[Path]):
        self._images = images
        self.called: list[str] = []

    def convert_to_images(self, pptx_path, out_dir):
        self.called.append(str(pptx_path))
        return list(self._images)


class FakeTranslator:
    """依序回傳結果；on_call 每呼叫前執行（cancel 測試用）。"""

    def __init__(self, results: list[VisionTranslation]):
        self._results = list(results)
        self.calls: list[str] = []
        self.on_call = None

    def translate_image(self, image_path, target_lang="zh-TW"):
        self.calls.append(str(image_path))
        if self.on_call:
            self.on_call()
        if not self._results:
            raise EngineError("結果不足（測試設定）")
        return self._results.pop(0)


def make_job(tmp_path, name="deck.pptx") -> TranslationJob:
    src = tmp_path / name
    src.write_bytes(b"fake pptx")
    return TranslationJob(job_id="j1", source_path=str(src), target_lang="zh-TW")


def test_translate_runs_full_pipeline_and_accumulates_tokens(tmp_path):
    images = [make_png(tmp_path / "imgs" / "a.png"), make_png(tmp_path / "imgs" / "b.png")]
    job = make_job(tmp_path)
    adapter = PptVisionAdapter(
        PptVisionConfig(api_key="SF-KEY"),
        converter=FakeConverter(images),
        translator=FakeTranslator([
            VisionTranslation("第一頁譯文", 100, 50),
            VisionTranslation("第二頁譯文", 200, 60),
        ]),
    )
    result = adapter.translate(job)
    assert isinstance(result, JobResult)
    assert result.mono_path is not None and Path(result.mono_path).exists()
    assert result.dual_path is None  # 視覺路徑單一產出（注記版）
    assert result.input_tokens == 300
    assert result.output_tokens == 110
    # PDF 兩頁、每頁有圖、譯文可提取（CJK 嵌入）
    doc = pymupdf.open(result.mono_path)
    assert doc.page_count == 2
    texts = [doc[i].get_text() for i in range(2)]
    assert any("第一頁譯文" in t for t in texts)
    assert any("第二頁譯文" in t for t in texts)
    assert all(doc[i].get_images() for i in range(2))
    doc.close()


def test_translate_cancel_mid_pipeline_raises(tmp_path):
    images = [make_png(tmp_path / "imgs" / "a.png"), make_png(tmp_path / "imgs" / "b.png")]
    job = make_job(tmp_path)
    translator = FakeTranslator([VisionTranslation("第一頁", 1, 1)])
    adapter = PptVisionAdapter(
        PptVisionConfig(api_key="SF-KEY"),
        converter=FakeConverter(images),
        translator=translator,
    )
    translator.on_call = adapter.cancel  # 第一頁翻譯前取消
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(job)
    assert len(translator.calls) == 1  # 取消後不再逐頁


def test_translate_cancel_before_convert_raises(tmp_path):
    job = make_job(tmp_path)
    adapter = PptVisionAdapter(PptVisionConfig(api_key="SF-KEY"), converter=FakeConverter([]))
    adapter.cancel()
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(job)


def test_translate_missing_source_raises(tmp_path):
    job = TranslationJob(job_id="j2", source_path=None)
    adapter = PptVisionAdapter(PptVisionConfig(api_key="SF-KEY"), converter=FakeConverter([]))
    with pytest.raises(EngineError, match="簡報"):
        adapter.translate(job)


def test_translate_translator_error_propagates(tmp_path):
    images = [make_png(tmp_path / "imgs" / "a.png")]
    job = make_job(tmp_path)
    adapter = PptVisionAdapter(
        PptVisionConfig(api_key="SF-KEY"),
        converter=FakeConverter(images),
        translator=FakeTranslator([]),  # 呼叫即失敗
    )
    with pytest.raises(EngineError, match="結果不足"):
        adapter.translate(job)


def test_build_notes_pdf_preserves_slide_design_and_text(tmp_path):
    images = [make_png(tmp_path / "a.png", w=640, h=360)]
    out = build_notes_pdf(images, ["繁體中文注記內容"], tmp_path / "notes.pdf")
    doc = pymupdf.open(str(out))
    assert doc.page_count == 1
    page = doc[0]
    assert page.get_images()  # 原圖嵌入（設計 100% 保留）
    assert "繁體中文注記內容" in page.get_text()  # 譯文可提取（CJK 字體嵌入）
    doc.close()


def test_build_notes_pdf_long_translation_keeps_all_text(tmp_path):
    """票 14 spec review：長譯文（>850 字臨界，max_tokens 2000 內）不消失。

    insert_textbox 溢位回負值＝整段不渲染、任務仍 COMPLETED（靜默空白注記）——
    長文必須自動分頁續放，開頭與結尾都要可提取。
    """
    long_text = "論文翻譯測試。" * 200  # 1400 字（實測臨界 ~850）
    images = [make_png(tmp_path / "a.png", w=640, h=360)]
    out = build_notes_pdf(images, [long_text], tmp_path / "notes.pdf")
    doc = pymupdf.open(str(out))
    assert doc.page_count > 1  # 溢位 → 自動開續頁
    joined = "".join(doc[i].get_text() for i in range(doc.page_count)).replace("\n", "")
    assert joined.startswith(long_text[:50])  # 開頭保留
    assert joined.endswith(long_text[-50:])  # 結尾保留（整段不再消失）
    doc.close()
