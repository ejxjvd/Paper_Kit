"""票 12：掃描件 OCR——無文字層偵測＋OCR→內嵌文字層（既有翻譯管線零改動）。

紅線設計：OCR 走本機 onnxruntime（RapidOCR）——不碰雲端視覺 API，
機密文件反而相容（本機直接看圖）。測試用 FakeOcr 注入（主接縫），
真實 RapidOCR 屬 slow 冒煙（依賴模型下載）。
"""

from pathlib import Path

import pytest

from paper_kit.application.errors import to_user_message
from paper_kit.application.ocr import OcrService, has_text_layer
from paper_kit.application.ports import EngineError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_has_text_layer_non_pdf_returns_false_without_error(tmp_path):
    """票 14：PPT 上傳走 OCR 偵測不炸——非 PDF 副檔名直接回 False（不上傳即報錯）。"""
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"not a real pptx")
    assert has_text_layer(pptx) is False


def test_ensure_text_layer_skips_non_pdf_without_error(tmp_path):
    """票 14 spec review：pptx＋勾 OCR 不炸——非 PDF 安全跳過（OCR 不被呼叫）。

    視覺路徑不需要文字層；pypdf 對非 PDF 檔拋 FileDataError，直接短路。
    """
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"not a real pptx")
    ocr = FakeOcr()
    service = OcrService(ocr=ocr, overlay=make_fake_overlay({}))
    assert service.ensure_text_layer(pptx) is None
    assert ocr.called == []


class FakeOcr:
    def __init__(self, pages: dict[int, str] | None = None, error: str | None = None):
        self._pages = pages or {1: "Fake OCR text page one"}
        self._error = error
        self.called: list[str] = []

    def extract_pages(self, pdf_path) -> dict[int, str]:
        self.called.append(str(pdf_path))
        if self._error:
            raise EngineError(self._error)
        return dict(self._pages)


def make_fake_overlay(record: dict):
    def overlay(pdf_path, pages, out_path):
        record["pdf"] = str(pdf_path)
        record["pages"] = dict(pages)
        Path(out_path).write_bytes(b"%PDF-1.4 ocr overlay output")
        return Path(out_path)

    return overlay


# ── AC1：掃描件偵測（無文字層提示） ──────────────────────────────

def test_has_text_layer_true_for_normal_pdf():
    assert has_text_layer(FIXTURES / "paper_p34.pdf") is True


def test_has_text_layer_false_for_blank_pdf(tmp_path: Path, make_blank_pdf):
    pdf = make_blank_pdf(tmp_path / "scan.pdf")
    assert has_text_layer(pdf) is False


# ── AC2：OCR 流程（Fake 注入主接縫） ────────────────────────────

def test_ensure_text_layer_returns_none_when_text_layer_exists(tmp_path: Path, make_blank_pdf):
    """有文字層 → 原檔不動、OCR 不被呼叫（回 None＝照翻原檔）。"""
    src = FIXTURES / "paper_p34.pdf"
    ocr = FakeOcr()
    service = OcrService(ocr=ocr, overlay=make_fake_overlay({}))
    assert service.ensure_text_layer(src) is None
    assert ocr.called == []


def test_ensure_text_layer_runs_ocr_and_overlays_for_scanned(tmp_path: Path, make_blank_pdf):
    """無文字層 → OCR 每頁 → overlay 內嵌 → 回傳 OCR 版路徑。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf")
    record: dict = {}
    service = OcrService(ocr=FakeOcr(pages={1: "hello", 2: "world"}), overlay=make_fake_overlay(record))
    result = service.ensure_text_layer(scan)
    assert result is not None and result != scan
    assert Path(record["pdf"]) == scan
    assert record["pages"] == {1: "hello", 2: "world"}
    assert result.name.startswith("ocr-")


def test_ensure_text_layer_raises_engine_error_on_ocr_failure(tmp_path: Path, make_blank_pdf):
    """OCR 失敗 → EngineError（既有 FAILED 路徑接手，使用者看得到友善訊息）。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf")
    service = OcrService(ocr=FakeOcr(error="模型下載失敗"), overlay=make_fake_overlay({}))
    with pytest.raises(EngineError):
        service.ensure_text_layer(scan)
    assert "模型下載失敗" in to_user_message(EngineError("模型下載失敗"))


def test_ensure_text_layer_rejects_empty_ocr_result(tmp_path: Path, make_blank_pdf):
    """spec review：OCR 全頁無文字 → 拒絕產出空白文字層（任務照翻會出空白 PDF）。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf")
    service = OcrService(ocr=FakeOcr(pages={1: ""}), overlay=make_fake_overlay({}))
    with pytest.raises(EngineError, match="OCR 無結果"):
        service.ensure_text_layer(scan)


# ── AC2 冒煙：真實 RapidOCR（模型自動下載，慢——引擎升級時才跑） ─────────

@pytest.mark.slow
def test_scanned_fixture_ocr_end_to_end(tmp_path: Path):
    """掃描件（圖像頁）→ 真實 RapidOCR → OCR 版 PDF 可提取文字（AC2 驗證留檔）。

    已實測（2026-08-12）：5.0s 完成，提取出 Scanned PaperOCRTest 123。
    PDF fixture 被 .gitignore 排除（*.pdf 慣例）→ 測試自己造圖像頁。
    """
    import pymupdf
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    draw.text((80, 120), "Scanned Paper OCR Test 123", fill="black")
    draw.text((80, 220), "Hello RapidOCR pipeline", fill="black")
    scan = tmp_path / "scan.pdf"
    import io

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=img_bytes.getvalue())  # 圖像頁 = 無文字層
    doc.save(str(scan))
    doc.close()

    from paper_kit.infrastructure.rapidocr_adapter import RapidOcrAdapter

    svc = OcrService(RapidOcrAdapter(dpi=150))
    out = svc.ensure_text_layer(scan)
    assert out is not None
    from pypdf import PdfReader

    text = PdfReader(str(out)).pages[0].extract_text() or ""
    assert "Scanned" in text
    assert "Hello" in text
