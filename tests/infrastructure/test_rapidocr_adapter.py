"""票 12：RapidOcrAdapter 的 render 管線測試（engine 注入 fake，不載真實模型）。

真實 OCR（模型下載）屬 slow 冒煙；這裡鎖住：頁 render → 三通道 ndarray →
OCR 回傳格式 → 每頁文字串接。
"""

from pathlib import Path

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.rapidocr_adapter import RapidOcrAdapter


class FakeRapidEngine:
    def __init__(self, lines: list | None = None):
        # lines=None → 預設；顯式傳 []（空 OCR）要保留——空 list 是 falsy，不能用 or
        self._lines = (
            lines
            if lines is not None
            else [["box", "scanned word", 0.99], ["box2", "second line", 0.9]]
        )
        self.received_shapes: list[tuple] = []

    def __call__(self, img):
        self.received_shapes.append(img.shape)
        return self._lines, 0.05


def test_extract_pages_renders_and_joins_ocr_text(tmp_path: Path, make_blank_pdf):
    """每頁 render 成三通道 ndarray → OCR 文字依序串接。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=2)
    engine = FakeRapidEngine()
    adapter = RapidOcrAdapter(dpi=72, engine=engine)
    pages = adapter.extract_pages(scan)
    assert pages == {1: "scanned word\nsecond line", 2: "scanned word\nsecond line"}
    assert len(engine.received_shapes) == 2
    assert all(shape[2] == 3 for shape in engine.received_shapes)  # RGB 三通道


def test_extract_pages_empty_ocr_returns_empty_string(tmp_path: Path, make_blank_pdf):
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=1)
    adapter = RapidOcrAdapter(dpi=72, engine=FakeRapidEngine(lines=[]))
    assert adapter.extract_pages(scan) == {1: ""}


def test_missing_dependency_gives_friendly_error(monkeypatch, tmp_path: Path, make_blank_pdf):
    """rapidocr 未裝 → 友善 EngineError（既有 FAILED 路徑接手）。"""
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("rapidocr_onnxruntime"):
            raise ImportError("No module named 'rapidocr_onnxruntime'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=1)
    with pytest.raises(EngineError, match="rapidocr_onnxruntime"):
        RapidOcrAdapter(dpi=72, engine=FakeRapidEngine()).extract_pages(scan)
